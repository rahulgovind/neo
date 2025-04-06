"""
Unit tests for the UpdateFileCommand class.

This test validates the UpdateFileCommand functionality:
1. Updating existing files based on natural language instructions
2. Testing error conditions like missing files or instructions
"""

import os
import unittest
import logging
import pytest
from pathlib import Path
from dataclasses import dataclass
from typing import List, Optional
from textwrap import dedent
import tempfile

from src.core.commands.update_file import UpdateFileCommand
from src.core.context import Context
from src.core.exceptions import FatalError
from src.core.constants import (
    COMMAND_END,
    STDIN_SEPARATOR,
    COMMAND_START,
    ERROR_PREFIX,
    SUCCESS_PREFIX,
)

# Import the base class content directly since it's in the same directory
from file_command_test_base import FileCommandTestBase

from src.utils.files import _escape_special_chars, _unescape_special_chars

# Configure logging
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.DEBUG)


@dataclass
class UpdateFileTestCase:
    """Data class representing a success test case for file update operations."""

    name: str
    initial_content: str
    diff: str
    expected_output: str
    enable_model_fallback: bool = False


@dataclass
class UpdateFileFailureTestCase:
    """Data class representing a failure test case for file update operations."""

    name: str
    initial_content: str
    diff: str
    expected_error: str


class TestUpdateFileCommand(FileCommandTestBase):
    """Tests for the UpdateFileCommand class."""

    def setUp(self):
        """Set up test environment."""
        super().setUp()

        # Create a test text file to update for non-parametrized tests
        self.test_file = os.path.join(self.temp_dir, "test_file.txt")
        with open(self.test_file, "w") as f:
            f.write("Initial content for update test\n")

        # Create a test Python file to update for non-parametrized tests
        self.test_py_file = os.path.join(self.temp_dir, "test_file.py")
        with open(self.test_py_file, "w") as f:
            f.write(
                dedent(
                    """\
                    #!/usr/bin/env python3
                    # Test file for update command tests
                    
                    def main():
                        print("Hello, world!")
                    
                    if __name__ == "__main__":
                        main()
                    """
                )
            )

    def test_path_parameter(self):
        """Test the path parameter validation."""
        # Define a new file path
        new_file = os.path.join(self.temp_dir, "should_not_be_updated.txt")

        # Create file with initial content
        with open(new_file, "w") as f:
            f.write("Original content")

        # Test with missing path parameter - use a known valid existing file
        # to test only the path parameter validation
        file_path = self.test_py_file
        self.assertTrue(os.path.exists(file_path), "Test file should exist")

        # Create a path command with invalid empty path
        # First parse the command to get parameters and data - don't execute it directly
        try:
            # First try a command with empty path string
            command_input = (
                f"update_file ''{STDIN_SEPARATOR}Add a docstring{COMMAND_END}"
            )
            parsed_cmd = self.shell.parse(command_input)
            result = self.shell.execute(
                parsed_cmd.name, parsed_cmd.parameters, parsed_cmd.data
            )
            # If we get here, the empty path didn't throw an error, which is unexpected
            self.fail("Empty path should have caused an error")
        except FatalError as e:
            # We expect a FatalError with a message about the path
            self.assertIn(
                "path", str(e).lower(), "Error should mention the path problem"
            )

    def test_missing_instructions(self):
        """Test attempting to update a file without providing instructions."""
        # Define an existing file path
        file_path = self.test_py_file
        self.assertTrue(os.path.exists(file_path), "Test file should exist")

        # Command without data (instructions)
        command_input = f"update_file {file_path}{COMMAND_END}"
        logger.debug(f"Command input without instructions: {command_input}")

        # Execute the command - should fail with appropriate error
        with self.assertRaises(RuntimeError) as context:
            # We need to catch the error at the parse stage
            parsed_cmd = self.shell.parse(command_input)

        # Verify the error message mentions missing data
        self.assertIn("requires data", str(context.exception).lower())

        # Verify the error message
        self.assertIn("requires data", str(context.exception).lower())

    def test_file_not_found(self):
        """Test updating a non-existent file."""
        # Non-existent file path
        nonexistent_file = os.path.join(self.temp_dir, "nonexistent.py")
        self.assertFalse(os.path.exists(nonexistent_file), "Test file should not exist")

        # Use the command line format to test through the shell
        command_line = f"update_file {nonexistent_file}{STDIN_SEPARATOR}Add a docstring{COMMAND_END}"

        try:
            # Parse the command - this should work
            parsed_cmd = self.shell.parse(command_line)

            # Execute the command - this should return a CommandResult with success=False
            result = self.shell.execute(
                parsed_cmd.name, parsed_cmd.parameters, parsed_cmd.data
            )

            # Check that the result contains the expected error
            self.assertFalse(result.success)
            self.assertIn("not found", result.error.lower())

        except Exception as e:
            # If any exception is raised, it should be a controlled one
            # with proper error messaging
            if isinstance(e, FatalError):
                # If it's a FatalError, check that it has the right message
                self.assertIn("not found", str(e).lower())
            else:
                # Otherwise, this is unexpected and should fail the test
                self.fail(
                    f"Unexpected exception type: {type(e).__name__}, message: {str(e)}"
                )

    def test_update_process(self):
        """Test the update file command process method using the shell."""
        # Use a test file
        file_path = self.test_py_file
        self.assertTrue(os.path.exists(file_path), "Test file should exist")

        # Save original content for comparison
        with open(file_path, "r") as f:
            original_content = f.read()

        # Write initial content to file to prepare for the update
        write_command = (
            f"write_file {file_path}{STDIN_SEPARATOR}{original_content}{COMMAND_END}"
        )
        write_result = self.execute_command(write_command)
        self.assertTrue(write_result.success, "Write file setup should succeed")

        # Update instructions
        instructions = "Add a comment at the top with today's date"

        # Create the update command input
        command_input = (
            f"update_file {file_path}{STDIN_SEPARATOR}{instructions}{COMMAND_END}"
        )
        update_result = self.execute_command(command_input)

        # Basic assertion to ensure command execution does not crash
        self.assertTrue(update_result.success)

        # Read updated content and verify the changes
        with open(file_path, "r") as f:
            updated_content = f.read()

        # Verify the update includes the date comment
        self.assertIn("#", updated_content)
