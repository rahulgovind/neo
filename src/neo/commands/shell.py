"""Implements the 'shell' commands for interacting with shell processes."""

import os
import logging
import shlex
import argparse
import time
from dataclasses import dataclass
from textwrap import dedent
from typing import Dict, Any, Optional, List

from src.neo.commands.base import Command, CommandTemplate, CommandParameter
from src.neo.core.messages import CommandResult
from src.neo.session import Session
from src.utils.shell_manager import ShellManager

# Configure logging
logger = logging.getLogger(__name__)


@dataclass
class ShellRunArgs:
    id: str = "default"
    exec_dir: str = ""
    command: str = ""


class ShellRunCommand(Command):

    @property
    def name(self) -> str:
        return "shell_run"

    def description(self) -> str:
        return "Execute commands in a shell."

    def help(self) -> str:
        return dedent(
            """\
            Use the `shell_run` command to run commands in a bash shell.
            
            This command will return the shell output. For commands that take longer than a few seconds, 
            the command will return the most recent shell output but keep the shell process running. 
            
            Usage: ▶shell_run [name] [exec_dir]｜Command to execute■

            - name (Optional): Unique identifier for this shell instance. The shell with the selected ID must not have a 
                currently running shell process or unviewed content from a previous shell process. 
                Use a new shellId to open a new shell. Defaults to `default`.
            - exec_dir (Optional): Absolute path to directory where command should be executed. Defaults to current workspace.
            
            Example:
            ▶shell_run custom-id /home/user｜echo "Hello, world!"■
            ✅Hello, world!■
            """
        )

    def _parse_statement(
        self, statement: str, data: Optional[str] = None
    ) -> ShellRunArgs:
        parser = argparse.ArgumentParser(prog="shell_run", add_help=False)
        parser.add_argument(
            "name",
            nargs="?",
            default="default",
            help="Unique identifier for this shell instance",
        )
        parser.add_argument(
            "exec_dir",
            nargs="?",
            default="",
            help="Directory where command should be executed",
        )

        # Parse statement if present, otherwise use defaults
        arg_list = shlex.split(statement) if statement else []
        parsed_args = parser.parse_args(arg_list)

        return ShellRunArgs(
            id=parsed_args.name,
            exec_dir=parsed_args.exec_dir,
            command=data if data else "",
        )

    def validate(self, session, statement: str, data: Optional[str] = None) -> None:
        # Check if command is provided
        if not data or not data.strip():
            logger.error("Empty command provided to shell run command")
            raise ValueError("Error: Empty command provided")
        
        # Parse statement for shell_id and exec_dir
        args = self._parse_statement(statement, data)

        # Default exec_dir to session workspace if not provided
        if not args.exec_dir and session and session.workspace:
            args.exec_dir = session.workspace

        # Validate directory exists if provided
        if args.exec_dir and not os.path.isdir(args.exec_dir):
            logger.error(f"Directory '{args.exec_dir}' does not exist")
            raise ValueError(f"Directory '{args.exec_dir}' does not exist")

    def execute(
        self, session, statement: str, data: Optional[str] = None
    ) -> CommandResult:
        # First run validation
        self.validate(session, statement, data)

        # Parse arguments
        args = self._parse_statement(statement, data)
        shell_id = args.id
        exec_dir = args.exec_dir
        command = args.command

        # Default exec_dir to session workspace if not provided
        if not exec_dir and session and session.workspace:
            exec_dir = session.workspace

        logger.info(f"Executing shell command with ID '{shell_id}': {command}")

        # Execute the command - passing session for logging
        cmd_status = ShellManager.execute_command(
            shell_id=shell_id, command=command, exec_dir=exec_dir, session=session
        )

        # Extract information from CommandStatus
        output = cmd_status.output
        exit_code = cmd_status.exit_code
        output_file = cmd_status.output_file
        is_truncated = cmd_status.is_truncated

        # Check for error patterns in the output that would indicate failure
        error_patterns = [
            "command not found",
            "No such file or directory",
            "not found",
            "nonexistent_command",
            "command_not_found",
            "syntax error",
            "invalid option",
        ]

        additional_output = ""

        if exit_code is None:
            additional_output += f"\n\nCommand is still running."

        # Check output for error patterns
        has_error_pattern = any(pattern in output.lower() for pattern in error_patterns)

        # Add note about output file if truncated
        if is_truncated and output_file:
            additional_output += (
                f"Only showing latest logs. Full output available in: {output_file}"
            )

        if additional_output:
            output += f"\n\n[{additional_output}]"

        # Set success based on the exit code
        # Unix/Bash convention: 0 means success, any other value indicates failure
        # Special case: exit code 124 is usually a timeout, which indicates the command
        # is still running and should be treated as success for long-running commands
        is_success = (exit_code == 0 or exit_code == 124) and not has_error_pattern

        if not is_success:
            return CommandResult(content=output, success=False)
        return CommandResult(content=output, success=True)


@dataclass
class ShellViewArgs:
    id: str


class ShellViewCommand(Command):
    @property
    def name(self) -> str:
        return "shell_view"

    def description(self) -> str:
        return "View the latest output from a shell process."

    def help(self) -> str:
        return dedent(
            """
            Use `shell_view` to view the latest output from a shell process.

            Usage: ▶shell_view [id]■

            - id (Required): ID of the shell to view.
            """
        )

    def _parse_statement(
        self, statement: str, data: Optional[str] = None
    ) -> ShellViewArgs:
        """Parse the command statement using shlex and argparse."""
        parser = argparse.ArgumentParser(prog="shell_view", add_help=False)
        parser.add_argument("id", help="Identifier of the shell instance to view")

        stmt = statement.strip()
        # Ensure statement is not empty
        if not stmt:
            raise ValueError("Shell ID is required")
        # Parse statement with shlex to handle quoted arguments
        arg_list = shlex.split(stmt)
        parsed_args = parser.parse_args(arg_list)
        return ShellViewArgs(id=parsed_args.id)

    def validate(self, session, statement: str, data: Optional[str] = None) -> None:
        """Validate the shell_view command."""
        # Parse and validate arguments
        self._parse_statement(statement, data)

    def execute(
        self, session, statement: str, data: Optional[str] = None
    ) -> CommandResult:
        # Parse arguments
        args = self._parse_statement(statement, data)
        shell_id = args.id

        # Use ShellManager to get the output from the shell
        cmd_status = ShellManager.view_output(shell_id, max_lines=100)  
        
        # Check if we could get the shell output
        if not cmd_status:
            return CommandResult(
                content=f"No shell found with ID '{shell_id}'", 
                success=False
            )

        # Extract information from CommandStatus
        output = cmd_status.output or "<No output available>"
        exit_code = cmd_status.exit_code
        output_file = cmd_status.output_file
        is_truncated = cmd_status.is_truncated

        # Add note about output file if truncated
        if is_truncated and output_file:
            output += f"\n\n[Output truncated. Full output available in: {output_file}]"

        # Return based on exit code
        if exit_code is not None and exit_code != 0:
            return CommandResult(content=output, success=False)

        return CommandResult(content=output, success=True)


@dataclass
class ShellWriteArgs:
    id: str
    press_enter: bool = True
    data: str = ""


class ShellWriteCommand(Command):
    """
    Command for writing input to an active shell process.
    """

    @property
    def name(self) -> str:
        return "shell_write"

    def description(self) -> str:
        return "Write input to an active shell process."

    def help(self) -> str:
        return """\
        Use `shell_write` to write input to an active shell process that needs user input.
        
        Usage: ▶shell_write [id] [--no-press-enter]｜Content to write■
        
        - id: Identifier of the shell instance to write to. Required.
        - no-press-enter: If provided, do not automatically press enter after writing the content.
        """

    def _parse_statement(
        self, statement: str, data: Optional[str] = None
    ) -> ShellWriteArgs:
        """Parse the command statement using shlex and argparse."""
        parser = argparse.ArgumentParser(prog="shell_write", add_help=False)
        parser.add_argument("id", help="Identifier of the shell instance to write to")
        parser.add_argument(
            "--no-press-enter",
            dest="no_press_enter",
            action="store_true",
            help="Do not press enter after sending the input",
        )

        # Parse statement with shlex to handle quoted arguments
        arg_list = shlex.split(statement)
        parsed_args = parser.parse_args(arg_list)
        return ShellWriteArgs(
            id=parsed_args.id,
            press_enter=not parsed_args.no_press_enter,
            data=data or "",
        )

    def validate(self, session, statement: str, data: Optional[str] = None) -> None:
        # Parse and validate arguments
        self._parse_statement(statement, data)

    def execute(
        self, session, statement: str, data: Optional[str] = None
    ) -> CommandResult:
        # Parse arguments
        args = self._parse_statement(statement, data)
        shell_id = args.id
        press_enter = args.press_enter
        content = args.data

        # Get shell info and validate it's active
        shell_info = ShellManager.get_process(shell_id)
        if not shell_info:
            return CommandResult(
                content=f"No shell found with ID '{shell_id}'", success=False
            )

        # Check if the process is still running
        process = shell_info.get("process")
        if not process or process.poll() is not None:
            return CommandResult(
                content=f"Shell process with ID '{shell_id}' has terminated",
                success=False,
            )

        # Write to the process
        success = ShellManager.write_to_process(
            shell_id=shell_id, content=content, press_enter=press_enter
        )

        if success:
            return CommandResult(
                content=f"Input sent to shell with ID '{shell_id}'", success=True
            )
        else:
            return CommandResult(content="Failed to send input to shell", success=False)


@dataclass
class ShellTerminateArgs:
    """Structured arguments for shell_terminate command."""

    id: str


class ShellTerminateCommand(Command):
    """
    Command for terminating a running shell process.
    """

    @property
    def name(self) -> str:
        return "shell_terminate"

    def description(self) -> str:
        return "Kill a running shell process."

    def help(self) -> str:
        return dedent(
            """
            Use `shell_terminate` to kill a running shell process.
            
            Usage: ▶shell_terminate [id]■
            
            - id: Identifier of the shell instance to kill. Required.
            """
        )

    def _parse_statement(
        self, statement: str, data: Optional[str] = None
    ) -> ShellTerminateArgs:
        # Parse and validate arguments
        parser = argparse.ArgumentParser(prog="shell_terminate", add_help=False)
        parser.add_argument("id", help="Identifier of the shell instance to terminate")

        # Parse statement with shlex to handle quoted arguments
        arg_list = shlex.split(statement)

        parsed_args = parser.parse_args(arg_list)
        return ShellTerminateArgs(id=parsed_args.id)

    def validate(self, session, statement: str, data: Optional[str] = None) -> None:
        # Parse and validate arguments
        self._parse_statement(statement, data)

    def execute(
        self, session, statement: str, data: Optional[str] = None
    ) -> CommandResult:
        # Parse arguments
        args = self._parse_statement(statement, data)
        shell_id = args.id

        # Terminate the process
        success = ShellManager.terminate_process(shell_id)

        if success:
            return CommandResult(
                content=f"Shell process with ID '{shell_id}' terminated", success=True
            )
        else:
            return CommandResult(
                content=f"Failed to terminate shell process with ID '{shell_id}'",
                success=False,
            )
