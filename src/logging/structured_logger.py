"""
Structured logging module for Neo application.

This module provides a StructuredLogger class for recording structured data
to a YAML file with proper formatting.
"""

import logging
import datetime
import os
import weakref
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, TextIO

# Configure logger
logger = logging.getLogger(__name__)


class LogFile:
    """Class representing a log file with its empty status and file handle."""
    
    def __init__(self, is_empty: bool, file: TextIO):
        self.is_empty = is_empty
        self._file = file
    
    @staticmethod
    @lru_cache(maxsize=32)
    def load_from_path(log_file_path: Path) -> 'LogFile':
        """
        Load or create a log file at the specified path.
        
        Args:
            log_file_path: Path to the log file
            
        Returns:
            LogFile: Object containing the file empty status and file handle
        """
        # Ensure the log directory exists
        log_file_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Check if the file exists
        file_exists = log_file_path.exists()
        
        # Initialize the log file if it doesn't exist
        if not file_exists:
            # Just create an empty file
            open(log_file_path, 'w', encoding='utf-8').close()
            is_empty = True
        else:
            # Check if file is empty
            is_empty = os.path.getsize(log_file_path) == 0
        
        # Open the file in append mode for continuous writing
        file = open(log_file_path, 'a', encoding='utf-8')
        
        # Register a finalizer to close the file when it's garbage collected
        weakref.finalize(file, lambda f: f.close() if not f.closed else None, file)
        
        # Create the log file object with the open file handle
        return LogFile(is_empty=is_empty, file=file)
    
    def add_document(self, data: Dict[str, Any]) -> None:
        """Add a new YAML document to the log file.
        
        Args:
            data: Dictionary data to log as a new document
        """
        # Start with the document separator based on file state
        document_content = "\n---\n" if not self.is_empty else ""
        
        # Format the data and add it to our content
        formatted_data = self._format_data(data)
        document_content += formatted_data
        
        # Write the content to the file
        self._file.write(document_content)
        self._file.flush()  # Ensure content is written to disk
        
        # If writing non-empty content to an empty file, update is_empty
        if self.is_empty and document_content:
            self.is_empty = False
    
    def _format_data(self, data: Any, indent: int = 0) -> str:
        """
        Recursively format data with proper YAML formatting and indentation.
        
        Args:
            data: Data to format
            indent: Current indentation level (spaces)
            
        Returns:
            str: Formatted YAML string
        """
        from io import StringIO
        output = StringIO()
        indent_str = ' ' * indent
        
        if isinstance(data, dict):
            for key, value in data.items():
                if isinstance(value, (dict, list)):
                    # For nested structures, write the key and recurse
                    output.write(f"{indent_str}{key}:\n")
                    output.write(self._format_data(value, indent + 2))
                elif isinstance(value, str) and '\n' in value:
                    # For multi-line strings, use block scalar style
                    output.write(f"{indent_str}{key}: |\n")
                    # Add 2 more spaces of indentation for the content
                    content_indent = ' ' * (indent + 2)
                    for line in value.split('\n'):
                        output.write(f"{content_indent}{line}\n")
                else:
                    # For simple values, write key-value pair directly
                    if value is None:
                        output.write(f"{indent_str}{key}: null\n")
                    elif isinstance(value, bool):
                        # Format booleans as true/false (lowercase in YAML)
                        bool_str = str(value).lower()
                        output.write(f"{indent_str}{key}: {bool_str}\n")
                    elif isinstance(value, (int, float)):
                        # Format numbers directly
                        output.write(f"{indent_str}{key}: {value}\n")
                    elif isinstance(value, str):
                        # Strings may need quoting if they contain special characters
                        if any(c in value for c in ':{[]}!@#%^&*'):
                            output.write(f"{indent_str}{key}: '{value}'\n")
                        else:
                            output.write(f"{indent_str}{key}: {value}\n")
                    else:
                        # Default formatting for other types
                        output.write(f"{indent_str}{key}: {value}\n")
        
        elif isinstance(data, list):
            for item in data:
                if isinstance(item, (dict, list)):
                    # For complex items, add a list marker and recurse
                    output.write(f"{indent_str}- \n")
                    output.write(self._format_data(item, indent + 2))
                elif isinstance(item, str) and '\n' in item:
                    # For multi-line strings in lists
                    output.write(f"{indent_str}- |\n")
                    content_indent = ' ' * (indent + 2)
                    for line in item.split('\n'):
                        output.write(f"{content_indent}{line}\n")
                else:
                    # For simple list items
                    if item is None:
                        output.write(f"{indent_str}- null\n")
                    elif isinstance(item, bool):
                        bool_str = str(item).lower()
                        output.write(f"{indent_str}- {bool_str}\n")
                    elif isinstance(item, (int, float)):
                        output.write(f"{indent_str}- {item}\n")
                    elif isinstance(item, str):
                        if any(c in item for c in ':{[]}!@#%^&*'):
                            output.write(f"{indent_str}- '{item}'\n")
                        else:
                            output.write(f"{indent_str}- {item}\n")
                    else:
                        output.write(f"{indent_str}- {item}\n")
        
        else:
            # Direct value (should not typically happen at the top level)
            if isinstance(data, str) and '\n' in data:
                output.write(f"{indent_str}|\n")
                content_indent = ' ' * (indent + 2)
                for line in data.split('\n'):
                    output.write(f"{content_indent}{line}\n")
            else:
                output.write(f"{indent_str}{data}\n")
                
        return output.getvalue()


class StructuredLogger:
    """
    A logger that records structured data to a YAML file.
    
    The StructuredLogger maintains a YAML file with multiple documents,
    each represented as a separate YAML document separated by '---'.
    It handles proper formatting of multi-line strings and complex nested data structures.
    """
    
    def record(self, logger_name: str, data: Dict[str, Any]) -> None:
        """
        Record structured data as a new YAML document.
        
        Args:
            logger_name: Name of the logger, used as file name
            data: Dictionary of structured data to log
        """
        # Extract session_id from data or use "unknown"
        session_id = data.get("session_id", "unknown")
        
        # Add timestamp if not already present
        if "timestamp" not in data:
            data["timestamp"] = datetime.datetime.now().isoformat()
        
        # Create path in ~/.neo/<session_id>/<logger_name>.yaml
        log_dir = Path(os.path.expanduser("~")) / ".neo" / f"{session_id}"
        log_file_path = log_dir / f"{logger_name}.yaml"
        
        # Load or create the log file
        log_file = LogFile.load_from_path(log_file_path)
        
        # Add the document to the log file
        log_file.add_document(data)
    

    

    