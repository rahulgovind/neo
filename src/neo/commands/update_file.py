"""
Update file command implementation.

This module provides the UpdateFile class for updating files based on diff structure.
"""

import os
import logging
import textwrap
from typing import Dict, Any, Optional, List

from src.neo.shell.command import Command, CommandTemplate, CommandParameter
from src.neo.exceptions import FatalError
from src.neo.core.messages import CommandResult
from src.neo.session import Session
from src.utils.merge import merge

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
                - @UPDATE - For lines to be updated, with @@BEFORE and @@AFTER subsections
                
                Each line in a section follows this format:
                <line_number>:<content>
                
                Important rules:
                - Diff chunks are applied in sequence from top to bottom
                - Diff chunks modifying earlier lines in the file should appear earlier in the sequence
                - Each new section starts with @DELETE or @UPDATE
                - @DELETE sections specify lines to be removed from the file
                - @UPDATE sections must contain both @@BEFORE and @@AFTER subsections
                - Line numbers in an @UPDATE's @@AFTER section typically match the @@BEFORE section
                - Additional lines in the @@AFTER section will be inserted after the updated lines
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
                
                ▶update_file delete_example.txt｜
                @DELETE Remove the second line
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
                
                ▶update_file update_example.py｜
                @UPDATE Update function name
                @@BEFORE
                1:def old_function():
                @@AFTER
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
                
                ▶update_file config.js｜
                @UPDATE Update configuration settings
                @@BEFORE
                3:    host: 'localhost',
                4:    port: 8080,
                @@AFTER
                3:    host: 'production.example.com',
                4:    port: 443,
                
                @UPDATE Insert secure settings
                @@BEFORE
                6:    timeout: 30000
                7:};
                @@AFTER
                6:    timeout: 30000,
                7:    secure: true,
                8:    retryCount: 3,
                9:};
                
                @DELETE Delete the export comment
                9:// Export configuration
                
                @UPDATE
                @@BEFORE
                10:module.exports = config;
                @@AFTER
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
        self, ctx: Session, args: Dict[str, Any], data: Optional[str] = None
    ) -> CommandResult:
        """Process the update file command with the parsed arguments and data.

        Args:
            ctx: Application context
            args: Dictionary of parameter names to their values
            data: The diff content to apply to the file

        Returns:
            CommandResult with success status and summary of the operation
        """
        # Get the file path from arguments
        file_path = args.get("path")
        if not file_path:
            raise FatalError("No file path provided")

        # Get the diff from data
        diff_text = data
        if not diff_text:
            raise FatalError("No diff provided")

        # Get shell from context
        shell = ctx.shell

        # First try to apply the diff using the merge function
        logger.info(f"Attempting to apply diff to {file_path}")
        try:
            # Check if file exists first
            if not os.path.exists(file_path):
                file_name = os.path.basename(file_path)
                return CommandResult(
                    content=f"File not found: {file_path}",
                    success=False,
                    summary=f"Failed to update {file_name}: File not found",
                )

            # Read the file content
            with open(file_path, "r", encoding="utf-8") as f:
                file_content = f.read()
            # Apply the merge with the diff
            updated_content = merge(file_content, diff_text)
            # If we got here, merge succeeded, write the updated content to the file
            workspace = ctx.workspace
            write_result = shell.execute(
                "write_file",
                parameters={"path": file_path, "workspace": workspace},
                data=updated_content,
            )

            if write_result.success:
                logger.info(f"Successfully applied diff to {file_path}")
                file_name = os.path.basename(file_path)
                summary = f"File updated: {file_name}"
                return CommandResult(
                    content="File updated successfully", success=True, summary=summary
                )
            else:
                return CommandResult(
                    success=False,
                    content=str(write_result.error),
                    error=write_result.error,
                )

        except RuntimeError as e:
            if bool(args.get("disable_model_fallback")):
                logger.warning(f"Disabling model fallback: {str(e)}")
                return CommandResult(
                    success=False,
                    content=str(e),
                    error=e,
                    summary="Model fallback disabled",
                )

            # Return a failure with the error details
            error_message = str(e)
            logger.warning(f"Merge application failed: {error_message}.")

            file_name = os.path.basename(file_path)
            return CommandResult(
                content=f"Failed to update file: {error_message}",
                success=False,
                summary=f"Failed to update {file_name}: {error_message}",
            )
