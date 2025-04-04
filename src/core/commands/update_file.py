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
                
                The diff format is:
                - Lines starting with '-' indicate lines to delete from the original content
                - Lines starting with '+' indicate lines to add
                - Lines starting with ' ' indicate unmodified lines that should match for validation
                
                The line number follows the prefix and precedes the line content.
                For example: '-3 existing line' means delete line 3.
                
                Important rules:
                - A space prefix means that line is not being modified and must match exactly for validation
                - It is invalid to have the same line number with both a space prefix and a '+' or '-' prefix
                - If a consecutive chunk of lines is being updated, the deletions must precede the additions.
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
                # Using the new chunk-based diff format:
                ▶update_file path/to/file.py｜@3 Update function name
                - def old_function():
                + def new_function():
                  # rest of the function■
                ✅File updated successfully■
                
                # Using the new chunk-based diff format for port update:
                ▶update_file config.json｜@5 Update port
                - "port": 8080,
                + "port": 9000,■
                ✅File updated successfully■
                
                # Multiple chunks in one diff:
                ▶update_file src/app.js｜@8 Update login function
                - function login() {
                - // Old implementation
                + function login() {
                + // New implementation
                @20 Add error handling
                  }
                + // Add error handling
                + catch(err) {
                +   console.error(err);
                + }■
                ❌Error: No such file or directory■
                

            """).strip()
        )
    
    def _get_system_prompt(self) -> str:
        """Get system prompt for the model with updated instructions"""
        return textwrap.dedent("""
            You are a specialized file updating assistant. Your task is to modify a file based on 
            a diff structure that could not be applied automatically.
            
            1. You have been provided with the current content of a file and a diff that failed to apply.
            2. First, analyze the original error message to identify what went wrong with the diff.
            3. If possible, identify the specific part of the file related to the error and provide that snippet.
            4. Carefully analyze the file content and understand what changes are requested by the diff.
            5. Make only the changes that align with the intent of the diff, preserving everything else.
            6. Use the write_file command to save the updated content.
            
            In your response:
            - ALWAYS start by showing the original error that occurred during the diff application.
            - DO NOT try to explain or interpret why the error occurred until you've shown the error.
            - If applicable, show a small snippet of the file where the error likely occurred to help the user understand the context.
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
                
        except FatalError as e:
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
            
            # Build the initial message with file content and diff
            initial_message = dedent(
                f"""
                I need to update the file at '{file_path}' with this diff that couldn't be applied automatically:
                {diff_text}

                Applying the diff previously failed with the following error: 
                {error_message}
                
                Here is the current content of the file:
                {escaped_file_content}

                Please make the necessary changes aligned with the intent of the diff and use the write_file command to save the updated content.

                Do the following after you are done - 
                - Say <Successfully updated file>, explain what changes you made, and also describe the original diff command failure
                - If you weren't able to update the file, explain why.
                """
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
        

