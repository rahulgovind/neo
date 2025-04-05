"""
Update file command implementation.

This module provides the UpdateFile class for updating files based on diff structure.
"""

import os
import logging
import textwrap
from typing import Dict, Any, Optional, List

from src.core.command import Command, CommandTemplate, CommandParameter
from src.core.exceptions import FatalError
from src.core.messages import Message, TextBlock
from src.core.context import Context
from src.utils.files import patch

from textwrap import dedent

# Configure logging
logger = logging.getLogger(__name__)


class UpdateFileCommand(Command):
    """
    Command for updating files based on a diff structure.
    
    Takes a file path as a parameter and a diff structure as data,
    then applies the diff to update the file content. If the diff cannot be applied,
    it falls back to using the model to perform the update.
    """
    
    def template(self) -> CommandTemplate:
        """Command template with parameter definitions"""
        return CommandTemplate(
            name="update_file",
            requires_data=True,
            description=textwrap.dedent("""
                Update a file using a diff structure.
                
                The update_file command modifies an existing file specified by PATH according 
                to the diff provided in STDIN.
                
                The PATH argument can be a relative or absolute path to an existing file.
                
                The diff format uses the following section types:
                - @DELETE - For lines to be deleted
                - @UPDATE - For lines to be updated, with BEFORE and AFTER subsections
                - @INSERT - For lines to be inserted
                
                Each line in a section follows this format:
                <line_number>:<content>
                
                For example:
                @DELETE
                2:line to delete
                3:another line to delete
                
                @UPDATE
                BEFORE
                5:original line
                6:original line 2
                AFTER
                5:updated line
                6:updated line 2
                7:new line
                
                @INSERT
                10:new line to insert
                11:another new line
                
                Important rules:
                - @DELETE sections specify lines to be removed from the file
                - @UPDATE sections must contain both BEFORE and AFTER subsections
                - @INSERT sections specify new lines to be added at the specified positions
                - Line numbers in an @UPDATE's AFTER section typically match the BEFORE section
                - Additional lines in the AFTER section will be inserted after the updated lines
            """).strip(),
            parameters=[
                CommandParameter(
                    name="path",
                    description="Path to the file to update",
                    required=True,
                    is_positional=True
                ),
                CommandParameter(
                    name="disable_model_fallback",
                    description="Disable model fallback if diff cannot be applied",
                    required=False,
                    is_positional=False,
                    default=False,
                    long_flag="disable-model-fallback",
                    is_flag=True,
                    hidden=True
                )
            ],
            examples=textwrap.dedent("""
                # Updating a function name in a Python file
                # Original file (path/to/file.py):
                1 def old_function():
                2     # Function implementation
                3     return True
                
                ▶update_file path/to/file.py｜@1 Update function name
                - def old_function():
                + def new_function():
                  # Function implementation■
                ✅File updated successfully■
                
                # Updated file (path/to/file.py):
                1 def new_function():
                2     # Function implementation
                3     return True
                
                # Updating a configuration value in a JSON file
                # Original file (config.json):
                1 {
                2     "host": "localhost",
                3     "port": 8080,
                4     "debug": false
                5 }
                
                ▶update_file config.json｜@3 Update port
                - "port": 8080,
                + "port": 9000,■
                ✅File updated successfully■
                
                # Updated file (config.json):
                1 {
                2     "host": "localhost",
                3     "port": 9000,
                4     "debug": false
                5 }
                
                # Multiple chunks in one diff with line numbers
                # Original file (src/app.js):
                1 // App initialization
                2 
                3 function init() {
                4     console.log('Initializing...');
                5 }
                6 
                7 function login() {
                8     // Old implementation
                9     console.log('Logging in...');
                10 }
                
                ▶update_file src/app.js｜@7 Update login function
                - function login() {
                - // Old implementation
                + function login() {
                + // New implementation with error handling
                @9 Add error handling
                  console.log('Logging in...');
                + try {
                +   // Authentication code
                + } catch(err) {
                +   console.error('Login failed:', err);
                + }
                ■
                ✅File updated successfully■
                
                # Updated file (src/app.js):
                1 // App initialization
                2 
                3 function init() {
                4     console.log('Initializing...');
                5 }
                6 
                7 function login() {
                8     // New implementation with error handling
                9     console.log('Logging in...');
                10     try {
                11       // Authentication code
                12     } catch(err) {
                13       console.error('Login failed:', err);
                14     }
                15 }
                
            """).strip()
        )
    
    def _get_system_prompt(self) -> str:
        """Get system prompt for the model with improved error reporting instructions"""
        return textwrap.dedent("""
            You are a specialized file updating assistant. Your task is to modify a file based on 
            a diff structure that could not be applied automatically.
            
            1. You have been provided with the current content of a file and a diff that failed to apply.
            2. First, you MUST include the exact original error message verbatim in your response.
            3. Then, identify the relevant portions of the file that are related to the error and include those exact lines.
            4. Carefully analyze the file content and understand what changes are requested by the diff.
            5. Make only the changes that align with the intent of the diff, preserving everything else.
            6. Use the write_file command to save the updated content.
            
            In your response:
            - ALWAYS start by quoting the original error that occurred during the diff application, exactly as provided.
            - VERBATIM include the relevant file sections. DO NOT paraphrase or modify these sections when quoting them.
            - Format the original file sections with line numbers to help the user locate the issue.
            - Only after showing the error and relevant file sections, provide your explanation and solution.
            - Be precise and maintain the original formatting and style of the file.
            - Only make the changes aligned with the intent of the diff.
            - If you cannot determine what changes are needed, explain why.
        """).strip()
    
    def process(self, ctx: Context, args: Dict[str, Any], data: Optional[str] = None) -> str:
        """Process the update file command"""
        # Get the file path from arguments
        file_path = args.get("path")
        if not file_path:
            raise FatalError("No file path provided")
        
        # Get the diff from data
        diff_text = data
        if not diff_text:
            raise FatalError("No diff provided")
        
        # Get shell from context and create small model for updates
        shell = ctx.shell
        model = ctx.select_model("SM")  # Create temporary small model
        
        # First try to apply the diff using the patch function
        logger.info(f"Attempting to apply diff to {file_path}")
        try:
            # Call the patch function which now throws exceptions on failure
            updated_content = patch(file_path, diff_text)
            
            # If we got here, patch succeeded, write the updated content to the file
            workspace = ctx.workspace
            write_result = shell.execute(
                "write_file", 
                parameters={
                    "path": file_path,
                    "workspace": workspace
                },
                data=updated_content
            )
            
            if write_result.success:
                logger.info(f"Successfully applied diff to {file_path}")
                return "✅File updated successfully"
            else:
                return f"❌{write_result.error}"
                
        except RuntimeError as e:
            if bool(args.get("disable_model_fallback")):
                logger.warning(f"Disabling model fallback: {str(e)}")
                return f"❌{str(e)}"
                
            # If patch failed with a FatalError, fall back to using the model
            error_message = str(e)
            logger.warning(f"Diff application failed: {error_message}. Falling back to model.")

            # Get the original content of the file with line numbers
            read_result = shell.execute("read_file", parameters={"path": file_path, "include_line_numbers": True})
            if not read_result.success:
                return f"❌{read_result.error}"

            file_content = read_result.result

            # Import the escaping function from messages.py
            from src.core.messages import _escape_special_chars

            # Escape the file content to avoid issues with special characters
            escaped_file_content = _escape_special_chars(file_content)
            
            # Build the initial message with file content, diff, and original error message
            initial_message = (
                f"I need to update the file at '{file_path}' with this diff that couldn't be applied automatically:\n\n{diff_text}\n\n" + \
                f"The automatic diff application failed with this error (which you MUST include verbatim in your response):\n\n```\n{error_message}\n```\n\n" + \
                f"Here is the current content of the file:\n\n{escaped_file_content}\n\n" + \
                f"First, quote the exact original error message as shown above. Then identify and show the exact relevant portions of the file related to this error, " + \
                f"including their line numbers. After that, make the necessary changes aligned with the intent of the diff and use the write_file command to save the updated content. " + \
                f"Once done, say <Successfully updated file> if you were successful, else say that you failed to update the file." + \
                f" You MUST always write the file in its entirety. DO NOT write partial contents."
            )
            
            # Create messages
            user_msg = Message(role="user")
            user_msg.add_content(TextBlock(_escape_special_chars(initial_message)))
            messages = [user_msg]
            
            # Process the message with the model - only allowing write_file command
            system_prompt = self._get_system_prompt()
            return model.process(
                system=system_prompt,
                messages=messages,
                commands=["write_file"],
                auto_execute_commands=True
            ).text()
        

