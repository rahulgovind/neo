"""
Read file command implementation.

This module provides the ReadFileCommand class for reading file contents.
"""

import os
import logging
import textwrap
from typing import Dict, Any, Optional

from src.neo.core.messages import CommandResult
from src.neo.shell.command import Command, CommandTemplate, CommandParameter
from src.neo.exceptions import FatalError
from src.utils.files import read
from src import NEO_HOME
# Configure logging
logger = logging.getLogger(__name__)


class ReadFileCommand(Command):
    """
    Command for reading file contents.

    Features:
    - Adds line numbers to make referencing specific lines easier
    - Handles common file reading errors gracefully
    - Uses the workspace from the Context
    - Supports reading specific line ranges with flexible syntax
    - Limits output to a reasonable number of lines by default
    - Shows indicators when content is truncated
    """

    def template(self) -> CommandTemplate:
        """
        Returns the command template with parameter definitions and documentation.
        """
        return CommandTemplate(
            name="read_file",
            description=textwrap.dedent(
                """
                Read and display file contents.

                The read_file command outputs the contents of a file specified by PATH.

                PATH can be a relative or absolute path to a file.
                By default, line numbers are included in the output.
                Use --no-line-numbers to display the content without line numbers.

                By default, at most 200 lines will be returned.
                Use --from and --until to specify particular sections of the file.
                Use --limit to change the maximum number of lines shown.
                Negative indices count from the end of the file.
                Use --limit -1 to read the entire file without line limits.
                """
            ),
            examples=textwrap.dedent(
                """
                ▶read_file path/to/file.py■
                ✅1:import os
                2:import sys
                3:
                4:print("Hello, World!")■

                ▶read_file --no-line-numbers path/to/file.py■
                ✅import os
                import sys

                print("Hello, World!")■

                ▶read_file --from 323 path/to/large_file.py■
                ✅323:def process_data():
                324:    # Process data function
                ...
                423:    return result
                ... 157 additional lines■

                ▶read_file --until 50 path/to/file.py■
                ✅... 20 additional lines
                30:import os
                ...
                50:# Show lines before line 50■

                ▶read_file --from 100 --until 200 config.json■
                ✅100:{
                101:    # Lines 100-200
                102:}■

                ▶read_file --from -100 path/to/file.py■
                ✅900:# Last 100 lines of the file
                ...
                999:# End of file■

                ▶read_file --limit -1 path/to/file.py■
                ✅1:# Entire file from beginning to end
                2:# Second line
                ...
                999:# Including the last line■

                ▶read_file nonexistent.py■
                ❌File not found: nonexistent.py■
                """
            ),
            requires_data=False,
            parameters=[
                CommandParameter(
                    name="path",
                    description="Path to the file to read.",
                    required=True,
                    is_positional=True,
                ),
                CommandParameter(
                    name="no_line_numbers",
                    description="Exclude line numbers from the output.",
                    required=False,
                    default=False,
                    is_flag=True,
                    long_flag="no-line-numbers",
                ),
                CommandParameter(
                    name="from_",
                    description=(
                        "Start reading from this line number. "
                        "Can be a positive number (1-indexed) "
                        "or negative (count from end)."
                    ),
                    required=False,
                    is_flag=True,
                    long_flag="from",
                ),
                CommandParameter(
                    name="until_",
                    description=(
                        "Read until this line number (inclusive). "
                        "Can be a positive number or negative (count from end)."
                    ),
                    required=False,
                    is_flag=True,
                    long_flag="until",
                ),
                CommandParameter(
                    name="limit",
                    description=(
                        "Maximum number of lines to show. "
                        "Default: 200. Use -1 for unlimited."
                    ),
                    required=False,
                    is_flag=True,
                    long_flag="limit",
                    default=200,
                ),
            ],
        )        

    def process(
        self, ctx, args: Dict[str, Any], data: Optional[str] = None
    ) -> CommandResult:
        """
        Process the command with the parsed arguments and optional data.

        Args:
            ctx: Application context
            args: Dictionary of parameter names to their values
            data: Optional data string (not used in this command)

        Returns:
            CommandResult with file contents and summary
        """
        # Get the workspace from the context
        workspace = ctx.workspace

        path = args.get("path")
        if not path:
            logger.error("Path not provided to read_file command")
            raise FatalError("Path argument is required")

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

        # Determine whether to include line numbers
        # (default is True, unless --no-line-numbers is specified)
        include_line_numbers = not args.get("no_line_numbers", False)

        # Get range parameters if specified
        from_line = args.get("from_")
        if from_line is not None:
            try:
                from_line = int(from_line)
            except ValueError:
                return CommandResult(success=False, content=f"Invalid value for --from. Found {from_line}. Expected a number.")

        until_line = args.get("until_")
        if until_line is not None:
            try:
                until_line = int(until_line)
            except ValueError:
                return CommandResult(success=False, content=f"Invalid value for --until. Found {until_line}. Expected a number.")

        limit = args.get("limit", 200)
        if limit is not None:
            try:
                limit = int(limit)
            except ValueError:
                return CommandResult(success=False, content=f"Invalid value for --limit. Found {limit}. Expected a number.")

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

            return CommandResult(content=formatted_content, success=True, summary=summary)
            
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



