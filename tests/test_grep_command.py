"""
Unit tests for the GrepCommand class.

This test validates the GrepCommand functionality:
1. Setting up a temporary test environment
2. Creating test files with known content
3. Testing search with various parameters 
4. Cleaning up the test environment
"""

import os
import unittest
import tempfile
import shutil
import logging
from pathlib import Path
from typing import Dict, Any

from src.core.command import Command
from src.core.commands.grep import GrepCommand
from src.core.exceptions import FatalError
from src.core import context
from src.core.context import Context
from src.core.shell import Shell
from src.core.constants import COMMAND_END
from src.utils.command_builder import CommandBuilder

# Configure logging
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.DEBUG)


class TestGrepCommand(unittest.TestCase):
    """Tests for the GrepCommand class."""
    
    def setUp(self):
        """Set up a temporary test environment."""
        # Create a temporary directory
        self.temp_dir = tempfile.mkdtemp()
        
        # Create a test file with known content
        self.test_py_file = os.path.join(self.temp_dir, "test_file.py")
        with open(self.test_py_file, "w") as f:
            f.write("""#!/usr/bin/env python3
# Test file for GrepCommand tests

import os
import sys
from typing import List, Dict

def main():
    \"\"\"Main function that does something.\"\"\"
    print("Hello, world!")
    
    # Process some data
    data = {
        "key1": "value1",
        "key2": "value2",
    }
    
    for key, value in data.items():
        print(f"{key}: {value}")

# Helper function for processing
def _process_data(data: Dict) -> List:
    \"\"\"Internal function to process data.\"\"\"
    return [f"{k}={v}" for k, v in data.items()]

if __name__ == "__main__":
    main()
""")

        # Create a text file
        self.test_txt_file = os.path.join(self.temp_dir, "test_file.txt")
        with open(self.test_txt_file, "w") as f:
            f.write("""This is a test file with some text content.
It has multiple lines.
Some lines contain the word 'test'.
Others don't.
Test with mixed case.
""")

        # Create a file in a subdirectory
        subdir = os.path.join(self.temp_dir, "subdir")
        os.makedirs(subdir)
        self.subdir_file = os.path.join(subdir, "subdir_file.py")
        with open(self.subdir_file, "w") as f:
            f.write("""
# File in subdirectory
def test_function():
    \"\"\"Test function in subdirectory.\"\"\"
    return "test"
""")
        
        # Create a temporary test session ID
        self.test_session_id = "test_grep_session"
        
        # Create a context with our temp directory as workspace
        self.ctx = context.Context.builder()\
            .session_id(self.test_session_id)\
            .workspace(self.temp_dir)\
            .initialize()
        
        # Create a shell instance (GrepCommand is already registered as a built-in command)
        self.shell = self.ctx.shell
    
    def tearDown(self):
        """Clean up the test environment."""
        # Remove temporary directory
        shutil.rmtree(self.temp_dir)
    
    def test_basic_search(self):
        """Test basic search functionality."""
        # Verify test files exist
        logger.debug(f"Checking if test files exist - py file: {os.path.exists(self.test_py_file)}, txt file: {os.path.exists(self.test_txt_file)}")
        logger.debug(f"Test directory contents: {os.listdir(self.temp_dir)}")
        
        # Use the shell.parse method to parse the command string
        command_input = f"grep \"import\" {self.temp_dir}{COMMAND_END}"
        logger.debug(f"Command input: {command_input}")
        
        # Get the command template to examine parameters
        cmd = self.shell.get_command("grep")
        logger.debug(f"Command parameters: {[p.name for p in cmd.template().parameters]}")
        
        # Parse the command
        parsed_cmd = self.shell.parse(command_input)
        logger.debug(f"Parsed command: {parsed_cmd}")
        
        # Execute the parsed command
        result = self.shell.execute(
            parsed_cmd.name,
            parsed_cmd.parameters,
            parsed_cmd.data
        )
        logger.debug(f"Command result success: {result.success}")
        logger.debug(f"Command result: {result.result}")
        
        # Check that the command was successful
        self.assertTrue(result.success)
        
        # Should find 'import' in the python file
        self.assertIn("import os", result.result)
        self.assertIn("import sys", result.result)
        
        # But not in the text file
        self.assertNotIn("test_file.txt", result.result)
        
        # Also verify the same behavior using the Command object directly
        grep_cmd = GrepCommand()
        cmd_args = {
            "pattern": "import",
            "path": self.temp_dir
        }
        direct_result = grep_cmd.process(self.ctx, cmd_args)
        self.assertIn("import os", direct_result)
    
    def test_file_pattern_filter(self):
        """Test filtering by file pattern."""
        # Verify test files exist
        logger.debug(f"Checking if test files exist - py file: {os.path.exists(self.test_py_file)}, txt file: {os.path.exists(self.test_txt_file)}")
        
        # Manually create the command string
        command_str = f"grep --file-pattern \"*.txt\" test {self.temp_dir}"
        command_input = f"{command_str}{COMMAND_END}"
        logger.debug(f"File pattern command: {command_input}")
        
        # Parse the command
        parsed_cmd = self.shell.parse(command_input)
        
        # Execute the parsed command
        logger.debug(f"Executing command with parameters: {parsed_cmd.parameters}")
        result = self.shell.execute(
            parsed_cmd.name,
            parsed_cmd.parameters,
            parsed_cmd.data
        )
        logger.debug(f"Command result success: {result.success}")
        logger.debug(f"Command result: {result.result}")
        
        # Check that the command was successful
        self.assertTrue(result.success)
        
        # Should only find 'test' in the text file
        self.assertIn("test_file.txt", result.result)
        
        # But not in the python file
        self.assertNotIn("test_file.py", result.result)
    
    def test_path_filter(self):
        """Test filtering by path."""
        # Get the subdir path relative to temp_dir
        subdir_path = os.path.join(self.temp_dir, "subdir")
        logger.debug(f"Subdirectory path: {subdir_path}")
        logger.debug(f"Files in subdirectory: {os.listdir(subdir_path)}")
        
        # Use the shell.parse method to parse the command string
        command_input = f"grep \"test_function\" {subdir_path}{COMMAND_END}"
        logger.debug(f"Path filter command: {command_input}")
        parsed_cmd = self.shell.parse(command_input)
        
        # Execute the parsed command
        logger.debug(f"Executing command with parameters: {parsed_cmd.parameters}")
        result = self.shell.execute(
            parsed_cmd.name,
            parsed_cmd.parameters,
            parsed_cmd.data
        )
        logger.debug(f"Command result success: {result.success}")
        logger.debug(f"Command result: {result.result}")
        
        # Check that the command was successful
        self.assertTrue(result.success)
        
        # Should find the function in the subdirectory
        self.assertIn("subdir_file.py", result.result)
        self.assertIn("def test_function", result.result)
        
        # But not in the main directory
        self.assertNotIn("test_file.py", result.result)
    
    def test_case_insensitive(self):
        """Test case-insensitive search."""
        # Verify txt test file exists
        logger.debug(f"Checking if txt file exists: {os.path.exists(self.test_txt_file)}")
        with open(self.test_txt_file, 'r') as f:
            txt_content = f.read()
        logger.debug(f"Test txt file contents:\n{txt_content}")
        
        # Use the shell.parse method to parse the command string
        # Use a pattern that actually exists in the test_file.txt in lowercase
        command_input = f"grep --ignore-case --file-pattern \"*.txt\" \"TEST\" {self.temp_dir}{COMMAND_END}"
        logger.debug(f"Case insensitive command: {command_input}")
        parsed_cmd = self.shell.parse(command_input)
        
        # Execute the parsed command
        logger.debug(f"Executing command with parameters: {parsed_cmd.parameters}")
        result = self.shell.execute(
            parsed_cmd.name,
            parsed_cmd.parameters,
            parsed_cmd.data
        )
        logger.debug(f"Command result success: {result.success}")
        logger.debug(f"Command result: {result.result}")
        
        # Check that the command was successful
        self.assertTrue(result.success)
        
        # Should find both 'test' and 'Test' in the text file
        self.assertIn("Test", result.result)
        self.assertIn("Test with mixed case", result.result)
    
    def test_context_lines(self):
        """Test showing context lines around matches."""
        # Verify test python file exists
        logger.debug(f"Checking if python file exists: {os.path.exists(self.test_py_file)}")
        with open(self.test_py_file, 'r') as f:
            py_content = f.read()[:200]
        logger.debug(f"Test python file head:\n{py_content}")
        
        # Use the shell.parse method to parse the command string
        # Using a numeric context value - search for a string that definitely exists
        command_input = f"grep --context=2 --file-pattern \"*.py\" \"def main\" {self.temp_dir}{COMMAND_END}"
        logger.debug(f"Context lines command: {command_input}")
        parsed_cmd = self.shell.parse(command_input)
        
        # Execute the parsed command
        logger.debug(f"Executing command with parameters: {parsed_cmd.parameters}")
        result = self.shell.execute(
            parsed_cmd.name,
            parsed_cmd.parameters,
            parsed_cmd.data
        )
        logger.debug(f"Command result success: {result.success}")
        logger.debug(f"Command result: {result.result}")
        
        # Check that the command was successful
        self.assertTrue(result.success)
        
        # Should include lines before and after the match
        self.assertIn("def main", result.result)
        # Also verify we get the context lines
        self.assertIn("print(\"Hello, world!\")", result.result)  # Line within context window
        self.assertIn("\"\"\"Main function", result.result)  # Line after
        self.assertIn("from typing", result.result)  # Line before
