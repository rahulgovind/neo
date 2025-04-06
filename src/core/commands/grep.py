"""
NeoGrep command implementation.

This module provides the NeoGrepCommand class for searching content in files.
"""

import os
import logging
import subprocess
import textwrap
from typing import Dict, Any, Optional, List

from src.core.command import Command, CommandTemplate, CommandParameter
from src.core.exceptions import FatalError
from src.core.messages import CommandResult
from src.core.context import Context

# Configure logging
logger = logging.getLogger(__name__)


class NeoGrepCommand(Command):
    """
    Command for searching content in files using neogrep.

    Features:
    - Delegates to the grep command for efficient searching
    - Supports case-sensitive and case-insensitive search
    - Allows filtering by file pattern
    - Uses the workspace from the Context
    """

    def template(self) -> CommandTemplate:
        """
        Returns the command template with parameter definitions and documentation.
        """
        return CommandTemplate(
            name="neogrep",
            description=textwrap.dedent(
                """
                Search for a pattern in files or directories.
                
                The grep command searches for PATTERN in the files at PATH and prints matching lines.
                
                PATTERN is a search string to match against file contents.
                PATH is a file, directory, or glob pattern to search within.
                """
            ),
            examples=textwrap.dedent(
                """
                ▶grep --file-pattern "*.py" "import" src■
                ✅src/core/command.py:8:import logging
                src/core/command.py:9:import textwrap
                src/core/command.py:10:from abc import ABC, abstractmethod■
                
                ▶grep -i --context 2 "function" .■
                ✅src/utils/files.py:24:  
                src/utils/files.py:25:def read_function(file_path):
                src/utils/files.py:26:    (Read file contents)
                src/utils/files.py:27:    
                --
                src/utils/files.py:41:  
                src/utils/files.py:42:# Helper function to process files
                src/utils/files.py:43:def _process_content(content)■
                
                ▶grep -f "*.py" "class" ./src/core■
                ✅src/core/command.py:15:class CommandParameter:
                src/core/command.py:65:class CommandTemplate:
                src/core/model.py:24:class Model:■
                """
            ),
            parameters=[
                CommandParameter(
                    name="pattern",
                    description="Search pattern to look for in files.",
                    required=True,
                    is_positional=True,
                ),
                CommandParameter(
                    name="path",
                    description="Path to search in (relative to workspace).",
                    required=True,
                    is_positional=True,
                ),
                CommandParameter(
                    name="file_pattern",
                    description="File pattern to limit search (e.g., '*.py').",
                    required=False,
                    default=None,
                    is_flag=True,
                    long_flag="file-pattern",
                    short_flag="f",
                ),
                CommandParameter(
                    name="ignore_case",
                    description="Perform case-insensitive matching.",
                    required=False,
                    default=False,
                    is_flag=True,
                    long_flag="ignore-case",
                    short_flag="i",
                ),
                CommandParameter(
                    name="context",
                    description="Number of context lines to show around each match.",
                    required=False,
                    default=7,
                    is_flag=True,
                    long_flag="context",
                    short_flag="C",
                ),
            ],
            requires_data=False,
        )

    def process(self, ctx, args: Dict[str, Any], data: Optional[str] = None) -> str:
        """
        Process the command with the parsed arguments and optional data.

        Args:
            ctx: Application context
            args: Dictionary of parameter names to their values
            data: Optional data string (not used)

        Returns:
            Search results from grep, or error message
        """
        # Get the workspace from the context
        workspace = ctx.workspace

        pattern = args.get("pattern")
        if not pattern:
            logger.error("Pattern not provided to grep command")
            raise FatalError("Pattern argument is required")

        path = args.get("path")
        if not path:
            logger.error("Path not provided to grep command")
            raise FatalError("Path argument is required")

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
        logger.debug(f"ignore_case parameter value: {args.get('ignore_case')}")
        if args.get("ignore_case", False):
            logger.debug("Adding case-insensitive flag (-i) to grep command")
            grep_cmd.append("-i")

        # Add context lines if specified
        try:
            context_lines = int(args.get("context", 0))
            logger.debug(f"context parameter value: {context_lines}")
            if context_lines > 0:
                logger.debug(
                    f"Adding context lines (-C {context_lines}) to grep command"
                )
                grep_cmd.extend(["-C", str(context_lines)])
        except (ValueError, TypeError) as e:
            logger.error(
                f"Invalid context value: {args.get('context')}, error: {str(e)}"
            )
            raise FatalError(f"Context must be a valid integer: {str(e)}")

        # Add the pattern and search path
        grep_cmd.extend([pattern, search_path])

        # Add file pattern if provided
        file_pattern = args.get("file_pattern")
        logger.debug(f"file_pattern parameter value: {file_pattern}")
        if file_pattern:
            logger.debug(
                f"Adding file pattern (--include {file_pattern}) to grep command"
            )
            grep_cmd.extend(["--include", file_pattern])

        try:
            # Execute grep command
            logger.debug(f"Executing grep command: {' '.join(grep_cmd)}")
            process = subprocess.run(
                grep_cmd,
                capture_output=True,
                text=True,
                check=False,  # Don't raise exception if grep returns non-zero (e.g., no matches)
                cwd=workspace,  # Ensure grep runs in the workspace directory
            )
            logger.debug(f"Grep command return code: {process.returncode}")
            logger.debug(
                f"Grep command stdout: {process.stdout[:200] if process.stdout else ''}"
            )
            logger.debug(
                f"Grep command stderr: {process.stderr[:200] if process.stderr else ''}"
            )

            # Check if we have results
            if process.returncode == 0:
                return process.stdout.strip()
            elif process.returncode == 1:
                return "No matches found."
            else:
                # Other error occurred
                logger.error(
                    f"Grep command failed with return code {process.returncode}: {process.stderr}"
                )
                raise FatalError(f"Search failed: {process.stderr}")
        except Exception as e:
            logger.error(f"Error executing grep command: {str(e)}")
            raise FatalError(f"Command execution failed: {str(e)}")
