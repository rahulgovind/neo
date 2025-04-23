"""
File text search command implementation.

This module provides the FileTextSearch class for searching content in files.
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
from src.neo.exceptions import FatalError
from src.neo.core.messages import CommandResult
from src.neo.session import Session

# Configure logging
logger = logging.getLogger(__name__)


@dataclass
class FileTextSearchArgs:
    """Structured arguments for file_text_search command."""
    pattern: str
    path: str
    file_pattern: Optional[str] = None
    ignore_case: bool = False
    context: int = 0


class FileTextSearch(Command):
    """
    Command for searching content in files.

    Features:
    - Delegates to the grep command for efficient searching
    - Supports case-sensitive and case-insensitive search
    - Allows filtering by file pattern
    - Uses the workspace from the Session
    - Provides context lines around matches
    """

    @property
    def name(self) -> str:
        """Return the command name."""
        return "file_text_search"

    def description(self) -> str:
        """Returns a short description of the command."""
        return "Search for text patterns in files."

    def help(self) -> str:
        """Returns detailed help for the command."""
        return textwrap.dedent(
            """
            ## Description
            Search for a pattern in files or directories.
            
            The file_text_search command searches for PATTERN in the files at PATH and prints matching lines.
            
            PATTERN is a search string to match against file contents.
            PATH is a file, directory, or glob pattern to search within.
            
            ## Usage
            ```
            ▶file_text_search PATTERN PATH [OPTIONS]■
            ```
            
            ## Parameters
            - `PATTERN`: Search pattern to look for in files (required)
            - `PATH`: Path to search in, relative to workspace (required)
            - `--file-pattern`, `-f`: File pattern to limit search (e.g., '*.py')
            - `--ignore-case`, `-i`: Perform case-insensitive matching
            - `--context`, `-C`: Number of context lines to show around each match
            
            ## Examples
            ```
            ▶file_text_search "import" src --file-pattern "*.py"■
            ✅src/core/command.py:8:import logging
            src/core/command.py:9:import textwrap
            src/core/command.py:10:from abc import ABC, abstractmethod■
            
            ▶file_text_search "function" . -i --context 2■
            ✅src/utils/files.py:24:  
            src/utils/files.py:25:def read_function(file_path):
            src/utils/files.py:26:    (Read file contents)
            src/utils/files.py:27:    
            --
            src/utils/files.py:41:  
            src/utils/files.py:42:# Helper function to process files
            src/utils/files.py:43:def _process_content(content)■
            
            ▶file_text_search "class" ./src/core -f "*.py"■
            ✅src/core/command.py:15:class CommandParameter:
            src/core/command.py:65:class CommandTemplate:
            src/core/model.py:24:class Model:■
            ```
            """
        )

    def _parse_statement(self, statement: str, data: Optional[str] = None) -> FileTextSearchArgs:
        """Parse the command statement using argparse."""
        # Validate that data parameter is not set
        if data:
            raise ValueError("The file_text_search command does not accept data input")
            
        # Create parser for file_text_search command
        parser = argparse.ArgumentParser(prog="file_text_search", exit_on_error=False)
        
        # Add arguments
        parser.add_argument("pattern", help="Search pattern to look for in files")
        parser.add_argument("path", help="Path to search in (relative to workspace)")
        # TODO: Remove short flags. Only keep long paths.
        # TODO: Allow multiple file patterns to be specified. This is a list.
        # TODO: Allow exclusion patterns i.e. !*.py excludes files that end with .py.
        parser.add_argument("-f", "--file-pattern", help="File pattern to limit search (e.g., '*.py')")
        parser.add_argument("-i", "--ignore-case", action="store_true", help="Perform case-insensitive matching")
        
        parser.add_argument("-C", "--context", type=int, default=0, help="Number of context lines to show around each match")

        # Split statement into parts using shlex for proper handling of quoted arguments
        args = shlex.split(statement)
        
        # Parse arguments
        parsed_args = parser.parse_args(args)
        return FileTextSearchArgs(
            pattern=parsed_args.pattern,
            path=parsed_args.path,
            file_pattern=parsed_args.file_pattern,
            ignore_case=parsed_args.ignore_case,
            context=parsed_args.context
        )
        
    def validate(self, session, statement: str, data: Optional[str] = None) -> None:
        """Validate the file_text_search command statement."""
        # The _parse_statement method will raise appropriate exceptions
        # if validation fails, so we just need to call it here
        self._parse_statement(statement, data)

    def execute(
        self, session: Session, statement: str, data: Optional[str] = None
    ) -> CommandResult:
        """
        Process the command with the parsed arguments and optional data.

        Args:
            session: Session object with shell and workspace
            statement: Command statement string
            data: Optional data string (not used)

        Returns:
            CommandResult with search results and summary
        """
        # Parse the command statement
        args = self._parse_statement(statement, data)
        
        # Get the workspace from the session
        workspace = session.workspace

        pattern = args.pattern
        path = args.path

        # Normalize the path to be relative to the workspace
        if not os.path.isabs(path):
            search_path = os.path.join(workspace, path)
        else:
            # If absolute path is provided, ensure it's within the workspace
            if not path.startswith(workspace):
                raise FatalError(f"Path must be within the workspace: {workspace}")
            search_path = path

        # Build the grep command
        grep_cmd = ["grep", "-r", "--color=never"]

        # Add case-insensitive flag if requested
        if args.ignore_case:
            logger.debug("Adding case-insensitive flag (-i) to grep command")
            grep_cmd.append("-i")

        # Add context lines if specified
        if args.context > 0:
            logger.debug(f"Adding context lines (-C {args.context}) to grep command")
            grep_cmd.extend(["-C", str(args.context)])

        # Add the pattern and search path
        grep_cmd.extend([pattern, search_path])

        # Add file pattern if provided
        if args.file_pattern:
            logger.debug(f"Adding file pattern (--include {args.file_pattern}) to grep command")
            grep_cmd.extend(["--include", args.file_pattern])

        try:
            # Execute grep command
            logger.debug(f"Executing grep command: {' '.join(grep_cmd)}")
            # TODO: Consolidate logic within a "run_shell_command" function in a utils/subprocess.py file.
            process = subprocess.run(
                grep_cmd,
                capture_output=True,
                text=True,
                check=False,  # Don't raise exception if grep returns non-zero (e.g., no matches)
                cwd=workspace,  # Ensure grep runs in the workspace directory
            )
            logger.debug(f"Grep command return code: {process.returncode}")

            # Check if we have results
            if process.returncode == 0:
                result = process.stdout.strip()
                # Create a summary of the search
                match_count = len(result.splitlines())
                search_path_display = os.path.basename(search_path) or search_path
                file_pattern_info = f" in {args.file_pattern} files" if args.file_pattern else ""
                case_info = " (case-insensitive)" if args.ignore_case else ""
                summary = f"Found {match_count} matches for '{pattern}' in {search_path_display}{file_pattern_info}{case_info}"
                return CommandResult(content=result, success=True, summary=summary)
            elif process.returncode == 1:
                summary = f"No matches found for '{pattern}'"
                return CommandResult(
                    content="No matches found.", success=True, summary=summary
                )
            else:
                # Other error occurred
                error_msg = f"Search failed: {process.stderr}"
                logger.error(
                    f"Grep command failed with return code {process.returncode}: {process.stderr}"
                )
                return CommandResult(success=False, content=error_msg)
        except Exception as e:
            error_msg = f"Command execution failed: {str(e)}"
            logger.error(f"Error executing search command: {str(e)}")
            return CommandResult(success=False, content=error_msg)
