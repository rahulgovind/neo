"""
Message classes for representing conversation content.
"""

import json
import re
import dataclasses
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional, Set, Union, Protocol, runtime_checkable, TYPE_CHECKING
from abc import ABC, abstractmethod

# Use forward references to avoid circular imports
if TYPE_CHECKING:
    from src.neo.shell.shell import ParsedCommand

from src.neo.core.constants import (
    COMMAND_END,
    COMMAND_START,
    ERROR_PREFIX,
    STDIN_SEPARATOR,
    SUCCESS_PREFIX,
)

from typing import Union


# Define OutputType
class PrimitiveOutputType:
    RAW = "raw"


OutputType = Union[PrimitiveOutputType, Dict[str, Any]]


@dataclass
class ParsedCommand:
    """
    Represents a parsed command with name, parameters, and optional data.
    """

    name: str
    parameters: Dict[str, Any]
    data: Optional[str] = None


class ContentBlock:
    """Base class for different types of content in a message."""

    def __str__(self) -> str:
        return self.model_text()

    def model_text(self) -> str:
        raise NotImplementedError("Subclasses must implement model_text")

    def display_text(self) -> str:
        """Returns text suitable for display to the user."""
        return self.model_text()

    def to_dict(self) -> Dict[str, Any]:
        """Convert the content block to a dictionary for serialization."""
        raise NotImplementedError("Subclasses must implement to_dict")

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ContentBlock":
        """Create a content block from a dictionary."""
        raise NotImplementedError("Subclasses must implement from_dict")

    @classmethod
    def create_from_dict(cls, data: Dict[str, Any]) -> "ContentBlock":
        """Factory method to create the appropriate ContentBlock subclass."""
        block_type = data.get("type", "TextBlock")

        if block_type == "TextBlock":
            return TextBlock.from_dict(data)
        elif block_type == "StructuredOutput":
            return StructuredOutput.from_dict(data)
        elif block_type == "CommandCall":
            return CommandCall.from_dict(data)
        elif block_type == "CommandResult":
            return CommandResult.from_dict(data)
        else:
            # Fail on unknown block types
            raise ValueError(f"Unknown content block type: {block_type}")


class TextBlock(ContentBlock):
    """Represents a text content block in a message."""

    def __init__(self, text: str):
        self._text = text

    def model_text(self) -> str:
        return self._text

    def to_dict(self) -> Dict[str, Any]:
        """Convert the TextBlock to a dictionary for serialization."""
        return {"type": "TextBlock", "value": self._text}

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TextBlock":
        """Create a TextBlock from a dictionary."""
        return cls(data.get("value", ""))


class CommandCall(ContentBlock):
    """Represents a command call content block in a message."""

    def __init__(self, content: str, parsed_cmd: Optional["ParsedCommand"] = None):
        self.content = content
        self.parsed_cmd = parsed_cmd

    def model_text(self) -> str:
        return self.content

    def to_dict(self) -> Dict[str, Any]:
        """Convert the CommandCall to a dictionary for serialization."""
        return {"type": "CommandCall", "value": self.content}

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CommandCall":
        """Create a CommandCall from a dictionary."""
        return cls(content=data.get("value", ""))


def _escape_special_chars(content: str) -> str:
    r"""
    Replace special command characters with their escaped unicode representation.

    Args:
        content: The content to process

    Returns:
        Content with special characters replaced
    """

    # Escape function to replace special characters with \u{hex} format
    def escape_special_chars(match):
        char = match.group(0)
        # Format the character's code point as a hex string - use raw string to avoid backslash escaping
        return f"\\u{ord(char):x}"

    # Create pattern of all special characters
    special_chars = "".join(
        [COMMAND_START, COMMAND_END, STDIN_SEPARATOR, ERROR_PREFIX, SUCCESS_PREFIX]
    )
    pattern = f"[{re.escape(special_chars)}]"

    # Escape all special characters in the content
    result = re.sub(pattern, escape_special_chars, content)

    return result


def _unescape_special_chars(content: str) -> str:
    r"""
    Reverse the escaping process, converting \u{hex} escape sequences back to special characters.
    Only converts escape sequences for our specific special characters.

    Args:
        content: The content to process

    Returns:
        Content with escape sequences converted back to special characters
    """
    if content is None:
        return ""

    # Create a mapping of hex codes to special characters
    hex_to_char = {
        f"{ord(COMMAND_START):x}": COMMAND_START,
        f"{ord(COMMAND_END):x}": COMMAND_END,
        f"{ord(STDIN_SEPARATOR):x}": STDIN_SEPARATOR,
        f"{ord(ERROR_PREFIX):x}": ERROR_PREFIX,
        f"{ord(SUCCESS_PREFIX):x}": SUCCESS_PREFIX,
    }

    # Function to replace only specific escape sequences
    def unescape_specific_chars(match):
        # Extract the hex code
        hex_code = match.group(1)
        # Only replace if it's one of our special characters
        if hex_code in hex_to_char:
            return hex_to_char[hex_code]
        # Otherwise keep the original
        return match.group(0)

    # Pattern to match our specific escape sequences
    hex_codes = "|".join(hex_to_char.keys())
    pattern = f"\\\\u({hex_codes})"

    # Replace only our specific escaped sequences
    result = re.sub(pattern, unescape_specific_chars, content)

    return result


@dataclass
class CommandOutput:
    """Base class for structured command output.
    
    This class serves as a base for command-specific output structures.
    Commands can extend this class to provide structured data 
    alongside the text representation.
    """
    name: str
    message: str


class CommandResult(ContentBlock):
    """Represents a command result content block in a message."""

    def __init__(
        self,
        content: str,
        success: bool,
        error: Optional[Exception] = None,
        command_call: Optional[ParsedCommand] = None,
        command_output: Optional[CommandOutput] = None,
    ):
        self.content = content
        self.success = success
        self.error = error
        self.command_call = command_call
        self.command_output = command_output

    def model_text(self) -> str:
        prefix = SUCCESS_PREFIX if self.success else ERROR_PREFIX
        # Escape the content before formatting it in the output string
        escaped_content = _escape_special_chars(str(self.content))
        return f"{prefix}{escaped_content}{COMMAND_END}"

    def display_text(self) -> str:
        """Returns the model text representation."""
        return self.model_text()

    def to_dict(self) -> Dict[str, Any]:
        """Convert the CommandResult to a dictionary for serialization.
        Note: error is intentionally excluded.
        """
        return {
            "type": "CommandResult",
            "value": self.content,
            "success": self.success,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CommandResult":
        """Create a CommandResult from a dictionary.
        
        Note: command_output is not loaded from serialized data.
        """
        return cls(
            content=data.get("value", ""),
            success=data.get("success", True),
        )


class StructuredOutput(CommandResult):
    """Represents a structured output content block in a message."""

    def __init__(
        self, content: str, value: Optional[Any] = None, destination: str = "default"
    ):
        super().__init__(content, success=True)
        self.value = value
        self.destination = destination

    def to_dict(self) -> Dict[str, Any]:
        """Convert the StructuredOutput to a dictionary for serialization."""
        return {
            "type": "StructuredOutput",
            "content": self.content,
            "value": self.value,
            "destination": self.destination,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "StructuredOutput":
        """Create a StructuredOutput from a dictionary."""
        return cls(
            content=data.get("content", ""),
            value=data.get("value"),
            destination=data.get("destination"),
        )


@dataclass
class Message:
    """
    Represents a message in the conversation with role and content blocks.
    """
    role: str
    content: List[ContentBlock]
    metadata: Dict[str, Any] = field(default_factory=dict)
    assistant_prefill: Optional[str] = None
    
    def __post_init__(self):
        # Handle string content by converting to TextBlock
        if isinstance(self.content, str):
            self.content = [TextBlock(self.content)]

            
        # Validate content blocks
        assert all(
            isinstance(block, ContentBlock) for block in self.content
        ), "All content blocks must be instances of ContentBlock"
    
    @classmethod
    def create(cls, role: str, content: Union[str, List[ContentBlock]], **kwargs) -> "Message":
        """Factory method to create a Message with default values."""
        return cls(role=role, content=content, **kwargs)

    def add_content(self, content: ContentBlock) -> None:
        assert isinstance(content, ContentBlock), "Content must be a ContentBlock"
        self.content.append(content)

    def has_command_executions(self) -> bool:
        return any(isinstance(block, CommandCall) for block in self.content)

    def get_command_calls(self) -> List[CommandCall]:
        return [block for block in self.content if isinstance(block, CommandCall)]

    def text(self) -> str:
        """Get all text content from the message, joined with newlines."""
        text_parts = [block.model_text() for block in self.content]
        return "\n".join(text_parts)

    def command_results(self) -> List[CommandResult]:
        return [block for block in self.content if isinstance(block, CommandResult)]

    def structured_output(self) -> Optional[StructuredOutput]:
        structured_output_blocks = [
            block
            for block in self.command_results()
            if isinstance(block, StructuredOutput)
        ]
        if structured_output_blocks:
            return structured_output_blocks[0]
        return None

    def model_text(self) -> str:
        """Get all model text content from the message, joined with newlines."""
        text_parts = [block.model_text() for block in self.content]
        return "\n".join(text_parts)

    def display_text(self) -> str:
        """Get all display text content from the message, joined with newlines."""
        text_parts = [block.display_text() for block in self.content]
        return "\n".join(text_parts)

    def to_dict(self) -> Dict[str, Any]:
        """Convert Message to a dictionary for serialization."""
        return {
            "role": self.role,
            "content": [block.to_dict() for block in self.content],
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Message":
        """Create Message from a dictionary."""
        content_blocks = []
        for item in data.get("content", []):
            content_blocks.append(ContentBlock.create_from_dict(item))

        return cls(
            role=data.get("role", "user"),
            content=content_blocks,
            metadata=data.get("metadata", {}),
        )

    def copy(self, metadata: Optional[Dict[str, Any]] = None) -> "Message":
        """Create a copy of this message, optionally with different metadata."""
        return dataclasses.replace(
            self,
            content=self.content.copy(),
            metadata=metadata if metadata is not None else self.metadata.copy()
        )

    def __str__(self) -> str:
        """
        Create a properly formatted string representation of the message.
        Handles multi-line content and preserves formatting of each content block.
        """
        parts = []
        for block in self.content:
            block_str = str(block)
            if block_str:
                parts.append(block_str)

        content_str = "\n".join(parts)
        return f"[{self.role}] {content_str}"
