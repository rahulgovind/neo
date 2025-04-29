"""
File text search command implementation.

This module provides the FileTextSearch class for searching content in files.
"""

import os
import logging
import textwrap
import argparse
import shlex
from dataclasses import dataclass
from typing import Dict, Any, Optional, List

from src.neo.commands.base import Command
from src.neo.exceptions import FatalError
from src.neo.core.messages import CommandResult, CommandOutput
from src.neo.session import Session
from src.utils.subprocess import run_shell_command

# Configure logging
logger = logging.getLogger(__name__)


@dataclass
class FileTextSearchArgs:
    """Structured arguments for file_text_search command."""
    pattern: str
    path: str
    file_patterns: Optional[List[str]] = None
    ignore_case: bool = False
    num_context_lines: int = 0


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
            Use the `file_text_search` command to search for file contents.
            
            Usage: ▶file_text_search PATTERN PATH [--file-pattern <pattern>] [--ignore-case] [--num-context-lines <lines>]■
            
            - PATTERN (required): Regex pattern to look for in files
            - PATH (required): Path to search in, relative to workspace
            - file-pattern: File pattern to limit search (e.g., '*.py'). Multiple patterns can be specified. Files can be excluded based on pattern by prefixing pattern with '!' (e.g., '!*.test.py')
            - ignore-case: Perform case-insensitive matching
            - num-context-lines: Number of context lines to show around each match
            
            Output includes filenames, line numbers, and matching content.
            
            Examples:

            ▶file_text_search "import" src --file-pattern "*.py"■
            ✅src/core/command.py:8:import logging
            src/core/command.py:9:import textwrap
            src/core/command.py:10:from abc import ABC, abstractmethod■
            
            ▶file_text_search "function" . --ignore-case --num-context-lines 2■
            ✅src/utils/files.py:24:  
            src/utils/files.py:25:def read_function(file_path):
            src/utils/files.py:26:    (Read file contents)
            src/utils/files.py:27:    
            --
            src/utils/files.py:41:  
            src/utils/files.py:42:# Helper function to process files
            src/utils/files.py:43:def _process_content(content)■
            
            ▶file_text_search "class" ./src/core --file-pattern "*.py" --file-pattern "!*test*.py"■
            ✅src/core/command.py:15:class CommandParameter:
            src/core/command.py:65:class CommandTemplate:
            src/core/model.py:24:class Model:■
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
        # Allow multiple file patterns to be specified
        parser.add_argument("--file-pattern", action="append", dest="file_patterns", 
                           help="File pattern to limit search (e.g., '*.py'). Can be specified multiple times. "
                                "Prefix with '!' to exclude files matching the pattern.")
        parser.add_argument("--ignore-case", action="store_true", help="Perform case-insensitive matching")
        
        parser.add_argument("--num-context-lines", type=int, default=0, help="Number of context lines to show around each match")

        # Split statement into parts using shlex for proper handling of quoted arguments
        args = shlex.split(statement)
        
        # Parse arguments
        parsed_args = parser.parse_args(args)
        return FileTextSearchArgs(
            pattern=parsed_args.pattern,
            path=parsed_args.path,
            file_patterns=parsed_args.file_patterns,
            ignore_case=parsed_args.ignore_case,
            num_context_lines=parsed_args.num_context_lines
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
        grep_cmd = ["grep", "-r", "-n", "--color=never"]

        # Add case-insensitive flag if requested
        if args.ignore_case:
            logger.debug("Adding case-insensitive flag (-i) to grep command")
            grep_cmd.append("-i")

        # Add context lines if specified
        if args.num_context_lines > 0:
            logger.debug(f"Adding context lines (-C {args.num_context_lines}) to grep command")
            grep_cmd.extend(["-C", str(args.num_context_lines)])

        # Add the pattern and search path
        grep_cmd.extend([pattern, search_path])

        # Process file patterns (including and excluding)
        include_patterns = []
        exclude_patterns = []
        
        if args.file_patterns:
            for pattern in args.file_patterns:
                if pattern.startswith('!'):
                    exclude_patterns.append(pattern[1:])
                else:
                    include_patterns.append(pattern)
                    
        # Add include file patterns if provided
        for include_pattern in include_patterns:
            logger.debug(f"Adding include file pattern (--include {include_pattern}) to grep command")
            grep_cmd.extend(["--include", include_pattern])
            
        # Add exclude file patterns if provided
        for exclude_pattern in exclude_patterns:
            logger.debug(f"Adding exclude file pattern (--exclude {exclude_pattern}) to grep command")
            grep_cmd.extend(["--exclude", exclude_pattern])

        try:
            # Execute grep command using the utils function
            process = run_shell_command(
                grep_cmd,
                cwd=workspace,  # Ensure grep runs in the workspace directory
                check=False,    # Don't raise exception if grep returns non-zero (e.g., no matches)
            )

            # Check if we have results
            if process.returncode == 0:
                result = process.stdout.strip()
                # Create a summary of the search
                match_count = len(result.splitlines())
                search_path_display = os.path.basename(search_path) or search_path
                
                # Create formatted pattern info for summary
                file_pattern_info = ""
                if include_patterns:
                    file_pattern_info = f" in files matching {', '.join(include_patterns)}"
                if exclude_patterns:
                    file_pattern_info += f" excluding {', '.join(exclude_patterns)}"
                    
                case_info = " (case-insensitive)" if args.ignore_case else ""
                summary = f"Found {match_count} matches for '{pattern}' in {search_path_display}{file_pattern_info}{case_info}"
                
                # Create message for CommandOutput
                command_msg = f"Search for text '{pattern}' in {search_path_display}"
                if include_patterns:
                    command_msg += f" in files matching {', '.join(include_patterns)}"
                if args.ignore_case:
                    command_msg += " (case-insensitive)"
                
                # Create CommandOutput
                command_output = CommandOutput(
                    name=self.name,
                    message=command_msg
                )
                
                return CommandResult(
                    content=result, 
                    success=True, 
                    command_output=command_output
                )
            elif process.returncode == 1:
                # No matches found - success but empty result
                return CommandResult(
                    content="No matches found.", success=True
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
