"""
Structured logging module for Neo application.

This module provides a StructuredLogger class for recording structured data
to a JSON file with proper formatting.
"""

import logging
import datetime
import json
import os
import weakref
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, TextIO, Union

# Configure logger
logger = logging.getLogger(__name__)


class LogFile:
    """Class representing a log file with its empty status and file handle."""

    def __init__(self, is_empty: bool, file: TextIO):
        self.is_empty = is_empty
        self._file = file

    @staticmethod
    @lru_cache(maxsize=32)
    def load_from_path(log_file_path: Path) -> "LogFile":
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
            # Initialize with an empty array for JSON
            with open(log_file_path, "w", encoding="utf-8") as f:
                f.write("[\n")
                f.write("]")
            # File is technically not empty, but we'll treat it as empty for append logic
            is_empty = True
        else:
            # Check if file is empty
            is_empty = os.path.getsize(log_file_path) == 0

        # Open the file for read/write
        if is_empty:
            file = open(log_file_path, "r+", encoding="utf-8")
            # Move to the beginning of file, after the opening bracket
            file.seek(2)  # Skip past the "[\n"
        else:
            # If file exists and has content, we need to insert before the closing bracket
            file = open(log_file_path, "r+", encoding="utf-8")
            # Move to the second-to-last character (before the closing bracket)
            file.seek(os.path.getsize(log_file_path) - 1)

        # Register a finalizer to close the file when it's garbage collected
        weakref.finalize(file, lambda f: f.close() if not f.closed else None, file)

        # Create the log file object with the open file handle
        return LogFile(is_empty=is_empty, file=file)

    def add_document(self, data: Dict[str, Any]) -> None:
        """Add a new JSON entry to the log file.

        Args:
            data: Dictionary data to log as a new entry
        """
        if self.is_empty:
            # If file was initialized but empty, we'll write directly after the opening bracket
            document_content = json.dumps(data, indent=2)
            self._file.write(document_content)
            # Write the closing bracket
            self._file.write("\n]")
            # Ensure content is written to disk
            self._file.flush()
            # Rewind to overwrite the closing bracket for future appends
            self._file.seek(self._file.tell() - 1)
        else:
            # If file already has content, add a comma and the new entry
            document_content = json.dumps(data, indent=2)
            self._file.write(",\n")
            self._file.write(document_content)
            # Write the closing bracket
            self._file.write("\n]")
            # Ensure content is written to disk
            self._file.flush()
            # Rewind to overwrite the closing bracket for future appends
            self._file.seek(self._file.tell() - 1)

        # If writing to an empty file, update is_empty
        if self.is_empty:
            self.is_empty = False


class StructuredLogger:
    """
    A logger that records structured data to a JSON file.

    The StructuredLogger maintains a JSON file with a JSON array containing
    multiple log entries. It handles proper formatting and serialization of
    complex nested data structures.
    """

    def record(self, logger_name: str, data: Dict[str, Any]) -> None:
        """
        Record structured data as a new JSON entry.

        Args:
            logger_name: Name of the logger, used as file name
            data: Dictionary of structured data to log
        """
        # Extract session_id from data or use "unknown"
        session_id = data.get("session_id", "unknown")

        # Add timestamp if not already present
        if "timestamp" not in data:
            data["timestamp"] = datetime.datetime.now().isoformat()

        # Create path in ~/.neo/<session_id>/<logger_name>.json
        log_dir = Path(os.path.expanduser("~")) / ".neo" / f"{session_id}"
        log_file_path = log_dir / f"{logger_name}.json"

        # Load or create log file
        log_file = LogFile.load_from_path(log_file_path)

        # Add the document to the log file
        log_file.add_document(data)
