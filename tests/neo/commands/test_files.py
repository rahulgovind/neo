"""
Unit tests for file-related functionality.

This module tests underlying file operation functionality:
1. FileContent class and utilities
2. Read operations and formatting
"""

import os
import tempfile
import unittest

from src.utils.files import FileContent, read



class TestFileContent(unittest.TestCase):
    """Unit tests for FileContent class and read function."""

    def setUp(self):
        """Set up test fixtures before each test method."""
        # Create a temporary file for testing
        self.temp_dir = tempfile.mkdtemp()
        self.test_file_path = os.path.join(self.temp_dir, "test_file.txt")
        
        # Create a test file with multiple lines
        with open(self.test_file_path, "w", encoding="utf-8") as f:
            f.write("Line 1\nLine 2\nLine 3\nLine 4\nLine 5\n")
    
    def tearDown(self):
        """Clean up after each test method."""
        # Remove the temporary directory and its contents
        if os.path.exists(self.temp_dir):
            import shutil
            shutil.rmtree(self.temp_dir)
    
    def test_read_returns_filecontent(self):
        """Test that read function returns a FileContent object."""
        result = read(self.test_file_path)
        self.assertIsInstance(result, FileContent)
        # The file has 5 lines plus a final newline which splits into 6 lines
        self.assertEqual(result.line_count, 6)
        self.assertEqual(len(result.lines), 6)
    
    def test_read_with_line_numbers(self):
        """Test that FileContent correctly formats with line numbers."""
        result = read(self.test_file_path)
        formatted = result.format_with_line_numbers()
        self.assertIn("1:Line 1", formatted)
        self.assertIn("5:Line 5", formatted)
    
    def test_read_without_line_numbers(self):
        """Test that FileContent correctly formats without line numbers."""
        result = read(self.test_file_path)
        formatted = result.format_without_line_numbers()
        self.assertIn("Line 1", formatted)
        self.assertNotIn("1:Line 1", formatted)
    
    def test_read_with_range(self):
        """Test that FileContent correctly handles line ranges."""
        result = read(self.test_file_path, from_=2, until=4)
        self.assertEqual(len(result.lines), 3)  # Lines 2-4
        self.assertEqual(result.displayed_range, (1, 4))  # 0-indexed
        
        # Check content of specific lines
        self.assertEqual(result.lines[0], "Line 2")
        self.assertEqual(result.lines[2], "Line 4")
    
    def test_read_nonexistent_file(self):
        """Test that read function raises appropriate exceptions."""
        with self.assertRaises(FileNotFoundError):
            read("/nonexistent/file.txt")
    
    def test_truncation_indicators(self):
        """Test that FileContent correctly shows truncation indicators."""
        # Read only middle lines
        result = read(self.test_file_path, from_=2, until=4)
        formatted = result.format_with_line_numbers()
        
        # Output should contain truncation indicators
        self.assertIn("additional lines", formatted)

    def test_string_representation(self):
        """Test that FileContent string representation includes line numbers."""
        result = read(self.test_file_path)
        string_repr = str(result)
        self.assertIn("1:Line 1", string_repr)
        
    def test_limit_parameter(self):
        """Test limiting the number of lines read."""
        # Read only 2 lines
        result = read(self.test_file_path, limit=2)
        self.assertEqual(len(result.lines), 2)
        self.assertEqual(result.lines[0], "Line 1")
        self.assertEqual(result.lines[1], "Line 2")
        
    def test_negative_line_indices(self):
        """Test reading with negative line indices."""
        # Read last 3 lines
        result = read(self.test_file_path, from_=-3)
        self.assertEqual(len(result.lines), 3)
        self.assertEqual(result.lines[0], "Line 4")
        self.assertEqual(result.lines[1], "Line 5")
        self.assertEqual(result.lines[2], "")  # Final newline creates empty line


if __name__ == "__main__":
    unittest.main()
