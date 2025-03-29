"""
Structured logging module for Neo application.

This module provides a StructuredLogger class for recording structured data
to a YAML file with proper formatting.
"""

import logging
import threading
import datetime
import os
from pathlib import Path
from typing import Any, Dict
import re

# Configure logger
logger = logging.getLogger(__name__)


class StructuredLogger:
    """
    A logger that records structured data to a YAML file.
    
    The StructuredLogger maintains a YAML file with multiple documents,
    each represented as a separate YAML document separated by '---'.
    It handles proper formatting of multi-line strings and complex nested data structures.
    """
    
    def __init__(self, logger_name: str):
        """
        Initialize a structured logger.
        
        Args:
            logger_name: Name of the logger, used as file name
        """
        self.logger_name = logger_name
        self.log_dir = None
        self.log_file = None
        self.counter = 0
        self.lock = threading.Lock()
        self.initialized = False
    
    def _count_existing_entries(self) -> None:
        """Count existing request entries to continue numbering."""
        try:
            with open(self.log_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Count occurrences of request_N patterns
            matches = re.findall(r'request_(\d+):', content)
            if matches:
                # Get the highest request number
                highest = max(int(m) for m in matches)
                self.counter = highest + 1
        except Exception as e:
            logger.warning(f"Error counting existing entries: {e}. Starting from 0.")
            self.counter = 0
    
    def _initialize(self):
        """
        Initialize the logger if it hasn't been already. This fetches the
        session_id from context if it wasn't provided at initialization.
        """
        if self.initialized:
            return
        
        # Get session_id from context
        try:
            from src.core import context
            ctx = context.get()
            session_id = ctx.session_id
        except Exception as e:
            logger.warning(f"Could not get session_id from context: {e}. Using 'default'")
            session_id = "default"
        
        # Create path in ~/.neo/session-<session_id>/<logger_name>.yaml
        self.log_dir = Path(os.path.expanduser("~")) / ".neo" / f"session-{session_id}"
        self.log_file = self.log_dir / f"{self.logger_name}.yaml"
        
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
        
        self.initialized = True
    
    def record(self, data: Dict[str, Any]) -> None:
        """
        Record structured data as a new YAML document.
        
        Args:
            data: Dictionary of structured data to log
        """
        with self.lock:
            # Ensure we're initialized before proceeding
            self._initialize()
            
            # Add timestamp as the first field
            timestamp = datetime.datetime.now().isoformat()
            data_with_timestamp = {"timestamp": timestamp, **data}
            
            try:
                # Format and append the entry to the log file as a new YAML document
                self._append_document(data_with_timestamp)
                self.counter += 1
                logger.debug(f"Recorded entry #{self.counter} to {self.log_file}")
            except Exception as e:
                logger.error(f"Failed to record entry: {e}")
                # Re-raise to allow caller to handle
                raise
    
    def _append_document(self, data: Dict[str, Any]) -> None:
        """
        Append a new YAML document to the log file.
        
        Args:
            data: Dictionary data to log as a new document
        """
        try:
            with open(self.log_file, 'a', encoding='utf-8') as f:
                # Add document separator if not the first entry
                if self.counter > 0:
                    f.write("\n---\n")
                else:
                    f.write("\n")
                # Write the data with proper formatting
                self._write_formatted_data(f, data, indent=0)
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