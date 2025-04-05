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
        
    def test_from_parameter(self):
        """Test reading from a specific line."""
        # Read from line 5
        command_input = f"read_file {self.test_py_file} --from 5{COMMAND_END}"
        result = self.execute_command(command_input)
        
        # Check that the command was successful
        self.assertTrue(result.success)
        
        # Check that we read from line 5
        lines = result.result.split('\n')
        if lines[0].strip().startswith("..."):
            lines = lines[1:]  # Remove truncation indicator
        
        # First line should be line 5
        self.assertTrue(lines[0].strip().startswith("5"))
        self.assertIn("import sys", lines[0])
        
        # Should not contain earlier lines
        self.assertNotIn("#!/usr/bin/env python3", result.result)
        
    def test_until_parameter(self):
        """Test reading until a specific line."""
        # Read until line 7
        command_input = f"read_file {self.test_py_file} --until 7{COMMAND_END}"
        result = self.execute_command(command_input)
        
        # Check that the command was successful
        self.assertTrue(result.success)
        
        # Check that we read until line 7
        self.assertIn("1 #!/usr/bin/env python3", result.result)
        self.assertIn("5 import sys", result.result) 
        self.assertIn("6 from typing import List, Dict", result.result)
        # Should not contain later lines
        self.assertNotIn("def main():", result.result)
        
    def test_from_until_parameters(self):
        """Test reading from a specific line until a specific line."""
        # Read from line 8 until line 11
        command_input = f"read_file {self.test_py_file} --from 8 --until 11{COMMAND_END}"
        result = self.execute_command(command_input)
        
        # Check that the command was successful
        self.assertTrue(result.success)
        
        # Check that we read the specified range
        lines = result.result.split('\n')
        if lines[0].strip().startswith("..."):
            lines = lines[1:]  # Remove truncation indicator
        
        self.assertIn("8 def main():", lines[0])
        self.assertIn('9     """Main function that does something."""', lines[1])
        self.assertIn('10     print("Hello, world!")', lines[2])
        # Should not contain lines outside the range
        self.assertNotIn("import sys", result.result)
        self.assertNotIn("data = {", result.result)
        
    def test_negative_line_indices(self):
        """Test reading with negative line indices."""
        # Read last 5 lines
        command_input = f"read_file {self.test_py_file} --from -5{COMMAND_END}"
        result = self.execute_command(command_input)
        
        # Check that the command was successful
        self.assertTrue(result.success)
        
        # Should contain the last 5 lines
        self.assertIn('24     return [f"{k}={v}" for k, v in data.items()]', result.result)
        self.assertIn('26 if __name__ == "__main__":', result.result)
        self.assertIn('27     main()', result.result)
        # Should not contain earlier lines
        self.assertNotIn("def main():", result.result)
        
    def test_limit_parameter(self):
        """Test limiting the number of lines read."""
        # Read with a limit of 3 lines
        command_input = f"read_file {self.test_py_file} --limit 3{COMMAND_END}"
        result = self.execute_command(command_input)
        
        # Check that the command was successful
        self.assertTrue(result.success)
        
        # Check that we limit the number of lines appropriately
        lines = result.result.split('\n')
        if lines[-1] == '':
            lines = lines[:-1]  # Remove empty trailing line if present
        
        # First verify expected content is included
        self.assertIn("1 #!/usr/bin/env python3", result.result)
        self.assertIn("2 # Test file for file command tests", result.result)
        self.assertIn("3 ", result.result)  # Line 3 should be included (even if blank)
        
        # Verify line limit is enforced - should not contain content beyond the limit
        self.assertNotIn("import sys", result.result)
        self.assertNotIn("from typing", result.result)
        
        # Make sure there aren't too many lines (allowing for a truncation indicator)
        self.assertLessEqual(len(lines), 4)  # 3 content lines + possibly 1 truncation indicator
        
    def test_unlimited_reading(self):
        """Test reading entire file without line limit."""
        # Read with unlimited lines (limit = -1)
        command_input = f"read_file {self.test_py_file} --limit -1{COMMAND_END}"
        result = self.execute_command(command_input)
        
        # Check that the command was successful
        self.assertTrue(result.success)
        
        # Check that we read the entire file
        self.assertIn("1 #!/usr/bin/env python3", result.result)
        self.assertIn("8 def main():", result.result)
        self.assertIn('10     print("Hello, world!")', result.result)
        self.assertIn('26 if __name__ == "__main__":', result.result)
        self.assertIn('27     main()', result.result)
        
        # Count lines to ensure we got everything
        with open(self.test_py_file, 'r') as f:
            file_lines = f.readlines()
            
        # Verify key parts of the file are present
        # Instead of checking exact format (which can vary with indentation),
        # verify that key content from each line exists somewhere in the result
        for i, line in enumerate(file_lines, 1):
            line_content = line.strip()
            if line_content and not line_content.isspace():  # Skip empty or whitespace-only lines
                # Just check that the content exists somewhere in the output
                self.assertIn(line_content, result.result, 
                              f"Line {i} content missing from output")
