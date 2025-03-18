"""
Structured logging module for Neo application.

This module provides a StructuredLogger class for recording structured data
to a single YAML file with proper formatting.
"""

import os
import logging
import threading
import yaml
from pathlib import Path
from typing import Any, Dict, Optional

# Configure logger
logger = logging.getLogger(__name__)


class StructuredLogger:
    """
    A logger that records structured data to a YAML file.
    
    The StructuredLogger maintains a single YAML file with multiple entries,
    each identified by a unique key. It handles proper formatting of multi-line
    strings and complex nested data structures.
    """
    
    def __init__(self, log_path: str):
        """
        Initialize a structured logger with the specified log path.
        
        Args:
            log_path: Directory path where the log file will be stored
        """
        self.log_dir = Path(log_path)
        self.log_file = self.log_dir / "requests.yaml"
        self.counter = 0
        self.lock = threading.Lock()
        
        # Ensure the log directory exists
        self.log_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize the log file if it doesn't exist
        if not self.log_file.exists():
            with open(self.log_file, 'w', encoding='utf-8') as f:
                f.write("# Neo structured logs\n")
            logger.info(f"Created new log file at {self.log_file}")
        else:
            # Count existing entries to continue numbering
            self._count_existing_entries()
            logger.info(f"Using existing log file at {self.log_file} with {self.counter} entries")
    
    def _count_existing_entries(self) -> None:
        """Count existing request entries to continue numbering."""
        try:
            with open(self.log_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Count occurrences of request_N patterns
            import re
            matches = re.findall(r'request_(\d+):', content)
            if matches:
                # Get the highest request number
                highest = max(int(m) for m in matches)
                self.counter = highest + 1
        except Exception as e:
            logger.warning(f"Error counting existing entries: {e}. Starting from 0.")
            self.counter = 0
    
    def record(self, key: str, data: Any) -> str:
        """
        Record structured data with the given key.
        
        Args:
            key: Base key for the log entry (will be appended with counter)
            data: Structured data to log
            
        Returns:
            The complete key used for the entry
        """
        with self.lock:
            # Generate unique key with counter
            entry_key = f"{key}_{self.counter}"
            self.counter += 1
            
            try:
                # Format and append the entry to the log file
                self._append_entry(entry_key, data)
                logger.debug(f"Recorded entry with key {entry_key}")
                return entry_key
            except Exception as e:
                logger.error(f"Failed to record entry {entry_key}: {e}")
                # Re-raise to allow caller to handle
                raise
    
    def _append_entry(self, key: str, data: Any) -> None:
        """
        Append a new entry to the log file with proper YAML formatting.
        
        Args:
            key: Unique key for the entry
            data: Data to log
        """
        try:
            with open(self.log_file, 'a', encoding='utf-8') as f:
                f.write(f"\n{key}:\n")
                self._write_formatted_data(f, data, indent=2)
        except Exception as e:
            logger.error(f"Error writing to log file: {e}")
            raise
    
    def _write_formatted_data(self, file_obj, data: Any, indent: int = 0) -> None:
        """
        Recursively write data with proper YAML formatting and indentation.
        
        Args:
            file_obj: Open file object to write to
            data: Data to format and write
            indent: Current indentation level (spaces)
        """
        indent_str = ' ' * indent
        
        if isinstance(data, dict):
            for key, value in data.items():
                if isinstance(value, (dict, list)):
                    # For nested structures, write the key and recurse
                    file_obj.write(f"{indent_str}{key}:\n")
                    self._write_formatted_data(file_obj, value, indent + 2)
                elif isinstance(value, str) and '\n' in value:
                    # For multi-line strings, use block scalar style
                    file_obj.write(f"{indent_str}{key}: |\n")
                    # Add 2 more spaces of indentation for the content
                    content_indent = ' ' * (indent + 2)
                    for line in value.split('\n'):
                        file_obj.write(f"{content_indent}{line}\n")
                else:
                    # For simple values, write key-value pair directly
                    if value is None:
                        file_obj.write(f"{indent_str}{key}: null\n")
                    elif isinstance(value, bool):
                        # Format booleans as true/false (lowercase in YAML)
                        bool_str = str(value).lower()
                        file_obj.write(f"{indent_str}{key}: {bool_str}\n")
                    elif isinstance(value, (int, float)):
                        # Format numbers directly
                        file_obj.write(f"{indent_str}{key}: {value}\n")
                    elif isinstance(value, str):
                        # Strings may need quoting if they contain special characters
                        if any(c in value for c in ':{[]}!@#%^&*'):
                            file_obj.write(f"{indent_str}{key}: '{value}'\n")
                        else:
                            file_obj.write(f"{indent_str}{key}: {value}\n")
                    else:
                        # Default formatting for other types
                        file_obj.write(f"{indent_str}{key}: {value}\n")
        
        elif isinstance(data, list):
            for item in data:
                if isinstance(item, (dict, list)):
                    # For complex items, add a list marker and recurse
                    file_obj.write(f"{indent_str}- \n")
                    self._write_formatted_data(file_obj, item, indent + 2)
                elif isinstance(item, str) and '\n' in item:
                    # For multi-line strings in lists
                    file_obj.write(f"{indent_str}- |\n")
                    content_indent = ' ' * (indent + 2)
                    for line in item.split('\n'):
                        file_obj.write(f"{content_indent}{line}\n")
                else:
                    # For simple list items
                    if item is None:
                        file_obj.write(f"{indent_str}- null\n")
                    elif isinstance(item, bool):
                        bool_str = str(item).lower()
                        file_obj.write(f"{indent_str}- {bool_str}\n")
                    elif isinstance(item, (int, float)):
                        file_obj.write(f"{indent_str}- {item}\n")
                    elif isinstance(item, str):
                        if any(c in item for c in ':{[]}!@#%^&*'):
                            file_obj.write(f"{indent_str}- '{item}'\n")
                        else:
                            file_obj.write(f"{indent_str}- {item}\n")
                    else:
                        file_obj.write(f"{indent_str}- {item}\n")
        
        else:
            # Direct value (should not typically happen at the top level)
            if isinstance(data, str) and '\n' in data:
                file_obj.write(f"{indent_str}|\n")
                content_indent = ' ' * (indent + 2)
                for line in data.split('\n'):
                    file_obj.write(f"{content_indent}{line}\n")
            else:
                file_obj.write(f"{indent_str}{data}\n")