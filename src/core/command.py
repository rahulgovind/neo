"""
Core command module defining the Command interface.

This module provides the foundation for all callable commands in the system:
- Abstract Command interface that all concrete commands must implement
- Support for CLI-like parameter parsing with positional and flag arguments
- Manual documentation for each command
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
class CommandManual:
    """Manual documentation for a command, similar to Unix man pages."""
    
    name: str
    synopsis: str
    description: str
    parameters: List[CommandParameter]
    examples: List[str] = field(default_factory=list)
    see_also: List[str] = field(default_factory=list)
    
    def format(self) -> str:
        """Format the manual as a string, similar to a man page."""
        lines = []
        
        # NAME section
        lines.append("NAME")
        lines.append(f"    {self.name} - {self.synopsis}")
        lines.append("")
        
        # DESCRIPTION section
        lines.append("DESCRIPTION")
        wrapped_desc = textwrap.fill(self.description, width=76, initial_indent="    ", 
                                    subsequent_indent="    ")
        lines.append(wrapped_desc)
        lines.append("")
        
        # PARAMETERS section
        if self.parameters:
            lines.append("PARAMETERS")
            
            # First list positional parameters
            positional = [p for p in self.parameters if p.is_positional]
            if positional:
                for param in positional:
                    lines.append(f"    {param.name} - {param.description}")
                    if param.required:
                        lines.append("        Required: Yes")
                    else:
                        lines.append(f"        Required: No (Default: {param.default})")
                    lines.append("")
            
            # Then list flag parameters
            flags = [p for p in self.parameters if p.is_flag]
            if flags:
                for param in flags:
                    flag_str = []
                    if param.short_flag:
                        flag_str.append(f"-{param.short_flag}")
                    if param.long_flag:
                        flag_str.append(f"--{param.long_flag}")
                    
                    lines.append(f"    {', '.join(flag_str)} - {param.description}")
                    if param.required:
                        lines.append("        Required: Yes")
                    else:
                        lines.append(f"        Required: No (Default: {param.default})")
                    lines.append("")
        
        # EXAMPLES section
        if self.examples:
            lines.append("EXAMPLES")
            for i, example in enumerate(self.examples, 1):
                lines.append(f"    Example {i}:")
                lines.append(f"        {example}")
                lines.append("")
        
        # SEE ALSO section
        if self.see_also:
            lines.append("SEE ALSO")
            lines.append(f"    {', '.join(self.see_also)}")
        
        return "\n".join(lines)


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
    def process(self, args: Dict[str, Any], data: Optional[str] = None) -> str:
        """
        Core implementation of the command's functionality.
        
        Args:
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
    
    def execute(self, parameters: Dict[str, Any], data: Optional[str] = None) -> CommandResult:
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
            result = self.process(parameters, data)
            
            # Return success result
            return CommandResult(result=result, success=True)
            
        except FatalError:
            # Re-raise fatal errors without converting to CommandResult
            raise
            
        except Exception as e:
            # Return failure result with error message
            logger.error(f"Error executing command {self.__class__.__name__}: {str(e)}")
            return CommandResult(success=False, error=str(e))
    