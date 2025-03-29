"""
Base class for file-related command tests.

This module provides a common base class for testing file-related commands
with shared test infrastructure for setting up and tearing down a test environment.
"""

import os
import unittest
import tempfile
import shutil
import logging
from pathlib import Path
from typing import Dict, Any

from src.core.command import Command
from src.core.exceptions import FatalError
from src.core import context
from src.core.context import Context
from src.core.shell import Shell
from src.core.constants import COMMAND_END

# Configure logging
logger = logging.getLogger(__name__)


class FileCommandTestBase(unittest.TestCase):
    """Base class for file command tests with common test infrastructure."""
    
    def setUp(self):
        """Set up a temporary test environment."""
        # Create a temporary directory
        self.temp_dir = tempfile.mkdtemp()
        
        # Create a test file with known content
        self.test_py_file = os.path.join(self.temp_dir, "test_file.py")
        with open(self.test_py_file, "w") as f:
            f.write("""#!/usr/bin/env python3
# Test file for file command tests

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
        self.test_session_id = f"test_{self.__class__.__name__.lower()}_session"
        
        # Create a context with our temp directory as workspace
        # Use context manager and save the context
        with context.new_context(session_id=self.test_session_id, workspace=self.temp_dir) as ctx:
            self.ctx = ctx
        
        # Create a shell instance
        self.shell = Shell()
        
        # NOTE: Do not mock the environment or model setup here.
        # Tests that require environment or model interaction should initialize
        # and configure these components as needed within the test method itself.
        
    def tearDown(self):
        """Clean up the test environment."""
        # Clean up thread-local context
        if hasattr(context._thread_local, 'context'):
            delattr(context._thread_local, 'context')
        
        # Remove temporary directory
        shutil.rmtree(self.temp_dir)
    
    def execute_command(self, command_line: str) -> Any:
        """Helper method to execute a command with the shell.
        
        Args:
            command_line: The command line string to execute
            
        Returns:
            The command result
        """
        logger.debug(f"Command input: {command_line}")
        parsed_cmd = self.shell.parse(command_line)
        
        logger.debug(f"Executing command with parameters: {parsed_cmd.parameters}")
        result = self.shell.execute(
            parsed_cmd.name,
            parsed_cmd.parameters,
            parsed_cmd.data
        )
        logger.debug(f"Command result success: {result.success}")
        logger.debug(f"Command result: {result.result}")
        
        return result
