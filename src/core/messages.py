"""
Message classes for representing conversation content.
"""

from typing import List, Any, Optional, Dict

from src.core.constants import (
    COMMAND_START, COMMAND_END, STDIN_SEPARATOR, 
    ERROR_PREFIX, SUCCESS_PREFIX
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
        return f"{prefix}{content}{COMMAND_END}"
        
    def __str__(self) -> str:
        return self._text


class ParsedCommand:
    """
    Represents a parsed command with name, parameters, and optional data.
    """
    
    def __init__(self, name: str, parameters: Dict[str, Any], data: Optional[str] = None):
        self.name = name
        self.parameters = parameters
        self.data = data
    
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
