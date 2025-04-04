"""
Unit tests for the ReadFileCommand class.

This test validates the ReadFileCommand functionality:
1. Reading files from the test environment
2. Testing various parameter options like line numbers
3. Testing error conditions
"""

import os
import unittest
import logging
from pathlib import Path

from src.core.commands.read_file import ReadFileCommand
from src.core.exceptions import FatalError
from src.core.constants import COMMAND_END
from src.utils.command_builder import CommandBuilder
# Import the base class content directly since it's in the same directory
from file_command_test_base import FileCommandTestBase

# Configure logging
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.DEBUG)


class TestReadFileCommand(FileCommandTestBase):
    """Tests for the ReadFileCommand class."""
    
    def test_basic_read(self):
        """Test basic file reading functionality."""
        # Verify test files exist
        logger.debug(f"Checking if test files exist - py file: {os.path.exists(self.test_py_file)}")
        logger.debug(f"Test directory contents: {os.listdir(self.temp_dir)}")
        
        # Use the execute_command helper to run the command
        command_input = f"read_file {self.test_py_file}{COMMAND_END}"
        logger.debug(f"Command input: {command_input}")
        
        result = self.execute_command(command_input)
        
        # Check that the command was successful
        self.assertTrue(result.success)
        
        # Check that we read the file contents
        self.assertIn("#!/usr/bin/env python3", result.result)
        self.assertIn("def main():", result.result)
        self.assertIn("print(\"Hello, world!\")", result.result)
        
        # Verify line numbers ARE included by default
        first_line = result.result.split('\n')[0].strip()
        self.assertRegex(first_line, r'^\d+\s+#!/usr/bin/env python3')
    
    def test_without_line_numbers(self):
        """Test reading without line numbers."""
        # Use the execute_command helper to run the command with the --no-line-numbers flag
        command_input = f"read_file {self.test_py_file} --no-line-numbers{COMMAND_END}"
        logger.debug(f"Command input without line numbers: {command_input}")
        
        result = self.execute_command(command_input)
        
        # Check that the command was successful
        self.assertTrue(result.success)
        
        # Check that we read the file contents
        self.assertIn("#!/usr/bin/env python3", result.result)
        self.assertIn("def main():", result.result)
        
        # Verify line numbers are NOT included
        first_line = result.result.split('\n')[0].strip()
        self.assertEqual(first_line, "#!/usr/bin/env python3")
    
    def test_read_text_file(self):
        """Test reading a text file."""
        # Use the execute_command helper to run the command
        command_input = f"read_file {self.test_txt_file}{COMMAND_END}"
        logger.debug(f"Command input for text file: {command_input}")
        
        result = self.execute_command(command_input)
        
        # Check that the command was successful
        self.assertTrue(result.success)
        
        # Check that we read the text file contents
        self.assertIn("This is a test file with some text content.", result.result)
        self.assertIn("Test with mixed case.", result.result)
    
    def test_read_file_in_subdir(self):
        """Test reading a file in a subdirectory."""
        # Use the execute_command helper to run the command
        command_input = f"read_file {self.subdir_file}{COMMAND_END}"
        logger.debug(f"Command input for subdir file: {command_input}")
        
        result = self.execute_command(command_input)
        
        # Check that the command was successful
        self.assertTrue(result.success)
        
        # Check that we read the file contents
        self.assertIn("File in subdirectory", result.result)
        self.assertIn("def test_function():", result.result)
        self.assertIn("return \"test\"", result.result)
    
    def test_nonexistent_file(self):
        """Test reading a nonexistent file."""
        # Try to read a file that doesn't exist
        nonexistent_file = os.path.join(self.temp_dir, "nonexistent.py")
        self.assertFalse(os.path.exists(nonexistent_file))
        
        command_input = f"read_file {nonexistent_file}{COMMAND_END}"
        logger.debug(f"Command input for nonexistent file: {command_input}")
        
        # Execute the command and expect a FatalError
        with self.assertRaises(FatalError) as context:
            parsed_cmd = self.shell.parse(command_input)
            self.shell.execute(
                parsed_cmd.name,
                parsed_cmd.parameters,
                parsed_cmd.data
            )
        
        # Check that we got an appropriate error message
        self.assertIn("not found", str(context.exception).lower())
