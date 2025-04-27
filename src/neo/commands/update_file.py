"""
Update file command implementation.

This module provides the UpdateFileCommand class for updating files based on diff structure.
"""

import os
import logging
import textwrap
import argparse
import shlex
from dataclasses import dataclass
from typing import Dict, Any, Optional, List

from src.neo.commands.base import Command, FileUpdate
from src.neo.exceptions import FatalError
from src.neo.core.messages import CommandResult
from src.neo.session import Session
from src.utils.merge import merge
from src.utils.files import write, FileWriteResult

# Configure logging
logger = logging.getLogger(__name__)


@dataclass
class UpdateFileArgs:
    """Structured arguments for update_file command."""

    path: str
    diff_content: str


class UpdateFileCommand(Command):
    """
    Command for updating files based on a diff structure.

    Takes a file path as a parameter and a diff structure as data,
    then applies the diff to update the file content. If the diff cannot be applied,
    it falls back to using the model to perform the update.
    """

    @property
    def name(self) -> str:
        """Return the command name."""
        return "update_file"

    def description(self) -> str:
        """Returns a short description of the command."""
        return "Update a file using a diff structure"

    def help(self) -> str:
        """Returns detailed help for the command."""
        return textwrap.dedent(
            """\
            Use the `update_file` command to update partial contents of a file.

            USAGE: ▶update_file PATH｜DIFF■

            - PATH: Path to the file to update (required)
            - DIFF: Diff structure to apply (required)

            DIFF format:
            @DELETE <Optional comment>
            Lines to delete
            @UPDATE <Optional comment>
            @@BEFORE
            Lines in the original content.
            @@AFTER
            Lines that replace those in the @@BEFORE section
            
            RULES:
            - Each diff MAY have multiple @DELETE and @UPDATE sections.
            - You SHOULD make multiple relevant changes using the same "update_file" command call.
            - Lines MUST include line numbers. 
            - Line numbers in @@AFTER subsection MUST start with the same initial line number as the corresponding @@BEFORE subsection.
            - Diffs MUST NOT overlap in the lines they change.
            - Diffs MUST be provided in the order of the line numbers they affect.

            NOTES:
            - Be careful about white spaces! Include necessary whitespace in both the original and new content.

            EXAMPLE:
            ▶read_file config.js■
            ✅1:// Configuration file
            2:const config = {
            3:    host: 'localhost',
            4:    port: 8080,
            5:    debug: false,
            6:    timeout: 30000
            7:};
            8:
            9:// Export configuration
            10:module.exports = config;■
            
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
            ▶read_file config.js■
            ✅1:// Configuration file
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
            16:module.exports = config;■
            """
        )

    def _get_system_prompt(self) -> str:
        """Get system prompt for the model with improved error reporting instructions"""
        return textwrap.dedent(
            """
            You are an expert assistant tasked with analyzing diff application errors and helping to fix them.
            
            In your response:
            - Always start by quoting the original error that occurred during the diff application, exactly as provided.
            - Verbatim include the relevant file sections. Do not paraphrase or modify these sections when quoting them.
            - Format the original file sections with line numbers to help the user locate the issue.
            - Only after showing the error and relevant file sections, provide your explanation and solution.
            - Be precise and maintain the original formatting and style of the file.
            - Only make the changes aligned with the intent of the diff.
            - If you cannot determine what changes are needed, explain why.
        """
        ).strip()

    def _parse_statement(
        self, statement: str, data: Optional[str] = None
    ) -> UpdateFileArgs:
        """Parse the command statement using argparse."""
        # Validate that data parameter is present
        if not data:
            raise ValueError("The update_file command requires diff content (after |)")

        # Create parser for update_file command
        parser = argparse.ArgumentParser(prog="update_file", exit_on_error=False)

        # Add arguments
        parser.add_argument("path", help="Path to the file to update")

        # Split statement into parts using shlex for proper handling of quoted arguments
        args = shlex.split(statement)

        # Parse arguments
        parsed_args = parser.parse_args(args)
        return UpdateFileArgs(path=parsed_args.path, diff_content=data)

    def validate(self, session, statement: str, data: Optional[str] = None) -> None:
        """Validate the update_file command statement."""
        # The _parse_statement method will raise appropriate exceptions
        # if validation fails, so we just need to call it here
        self._parse_statement(statement, data)

    def execute(
        self, session: Session, statement: str, data: Optional[str] = None
    ) -> CommandResult:
        """Process the update file command with the parsed arguments and data.

        Args:
            session: Session object with shell and workspace
            statement: Command statement string
            data: The diff content to apply to the file

        Returns:
            CommandResult with success status and summary of the operation
        """
        # Parse the command statement
        args = self._parse_statement(statement, data)

        # Get the file path
        file_path = args.path

        # Get the diff content from the parsed args
        diff_text = args.diff_content

        # Get shell from session
        shell = session.shell

        # First try to apply the diff using the merge function
        logger.info(f"Attempting to apply diff to {file_path}")
        try:
            # Check if file exists first
            if not os.path.exists(file_path):
                file_name = os.path.basename(file_path)
                return CommandResult(
                    content=f"File not found: {file_path}",
                    success=False
                )

            # Read the file content
            with open(file_path, "r", encoding="utf-8") as f:
                file_content = f.read()
                
            # Apply the merge with the diff
            updated_content = merge(file_content, diff_text)
            
            # Use the enhanced write function directly with diff generation
            workspace = session.workspace
            relative_path = os.path.relpath(file_path, workspace)
            
            # Write the updated content and get the FileWriteResult
            write_result = write(workspace, relative_path, updated_content)
            
            logger.info(f"Successfully applied diff to {file_path}")
            file_name = os.path.basename(file_path)
            
            # Create FileUpdate command output using the diff from write_result
            file_update = FileUpdate(
                name="update_file",
                message=f"Updated {file_name} (+{write_result.lines_added},-{write_result.lines_deleted})",
                diff=write_result.diff
            )
            
            return CommandResult(
                content=f"File updated successfully", 
                success=True, 
                command_output=file_update
            )

        except RuntimeError as e:
            # Model fallback is now always enabled
            # Return a failure with the error details
            error_message = str(e)
            logger.warning(f"Merge application failed: {error_message}.")

            file_name = os.path.basename(file_path)
            return CommandResult(
                content=f"Failed to update file: {error_message}",
                success=False
            )
