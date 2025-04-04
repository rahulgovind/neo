"""
Read file command implementation.

This module provides the ReadFileCommand class for reading file contents.
"""

import os
import logging
import textwrap
from typing import Dict, Any, Optional

from src.core.command import Command, CommandTemplate, CommandParameter
from src.core.exceptions import FatalError
from src.core.messages import CommandResult
from src.core.context import Context
from src.utils.files import read

# Configure logging
logger = logging.getLogger(__name__)


class ReadFileCommand(Command):
    """
    Command for reading file contents.
    
    Features:
    - Adds line numbers to make referencing specific lines easier
    - Handles common file reading errors gracefully
    - Uses the workspace from the Context
    """
    

    
    def template(self) -> CommandTemplate:
        """
        Returns the command template with parameter definitions and documentation.
        """
        return CommandTemplate(
            name="read_file",
            description=textwrap.dedent("""
                Read a file from the file system.
                
                By default, line numbers are not included in the output. Use --include-line-numbers to add line numbers.
                
                Example:
                ▶read_file path/to/file.py■
                ✅import os
                import sys
                
                print("Hello, World!")■
                
                ▶read_file path/to/file.py --include-line-numbers■
                ✅1 import os
                2 import sys
                3 
                4 print("Hello, World!")■
                
                ▶read_file config.json■
                ✅{
                    "debug": true,
                    "port": 8080
                }■
                
                ▶read_file nonexistent.py■
                ❌File not found: nonexistent.py■
            """),
            requires_data=False,
            parameters=[
                CommandParameter(
                    name="path",
                    description="Path to the file to read.",
                    required=True,
                    is_positional=True
                ),
                CommandParameter(
                    name="include_line_numbers",
                    description="Include line numbers in the output.",
                    required=False,
                    default=False,
                    is_flag=True,
                    long_flag="include-line-numbers"
                )
            ]
        )
    
    def process(self, ctx, args: Dict[str, Any], data: Optional[str] = None) -> str:
        """
        Process the command with the parsed arguments and optional data.
        
        Args:
            ctx: Application context
            args: Dictionary of parameter names to their values
            data: Optional data string (not used in this command)
            
        Returns:
            File contents with optional line numbers, or error message
        """
        # Get the workspace from the context
        workspace = ctx.workspace
        
        path = args.get("path")
        if not path:
            logger.error("Path not provided to read_file command")
            raise FatalError("Path argument is required")
        
        # Normalize the path to be relative to the workspace
        if not os.path.isabs(path):
            full_path = os.path.join(workspace, path)
        else:
            # If absolute path is provided, ensure it's within the workspace
            if not path.startswith(workspace):
                raise FatalError(f"Path must be within the workspace: {workspace}")
            full_path = path
        
        # Determine whether to include line numbers
        include_line_numbers = args.get("include_line_numbers", False)
        
        # Read the file content
        content = read(full_path, include_line_numbers=include_line_numbers)
        
        # Check for error conditions
        if content.startswith("File not found:") or \
           content.startswith("Path is not a file:") or \
           content.startswith("Error:"):
            raise FatalError(content)
            
        return content
