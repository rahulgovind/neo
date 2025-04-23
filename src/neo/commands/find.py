"""
File path search command implementation.

This module provides the FilePathSearch class for finding files based on name and type.
"""

import os
import logging
import subprocess
import textwrap
import argparse
import shlex
from dataclasses import dataclass
from typing import Dict, Any, Optional, List

from src.neo.shell.command import Command
from src.neo.session import Session
from src.neo.core.messages import CommandResult
from src.neo.exceptions import FatalError

# Configure logging
logger = logging.getLogger(__name__)


@dataclass
class FilePathSearchArgs:
    """Structured arguments for file_path_search command."""
    path: str
    name: Optional[str] = None
    type: Optional[str] = None


class FilePathSearch(Command):
    """Command for finding files and directories based on name and type criteria.

    Features:
    - Delegates to the find command for efficient file searching
    - Supports filtering by name pattern
    - Supports filtering by file type (file or directory)
    - Uses the workspace from the Session
    """

    @property
    def name(self) -> str:
        """Return the command name."""
        # TODO: Implement name property to return command name
        return "file_path_search"

    def description(self) -> str:
        """Returns a short description of the command."""
        # TODO: Implement description method to return a brief command description
        return "Find files and directories matching specified criteria."

    def _parse_statement(self, statement: str, data: Optional[str] = None) -> FilePathSearchArgs:
        """Parse the command statement using argparse."""
        # TODO: Implement _parse_statement to convert shell arguments to structured args
        # Validate that data parameter is not set
        if data:
            raise ValueError("The file_path_search command does not accept data input")

        # Create parser for file_path_search command
        parser = argparse.ArgumentParser(prog="file_path_search", exit_on_error=False)

        # Add arguments

        parser.add_argument("path", help="Path to search in (relative to workspace)")
        # TODO: Rename to "--file-pattern". Multiple patterns can be specified. Including exclusion patterns.
        parser.add_argument("-n", "--name", help="File name pattern to search for (e.g., '*.py')")
        parser.add_argument("-t", "--type", help="File type to search for ('f' for files, 'd' for directories)")
        # TODO: Add a content pattern to search for within files.

        # Split statement into parts using shlex for proper handling of quoted arguments
        args = shlex.split(statement)

        # Parse arguments
        parsed_args = parser.parse_args(args)
        return FilePathSearchArgs(
            path=parsed_args.path,
            name=parsed_args.name,
            type=parsed_args.type
        )

    def validate(self, session, statement: str, data: Optional[str] = None) -> None:
        """Validate the file_path_search command statement."""
        # TODO: Implement validate to check if command parameters are valid
        # The _parse_statement method will raise appropriate exceptions
        # if validation fails, so we just need to call it here
        self._parse_statement(statement, data)

    def help(self) -> str:
        """Returns detailed help for the command."""
        # TODO: Implement help method to return comprehensive command documentation
        return textwrap.dedent(
            """
            ## Description
            Find files and directories matching the specified criteria.

            The file_path_search command searches for files and directories in PATH based on name patterns
            and file type filters.

            PATH is a directory to start searching from (relative to workspace).

            ## Usage
            ```
            ▶file_path_search PATH [OPTIONS]■
            ```

            ## Parameters
            - `PATH`: Path to search in, relative to workspace (required)
            - `--name`, `-n`: File name pattern to search for (e.g., '*.py')
            - `--type`, `-t`: File type to search for ('f' for files, 'd' for directories)

            ## Examples
            ```
            ▶file_path_search src --name "*.py"■
            ✅src/core/command.py
            src/core/commands/grep.py
            src/utils/files.py■

            ▶file_path_search . --type f --name "README*"■
            ✅./README.md
            ./docs/README.txt■

            ▶file_path_search /tmp --type d■
            ✅/tmp/cache
            /tmp/logs
            /tmp/uploads■
            ```
            """
        )

    def execute(
        self, session: Session, statement: str, data: Optional[str] = None
    ) -> CommandResult:
        """
        Process the command with the parsed arguments and optional data.

        Args:
            session: Application session
            statement: Command statement
            data: Optional data string (not used)

        Returns:
            CommandResult with find command results and summary
        """
        # TODO: Implement execute method to search for files based on parameters

        # Parse the command statement
        args = self._parse_statement(statement, data)

        # Get the workspace from the session
        workspace = session.workspace

        path = args.path

        # Normalize the path to be relative to the workspace
        if not os.path.isabs(path):
            search_path = os.path.join(workspace, path)
        else:
            # If absolute path is provided, ensure it's within the workspace
            if not path.startswith(workspace):
                raise FatalError(f"Path must be within the workspace: {workspace}")
            search_path = path

        # Build the find command
        find_cmd = ["find", search_path]

        # Add type filter if provided
        file_type = args.type
        if file_type:
            if file_type not in ["f", "d"]:
                raise FatalError("Type must be 'f' for files or 'd' for directories")
            logger.debug(f"Adding type filter (-type {file_type}) to find command")
            find_cmd.extend(["-type", file_type])

        # Add name pattern if provided
        name_pattern = args.name
        if name_pattern:
            logger.debug(
                f"Adding name pattern filter (-name {name_pattern}) to find command"
            )
            find_cmd.extend(["-name", name_pattern])

        try:
            # Execute find command
            logger.debug(f"Executing find command: {' '.join(find_cmd)}")
            process = subprocess.run(
                find_cmd,
                capture_output=True,
                text=True,
                check=False,
                cwd=workspace,  # Ensure find runs in the workspace directory
            )
            logger.debug(f"Find command return code: {process.returncode}")
            logger.debug(
                f"Find command stdout: {process.stdout[:200] if process.stdout else ''}"
            )
            logger.debug(
                f"Find command stderr: {process.stderr[:200] if process.stderr else ''}"
            )

            # Check if we have results
            if process.returncode == 0:
                result = process.stdout.strip()
                if not result:
                    summary = "No matching files found"
                    return CommandResult(
                        content="No matching files found.", success=True, summary=summary
                    )

                # Create a summary of the operation
                file_count = len(result.splitlines())
                search_path_display = os.path.basename(search_path) or search_path
                pattern_info = f" matching '{name_pattern}'" if name_pattern else ""
                type_info = ""
                if file_type:
                    type_info = (
                        " (directories only)" if file_type == "d" else " (files only)"
                    )

                summary = f"Found {file_count} items in {search_path_display}{pattern_info}{type_info}"
                return CommandResult(content=result, success=True, summary=summary)
            else:
                # Error occurred
                error_msg = f"Find failed: {process.stderr}"
                logger.error(
                    f"Find command failed with return code {process.returncode}: {process.stderr}"
                )
                return CommandResult(success=False, content=error_msg)

        except Exception as e:
            error_msg = f"Error executing find: {str(e)}"
            logger.error(f"Error executing find command: {str(e)}")
            return CommandResult(success=False, content=error_msg)
