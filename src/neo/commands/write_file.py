"""
Write file command implementation.

This module provides the WriteFileCommand class for creating or overwriting files.
"""

"""Implements the 'write_file' command for creating or overwriting files."""

import os
import logging
import textwrap
import argparse
import shlex
from dataclasses import dataclass
from typing import Dict, Any, Optional, Tuple

from src.neo.exceptions import FatalError

from src.neo.commands.base import Command, FileUpdate
from src.neo.core.messages import CommandResult
from src.neo.session import Session
from src.utils.files import write, FileWriteResult

# Configure logging
logger = logging.getLogger(__name__)


@dataclass
class WriteFileArgs:
    """Structured arguments for write_file command."""
    path: str
    content: str


class WriteFileCommand(Command):
    """
    Command for creating or overwriting files.

    Features:
    - Creates new files or completely replaces content of existing files
    - Creates parent directories automatically if they don't exist
    - Returns line addition/deletion statistics
    - Uses the workspace from the Session
    """

    @property
    def name(self) -> str:
        """Return the command name."""
        return "write_file"
        
    def description(self) -> str:
        """Returns a short description of the command."""
        return "Create a new file or overwrite an existing file"
        
    def help(self) -> str:
        """Returns detailed help for the command."""
        return textwrap.dedent(
            """
            Use the `write_file` command to create a new file or overwrite an existing file.
            
            Usage: ▶write_file PATH｜CONTENT■
            
            - PATH (required): Path to the file to create or overwrite.
            - CONTENT (required): Content to write to the file
            
            Create a new file or overwrite an existing file.
            
            The write_file command creates or overwrites a file specified by PATH using data content.
            
            Example:
            ▶write_file path/to/new_file.py｜def hello_world():
                print("Hello, World!")■
            ✅SUCCESS (+4,-0)■
            
            ▶read_file path/to/new_file.py■
            ✅def hello_world():
                print("Hello, World!")■
            """
        )

    def _parse_statement(self, statement: str, data: Optional[str] = None) -> WriteFileArgs:
        """Parse the command statement using argparse."""
        # Validate that data parameter is present
        if not data:
            raise ValueError("The write_file command requires data input (content after |)")
            
        # Create parser for write_file command
        parser = argparse.ArgumentParser(prog="write_file", exit_on_error=False)
        
        # Add arguments
        parser.add_argument("path", help="Path to the file to create or overwrite")
        
        # Split statement into parts using shlex for proper handling of quoted arguments
        try:
            args = shlex.split(statement)
            
            # Parse arguments
            parsed_args = parser.parse_args(args)
            return WriteFileArgs(
                path=parsed_args.path,
                content=data
            )
        except argparse.ArgumentError as e:
            raise ValueError(f"The write_file command {str(e)}")
        except Exception as e:
            raise ValueError(f"The write_file command requires path: {str(e)}")
            
    def validate(self, session, statement: str, data: Optional[str] = None) -> None:
        """Validate the write_file command statement."""
        # The _parse_statement method will raise appropriate exceptions
        # if validation fails, so we just need to call it here
        self._parse_statement(statement, data)
        
    def execute(
        self, session, statement: str, data: Optional[str] = None
    ) -> CommandResult:
        """Execute the write_file command with the parsed arguments and data."""
        try:
            # First run validation
            parsed_args = self._parse_statement(statement, data)

            # Get the path argument
            path = parsed_args.path

            # Get the content from the parsed args
            content = parsed_args.content

            # Get workspace from session
            workspace = session.workspace
            
            # Use the enhanced write function that handles diff generation
            result: FileWriteResult = write(workspace, path, content)
            
            # Prepare message based on whether file was created or updated
            if result.file_existed:
                command_msg = f"SUCCESS: Updated {path} (+{result.lines_added},-{result.lines_deleted})"
            else:
                command_msg = f"SUCCESS: Created {path} (+{result.lines_added},-0)"

            # Create FileUpdate instance
            file_update = FileUpdate(
                name=self.name,
                message=command_msg,
                diff=result.diff
            )
            
            return CommandResult(
                content=command_msg, 
                success=True,
                command_output=file_update
            )
            
        except ValueError as ve:
            logger.error(f"Error writing file: {ve}")
            return CommandResult(
                content=str(ve),
                success=False
            )
        except Exception as e:
            logger.error(f"Error writing file: {e}")
            return CommandResult(
                content=f"Failed to write to file: {e}",
                success=False
            )
