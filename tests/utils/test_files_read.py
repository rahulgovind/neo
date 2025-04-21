import unittest
import os
import tempfile

from src.utils.files import read, FileContent


class TestFilesReadFunction(unittest.TestCase):
    """Unit tests for the read function in files.py."""

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
    
    def test_read_function_returns_filecontent(self):
        """Test that read function now returns a FileContent object."""
        result = read(self.test_file_path)
        self.assertIsInstance(result, FileContent)
        
        # Verify core attributes are set correctly
        self.assertIsNotNone(result.content)
        self.assertIsNotNone(result.lines)
        self.assertIsNotNone(result.line_count)
        self.assertIsNotNone(result.displayed_range)
    
    def test_formatting_with_line_numbers(self):
        """Test that the FileContent can format with line numbers."""
        result = read(self.test_file_path)
        formatted = result.format_with_line_numbers()
        
        # Should have line numbers
        for i, line in enumerate(["Line 1", "Line 2", "Line 3", "Line 4", "Line 5"], 1):
            self.assertIn(f"{i}:{line}", formatted)
    
    def test_formatting_without_line_numbers(self):
        """Test that the FileContent can format without line numbers."""
        result = read(self.test_file_path)
        formatted = result.format_without_line_numbers()
        
        # Should contain content without line numbers
        self.assertIn("Line 1", formatted)
        self.assertIn("Line 2", formatted)
        
        # Should NOT have the line number format
        self.assertNotIn("1:Line", formatted)
    
    def test_error_handling(self):
        """Test that read function properly raises exceptions for errors."""
        # Should raise FileNotFoundError for nonexistent file
        with self.assertRaises(FileNotFoundError):
            read("/nonexistent/file.txt")
    
    def test_with_line_range(self):
        """Test reading specific line ranges."""
        result = read(self.test_file_path, from_=2, until=4)
        
        # Should contain only the specified range
        self.assertEqual(len(result.lines), 3)  # Lines 2-4
        self.assertEqual(result.displayed_range[0], 1)  # 0-indexed
        self.assertEqual(result.displayed_range[1], 4)  # exclusive
        self.assertIn("Line 2", result.lines[0])
        self.assertIn("Line 4", result.lines[2])
        
        # Calculate if truncation should be shown in formatted output
        is_truncated_start = result.displayed_range[0] > 0
        is_truncated_end = result.displayed_range[1] < result.line_count
        
        # Verify truncation is correctly calculated
        self.assertTrue(is_truncated_start)
        self.assertTrue(is_truncated_end)



if __name__ == "__main__":
    unittest.main()
