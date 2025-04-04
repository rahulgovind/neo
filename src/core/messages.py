"""
Message classes for representing conversation content.
"""

import json
import re
import uuid
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Union, Type

from src.core.constants import (
    COMMAND_END,
    COMMAND_START,
    ERROR_PREFIX,
    STDIN_SEPARATOR,
    SUCCESS_PREFIX,
)


class ContentBlock:
    """Base class for different types of content in a message."""
    
    def __str__(self) -> str:
        return ""
        
    def text(self) -> str:
        return self.__str__()


class TextBlock(ContentBlock):
    """Represents a text content block in a message."""
    
    def __init__(self, text: str):
        self._text = text
        
    def __str__(self) -> str:
        return self._text
        
    def text(self) -> str:
        return self._text


class CommandCall(TextBlock):
    """Represents a command call content block in a message."""
    
    def __init__(self, content: str = "", end_marker_set: bool = False):
        """Initialize a command call with content and end marker status.
        
        Args:
            content: The command content (without COMMAND_START or COMMAND_END markers)
            end_marker_set: Whether the COMMAND_END marker was present
        """
        self._content = content
        self.end_marker_set = end_marker_set
        self._text = self._generate_text()
        
    def _generate_text(self) -> str:
        if self.end_marker_set:
            return f"{COMMAND_START}{self._content}{COMMAND_END}"
        else:
            return f"{COMMAND_START}{self._content}"
            
    def __str__(self) -> str:
        return self._text
        
    def text(self) -> str:
        return self._text
        
    def content(self) -> str:
        """Get the raw command content without markers."""
        return self._content


def _escape_special_chars(content: str) -> str:
    """
    Replace special command characters with their escaped Unicode variants.
    Also properly escapes already-escaped unicode sequences.
    
    Args:
        content: The content to process
        
    Returns:
        Content with special characters replaced
    """
    if content is None:
        return ""
    
    # First, handle already-escaped sequences by doubling the backslashes
    # This matches \\u25b6, \\u25a0, etc. and replaces with \\\u25b6, \\\u25a0, etc.
    result = re.sub(
        r'\\u(25b6|25a0|ff5c|274c|2705)', 
        r'\\\\u\1',  # \1 is the backreference to the captured group
        content
    )
    
    # Then replace actual special characters with their escape sequences
    # Create a dictionary mapping special characters to their escape sequences
    char_to_escape = {
        COMMAND_START: '\\\u25b6',    # \u25b6 -> \\u25b6
        COMMAND_END: '\\\u25a0',      # \u25a0 -> \\u25a0
        STDIN_SEPARATOR: '\\\uff5c',  # \uff5c -> \\uff5c
        ERROR_PREFIX: '\\\u274c',     # \u274c -> \\u274c
        SUCCESS_PREFIX: '\\\u2705',   # \u2705 -> \\u2705
    }
    
    # Build the pattern of all special characters to match
    pattern = '[' + re.escape(''.join(char_to_escape.keys())) + ']'
    
    # Define a replacement function that looks up the correct escape sequence
    def replace_special_char(match):
        return char_to_escape[match.group(0)]
    
    # Apply the substitution for special characters
    result = re.sub(pattern, replace_special_char, result)
    
    return result


def _unescape_special_chars(content: str) -> str:
    """
    Reverse the escaping process, converting Unicode escapes back to special characters.
    Handles both single-escaped and double-escaped sequences correctly.
    
    Args:
        content: The content to process
        
    Returns:
        Content with Unicode escapes converted back to special characters
    """
    if content is None:
        return ""
    
    # We need to detect if we're working with:
    # 1. A literal double-escaped sequence like "\\\u25b6" (which should become "\\u25b6")
    # 2. A single-escaped sequence like "\\u25b6" (which should become the actual character)
    
    # Create a dictionary for the escape sequence to special character mapping
    escape_to_char = {
        '\\\u25b6': COMMAND_START,     # \\u25b6 -> \u25b6
        '\\\u25a0': COMMAND_END,       # \\u25a0 -> \u25a0
        '\\\uff5c': STDIN_SEPARATOR,   # \\uff5c -> \uff5c
        '\\\u274c': ERROR_PREFIX,      # \\u274c -> \u274c
        '\\\u2705': SUCCESS_PREFIX,    # \\u2705 -> \u2705
    }
    
    # Define a replacement function for our regex
    def replacer(match):
        # Get the full match
        full_match = match.group(0)
        prefix = match.group(1)  # Will be either '\\' or '\'
        code = match.group(2)    # Will be one of our unicode values
        
        # If this is a double-escaped sequence (\\u...)
        if prefix == '\\\\':
            # Return a single-escaped sequence (\u...)
            return f'\\u{code}'
        
        # Otherwise it's a single-escaped sequence (\u...) 
        # Return the corresponding special character
        return escape_to_char.get(f'\\u{code}')
    
    # Use a pattern that captures both the prefix and the code to distinguish
    # between double-escaped (\\u...) and single-escaped (\u...)
    pattern = r'(\\\\|\\)u(25b6|25a0|ff5c|274c|2705)'
    
    # Apply the substitution
    result = re.sub(pattern, replacer, content)
    
    return result


class CommandResult(TextBlock):
    """Represents a command result content block in a message."""
    
    def __init__(self, result: Any = None, success: bool = True, error: Optional[str] = None):
        self.result = result
        self.success = success
        self.error = error
        self._text = self._generate_text()
        
    def _generate_text(self) -> str:
        prefix = SUCCESS_PREFIX if self.success else ERROR_PREFIX
        content = self.result if self.success else (self.error or "Unknown error")
        # Escape the content before formatting it in the output string
        escaped_content = _escape_special_chars(str(content))
        return f"{prefix}{escaped_content}{COMMAND_END}"
        
    def __str__(self) -> str:
        return self._text


class ParsedCommand:
    """
    Represents a parsed command with name, parameters, and optional data.
    """
    
    def __init__(self, name: str, parameters: Dict[str, Any], data: Optional[str] = None):
        self.name = name
        self.parameters = parameters
        # Unescape the data if it contains escaped sequences
        self.data = _unescape_special_chars(data) if data else None
    
    def __str__(self) -> str:
        params_str = " ".join([f"--{k} {v}" if not isinstance(v, bool) else f"--{k}" for k, v in self.parameters.items()])
        if self.data:
            return f"{self.name} {params_str}{STDIN_SEPARATOR}{self.data}"
        else:
            return f"{self.name} {params_str}"


class Message:
    """
    Represents a message in the conversation with role and content blocks.
    """
    
    def __init__(self, role: str, content: List[ContentBlock] = None, metadata: Optional[Dict[str, Any]] = None):
        self.role = role
        self.content = content or []
        self.metadata = metadata or {}
    
    def add_content(self, content: ContentBlock) -> None:
        self.content.append(content)
    
    def has_command_executions(self) -> bool:
        return any(isinstance(block, CommandCall) for block in self.content)
    
    def get_command_calls(self) -> List[CommandCall]:
        return [block for block in self.content if isinstance(block, CommandCall)]
        
    def text(self) -> str:
        """Get all text content from the message, joined with newlines."""
        text_parts = [block.text() for block in self.content]
        return "\n".join(text_parts)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert Message to a dictionary for serialization."""
        return {
            "role": self.role,
            "content": [
                {
                    "type": block.__class__.__name__,
                    "value": block.text() if isinstance(block, TextBlock) else str(block)
                }
                for block in self.content
            ],
            "metadata": self.metadata
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Message':
        """Create Message from a dictionary."""
        content_blocks = []
        for item in data.get("content", []):
            block_type = item.get("type", "TextBlock")
            value = item.get("value", "")
            
            if block_type == "TextBlock":
                content_blocks.append(TextBlock(value))
            elif block_type == "CommandCall":
                # Determine if the command has an end marker
                end_marker_set = value.endswith(COMMAND_END)
                # Extract content without markers
                content = value.replace(COMMAND_START, "").replace(COMMAND_END, "")
                content_blocks.append(CommandCall(content, end_marker_set))
            elif block_type == "CommandResult":
                # Simplified approach - we store the full text and recreate a TextBlock
                # This is sufficient for display purposes
                content_blocks.append(TextBlock(value))
            else:
                # Default to TextBlock for unknown types
                content_blocks.append(TextBlock(value))
        
        return cls(
            role=data.get("role", "user"),
            content=content_blocks,
            metadata=data.get("metadata", {})
        )

    def copy(self, metadata: Optional[Dict[str, Any]] = None) -> 'Message':
        return Message(
            self.role, 
            self.content.copy(),
            metadata if metadata else self.metadata.copy()
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
