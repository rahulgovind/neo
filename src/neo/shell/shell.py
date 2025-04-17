"""
Shell module for command execution.

This module provides a Shell class that manages command registration and execution.
It acts as a central hub for executing commands by name.
"""

import logging
from dataclasses import dataclass
from typing import Dict, Any, List, Optional

from src.neo.core.messages import CommandResult, CommandCall
from src.neo.shell.command import Command
from src.neo.commands.read_file import ReadFileCommand
from src.neo.commands.write_file import WriteFileCommand
from src.neo.commands.update_file import UpdateFileCommand
from src.neo.commands.grep import NeoGrepCommand
from src.neo.commands.find import NeoFindCommand
from src.neo.commands.bash import BashCommand
from src.neo.core.constants import COMMAND_END
from src.neo.session import Session

# Configure logging
logger = logging.getLogger(__name__)

@dataclass
class ParsedCommand:
    """
    Represents a parsed command with name, parameters, and optional data.
    """

    name: str
    parameters: Dict[str, Any]
    data: Optional[str] = None

class Shell:
    """
    Shell for registering and executing commands.
    """

    def __init__(self, session: Session):
        self._commands: Dict[str, Command] = {}
        self._session = session

        # Register built-in commands
        self._register_builtin_commands()

    def register_command(self, command: Command) -> None:
        """
        Register a command with the shell.

        Raises:
            ValueError: If a command with the same name is already registered
        """
        cmd_name = command.template().name
        if cmd_name in self._commands:
            raise ValueError(f"Command '{cmd_name}' is already registered")

        self._commands[cmd_name] = command
        logger.debug(f"Registered command: {cmd_name}")

    def register_commands(self, commands: List[Command]) -> None:
        """
        Register multiple commands with the shell.

        Raises:
            ValueError: If any command has a name collision
        """
        for command in commands:
            self.register_command(command)

    def get_command(self, command_name: str) -> Command:
        """
        Get a registered command by name.

        Raises:
            ValueError: If the command is not registered
        """
        if command_name not in self._commands:
            raise ValueError(f"Command '{command_name}' is not registered")

        return self._commands[command_name]

    def list_commands(self) -> List[str]:
        """
        Get a list of all registered command names.
        """
        return list(self._commands.keys())

    def parse(self, command_input: str) -> ParsedCommand:
        """
        Parse a command input string in the format "command_name [args] [|data]"

        Raises:
            ValueError: If the command is not registered, not found, or parsing fails
        """

        # Split the input to get the command name
        # First check if the command starts with a pipe
        if "｜" in command_input:
            # If a pipe exists, take everything before it as the command part
            command_part = command_input.split("｜", 1)[0].strip()
        else:
            command_part = command_input

        parts = command_part.split()
        if not parts:
            raise ValueError("Empty command input")

        command_name = parts[0]

        # Check if command exists
        if command_name not in self._commands:
            raise ValueError(f"Command '{command_name}' is not registered")

        # Get the command and parse the input
        command = self.get_command(command_name)
        parameters, data = command.parse(command_input)

        # Return the parsed command
        return ParsedCommand(command_name, parameters, data)

    def validate(
        self, command_input: str
    ) -> CommandResult:
        """
        Validate a command with the given parameters and data.

        Args:
            command_input: Command input string to validate

        Returns:
            CommandResult object with success/failure status, result/error, and optional summary
        """
        try:
            parsed_cmd = self.parse(command_input)
            command = self.get_command(parsed_cmd.name)
            command.validate(self._session, parsed_cmd.parameters, parsed_cmd.data)
            return CommandResult(content="Command is valid", success=True)
        except Exception as e:
            return CommandResult(content=str(e), success=False, error=e)

    def execute(
        self, command_name: str, parameters: Dict[str, Any], data: Optional[str] = None
    ) -> CommandResult:
        """
        Execute a command with the given parameters and data.

        Raises:
            ValueError: If the command is not registered
        """
        command = self.get_command(command_name)
        return command.execute(self._session, parameters, data)

    def parse_and_execute(self, command_input: str) -> CommandResult:
        """
        Parse and execute a command from a command input string.

        Args:
            command_input: The command input string to parse and execute

        Returns:
            CommandResult object with the result of the command execution
        """
        logger.debug(f"Command input: {command_input}")
        try:
            parsed_cmd = self.parse(command_input)
        except Exception as e:
            return CommandResult(content=str(e), success=False, error=e)

        logger.debug(f"Executing command with parameters: {parsed_cmd.parameters}")
        result = self.execute(parsed_cmd.name, parsed_cmd.parameters, parsed_cmd.data)
        logger.debug(f"Command result success: {result.success}")
        logger.debug(f"Command result: {result.content}")

        return result

    def process_commands(self, commands: List[CommandCall]) -> List[CommandResult]:
        """
        Process a list of command calls and return the results.

        Args:
            commands: List of command calls to process

        Returns:
            List of CommandResult objects with the results of each command
        """
        assert (
            len(commands) > 0
        ), f"Expected at least one command call, got {len(commands)}"

        # Create a list to collect all command results
        result_blocks = []

        # Execute each command and collect the results
        for cmd_call in commands:
            try:
                if not cmd_call.content.endswith(COMMAND_END):
                    error_result = CommandResult(
                        content=None,
                        success=False,
                        error="Command call missing end marker",
                    )
                    result_blocks.append(error_result)
                    continue

                # Parse the command
                cmd_statement = cmd_call.content[1:-1]
                parsed_cmd = self.parse(cmd_statement)

                # Execute the command
                result = self.execute(
                    parsed_cmd.name, parsed_cmd.parameters, parsed_cmd.data
                )

                # Add the result to our collection
                result_blocks.append(result)

            except Exception as e:
                # Create an error result and add it to our collection
                error_result = CommandResult(content=str(e), success=False, error=e)
                result_blocks.append(error_result)

        return result_blocks

    def describe(self, command_name: str) -> str:
        """
        Get the manual documentation for a command.

        Raises:
            ValueError: If the command is not registered
        """
        command = self.get_command(command_name)
        return command.describe()

    def _register_builtin_commands(self) -> None:
        """
        Register built-in commands with the shell.
        """
        # Register file operation commands
        self.register_command(ReadFileCommand())
        self.register_command(WriteFileCommand())
        self.register_command(UpdateFileCommand())
        self.register_command(NeoGrepCommand())
        self.register_command(NeoFindCommand())

        # Register shell command
        self.register_command(BashCommand())
        
        # Register structured output command - import locally to avoid circular imports
        from src.neo.commands.structured_output import StructuredOutput
        self.register_command(StructuredOutput())

        logger.debug(f"Registered built-in commands: {', '.join(self.list_commands())}")
