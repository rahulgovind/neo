"""
Core command module defining the Command interface.

This module provides the foundation for all callable commands in the system:
- Abstract Command interface that all concrete commands must implement
- Support for CLI-like parameter parsing with positional and flag arguments
- Example class for storing command usage examples
"""

import logging
import textwrap
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional, Tuple

from src.core.exceptions import FatalError
from src.core.messages import CommandResult
from src.utils.command_builder import CommandBuilder

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
    is_flag: bool = False
    short_flag: Optional[str] = None  # Single character for short flag (e.g., 'f' for -f)
    long_flag: Optional[str] = None   # Word for long flag (e.g., 'file' for --file)
    
    def __post_init__(self):
        # Validate parameter configuration        
        if self.is_flag and not (self.short_flag or self.long_flag):
            raise ValueError(f"Flag parameter {self.name} must have either short_flag or long_flag")


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
    manual: str = ""
    epilog: str = ""
    requires_data: bool = False
    
    def format_manual(self, extended: bool = False) -> str:
        """Format the manual as a string, similar to a man page.
        
        Args:
            extended: If True, include the extended manual text
            
        Returns:
            Formatted manual string
        """
        from src.utils.command_builder import CommandBuilder
        return CommandBuilder.format_manual(
            name=self.name,
            description=self.description,
            parameters=self.parameters,
            manual=self.manual,
            epilog=self.epilog,
            extended=extended
        )


class Command(ABC):
    """
    Abstract base class for commands callable in a CLI-like fashion.
    
    Commands can be executed with positional parameters and flags, similar to
    command-line programs. For example:
    
    <cmd> param1 -f val1 --foo val2
    
    This executes <cmd> with param1 as a positional parameter, val1 set to the
    parameter corresponding to the flag "f" and val2 to the parameter
    corresponding to the flag "foo".
    
    Subclasses must implement:
    - template: Returns a CommandTemplate with parameter definitions and documentation
    - process: Processes the parsed arguments and returns a result or raises an exception
    """
    

    
    @abstractmethod
    def template(self) -> 'CommandTemplate':
        """
        Returns the command template containing parameter definitions and documentation.
        """
        pass
    
    @abstractmethod
    def process(self, ctx, args: Dict[str, Any], data: Optional[str] = None) -> str:
        """
        Core implementation of the command's functionality.
        
        Args:
            ctx: Application context
            args: Parameter name-value pairs
            data: Optional data string (similar to stdin)
            
        Raises:
            Exception: If command execution fails
        """
        pass
    
    def describe(self, extended: bool = False) -> str:
        """
        Returns the manual describing how to use the command.
        """
        return self.template().format_manual(extended)
    
    def parse(self, command_input: str) -> Tuple[Dict[str, Any], Optional[str]]:
        """
        Parse a command input string into a dictionary of parameter values and optional data.
        
        Args:
            command_input: Command input string (can include optional data after a pipe symbol)
            
        Returns:
            Tuple of (parameter dictionary, optional data string)
            
        Raises:
            ValueError: If parsing fails
            FatalError: If data requirements are not met
        """
        cmd_template = self.template()
        return CommandBuilder.parse_command_input(
            cmd_template.name,
            command_input,
            cmd_template.parameters,
            cmd_template.requires_data
        )
    
    def execute(self, ctx, parameters: Dict[str, Any], data: Optional[str] = None) -> CommandResult:
        """
        Execute the command with the given parameters and data.
        
        This is the main entry point for executing commands that external
        callers should use.
        
        Args:
            parameters: Dictionary of parameter names to their values
            data: Optional data string
            
        Returns:
            CommandResult object with success/failure status and result/error
        """
        try:
            # Process the command
            result = self.process(ctx, parameters, data)
            
            # Return success result
            return CommandResult(result=result, success=True)
            
        except FatalError:
            # Re-raise fatal errors without converting to CommandResult
            raise
            
        except Exception as e:
            # Return failure result with error message
            logger.error(f"Error executing command {self.__class__.__name__}: {str(e)}")
            return CommandResult(success=False, error=str(e))
