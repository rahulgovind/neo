"""
Write file command implementation.

This module provides the WriteFileCommand class for creating or overwriting files.
"""

import os
import logging
import textwrap
from typing import Dict, Any, Optional, Tuple

from src.core.constants import COMMAND_START, COMMAND_END, SUCCESS_PREFIX, ERROR_PREFIX, STDIN_SEPARATOR
from src.core.exceptions import FatalError

from src.core.command import Command, CommandTemplate, CommandParameter
from src.core.messages import CommandResult
from src.core import context
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
            description=textwrap.dedent("""
                Create a new file or completely overwrite an existing file in the workspace.
                
                Example:

                ▶write_file path/to/new_file.py｜def hello_world():
                print("Hello, World!")■
                ✅SUCCESS (+4,-0)■
                
                ▶write_file config.json｜{
                    "debug": true,
                    "port": 8080
                }■
                ✅SUCCESS (+4,-0)■
            """),
            parameters=[
                CommandParameter(
                    name="path",
                    description="Path to the file to create or overwrite.",
                    required=True,
                    is_positional=True
                )
            ]
        )
    
    def process(self, args: Dict[str, Any], data: Optional[str] = None) -> str:
        """
        Process the command with the parsed arguments and optional data.
        
        Args:
            args: Dictionary of parameter names to their values
            data: Optional data string containing the content to write to the file
            
        Returns:
            Status message with line addition/deletion counts
        """
        # Get the workspace from the context
        ctx = context.get()
        workspace = ctx.workspace
        if not workspace:
            raise FatalError("No workspace set in context")
        
        path = args.get("path")
        if not path:
            logger.error("Path not provided to write_file command")
            raise FatalError("Path argument is required")
        
        if not data:
            logger.error("No content provided to write_file command")
            raise FatalError("Content must be provided as data (after |)")
        
        # Let exceptions propagate up to the caller
        success, lines_added, lines_deleted = overwrite(workspace, path, data)
        return f"SUCCESS (+{lines_added},-{lines_deleted})"
