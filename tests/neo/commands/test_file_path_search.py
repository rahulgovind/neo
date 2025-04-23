"""
Unit tests for the FilePathSearch class.

This test validates the FilePathSearch functionality:
1. Setting up a temporary test environment
2. Creating test files and directories with known structure
3. Testing file path search with file pattern and type parameters
4. Cleaning up the test environment
"""

import os
import unittest
import tempfile
import shutil
import logging
from typing import Dict

from src.neo.commands.file_path_search import FilePathSearch
from src.neo.exceptions import FatalError
from src.neo.session import Session
from src.neo.core.constants import COMMAND_END

# Configure logging
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.DEBUG)


class TestFilePathSearch(unittest.TestCase):
    """Tests for the FilePathSearch class."""

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
            "test_file.py": "# Test Python file\nimport os\n# This file contains import os statement",
            "test_file.txt": "Test text file content\nAnother line with important content",
            "README.md": "# README file\nThis is documentation for the project",
            "subdir1": {
                "subdir1_file.py": "# File in subdir1\nimport sys\n# This file has different imports",
                "nested": {"nested_file.py": "# File in nested directory\nimport time\n# This uses time module"},
            },
            "subdir2": {"subdir2_file.txt": "File in subdir2\nNo special content here"},
        }

        # Create the file structure
        self._create_file_structure(self.temp_dir, file_structure)

        # Create a temporary test session ID
        self.test_session_id = "test_file_path_search_session"

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

        # Execute the command directly
        logger.debug("Executing file_path_search command with path '.'")
        result = self.shell.execute(
            "file_path_search", ".", None
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
        # Execute the command directly
        logger.debug("Executing file_path_search command with file pattern '*.py'")
        result = self.shell.execute(
            "file_path_search", ". --file-pattern \"*.py\"", None
        )

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
        # Execute the command directly
        logger.debug("Executing file_path_search command with file pattern 'README*'")
        result = self.shell.execute(
            "file_path_search", ". --file-pattern \"README*\"", None
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
        # Execute the command directly
        logger.debug("Executing file_path_search command with type 'd' for directories")
        result = self.shell.execute(
            "file_path_search", ". --type d", None
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
        # Execute the command directly
        logger.debug("Executing file_path_search command with type 'f' for files")
        result = self.shell.execute(
            "file_path_search", ". --type f", None
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
        # Execute the command directly
        logger.debug("Executing file_path_search command with combined filters")
        result = self.shell.execute(
            "file_path_search", ". --type f --file-pattern \"*.py\"", None
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
        # Execute the command directly
        logger.debug("Executing file_path_search command with specific path './subdir1'")
        result = self.shell.execute(
            "file_path_search", "./subdir1", None
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
        
    def test_content_filter(self):
        """Test finding files containing specific content."""
        # Execute the command directly
        logger.debug("Executing file_path_search command with content filter 'import os'")
        result = self.shell.execute(
            "file_path_search", ". --content 'import os'", None
        )

        # Check that the command was successful
        self.assertTrue(result.success)

        # Should find only files containing 'import os'
        self.assertIn("test_file.py", result.content)
        
        # Should not find files that don't contain 'import os'
        self.assertNotIn("test_file.txt", result.content)
        self.assertNotIn("README.md", result.content)
        self.assertNotIn("subdir1_file.py", result.content)
        self.assertNotIn("nested_file.py", result.content)
        self.assertNotIn("subdir2_file.txt", result.content)
        
        # Test with combined filters
        logger.debug("Executing file_path_search command with file pattern and content filter")
        result = self.shell.execute(
            "file_path_search", ". --file-pattern '*.py' --content 'import'", None
        )
        
        # Check that the command was successful
        self.assertTrue(result.success)
        
        # Should find all Python files containing 'import'
        self.assertIn("test_file.py", result.content)
        self.assertIn("subdir1_file.py", result.content)
        self.assertIn("nested_file.py", result.content)
        
        # Should not find text files or files without 'import'
        self.assertNotIn("test_file.txt", result.content)
        self.assertNotIn("README.md", result.content)
        self.assertNotIn("subdir2_file.txt", result.content)
    
    def test_exclusion_pattern(self):
        """Test exclusion patterns with the --file-pattern parameter."""
        # Execute the command directly
        logger.debug("Executing file_path_search command with exclusion pattern !*.txt")
        result = self.shell.execute(
            "file_path_search", ". --file-pattern '!*.txt'", None
        )

        # Check that the command was successful
        self.assertTrue(result.success)

        # Should find all non-txt files and directories
        self.assertIn("test_file.py", result.content)
        self.assertIn("README.md", result.content)
        self.assertIn("subdir1", result.content)
        self.assertIn("subdir2", result.content)
        self.assertIn("subdir1_file.py", result.content)
        self.assertIn("nested_file.py", result.content)
        
        # Should not find txt files
        self.assertNotIn("test_file.txt", result.content)
        self.assertNotIn("subdir2_file.txt", result.content)
        
        # Test with multiple patterns - include Python files, exclude files in nested directory
        logger.debug("Executing file_path_search command with include and exclude patterns")
        result = self.shell.execute(
            "file_path_search", ". --file-pattern '*.py' --file-pattern '!*nested*'", None
        )
        
        # Check that the command was successful
        self.assertTrue(result.success)
        
        # Should find Python files not in nested directories
        self.assertIn("test_file.py", result.content)
        self.assertIn("subdir1_file.py", result.content)
        
        # Should not find nested files or non-Python files
        self.assertNotIn("nested_file.py", result.content)
        self.assertNotIn("test_file.txt", result.content)
        self.assertNotIn("README.md", result.content)
        self.assertNotIn("subdir2_file.txt", result.content)


if __name__ == "__main__":
    unittest.main()
