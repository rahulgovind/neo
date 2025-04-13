"""
Write file command implementation.

This module provides the WriteFileCommand class for creating or overwriting files.
"""

import os
import logging
import textwrap
from typing import Dict, Any, Optional, Tuple

from src.core.constants import (
    COMMAND_START,
    COMMAND_END,
    SUCCESS_PREFIX,
    ERROR_PREFIX,
    STDIN_SEPARATOR,
)
from src.core.exceptions import FatalError

from src.core.command import Command, CommandTemplate, CommandParameter
from src.core.messages import CommandResult
from src.core.context import Context
from src.utils.files import overwrite

# Configure logging
logger = logging.getLogger(__name__)


class WriteFileCommand(Command):
    """
    Command for creating or overwriting files.

    Features:
    - Creates new files or completely replaces content of existing files
    - Creates parent directories automatically if they don't exist
    - Returns line addition/deletion statistics
    - Uses the workspace from the Context
    """

    def template(self) -> CommandTemplate:
        """
        Returns the command template with parameter definitions and documentation.
        """
        return CommandTemplate(
            name="write_file",
            requires_data=True,
            description=textwrap.dedent(
                """
                Create a new file or overwrite an existing file.
                
                The write_file command creates or overwrites a file specified by PATH using STDIN as content.
                
                The PATH argument can be a relative path from the current workspace or an absolute path.
                Parent directories are created automatically if they don't exist.
            """
            ),
            examples=textwrap.dedent(
                """
                ▶write_file path/to/new_file.py｜def hello_world():
                print("Hello, World!")■
                ✅SUCCESS (+4,-0)■
                
                ▶write_file config.json｜{
                    "debug": true,
                    "port": 8080
                }■
                ✅SUCCESS (+4,-0)■
            """
            ),
            parameters=[
                CommandParameter(
                    name="path",
                    description="Path to the file to create or overwrite.",
                    required=True,
                    is_positional=True,
                ),
            ],
        )

    def process(self, ctx, args: Dict[str, Any], data: Optional[str] = None) -> CommandResult:
        """
        Process the command with the parsed arguments and optional data.

        Args:
            ctx: Application context
            args: Dictionary of parameter names to their values
            data: Optional data string containing the content to write to the file

        Returns:
            CommandResult with success status and summary of the operation
        """
        # Get the workspace from the context
        workspace = ctx.workspace

        path = args.get("path")
        if not path:
            logger.error("Path not provided to write_file command")
            raise FatalError("Path argument is required")

        if not data:
            logger.error("No content provided to write_file command")
            raise FatalError("Content must be provided as data (after |)")

        # Get the no_lint flag (defaults to False)
        no_lint = args.get("no_lint", False)
        
        # Pass the no_lint flag to the overwrite function
        success, lines_added, lines_deleted = overwrite(workspace, path, data, no_lint)
        
        if not success:
            return CommandResult(success=False, error=f"Failed to write to {path}")
        
        result_text = f"SUCCESS (+{lines_added},-{lines_deleted})"
        file_path = os.path.basename(path)
        summary = f"File updated: {file_path} (+{lines_added},-{lines_deleted})"
        
        return CommandResult(result=result_text, success=True, summary=summary)
