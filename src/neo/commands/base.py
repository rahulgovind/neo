"""
Core command module defining the Command interface.

This module provides the foundation for all callable commands in the system:
- Abstract Command interface that all concrete commands must implement
- Support for CLI-like parameter parsing with positional and flag arguments
- Example class for storing command usage examples
"""

import logging
import traceback
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Dict, Any, List, Optional, Tuple

from src.neo.core.messages import CommandResult
from src.utils.command_parser import CommandParser
from src.neo.exceptions import FatalError
from src.neo.session import Session

# Configure logging
logger = logging.getLogger(__name__)


@dataclass
class CommandParameter:
    """Defines a parameter for a Command."""

    name: str
    description: str
    required: bool = False
    default: Any = None
    is_positional: bool = False
    hidden: bool = False
    is_flag: bool = False
    short_flag: Optional[str] = (
        None  # Single character for short flag (e.g., 'f' for -f)
    )
    long_flag: Optional[str] = None  # Word for long flag (e.g., 'file' for --file)

    def __post_init__(self):
        # Validate parameter configuration
        if self.is_flag and not (self.short_flag or self.long_flag):
            raise ValueError(
                f"Flag parameter {self.name} must have either short_flag or long_flag"
            )


@dataclass
class CommandTemplate:
    """
    Template for a command, containing parameter definitions and documentation.

    This class defines the structure of a command, including its name, parameters,
    description, and additional documentation.
    """

    name: str
    description: str
    parameters: List[CommandParameter]
    examples: str = ""
    requires_data: bool = False

    def manual(self) -> str:
        """Format the manual as a string, similar to a man page.

        Returns:
            Formatted manual string
        """
        lines = []

        # NAME section - flat format
        # Get first line of description for the short summary
        short_desc = self.description.strip().split("\n")[0] if self.description else ""
        lines.append(f"NAME: {self.name} - {short_desc}")

        # SYNOPSIS section - flat format
        synopsis = f"\u25b6{self.name}"

        # Add options placeholder to synopsis if flags exist
        flags = [p for p in self.parameters if p.is_flag]
        if flags:
            synopsis += " [OPTION]..."

        # Add positional parameters to synopsis
        pos_params = [p for p in self.parameters if p.is_positional]
        for param in pos_params:
            param_name = param.name.upper()
            if not param.required:
                param_name = f"[{param_name}]"
            synopsis += f" {param_name}"

        # Add STDIN indicator if the command requires data
        if self.requires_data:
            synopsis += "\uff5cSTDIN"

        # Add terminating character
        synopsis += "\u25a0"

        lines.append(f"SYNOPSIS: {synopsis}")

        # DESCRIPTION section - on new lines
        lines.append("DESCRIPTION:")
        if self.description:
            desc_lines = self.description.strip().split("\n")
            # Use all lines of the description
            for line in desc_lines:
                lines.append(f"    {line}")

        # OPTIONS section with flags - flat format
        if flags:
            lines.append("OPTIONS:")
            for param in flags:
                option_str = ""
                if param.short_flag and param.long_flag:
                    option_str = f"-{param.short_flag}, --{param.long_flag}"
                elif param.short_flag:
                    option_str = f"-{param.short_flag}"
                elif param.long_flag:
                    option_str = f"--{param.long_flag}"

                # Flatten flag description
                param_desc = " ".join(param.description.split("\n"))
                lines.append(f"    {option_str}: {param_desc}")

        # Examples section - on new lines
        if self.examples:
            lines.append("EXAMPLES:")
            for example_line in self.examples.split("\n"):
                lines.append(f"    {example_line}")

        return "\n".join(lines)


class Command(ABC):
    """
    Abstract base class for commands callable in a CLI-like fashion.

    Commands can be executed with positional parameters and flags, similar to
    command-line programs. For example:

    ▶<cmd> param1 -f val1 --foo val2■

    This executes <cmd> with param1 as a positional parameter, val1 set to the
    parameter corresponding to the flag "f" and val2 to the parameter
    corresponding to the flag "foo".

    Subclasses must implement:
    - name: Property that returns the command name
    - description(): Returns a short description of the command
    - help(): Returns detailed description with examples and parameter lists
    - validate(): Validates that a given command statement is valid
    - execute(): Executes the command and returns a CommandResult
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """
        Returns the name of the command.
        """
        pass
    
    @abstractmethod
    def description(self) -> str:
        """
        Returns a short description of the command.
        """
        pass

    @abstractmethod
    def help(self) -> str:
        """
        Returns a detailed description of the command with examples and parameter lists.
        """
        pass
    
    @abstractmethod
    def validate(
        self, session: Session, statement: str, data: Optional[str] = None
    ) -> None:
        """
        Validates that the command statement and data are valid for execution.
        
        Args:
            session: The current session context
            statement: The full command statement without markers
            data: Optional data string (similar to stdin)
            
        Raises:
            ValueError: If validation fails
        """
        pass
    
    @abstractmethod
    def execute(
        self, session: Session, statement: str, data: Optional[str] = None
    ) -> CommandResult:
        """
        Executes the command and returns a result.

        Args:
            session: The current session context
            statement: The full command statement without markers
            data: Optional data string (similar to stdin)

        Returns:
            CommandResult object with result, success status, and optional summary

        Raises:
            FatalError: For unrecoverable errors that should terminate execution
        """


    
    def describe(self) -> str:
        """
        Returns the full help documentation for the command.
        """
        return self.help()
