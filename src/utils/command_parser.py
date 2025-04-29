"""
Command builder module for parsing and building command line arguments.

This module provides utilities for parsing command line arguments in a CLI-like fashion,
similar to argparse but tailored for the command system. It also provides utilities for
building command documentation.
"""

import argparse
import logging
from typing import Dict, Any, List, Optional, Tuple

# Configure logging
logger = logging.getLogger(__name__)


class CommandParser:
    """
    Builder for command line arguments and documentation in a CLI-like fashion.

    This class handles the parsing of command line arguments for Command objects,
    converting CLI-style strings into structured parameter dictionaries. It also
    provides utilities for building command documentation.
    """

    @staticmethod
    def parse_command_input(
        command_name: str,
        command_input: str,
        parameters: List["CommandParameter"],
        requires_data: bool = False,
    ) -> Tuple[Dict[str, Any], Optional[str]]:
        """
        Parse a command input string into a dictionary of parameter values and optional data.

        Args:
            command_name: The name of the command being parsed
            command_input: Command input string (can include optional data after a pipe symbol)
            parameters: List of CommandParameter objects defining the command's parameters

        Returns:
            Tuple of (parameter dictionary, optional data string)

        Raises:
            ValueError: If parsing fails
        """
        # Split command and data if the separator exists
        data = None
        if "｜" in command_input:
            command_line, data = command_input.split("｜", 1)
        else:
            command_line = command_input

        # Validate data requirements
        if requires_data and not data:
            raise RuntimeError(
                f"Command '{command_name}' requires data (content after |)"
            )
        elif not requires_data and data:
            raise RuntimeError(
                f"Command '{command_name}' does not accept data (content after |)"
            )

        # Parse the command line part
        return CommandParser.parse(command_name, command_line, parameters), data

    @staticmethod
    def parse(
        command_name: str, command_line: str, parameters: List["CommandParameter"]
    ) -> Dict[str, Any]:
        """
        Parse a command line string into a dictionary of parameter values.

        Args:
            command_name: The name of the command being parsed
            command_line: CLI-style command string (e.g., "cmd pos1 pos2 -f val --flag val2")
            parameters: List of CommandParameter objects defining the command's parameters

        Returns:
            Dictionary mapping parameter names to their values

        Raises:
            ValueError: If parsing fails or required arguments are missing
        """

        # Create an argument parser
        parser = argparse.ArgumentParser(prog=command_name, exit_on_error=False)

        # Add parameters based on the command's parameter definitions
        positional_params = []

        for param in parameters:
            if param.is_positional:
                positional_params.append(param)
                parser.add_argument(
                    param.name,
                    help=param.description,
                    default=param.default,
                )
            elif param.is_flag:
                flag_args = []
                if param.short_flag:
                    flag_args.append(f"-{param.short_flag}")
                if param.long_flag:
                    flag_args.append(f"--{param.long_flag}")

                # Check if the parameter is a boolean flag (default is a boolean value)
                if isinstance(param.default, bool):
                    parser.add_argument(
                        *flag_args,
                        dest=param.name,
                        help=param.description,
                        action=(
                            "store_true" if param.default is False else "store_false"
                        ),
                        required=param.required,
                    )
                else:
                    parser.add_argument(
                        *flag_args,
                        dest=param.name,
                        help=param.description,
                        default=param.default,
                        required=param.required,
                    )

        # Use shlex to properly handle quoted arguments
        import shlex

        # Split the command line using shlex for proper quote handling
        try:
            parts = shlex.split(command_line)
            logger.debug(f"Parsed command parts with shlex: {parts}")
            if parts and parts[0] == command_name:
                parts = parts[1:]
        except ValueError as e:
            logger.error(f"Error parsing command with shlex: {str(e)}")
            # Fall back to basic split if shlex fails
            parts = command_line.split()
            logger.debug(f"Falling back to basic split: {parts}")
            if parts and parts[0] == command_name:
                parts = parts[1:]

        # Parse the arguments
        try:
            args = vars(parser.parse_args(parts))
            return args
        except Exception as e:
            raise ValueError(f"Error parsing command line: {str(e)}")
