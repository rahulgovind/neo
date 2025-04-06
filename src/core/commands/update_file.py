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
            description=textwrap.dedent(
                """
                Update a file using a diff structure.
                
                The update_file command modifies an existing file specified by PATH according 
                to the diff provided in STDIN.
                
                The PATH argument can be a relative or absolute path to an existing file.
                
                The diff format uses the following section types:
                - @DELETE - For lines to be deleted
                - @UPDATE - For lines to be updated, with BEFORE and AFTER subsections
                
                Each line in a section follows this format:
                <line_number>:<content>
                
                Important rules:
                - Diff chunks are applied in sequence from top to bottom
                - Diff chunks modifying earlier lines in the file should appear earlier in the sequence
                - Each new section starts with @DELETE or @UPDATE
                - @DELETE sections specify lines to be removed from the file
                - @UPDATE sections must contain both BEFORE and AFTER subsections
                - Line numbers in an @UPDATE's AFTER section typically match the BEFORE section
                - Additional lines in the AFTER section will be inserted after the updated lines
                - Different sections should not overlap in the lines they modify
                - Line numbers always correspond to the original file contents
            """
            ).strip(),
            parameters=[
                CommandParameter(
                    name="path",
                    description="Path to the file to update",
                    required=True,
                    is_positional=True,
                ),
                CommandParameter(
                    name="disable_model_fallback",
                    description="Disable model fallback if diff cannot be applied",
                    required=False,
                    is_positional=False,
                    default=False,
                    long_flag="disable-model-fallback",
                    is_flag=True,
                    hidden=True,
                ),
            ],
            examples=textwrap.dedent(
                """
                # Example 1: Simple @DELETE operation
                # Original file (delete_example.txt):
                1:First line
                2:Line to be deleted
                3:Third line
                4:Fourth line
                
                ▶update_file delete_example.txt｜Remove the second line
                @DELETE
                2:Line to be deleted
                ■
                ✅File updated successfully■
                
                # Updated file (delete_example.txt):
                1:First line
                2:Third line
                3:Fourth line
                
                # Example 2: Simple @UPDATE operation
                # Original file (update_example.py):
                1:def old_function():
                2:    # Function implementation
                3:    return True
                
                ▶update_file update_example.py｜Update function name
                @UPDATE
                BEFORE
                1:def old_function():
                AFTER
                1:def new_function():
                ■
                ✅File updated successfully■
                
                # Updated file (update_example.py):
                1:def new_function():
                2:    # Function implementation
                3:    return True
                
                # Example 3: Complex example with all operations (applied in sequence)
                # Original file (config.js):
                1:// Configuration file
                2:const config = {
                3:    host: 'localhost',
                4:    port: 8080,
                5:    debug: false,
                6:    timeout: 30000
                7:};
                8:
                9:// Export configuration
                10:module.exports = config;
                
                ▶update_file config.js｜Update configuration settings - applied in sequence
                # The following diff chunks are applied in sequence from top to bottom
                # Chunks modifying earlier lines should appear earlier in the sequence
                
                # First operation: Update the host and port (lines 3-4)
                @UPDATE
                BEFORE
                3:    host: 'localhost',
                4:    port: 8080,
                AFTER
                3:    host: 'production.example.com',
                4:    port: 443,
                
                # Second operation: Insert secure settings (lines 7-8)
                @INSERT
                7:    secure: true,
                8:    retryCount: 3,
                
                # Third operation: Delete the export comment (line 9)
                @DELETE
                9:// Export configuration
                
                # Fourth operation: Update the export statement (line 10+)
                @UPDATE
                BEFORE
                10:module.exports = config;
                AFTER
                10:// Add environment-specific overrides
                11:if (process.env.NODE_ENV === 'development') {
                12:    config.host = 'localhost';
                13:    config.port = 8080;
                14:}
                15:
                16:module.exports = config;
                ■
                ✅File updated successfully■
                
                # Final file (config.js) after all sequential operations:
                1:// Configuration file
                2:const config = {
                3:    host: 'production.example.com',
                4:    port: 443,
                5:    debug: false,
                6:    timeout: 30000,
                7:    secure: true,
                8:    retryCount: 3
                9:};
                10:// Add environment-specific overrides
                11:if (process.env.NODE_ENV === 'development') {
                12:    config.host = 'localhost';
                13:    config.port = 8080;
                14:}
                15:
                16:module.exports = config;
                
            """
            ).strip(),
        )

    def _get_system_prompt(self) -> str:
        """Get system prompt for the model with improved error reporting instructions"""
        return textwrap.dedent(
            """
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
        """
        ).strip()

    def process(
        self, ctx: Context, args: Dict[str, Any], data: Optional[str] = None
    ) -> str:
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
                parameters={"path": file_path, "workspace": workspace},
                data=updated_content,
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
            logger.warning(
                f"Diff application failed: {error_message}. Falling back to model."
            )

            # Get the original content of the file with line numbers
            read_result = shell.execute(
                "read_file",
                parameters={"path": file_path, "include_line_numbers": True},
            )
            if not read_result.success:
                return f"❌{read_result.error}"

            file_content = read_result.result

            # Import the escaping function from messages.py
            from src.core.messages import _escape_special_chars

            # Escape the file content to avoid issues with special characters
            escaped_file_content = _escape_special_chars(file_content)

            # Build the initial message with file content, diff, and original error message
            initial_message = (
                f"I need to update the file at '{file_path}' with this diff that couldn't be applied automatically:\n\n{diff_text}\n\n"
                + f"The automatic diff application failed with this error (which you MUST include verbatim in your response):\n\n```\n{error_message}\n```\n\n"
                + f"Here is the current content of the file:\n\n{escaped_file_content}\n\n"
                + f"First, quote the exact original error message as shown above. Then identify and show the exact relevant portions of the file related to this error, "
                + f"including their line numbers. After that, make the necessary changes aligned with the intent of the diff and use the write_file command to save the updated content. "
                + f"Once done, say <Successfully updated file> if you were successful, else say that you failed to update the file."
                + f" You MUST always write the file in its entirety. DO NOT write partial contents."
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
                commands=["read_file", "write_file"],
                auto_execute_commands=True,
            ).text()
