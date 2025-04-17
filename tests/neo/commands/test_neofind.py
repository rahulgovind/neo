"""
Unit tests for the NeoFindCommand class.

This test validates the NeoFindCommand functionality:
1. Setting up a temporary test environment
2. Creating test files and directories with known structure
3. Testing find with name and type parameters
4. Cleaning up the test environment
"""

import os
import unittest
import tempfile
import shutil
import logging
from typing import Dict

from src.neo.commands.find import NeoFindCommand
from src.neo.exceptions import FatalError
from src.neo.session import Session
from src.neo.core.constants import COMMAND_END

# Configure logging
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.DEBUG)


class TestNeoFindCommand(unittest.TestCase):
    """Tests for the NeoFindCommand class."""

    def _create_file_structure(self, base_dir: str, structure: Dict) -> None:
        """Create a file structure from a dictionary specification.

        Args:
            base_dir: The base directory to create the structure in
            structure: A dictionary specifying the structure. Keys represent file/directory names,
                      values are either strings (file contents) or dictionaries (subdirectories)
        """
        for name, content in structure.items():
            path = os.path.join(base_dir, name)

            if isinstance(content, dict):
                # If content is a dictionary, it's a directory
                os.makedirs(path, exist_ok=True)
                self._create_file_structure(path, content)
            else:
                # Otherwise, it's a file with contents
                with open(path, "w") as f:
                    f.write(content)

    def setUp(self):
        """Set up a temporary test environment."""
        # Create a temporary directory
        self.temp_dir = tempfile.mkdtemp()

        # Define file structure as a dictionary
        file_structure = {
            "test_file.py": "# Test Python file",
            "test_file.txt": "Test text file content",
            "README.md": "# README file",
            "subdir1": {
                "subdir1_file.py": "# File in subdir1",
                "nested": {"nested_file.py": "# File in nested directory"},
            },
            "subdir2": {"subdir2_file.txt": "File in subdir2"},
        }

        # Create the file structure
        self._create_file_structure(self.temp_dir, file_structure)

        # Create a temporary test session ID
        self.test_session_id = "test_neofind_session"

        # Create a context with our temp directory as workspace
        self.ctx = (
            Session.builder()
            .session_id(self.test_session_id)
            .workspace(self.temp_dir)
            .initialize()
        )

        # Create a shell instance
        self.shell = self.ctx.shell

    def tearDown(self):
        """Clean up the test environment."""
        # Remove temporary directory
        shutil.rmtree(self.temp_dir)

    def test_basic_find(self):
        """Test basic find functionality without filters."""
        # Verify test directory exists
        logger.debug(f"Test directory contents: {os.listdir(self.temp_dir)}")

        # Use the shell.parse method to parse the command string
        command_input = f"neofind ."
        logger.debug(f"Command input: {command_input}")

        # Parse the command
        parsed_cmd = self.shell.parse(command_input)
        logger.debug(f"Parsed command: {parsed_cmd}")

        # Execute the parsed command
        result = self.shell.execute(
            parsed_cmd.name, parsed_cmd.parameters, parsed_cmd.data
        )

        # Check that the command was successful
        self.assertTrue(result.success)

        # Should find all files and directories
        self.assertIn("test_file.py", result.content)
        self.assertIn("test_file.txt", result.content)
        self.assertIn("README.md", result.content)
        self.assertIn("subdir1", result.content)
        self.assertIn("subdir2", result.content)

    def test_name_filter(self):
        """Test finding files by name pattern."""
        # Use the shell.parse method to parse the command string
        command_input = f'neofind . --name "*.py"'
        logger.debug(f"Name filter command: {command_input}")
        parsed_cmd = self.shell.parse(command_input)

        # Execute the parsed command
        logger.debug(f"Executing command with parameters: {parsed_cmd.parameters}")
        result = self.shell.execute(
            parsed_cmd.name, parsed_cmd.parameters, parsed_cmd.data
        )
        logger.debug(f"Command result success: {result.success}")
        logger.debug(f"Command result: {result.content}")

        # Check that the command was successful
        self.assertTrue(result.success)

        # Should find only Python files
        self.assertIn("test_file.py", result.content)
        self.assertIn("subdir1_file.py", result.content)
        self.assertIn("nested_file.py", result.content)

        # Should not find non-Python files
        self.assertNotIn("test_file.txt", result.content)
        self.assertNotIn("README.md", result.content)
        self.assertNotIn("subdir2_file.txt", result.content)

    def test_readme_filter(self):
        """Test finding README files."""
        # Use the shell.parse method to parse the command string
        command_input = f'neofind . --name "README*"'
        logger.debug(f"README filter command: {command_input}")
        parsed_cmd = self.shell.parse(command_input)

        # Execute the parsed command
        result = self.shell.execute(
            parsed_cmd.name, parsed_cmd.parameters, parsed_cmd.data
        )

        # Check that the command was successful
        self.assertTrue(result.success)

        # Should find only README files
        self.assertIn("README.md", result.content)

        # Should not find other files
        self.assertNotIn("test_file.py", result.content)
        self.assertNotIn("test_file.txt", result.content)

    def test_type_filter_directories(self):
        """Test finding only directories."""
        # Use the shell.parse method to parse the command string
        command_input = f"neofind . --type d"
        logger.debug(f"Type filter (directories) command: {command_input}")
        parsed_cmd = self.shell.parse(command_input)

        # Execute the parsed command
        result = self.shell.execute(
            parsed_cmd.name, parsed_cmd.parameters, parsed_cmd.data
        )

        # Check that the command was successful
        self.assertTrue(result.success)

        # Should find only directories
        self.assertIn("subdir1", result.content)
        self.assertIn("subdir2", result.content)
        self.assertIn("nested", result.content)

        # Should not find files
        self.assertNotIn("test_file.py", result.content)
        self.assertNotIn("test_file.txt", result.content)
        self.assertNotIn("README.md", result.content)

    def test_type_filter_files(self):
        """Test finding only files."""
        # Use the shell.parse method to parse the command string
        command_input = f"neofind . --type f"
        logger.debug(f"Type filter (files) command: {command_input}")
        parsed_cmd = self.shell.parse(command_input)

        # Execute the parsed command
        result = self.shell.execute(
            parsed_cmd.name, parsed_cmd.parameters, parsed_cmd.data
        )

        # Check that the command was successful
        self.assertTrue(result.success)

        # Should find only files
        self.assertIn("test_file.py", result.content)
        self.assertIn("test_file.txt", result.content)
        self.assertIn("README.md", result.content)
        self.assertIn("subdir1_file.py", result.content)
        self.assertIn("subdir2_file.txt", result.content)
        self.assertIn("nested_file.py", result.content)

        # Should not find directories
        self.assertNotIn("./subdir1\n", result.content)
        self.assertNotIn("./subdir2\n", result.content)
        self.assertNotIn("./subdir1/nested\n", result.content)

    def test_combined_filters(self):
        """Test combining name and type filters."""
        # Use the shell.parse method to parse the command string
        command_input = f'neofind . --type f --name "*.py"'
        logger.debug(f"Combined filters command: {command_input}")
        parsed_cmd = self.shell.parse(command_input)

        # Execute the parsed command
        result = self.shell.execute(
            parsed_cmd.name, parsed_cmd.parameters, parsed_cmd.data
        )

        # Check that the command was successful
        self.assertTrue(result.success)

        # Should find only Python files
        self.assertIn("test_file.py", result.content)
        self.assertIn("subdir1_file.py", result.content)
        self.assertIn("nested_file.py", result.content)

        # Should not find non-Python files or directories
        self.assertNotIn("test_file.txt", result.content)
        self.assertNotIn("README.md", result.content)
        self.assertNotIn("subdir2_file.txt", result.content)
        self.assertNotIn("./subdir1\n", result.content)
        self.assertNotIn("./subdir2\n", result.content)

    def test_specific_path(self):
        """Test finding in a specific subdirectory."""
        # Use the shell.parse method to parse the command string
        command_input = f"neofind ./subdir1"
        logger.debug(f"Specific path command: {command_input}")
        parsed_cmd = self.shell.parse(command_input)

        # Execute the parsed command
        result = self.shell.execute(
            parsed_cmd.name, parsed_cmd.parameters, parsed_cmd.data
        )

        # Check that the command was successful
        self.assertTrue(result.success)

        # Should find files and directories in subdir1
        self.assertIn("subdir1_file.py", result.content)
        self.assertIn("nested", result.content)

        # Should not find files outside subdir1
        self.assertNotIn("test_file.py", result.content)
        self.assertNotIn("test_file.txt", result.content)
        self.assertNotIn("README.md", result.content)
        self.assertNotIn("subdir2_file.txt", result.content)


if __name__ == "__main__":
    unittest.main()
