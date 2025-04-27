"""
Tests for the file utility functions in src/utils/files.py.

This module tests:
1. File reading with the read function
2. File writing with the write function
3. Diff generation during write operations
"""

import os
import logging
import tempfile
import shutil
import textwrap
import pytest
from typing import Tuple

from src.utils.files import read, write, FileWriteResult, overwrite, FileContent


# Configure logging
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.DEBUG)


class TestFileWrite:
    """Tests for the write function."""

    def setup_method(self):
        """Set up a temporary workspace for file operations."""
        self.temp_dir = tempfile.mkdtemp()
        logger.info(f"Created temporary test directory: {self.temp_dir}")
    
    def teardown_method(self):
        """Clean up the temporary workspace."""
        shutil.rmtree(self.temp_dir)
        logger.info(f"Removed temporary test directory: {self.temp_dir}")
    
    def create_test_file(self, path: str, content: str) -> str:
        """Helper to create a test file with the given content."""
        full_path = os.path.join(self.temp_dir, path)
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        with open(full_path, "w", encoding="utf-8") as f:
            f.write(content)
        return full_path
    
    def test_write_new_file(self):
        """Test writing to a new file with diff generation."""
        # File path
        path = "test_new_file.txt"
        content = "This is a new file.\nWith multiple lines.\nOf content."
        
        # Write the file
        result = write(self.temp_dir, path, content)
        
        # Verify the file was created
        full_path = os.path.join(self.temp_dir, path)
        assert os.path.exists(full_path)
        
        # Read the file to verify content
        with open(full_path, "r", encoding="utf-8") as f:
            file_content = f.read()
        assert file_content == content
        
        # Check the FileWriteResult
        assert isinstance(result, FileWriteResult)
        assert result.path == path
        assert result.content == content
        assert result.lines_added == 3
        assert result.lines_deleted == 0
        assert not result.file_existed
        
        # Get the first part of diff output (first 6 lines) for verification
        diff_first_lines = "\n".join(result.diff.splitlines()[:6])
        
        # Verify the diff with exact content match
        expected_diff = textwrap.dedent("""
            --- a/test_new_file.txt
            +++ b/test_new_file.txt
            @@ -0,0 +1,3 @@
            +This is a new file.
            +With multiple lines.
            +Of content.
        """).strip()
        
        assert diff_first_lines == expected_diff, "Diff content does not match expected output"
    
    def test_write_existing_file(self):
        """Test overwriting an existing file with diff generation."""
        # File path
        path = "test_existing_file.txt"
        original_content = "Original content.\nSecond line.\nThird line."
        new_content = "New content.\nModified line.\nThird line."
        
        # Create the file first
        self.create_test_file(path, original_content)
        
        # Write the updated content
        result = write(self.temp_dir, path, new_content)
        
        # Verify the file was updated
        full_path = os.path.join(self.temp_dir, path)
        with open(full_path, "r", encoding="utf-8") as f:
            file_content = f.read()
        assert file_content == new_content
        
        # Check the FileWriteResult
        assert isinstance(result, FileWriteResult)
        assert result.path == path
        assert result.content == new_content
        assert result.lines_added == 3
        assert result.lines_deleted == 3
        assert result.file_existed
        
        # Split diff into lines for verification
        diff_lines = result.diff.splitlines()
        
        # Verify diff header with exact content match
        expected_header = textwrap.dedent("""
            --- a/test_existing_file.txt
            +++ b/test_existing_file.txt
        """).strip()
        
        actual_header = "\n".join(diff_lines[:2])
        assert actual_header == expected_header, "Diff header does not match expected format"
        
        # Extract lines from diff in a structured way
        diff_content = {
            "added": [line for line in diff_lines if line.startswith("+") and not line.startswith("++")],
            "removed": [line for line in diff_lines if line.startswith("-") and not line.startswith("---")],
            "unchanged": [line.strip() for line in diff_lines if not line.startswith("+") and 
                         not line.startswith("-") and line.strip() and 
                         not line.startswith("@")]
        }
        
        # Define expected content and verify presence
        expected_content = {
            "added": ["+New content.", "+Modified line."],
            "removed": ["-Original content.", "-Second line."],
            "unchanged": ["Third line."]
        }
        
        # Verify each category of content
        for expected_line in expected_content["added"]:
            assert expected_line in diff_content["added"], f"Missing expected added line: {expected_line}"
            
        for expected_line in expected_content["removed"]:
            assert expected_line in diff_content["removed"], f"Missing expected removed line: {expected_line}"
            
        for expected_line in expected_content["unchanged"]:
            assert expected_line in diff_content["unchanged"], f"Missing expected unchanged line: {expected_line}"
    
    def test_write_with_new_directories(self):
        """Test writing to a file in a directory that doesn't exist."""
        # File path with nested directories
        path = "new_dir/nested_dir/test_file.txt"
        content = "File in a new directory.\nWith content."
        
        # Write the file
        result = write(self.temp_dir, path, content)
        
        # Verify the file and directories were created
        full_path = os.path.join(self.temp_dir, path)
        assert os.path.exists(full_path)
        assert os.path.isdir(os.path.dirname(full_path))
        
        # Read the file to verify content
        with open(full_path, "r", encoding="utf-8") as f:
            file_content = f.read()
        assert file_content == content
        
        # Check the FileWriteResult
        assert isinstance(result, FileWriteResult)
        assert result.path == path
        assert result.content == content
        assert result.lines_added == 2
        assert result.lines_deleted == 0
        assert not result.file_existed
        
        # Get the first part of diff output (first 5 lines) for verification
        diff_first_lines = "\n".join(result.diff.splitlines()[:5])
        
        # Verify the diff with exact content match
        expected_diff = textwrap.dedent("""
            --- a/test_file.txt
            +++ b/test_file.txt
            @@ -0,0 +1,2 @@
            +File in a new directory.
            +With content.
        """).strip()
        
        assert diff_first_lines == expected_diff, "Diff content does not match expected output"
    
    def test_write_with_no_changes(self):
        """Test writing the same content to an existing file."""
        # File path
        path = "unchanged_file.txt"
        content = "Unchanged content.\nSecond line.\nThird line."
        
        # Create the file first
        self.create_test_file(path, content)
        
        # Write the same content
        result = write(self.temp_dir, path, content)
        
        # Verify the file exists and content hasn't changed
        full_path = os.path.join(self.temp_dir, path)
        with open(full_path, "r", encoding="utf-8") as f:
            file_content = f.read()
        assert file_content == content
        
        # Check the FileWriteResult
        assert isinstance(result, FileWriteResult)
        assert result.path == path
        assert result.content == content
        assert result.lines_added == 3
        assert result.lines_deleted == 3
        assert result.file_existed
        
        # For unchanged files, either difflib will generate no meaningful diff
        # or it will show context lines but no actual changes
        
        # Extract and categorize diff content in a structured way
        diff_content = self._analyze_diff(result.diff)
        
        # Verify no content changes with clearer error messages
        assert not diff_content["added"], f"Diff should not contain added lines, but found: {diff_content['added']}"
        assert not diff_content["removed"], f"Diff should not contain removed lines, but found: {diff_content['removed']}"
        
    def _analyze_diff(self, diff_text):
        """Helper method to analyze diff content into structured categories."""
        diff_lines = diff_text.splitlines()
        
        return {
            "header": [line for line in diff_lines if line.startswith("---") or line.startswith("+++") or line.startswith("@@")],
            "added": [line for line in diff_lines if line.startswith("+") and not line.startswith("++")],
            "removed": [line for line in diff_lines if line.startswith("-") and not line.startswith("---")],
            "unchanged": [line.strip() for line in diff_lines if not line.startswith("+") and 
                         not line.startswith("-") and line.strip() and 
                         not line.startswith("@")]
        }
