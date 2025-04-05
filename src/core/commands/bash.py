"""
Bash command implementation.

This module provides the BashCommand class for executing shell commands.
"""

import os
import logging
import subprocess
import textwrap
from typing import Dict, Any, Optional, List

from src.core.command import Command, CommandTemplate, CommandParameter
from src.core.context import Context

# Configure logging
logger = logging.getLogger(__name__)


class BashCommand(Command):
    """
    Command for executing shell commands.
    
    Features:
    - Runs standard shell commands
    - Captures and returns command output
    - Uses the workspace from the Context as the working directory
    """
    
    def template(self) -> CommandTemplate:
        """
        Returns the command template with parameter definitions and documentation.
        """
        return CommandTemplate(
            name="bash",
            description=textwrap.dedent("""
                Execute a shell command.
                
                The bash command executes the shell command specified in the data section after the pipe symbol.
                The command is executed in the current workspace directory.
                
                NOTE: This command should only be used when more specialized commands cannot be used.
                Always prefer using dedicated commands like read_file, write_file, grep, or find when possible.
            """),
            examples=textwrap.dedent("""
                ▶bash｜ls -la■
                ✅total 24
                drwxr-xr-x  5 user  staff  160 Apr  4 10:00 .
                drwxr-xr-x  8 user  staff  256 Apr  4 09:58 ..
                -rw-r--r--  1 user  staff   78 Apr  4 10:00 file1.txt
                -rw-r--r--  1 user  staff  102 Apr  4 10:00 file2.py■
                
                ▶bash｜cat file1.txt■
                ✅This is the content of file1.txt■
                
                ▶bash｜echo "Hello, world!"■
                ✅Hello, world!■
            """),
            requires_data=True,
            parameters=[]
        )
    
    def process(self, ctx, args: Dict[str, Any], data: Optional[str] = None) -> str:
        """
        Process the command with the parsed arguments and data.
        
        Args:
            ctx: Application context
            args: Dictionary of parameter names to their values
            data: The shell command to execute as a string
            
        Returns:
            Output from the shell command
        """
        # Get the workspace from the context
        workspace = ctx.workspace
        
        # Get the command from the data parameter
        command = data.strip() if data else ""
        if not command:
            logger.error("Empty command provided to bash command")
            raise RuntimeError("Command cannot be empty")
        
        logger.info(f"Executing shell command: {command}")
        
        try:
            # Execute the command in a shell and capture the output
            result = subprocess.run(
                command,
                shell=True,
                cwd=workspace,
                capture_output=True,
                text=True,
                check=False
            )
            
            # Log command execution details
            logger.debug(f"Bash command exit code: {result.returncode}")
            logger.debug(f"Bash command stdout: {result.stdout[:200] if result.stdout else ''}")
            logger.debug(f"Bash command stderr: {result.stderr[:200] if result.stderr else ''}")
            
            # If there's an error, include the stderr in the output
            if result.returncode != 0:
                error_msg = result.stderr.strip() if result.stderr else f"Command exited with code {result.returncode}"
                logger.error(f"Bash command failed: {error_msg}")
                raise RuntimeError(f"Command failed: {error_msg}")
            
            # Return the stdout from the command
            return result.stdout.strip()
            
        except Exception as e:
            logger.error(f"Error executing bash command: {str(e)}")
            raise RuntimeError(f"Error executing command: {str(e)}")
