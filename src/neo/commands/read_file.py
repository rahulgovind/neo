"""
Read file command implementation.

This module provides the ReadFileCommand class for reading file contents.
"""

import os
import logging
import textwrap
import argparse
import shlex
from dataclasses import dataclass
from typing import Dict, Any, Optional

from src.neo.core.messages import CommandResult
from src.neo.commands.base import Command
from src.neo.exceptions import FatalError
from src.utils.files import read
from src import NEO_HOME
# Configure logging
logger = logging.getLogger(__name__)


@dataclass
class ReadFileArgs:
    """Structured arguments for read_file command."""
    path: str
    no_line_numbers: bool = False
    limit: int = 200
    from_: Optional[int] = None
    until_: Optional[int] = None



class ReadFileCommand(Command):
    """
    Command for reading file contents.

    Features:
    - Adds line numbers to make referencing specific lines easier
    - Handles common file reading errors gracefully
    - Uses the workspace from the Session
    - Supports reading specific line ranges with flexible syntax
    - Limits output to a reasonable number of lines by default
    - Shows indicators when content is truncated
    """

    @property
    def name(self) -> str:
        """Return the command name."""
        return "read_file"
        
    def _parse_statement(self, statement: str, data: Optional[str] = None) -> ReadFileArgs:
        """Parse the command statement using argparse."""
        # Validate that data parameter is not set
        if data:
            raise ValueError("The read_file command does not accept data input")
            
        # Create parser for read_file command
        parser = argparse.ArgumentParser(prog="read_file", exit_on_error=False)
        
        # Add arguments
        parser.add_argument("path", help="Path to the file to read")
        parser.add_argument("--no-line-numbers", action="store_true", help="Exclude line numbers from output")
        parser.add_argument("--limit", type=int, default=200, help="Maximum number of lines to display")
        parser.add_argument("--from", dest="from_", type=int, help="First line to read (1-indexed)")
        parser.add_argument("--until", dest="until_", type=int, help="Last line to read (inclusive)")
        
        # Split statement into parts using shlex for proper handling of quoted arguments
        args = shlex.split(statement)
        
        # Parse arguments
        parsed_args = parser.parse_args(args)
        return ReadFileArgs(
            path=parsed_args.path,
            no_line_numbers=parsed_args.no_line_numbers,
            limit=parsed_args.limit,
            from_=parsed_args.from_,
            until_=parsed_args.until_
        )
            
    def validate(self, session, statement: str, data: Optional[str] = None) -> None:
        """Validate the read_file command statement."""
        # The _parse_statement method will raise appropriate exceptions
        # if validation fails, so we just need to call it here
        self._parse_statement(statement, data)
    
    def description(self) -> str:
        """Returns a short description of the command."""
        return "Read and display file contents."
    
    def help(self) -> str:
        """Returns a detailed description of the command with examples and parameter lists."""
        return textwrap.dedent(
            """
            Use the `read_file` command to read and display file contents.
            
            Usage: ▶read_file PATH [--from <from>] [--until <until>] [--limit <limit>]■
            
            - PATH: Path to the file to read
            - from: First line to read (1-indexed). Negative values count from the end.
            - until: Last line to read (inclusive). Negative values count from the end.
            - limit: Maximum number of lines to display. Default: 200
            
            Examples:
            
            ▶read_file path/to/file.py■
            ✅1:import os
            2:import sys
            3:
            4:print("Hello, World!")
            5:x = 2■
            
            ▶read_file --from 2 --until 4 path/to/file.py■
            ✅2:import sys
            3:
            4:print("Hello, World!")■
            
            ▶read_file --from -2 --until -1 path/to/file.py■
            ✅4:print("Hello, World!")
            5:x = 2■
            """
        )


    def execute(
        self, session, statement: str, data: Optional[str] = None
    ) -> CommandResult:
        """Execute the read_file command."""
        # Parse the command statement
        args = self._parse_statement(statement, data)
        path = args.path

        # Determine the workspace
        workspace = session.workspace
        if not workspace:
            return CommandResult(success=False, content="Workspace path is not set. Please specify a workspace directory.")

        # Check if the path is explicitly targeting the NEO_HOME directory
        if path.startswith(NEO_HOME):
            # Normalize and expand the path for NEO_HOME
            full_path = os.path.expanduser(path) if path.startswith("~") else path
            logger.info("Accessing file in NEO_HOME directory: %s", full_path)
        # Standard case: normalize the path to be relative to the workspace
        elif not os.path.isabs(path):
            full_path = os.path.join(workspace, path)
        else:
            # If absolute path is provided, ensure it's within the workspace
            if not path.startswith(workspace):
                raise FatalError(f"Path must be within the workspace: {workspace}")
            full_path = path

        # Get the parameters from the parsed args
        include_line_numbers = not args.no_line_numbers
        from_line = args.from_
        until_line = args.until_
        limit = args.limit

        try:
            # Read the file content - now returns a FileContent object or raises an exception
            file_content = read(
                full_path,
                from_=from_line,
                until=until_line,
                limit=limit,
            )
            
            # Format the output based on whether line numbers are requested
            formatted_content = file_content.format(include_line_numbers=include_line_numbers)


            # Create a summary of the operation
            file_path = os.path.basename(full_path)
            summary = f"Read file: {file_path}"
            
            # Add line range info to summary if applicable
            if from_line is not None or until_line is not None:
                line_range = ""
                if from_line is not None:
                    line_range += f"from line {from_line} "
                if until_line is not None:
                    line_range += f"to line {until_line}"
                summary += f" ({line_range.strip()})"
                
            # Add displayed range info
            start_line, end_line = file_content.displayed_range
            summary += f" (showing lines {start_line+1}-{end_line} of {file_content.line_count})"

            return CommandResult(content=formatted_content, success=True)
            
        except FileNotFoundError as e:
            return CommandResult(success=False, content=str(e))
        except IsADirectoryError as e:
            return CommandResult(success=False, content=str(e))
        except PermissionError as e:
            return CommandResult(success=False, content=f"Permission denied: {str(e)}")
        except UnicodeDecodeError:
            return CommandResult(success=False, content=f"File is not text or has unknown encoding: {full_path}")
        except ValueError as e:
            return CommandResult(success=False, content=f"Invalid parameters: {str(e)}")
        except IOError as e:
            # Handle any other file I/O errors
            logger.exception("Unexpected I/O error: %s", str(e))
            return CommandResult(success=False, content=f"Error reading file: {str(e)}")
        except Exception as e:  # pylint: disable=broad-except
            # This is a fallback for any unforeseen errors
            logger.exception("Unexpected error reading file: %s", full_path)
            return CommandResult(success=False, content=f"Unexpected error: {str(e)}")



