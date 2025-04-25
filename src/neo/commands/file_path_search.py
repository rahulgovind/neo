"""
File path search command implementation.

This module provides the FilePathSearch class for finding files based on name and type.
"""

import os
import logging
import textwrap
import argparse
import shlex
from dataclasses import dataclass
from typing import Dict, Any, Optional, List

from src.neo.commands.base import Command
from src.neo.session import Session
from src.neo.core.messages import CommandResult
from src.neo.exceptions import FatalError
from src.utils.subprocess import run_shell_command

# Configure logging
logger = logging.getLogger(__name__)


@dataclass
class FilePathSearchArgs:
    """Structured arguments for file_path_search command."""
    path: str
    file_patterns: Optional[List[str]] = None  # Changed from name to file_patterns
    type: Optional[str] = None
    content_pattern: Optional[str] = None  # Added content_pattern


class FilePathSearch(Command):
    """Command for finding files and directories based on name and type criteria.

    Features:
    - Delegates to the find command for efficient file searching
    - Supports filtering by file pattern (including multiple patterns and exclusions)
    - Supports filtering by file type (file or directory)
    - Supports searching for content within files
    - Uses the workspace from the Session
    """

    @property
    def name(self) -> str:
        """Return the command name."""
        return "file_path_search"

    def description(self) -> str:
        """Returns a short description of the command."""
        return "Find files and directories matching specified criteria."

    def _parse_statement(self, statement: str, data: Optional[str] = None) -> FilePathSearchArgs:
        """Parse the command statement using argparse."""
        # Validate that data parameter is not set
        if data:
            raise ValueError("The file_path_search command does not accept data input")
            
        # Create parser for file_path_search command
        parser = argparse.ArgumentParser(prog="file_path_search", exit_on_error=False)
        
        # Add arguments
        parser.add_argument("path", help="Path to search in (relative to workspace)")
        
        # Updated to use --file-pattern instead of --name, allowing multiple patterns
        parser.add_argument("--file-pattern", action="append", dest="file_patterns", 
                           help="File pattern to match (e.g., '*.py'). Can be specified multiple times. "
                                "Prefix with '!' to exclude files matching the pattern.")
                                
        parser.add_argument("--type", choices=["f", "d"], 
                           help="File type to search for ('f' for files, 'd' for directories)")
                           
        # Added content pattern for searching within files                    
        parser.add_argument("--content", dest="content_pattern", 
                           help="Pattern to search for within files")
        
        # Split statement into parts using shlex for proper handling of quoted arguments
        args = shlex.split(statement)
        
        # Parse arguments
        parsed_args = parser.parse_args(args)
        return FilePathSearchArgs(
            path=parsed_args.path,
            file_patterns=parsed_args.file_patterns,
            type=parsed_args.type,
            content_pattern=parsed_args.content_pattern
        )
        
    def validate(self, session, statement: str, data: Optional[str] = None) -> None:
        """Validate the file_path_search command statement."""
        # The _parse_statement method will raise appropriate exceptions
        # if validation fails, so we just need to call it here
        self._parse_statement(statement, data)
    
    def help(self) -> str:
        """Returns detailed help for the command."""
        return textwrap.dedent(
            """
            Use the `file_path_search` command to search for files and directories.
            
            Usage: ▶file_path_search PATH [--file-pattern <pattern>] [--type <type>] [--content <pattern>]■
            
            - PATH: Path to search in, relative to workspace (required)
            - file-pattern: File pattern to match (e.g., '*.py'). Multiple patterns can be specified. Files can be excluded by prefixing with '!' (e.g., '!*.test.py')
            - type: File type to search for ('f' for files, 'd' for directories). By default both are included.
            - content: Regex pattern to filter files based on their content.
            
            Examples:
            
            ▶file_path_search src --file-pattern "*"■
            ✅src
            src/core
            src/core/command.py
            src/core/commands/grep.py
            src/utils
            src/utils/__pycache__/files.cpython-313.pyc
            src/utils/files.py■
            
            ▶file_path_search src --type f --file-pattern "*.py"■
            ✅src/core/command.py
            src/core/commands/grep.py
            src/utils/files.py■
            
            ▶file_path_search src --type f --file-pattern "*.py"■
            ✅src/core/command.py
            src/core/commands/grep.py
            src/utils/files.py■
            
            ▶file_path_search src --content "class File"■
            ✅src/utils/files.py■
            """
        )

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

        # Process file patterns
        include_patterns = []
        exclude_patterns = []
        
        if args.file_patterns:
            for pattern in args.file_patterns:
                if pattern.startswith('!'):
                    exclude_patterns.append(pattern[1:])
                else:
                    include_patterns.append(pattern)

        # Build pattern expressions for find
        if include_patterns or exclude_patterns:
            find_cmd.append("(")
            
            # Add include patterns
            for i, pattern in enumerate(include_patterns):
                if i > 0:
                    find_cmd.append("-o")
                find_cmd.extend(["-name", pattern])
            
            # Add exclude patterns if any exist
            if exclude_patterns:
                if include_patterns:
                    find_cmd.append(")")
                    find_cmd.append("!")
                    find_cmd.append("(")
                
                for i, pattern in enumerate(exclude_patterns):
                    if i > 0:
                        find_cmd.append("-o")
                    find_cmd.extend(["-name", pattern])
            
            find_cmd.append(")")

        try:
            # Execute find command
            process = run_shell_command(
                find_cmd,
                cwd=workspace,  # Ensure find runs in the workspace directory
                check=False
            )

            # Check if we have results and process them
            if process.returncode == 0:
                result_files = process.stdout.strip().splitlines() if process.stdout else []
                
                # If there's a content pattern, filter results by searching within files
                if args.content_pattern and result_files:
                    filtered_files = []
                    
                    for file_path in result_files:
                        # Skip directories for content search
                        if os.path.isdir(file_path):
                            continue
                            
                        try:
                            # Use grep to search for content within the file
                            grep_process = run_shell_command(
                                ["grep", "-l", args.content_pattern, file_path],
                                cwd=workspace,
                                check=False
                            )
                            
                            # If grep found a match, add the file to the filtered list
                            if grep_process.returncode == 0 and grep_process.stdout.strip():
                                filtered_files.append(file_path)
                        except Exception as e:
                            logger.warning(f"Error searching content in {file_path}: {str(e)}")
                    
                    # Replace the original result list with the filtered list
                    result_files = filtered_files
                    result = "\n".join(result_files)
                else:
                    result = process.stdout.strip()
                
                # Create a summary of the operation
                if not result_files:
                    summary = "No matching files found"
                    return CommandResult(
                        content="No matching files found.", success=True, summary=summary
                    )
                
                file_count = len(result_files)
                search_path_display = os.path.basename(search_path) or search_path
                
                # Create formatted pattern info for summary
                pattern_info = ""
                if include_patterns:
                    pattern_info = f" matching {', '.join(include_patterns)}"
                if exclude_patterns:
                    pattern_info += f" excluding {', '.join(exclude_patterns)}"
                    
                # Type info
                type_info = ""
                if file_type:
                    type_info = f" (directories only)" if file_type == "d" else f" (files only)"
                
                # Content pattern info
                content_info = ""
                if args.content_pattern:
                    content_info = f" containing '{args.content_pattern}'"

                summary = f"Found {file_count} items in {search_path_display}{pattern_info}{type_info}{content_info}"
                return CommandResult(content=result, success=True)
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
