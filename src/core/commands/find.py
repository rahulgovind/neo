"""
NeoFind command implementation.

This module provides the NeoFindCommand class for finding files based on name and type.
"""

import os
import logging
import subprocess
import textwrap
from typing import Dict, Any, Optional, List

from src.core.command import Command, CommandTemplate, CommandParameter
from src.core.messages import CommandResult
from src.core.context import Context

# Configure logging
logger = logging.getLogger(__name__)


class NeoFindCommand(Command):
    """
    Command for finding files and directories based on name and type using neofind.

    Features:
    - Delegates to the find command for efficient file searching
    - Supports filtering by name pattern
    - Supports filtering by file type (file or directory)
    - Uses the workspace from the Context
    """

    def template(self) -> CommandTemplate:
        """
        Returns the command template with parameter definitions and documentation.
        """
        return CommandTemplate(
            name="neofind",
            description=textwrap.dedent(
                """
                Find files and directories matching the specified criteria.
                
                The find command searches for files and directories in PATH based on name patterns
                and file type filters.
                
                PATH is a directory to start searching from (relative to workspace).
                """
            ),
            examples=textwrap.dedent(
                """
                ▶find src --name "*.py"■
                ✅src/core/command.py
                src/core/commands/grep.py
                src/utils/files.py■
                
                ▶find . --type f --name "README*"■
                ✅./README.md
                ./docs/README.txt■
                
                ▶find /tmp --type d■
                ✅/tmp/cache
                /tmp/logs
                /tmp/uploads■
                """
            ),
            parameters=[
                CommandParameter(
                    name="path",
                    description="Path to search in (relative to workspace).",
                    required=True,
                    is_positional=True,
                ),
                CommandParameter(
                    name="name",
                    description="File name pattern to search for (e.g., '*.py').",
                    required=False,
                    default=None,
                    is_flag=True,
                    long_flag="name",
                    short_flag="n",
                ),
                CommandParameter(
                    name="type",
                    description="File type to search for ('f' for files, 'd' for directories).",
                    required=False,
                    default=None,
                    is_flag=True,
                    long_flag="type",
                    short_flag="t",
                ),
            ],
            requires_data=False,
        )

    def process(self, ctx, args: Dict[str, Any], data: Optional[str] = None) -> CommandResult:
        """
        Process the command with the parsed arguments and optional data.

        Args:
            ctx: Application context
            args: Dictionary of parameter names to their values
            data: Optional data string (not used)

        Returns:
            CommandResult with find command results and summary
        """
        # Get the workspace from the context
        workspace = ctx.workspace

        path = args.get("path")
        if not path:
            logger.error("Path not provided to find command")
            raise RuntimeError("Path argument is required")

        # Normalize the path to be relative to the workspace
        if not os.path.isabs(path):
            search_path = os.path.join(workspace, path)
        else:
            # If absolute path is provided, ensure it's within the workspace
            if not path.startswith(workspace):
                raise RuntimeError(f"Path must be within the workspace: {workspace}")
            search_path = path

        # Build the find command
        find_cmd = ["find", search_path]

        # Add type filter if provided
        file_type = args.get("type")
        if file_type:
            if file_type not in ["f", "d"]:
                raise RuntimeError("Type must be 'f' for files or 'd' for directories")
            logger.debug(f"Adding type filter (-type {file_type}) to find command")
            find_cmd.extend(["-type", file_type])

        # Add name pattern if provided
        name_pattern = args.get("name")
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
                    return CommandResult(result="No matching files found.", success=True, summary=summary)
                
                # Create a summary of the operation
                file_count = len(result.splitlines())
                search_path_display = os.path.basename(search_path) or search_path
                pattern_info = f" matching '{name_pattern}'" if name_pattern else ""
                type_info = ""
                if file_type:
                    type_info = " (directories only)" if file_type == "d" else " (files only)"
                
                summary = f"Found {file_count} items in {search_path_display}{pattern_info}{type_info}"
                return CommandResult(result=result, success=True, summary=summary)
            else:
                # Error occurred
                error_msg = f"Find failed: {process.stderr}"
                logger.error(
                    f"Find command failed with return code {process.returncode}: {process.stderr}"
                )
                return CommandResult(success=False, error=error_msg)

        except Exception as e:
            error_msg = f"Error executing find: {str(e)}"
            logger.error(f"Error executing find command: {str(e)}")
            return CommandResult(success=False, error=error_msg)
