"""
Shell module for command execution.

This module provides a Shell class that manages command registration and execution.
It acts as a central hub for executing commands by name.
"""

import logging
import jsonschema
import json
from typing import Dict, Any, List, Optional, Union

from src.neo.core.messages import CommandResult, CommandCall, StructuredOutput, ParsedCommand, OutputType, PrimitiveOutputType
from src.neo.commands.base import Command
from src.neo.commands.read_file import ReadFileCommand
from src.neo.commands.write_file import WriteFileCommand
from src.neo.commands.update_file import UpdateFileCommand
from src.neo.commands.file_text_search import FileTextSearch
from src.neo.commands.file_path_search import FilePathSearch
from src.neo.commands.shell import ShellRunCommand, ShellViewCommand, ShellWriteCommand, ShellTerminateCommand
from src.neo.core.constants import COMMAND_END
from src.neo.session import Session
import traceback

# Configure logging
logger = logging.getLogger(__name__)

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

        Args:
            command: Command instance to register

        Raises:
            ValueError: If a command with the same name is already registered
        """
        name = command.name
        if name in self._commands:
            raise ValueError(f"Command '{name}' is already registered")

        self._commands[name] = command
        logger.debug(f"Registered command: {name}")

    def register_commands(self, commands: List[Command]) -> None:
        """
        Register multiple commands with the shell.

        Raises:
            ValueError: If any command has a name collision
        """
        for command in commands:
            self.register_command(command)

    def _get_command(self, command_name: str) -> Command:
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

    def _parse(self, command_input: str) -> ParsedCommand:
        """
        Parse a command input string in the format "command_name [args] [|data]"

        Args:
            command_input: The command input string to parse
            
        Returns:
            ParsedCommand containing command name, statement, and data
            
        Raises:
            ValueError: If the command is not registered or not found
        """
        # Extract data if present (after pipe symbol)
        data = None
        if "｜" in command_input:
            parts = command_input.split("｜", 1)
            if len(parts) == 2:
                statement_part, data = parts
                statement_part = statement_part.strip()
                data = data.strip() if data else None
            else:
                # Handle case where command starts with pipe
                statement_part = ""
                data = parts[0].strip() if parts[0] else None
        else:
            statement_part = command_input.strip()

        # Get the command name (first word) from statement part if available
        statement_parts = statement_part.split() if statement_part else []
        
        # If statement is empty but command starts with pipe, take first word of data as command
        if not statement_parts and data:
            # For empty statement with data, assume first token in command_input is the command name
            command_name = command_input.split()[0] if command_input.split() else ""
        else:
            # Normal case - command name is first word in statement
            if not statement_parts:
                raise ValueError("Empty command input")
            command_name = statement_parts[0]

        # Check if command exists
        if command_name not in self._commands:
            raise ValueError(f"Command '{command_name}' is not registered")

        # Return the parsed command with the full statement
        return ParsedCommand(command_name, statement_part, data)

    def validate(self, command_input: str) -> None:
        """Validate a command input string."""
        parsed_cmd = self._parse(command_input)
        command = self._get_command(parsed_cmd.name)
        command.validate(self._session, parsed_cmd.parameters, parsed_cmd.data)

    def parse_command_call(self, command_call: CommandCall, output_schema: Optional[OutputType] = None) -> CommandCall:
        """
        Parses a command call and returns a CommandCall with parsed_cmd set.
        
        Args:
            command_call: The command call to parse
            output_schema: Output schema for structured output validation
            
        Returns:
            CommandCall with parsed_cmd field set
        """
        # Extract command statement without markers
        statement = command_call.content[1:-1]
        parsed_cmd = self._parse(statement)
        
        # Return the original command call with parsed command
        return CommandCall(
            content=command_call.content,
            parsed_cmd=parsed_cmd
        )
        
    def validate_command_calls(
        self, command_calls: List[CommandCall], output_schema: Optional[OutputType] = None
    ) -> List[CommandResult]:
        """
        Validate a list of command calls.
        
        Args:
            command_calls: List of command calls to validate
            output_schema: Output schema for structured output validation
            
        Returns:
            List of CommandResult objects for failed validations
        """
        output_schema = output_schema or PrimitiveOutputType.RAW
        validation_failures = []
        num_standard_command_calls = 0
        num_structured_output_calls = 0

        for cmd_call in command_calls:
            if not cmd_call.content.endswith(COMMAND_END):
                validation_failure = CommandResult(
                    content=f"{cmd_call.content} - Command call missing end marker",
                    success=False,
                )
                validation_failures.append(validation_failure)
                continue

            # Validate the command
            try:
                statement = cmd_call.content[1:-1]
                parsed_cmd = self._parse(statement)
                command = self._get_command(parsed_cmd.name)
                
                # Validate the command
                command.validate(self._session, parsed_cmd.parameters, parsed_cmd.data)
                
                # Track command types
                if parsed_cmd.name == "output":
                    num_structured_output_calls += 1
                else:
                    num_standard_command_calls += 1
                    
                # Validate command combination rules
                if num_structured_output_calls > 1:
                    raise ValueError(f"Only a single structured output call may be provided at a time. Only send the first output call from your previous message.")
                if num_structured_output_calls > 0 and output_schema is None:
                    raise ValueError(f"{cmd_call.content} - A structured output was not requested")
                if num_structured_output_calls > 0 and num_standard_command_calls > 0:
                    raise ValueError(f"{cmd_call.content} - Cannot mix structured output with other commands")
            except Exception as e:
                validation_failure = CommandResult(
                    content=f"{cmd_call.content} - Command is not valid",
                    success=False,
                    error=e
                )
                validation_failures.append(validation_failure)
                continue

        for validation_failure in validation_failures:
            if validation_failure.success:
                continue

            error = validation_failure.content + (
                f"\n{traceback.format_exception(validation_failure.error)}" if validation_failure.error else ""
            )
            logger.error(error)

        return validation_failures
        
    def execute(
        self, command_name: str, statement: str, data: Optional[str] = None
    ) -> CommandResult:
        """
        Execute a command with the given statement and data.
        """
        try:
            command = self._get_command(command_name)
            return command.execute(self._session, statement, data)
        except Exception as e:
            logger.error(f"Error executing command {command_name}: {str(e)}")
            return CommandResult(content=str(e), success=False, error=e)

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
            # Parse the command
            statement = cmd_call.content[1:-1]  # Remove markers
            
            try:
                parsed_cmd = self._parse(statement)
                
                # For handling commands with empty statement before pipe
                # Only pass the statement if it's not empty
                cmd_statement = "" if parsed_cmd.name == statement.strip() else statement
                
                # Execute the command
                result = self.execute(
                    parsed_cmd.name, parsed_cmd.parameters, parsed_cmd.data
                )

                result.command_call = parsed_cmd
                # Add the result to our collection
                result_blocks.append(result)
            except Exception as e:
                # Create an error result and add it to our collection
                error_result = CommandResult(content=str(e), success=False, error=e)
                result_blocks.append(error_result)

        for result in result_blocks:
            if result.success:
                logger.info(f"Command result: {result.content}")
            else:
                error_message = result.content + (
                    f"\n{traceback.format_exception(result.error)}" if result.error else ""
                )
                logger.error(f"Command failed: {error_message}")

        return result_blocks

    def describe(self, command_name: str) -> str:
        """
        Get the manual documentation for a command.

        Raises:
            ValueError: If the command is not registered
        """
        command = self._get_command(command_name)
        return command.help()

    def _register_builtin_commands(self) -> None:
        """
        Register built-in commands with the shell.
        """
        # Register file operation commands
        self.register_command(ReadFileCommand())
        self.register_command(WriteFileCommand())
        self.register_command(UpdateFileCommand())
        self.register_command(FileTextSearch())
        self.register_command(FilePathSearch())

        # Register shell commands
        self.register_command(ShellRunCommand())
        self.register_command(ShellViewCommand())
        self.register_command(ShellWriteCommand())
        self.register_command(ShellTerminateCommand())
        
        # Register structured output command - import locally to avoid circular imports
        from src.neo.commands.structured_output import StructuredOutputCommand
        self.register_command(StructuredOutputCommand())
        
        logger.debug(f"Registered built-in commands: {', '.join(self.list_commands())}")
