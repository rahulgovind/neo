"""
Unit tests for the WriteFileCommand class.

This test validates the WriteFileCommand functionality:
1. Creating new files in the test environment
2. Overwriting existing files
3. Creating necessary parent directories
4. Testing error conditions
"""

import os
import unittest
import logging
from pathlib import Path

from src.core.commands.write_file import WriteFileCommand
from src.core.exceptions import FatalError
from src.core.constants import COMMAND_END, COMMAND_START, STDIN_SEPARATOR
from src.utils.command_builder import CommandBuilder
from tests.file_command_test_base import FileCommandTestBase

# Configure logging
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.DEBUG)


class TestWriteFileCommand(FileCommandTestBase):
    """Tests for the WriteFileCommand class."""
    
    def test_create_new_file(self):
        """Test creating a new file."""
        # Define a new file path
        new_file = os.path.join(self.temp_dir, "new_file.py")
        self.assertFalse(os.path.exists(new_file), "Test file should not exist before the test")
        
        # File content to write
        content = """#!/usr/bin/env python3
# New test file

def hello():
    # This is a test function
    return "Hello, world!"
"""
        
        # Use the execute_command helper to run the command
        command_input = f"write_file {new_file}{STDIN_SEPARATOR}{content}{COMMAND_END}"
        logger.debug(f"Command input: {command_input}")
        
        result = self.execute_command(command_input)
        
        # Check that the command was successful
        self.assertTrue(result.success)
        
        # Verify the file was created
        self.assertTrue(os.path.exists(new_file), "File should have been created")
        
        # Verify the file has the correct content
        with open(new_file, 'r') as f:
            file_content = f.read()
            self.assertEqual(file_content, content)
        
        # Check the result contains expected lines added info
        self.assertIn("SUCCESS", result.result)
        self.assertIn("+6", result.result)  # 6 lines added
        self.assertIn("-0", result.result)  # 0 lines deleted
    
    def test_overwrite_existing_file(self):
        """Test overwriting an existing file."""
        # File should already exist from setup
        self.assertTrue(os.path.exists(self.test_py_file), "Test file should exist")
        
        # New content to write
        new_content = """# Completely replaced content
print("File was overwritten")
"""
        
        # Use the execute_command helper to run the command
        command_input = f"write_file {self.test_py_file}{STDIN_SEPARATOR}{new_content}{COMMAND_END}"
        logger.debug(f"Command input: {command_input}")
        
        result = self.execute_command(command_input)
        
        # Check that the command was successful
        self.assertTrue(result.success)
        
        # Verify the file has the updated content
        with open(self.test_py_file, 'r') as f:
            file_content = f.read()
            self.assertEqual(file_content, new_content)
        
        # Check result contains expected lines info (original file had more lines)
        self.assertIn("SUCCESS", result.result)
        # Don't check exact numbers since the test file content may change
        self.assertRegex(result.result, r'\+\d+')  # Some lines added
        self.assertRegex(result.result, r'\-\d+')  # Some lines deleted
    
    def test_create_file_in_new_directory(self):
        """Test creating a file in a new directory structure."""
        # Define a path with multiple directory levels that don't exist
        new_dir_path = os.path.join(self.temp_dir, "new_dir", "nested_dir")
        new_file = os.path.join(new_dir_path, "nested_file.txt")
        
        self.assertFalse(os.path.exists(new_dir_path), "Directory should not exist yet")
        
        # Content to write
        content = "This is a file in a newly created directory structure."
        
        # Get relative path from workspace
        relative_path = os.path.relpath(new_file, self.temp_dir)
        
        # Use the execute_command helper to run the command
        command_input = f"write_file {relative_path}{STDIN_SEPARATOR}{content}{COMMAND_END}"
        logger.debug(f"Command input: {command_input}")
        
        result = self.execute_command(command_input)
        
        # Check that the command was successful
        self.assertTrue(result.success)
        
        # Verify the directory structure was created
        self.assertTrue(os.path.exists(new_dir_path), "Directory structure should have been created")
        self.assertTrue(os.path.exists(new_file), "File should have been created")
        
        # Verify the file has the correct content
        with open(new_file, 'r') as f:
            file_content = f.read()
            self.assertEqual(file_content, content)
    
    def test_missing_data(self):
        """Test attempting to write a file without providing content data."""
        # Define a new file path
        new_file = os.path.join(self.temp_dir, "should_not_be_created.txt")
        
        # Command without data
        command_input = f"write_file {new_file}{COMMAND_END}"
        logger.debug(f"Command input without data: {command_input}")
        
        # Execute the command and expect a FatalError
        with self.assertRaises(FatalError) as context:
            self.execute_command(command_input)
        
        # Check that we got an appropriate error message
        self.assertIn("content", str(context.exception).lower())
        
        # Verify the file was not created
        self.assertFalse(os.path.exists(new_file), "File should not have been created")
    
    def test_missing_path(self):
        """Test attempting to write a file without providing a path."""
        # Command without path but with data
        command_input = f"write_file{STDIN_SEPARATOR}Some content{COMMAND_END}"
        logger.debug(f"Command input without path: {command_input}")
        
        # Execute the command and expect a FatalError or ValueError
        with self.assertRaises((FatalError, ValueError, SystemExit)) as context:
            # We can't use execute_command directly as it will catch and ignore SystemExit
            # Handle both types of errors (FatalError or SystemExit from argparse)
            parsed_cmd = self.shell.parse(command_input)
        
        # Don't check for specific error message as it could be coming from different sources
