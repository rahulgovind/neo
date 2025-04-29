"""
Unit tests for the FilePathSearch class.

This test validates the FilePathSearch functionality:
1. Setting up a temporary test environment
2. Creating test files and directories with known structure
3. Testing file path search with file pattern, type, and content parameters
4. Testing single, multiple, and exclusion file patterns
5. Testing exact output matching
6. Cleaning up the test environment
"""

import os
import re
import logging
import pytest
import tempfile
import shutil
from dataclasses import dataclass
from typing import Dict, Optional, List

from src.neo.commands.file_path_search import FilePathSearch
from src.neo.exceptions import FatalError
from src.neo.session import Session

# Configure logging
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.DEBUG)


@dataclass
class FilePathSearchTestCase:
    """Data class representing a test case for file path search operations."""
    
    name: str
    file_structure: Dict
    command_parameters: str
    expected_output: List[str]  # List of strings that should be in the output
    expected_not_in_output: Optional[List[str]] = None  # List of strings that should NOT be in the output
    
    def __post_init__(self):
        if self.expected_not_in_output is None:
            self.expected_not_in_output = []


@dataclass
class FilePathSearchFailureTestCase:
    """Data class representing an error test case for file path search operations."""
    
    name: str
    file_structure: Optional[Dict]
    command_parameters: str
    expected_error: str

# Helper function to create file structure from dictionary
def create_file_structure(base_dir: str, structure: Dict) -> None:
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
            create_file_structure(path, content)
        else:
            # Otherwise, it's a file with contents
            # Create parent directory if needed
            parent_dir = os.path.dirname(path)
            if parent_dir and not os.path.exists(parent_dir):
                os.makedirs(parent_dir, exist_ok=True)
                
            # Write file content
            with open(path, "w") as f:
                f.write(content)


# Define basic file structure used in all tests
DEFAULT_FILE_STRUCTURE = {
    "test_file.py": "# Test Python file\nimport os\n# This file contains import os statement",
    "test_file.txt": "Test text file content\nAnother line with important content",
    "README.md": "# README file\nThis is documentation for the project",
    "subdir1": {
        "subdir1_file.py": "# File in subdir1\nimport sys\n# This file has different imports",
        "nested": {"nested_file.py": "# File in nested directory\nimport time\n# This uses time module"},
    },
    "subdir2": {"subdir2_file.txt": "File in subdir2\nNo special content here"},
}



# Define test cases
test_cases = [
    # Basic search test with no filters
    FilePathSearchTestCase(
        name="basic_search",
        file_structure=DEFAULT_FILE_STRUCTURE,
        command_parameters=".",
        expected_output=[
            "test_file.py",
            "test_file.txt",
            "README.md",
            "subdir1",
            "subdir2",
            "subdir1/subdir1_file.py",
            "subdir1/nested",
            "subdir1/nested/nested_file.py",
            "subdir2/subdir2_file.txt"
        ],
    ),
    
    # Test with single file pattern
    FilePathSearchTestCase(
        name="single_file_pattern",
        file_structure=DEFAULT_FILE_STRUCTURE,
        command_parameters=". --file-pattern *.py",
        expected_output=[
            "test_file.py",
            "subdir1/subdir1_file.py",
            "subdir1/nested/nested_file.py"
        ],
        expected_not_in_output=[
            "test_file.txt",
            "README.md",
            "subdir2/subdir2_file.txt"
        ],
    ),
    
    # Test with multiple file patterns
    FilePathSearchTestCase(
        name="multiple_file_patterns",
        file_structure=DEFAULT_FILE_STRUCTURE,
        command_parameters=". --file-pattern *.py --file-pattern *.md",
        expected_output=[
            "test_file.py",
            "README.md",
            "subdir1/subdir1_file.py",
            "subdir1/nested/nested_file.py"
        ],
        expected_not_in_output=[
            "test_file.txt",
            "subdir2/subdir2_file.txt"
        ],
    ),
    
    # Test with exclusion file pattern - using *.* then excluding a pattern
    FilePathSearchTestCase(
        name="exclusion_file_pattern",
        file_structure=DEFAULT_FILE_STRUCTURE,
        # Using *.* to include all files, then exclude .txt files
        command_parameters=". --file-pattern '*.*' --file-pattern '!*.txt'",
        expected_output=[
            "test_file.py",
            "README.md",
            "subdir1/subdir1_file.py",
            "subdir1/nested/nested_file.py"
        ],
        expected_not_in_output=[
            "test_file.txt",
            "subdir2/subdir2_file.txt"
        ],
    ),
    
    # Test with multiple patterns including exclusion
    FilePathSearchTestCase(
        name="multiple_with_exclusion",
        file_structure=DEFAULT_FILE_STRUCTURE,
        command_parameters=". --file-pattern *.py --file-pattern !*nested*",
        expected_output=[
            "test_file.py",
            "subdir1/subdir1_file.py"
        ],
        expected_not_in_output=[
            "subdir1/nested/nested_file.py",
            "test_file.txt",
            "README.md",
            "subdir2/subdir2_file.txt"
        ],
    ),
    
    # Test with type filter - only files
    FilePathSearchTestCase(
        name="type_filter_files",
        file_structure=DEFAULT_FILE_STRUCTURE,
        command_parameters=". --type f",
        expected_output=[
            "test_file.py",
            "test_file.txt",
            "README.md",
            "subdir1/subdir1_file.py",
            "subdir1/nested/nested_file.py",
            "subdir2/subdir2_file.txt"
        ],
        expected_not_in_output=[
            "subdir1",
            "subdir2",
            "subdir1/nested"
        ],
    ),
    
    # Test with type filter - only directories
    FilePathSearchTestCase(
        name="type_filter_directories",
        file_structure=DEFAULT_FILE_STRUCTURE,
        command_parameters=". --type d",
        expected_output=[
            "subdir1",
            "subdir2",
            "subdir1/nested"
        ],
        expected_not_in_output=[
            "test_file.py",
            "test_file.txt",
            "README.md",
            "subdir1/subdir1_file.py",
            "subdir1/nested/nested_file.py",
            "subdir2/subdir2_file.txt"
        ],
    ),
    
    # Test with content filter
    FilePathSearchTestCase(
        name="content_filter",
        file_structure=DEFAULT_FILE_STRUCTURE,
        command_parameters=". --content 'import os'",
        expected_output=[
            "test_file.py"
        ],
        expected_not_in_output=[
            "subdir1/subdir1_file.py",
            "subdir1/nested/nested_file.py",
            "test_file.txt",
            "README.md",
            "subdir2/subdir2_file.txt"
        ],
    ),
    
    # Test with content filter and file pattern
    FilePathSearchTestCase(
        name="content_with_file_pattern",
        file_structure=DEFAULT_FILE_STRUCTURE,
        command_parameters=". --content 'import' --file-pattern *.py",
        expected_output=[
            "test_file.py",
            "subdir1/subdir1_file.py",
            "subdir1/nested/nested_file.py"
        ],
        expected_not_in_output=[
            "test_file.txt",
            "README.md",
            "subdir2/subdir2_file.txt"
        ],
    ),
    
    # Test with specific path
    FilePathSearchTestCase(
        name="specific_path",
        file_structure=DEFAULT_FILE_STRUCTURE,
        command_parameters="subdir1",
        expected_output=[
            "subdir1/subdir1_file.py",
            "subdir1/nested",
            "subdir1/nested/nested_file.py"
        ],
        expected_not_in_output=[
            "test_file.py",
            "test_file.txt",
            "README.md",
            "subdir2/subdir2_file.txt"
        ],
    ),
]

# Define error test cases
error_test_cases = [
    # Test with non-existent path
    FilePathSearchFailureTestCase(
        name="nonexistent_path",
        file_structure=DEFAULT_FILE_STRUCTURE,
        command_parameters="nonexistent_directory",
        expected_error="No such file or directory",
    ),
    
    # Test with invalid type parameter
    FilePathSearchFailureTestCase(
        name="invalid_type",
        file_structure=DEFAULT_FILE_STRUCTURE,
        command_parameters=". --type x",
        expected_error="argument --type: invalid choice",
    ),
]


@pytest.mark.parametrize("test_case", test_cases, ids=lambda tc: tc.name)
def test_file_path_search_command(test_case):
    """Test successful file_path_search commands using the defined test cases."""
    # Create a temporary directory for the test
    temp_dir = tempfile.mkdtemp()
    
    try:
        # Create a test session
        ctx = Session.builder().session_id("test_session_id").workspace(temp_dir).initialize()
        
        # Create the file structure
        create_file_structure(temp_dir, test_case.file_structure)
        
        # Execute the command directly
        logger.debug(f"Executing file_path_search command with parameters: {test_case.command_parameters}")
        result = ctx.shell.execute("file_path_search", test_case.command_parameters, None)
        
        # Verify the command executed successfully
        assert result.success, f"Command should execute successfully for test case {test_case.name}. Error: {result.content}"
        
        # Print the result content for debugging
        print(f"\nDEBUG Result content for {test_case.name}:\n{result.content}")
        logger.debug(f"Result content for {test_case.name}:\n{result.content}")
        
        # Split the result into lines for comparing output - preserve all whitespace
        result_lines = [line for line in result.content.split("\n") if line]
        
        # Extract regex patterns and exact string matches
        regex_patterns = [pattern for pattern in test_case.expected_output if pattern.startswith("^")]
        exact_lines = [line for line in test_case.expected_output if not line.startswith("^")]
        
        # Check regex patterns
        for regex_pattern in regex_patterns:
            assert any(
                re.match(regex_pattern, line)
                for line in result_lines
            ), f"Regex pattern '{regex_pattern}' not found in output for test case {test_case.name}"
        
        # For exact string matches, collect all matching lines
        matched_lines = []
        for result_line in result_lines:
            for expected_line in exact_lines:
                if expected_line == result_line or result_line.endswith(expected_line):
                    matched_lines.append(expected_line)
        
        # Sort both lists for accurate comparison
        sorted_matched_lines = sorted(matched_lines)
        sorted_expected_lines = sorted(exact_lines)
        
        # Check if all expected lines are in the matched lines
        assert sorted_matched_lines == sorted_expected_lines, \
            f"Expected lines not found in output for test case {test_case.name}\n" \
            f"Expected: {sorted_expected_lines}\n" \
            f"Found: {sorted_matched_lines}\n" \
            f"Actual output: {result.content}"
        
        # Check that unwanted strings are not in the output
        regex_not_expected = [pattern for pattern in test_case.expected_not_in_output if pattern.startswith("^")]
        exact_not_expected = [line for line in test_case.expected_not_in_output if not line.startswith("^")]
        
        # Check regex patterns that should not be present
        for regex_pattern in regex_not_expected:
            assert not any(
                re.match(regex_pattern, line)
                for line in result_lines
            ), f"Regex pattern '{regex_pattern}' found in output but should not be for test case {test_case.name}"
        
        # Check exact lines that should not be present
        for not_expected_line in exact_not_expected:
            assert not any(
                not_expected_line == line or line.endswith(not_expected_line)
                for line in result_lines
            ), f"Line '{not_expected_line}' found in output but should not be for test case {test_case.name}"
    
    finally:
        # Clean up
        shutil.rmtree(temp_dir)


@pytest.mark.parametrize("test_case", error_test_cases, ids=lambda tc: tc.name)
def test_file_path_search_errors(test_case):
    """Test error conditions in file_path_search commands using the defined error test cases."""
    # Create a temporary directory for the test
    temp_dir = tempfile.mkdtemp()
    
    try:
        # Create a test session
        ctx = Session.builder().session_id("test_session_id").workspace(temp_dir).initialize()
        
        # Create the file structure if provided
        if test_case.file_structure:
            create_file_structure(temp_dir, test_case.file_structure)
        
        # Execute the command directly
        logger.debug(f"Executing file_path_search command with parameters: {test_case.command_parameters}")
        result = ctx.shell.execute("file_path_search", test_case.command_parameters, None)
        
        # Verify the command failed as expected
        assert not result.success, f"Command should fail for error test case {test_case.name}"
        
        # Verify the error message contains the expected text
        if result.content is None:
            # For exceptions that are raised and don't set result.content
            print(f"Warning: result.content is None for test case {test_case.name}")
        else:
            assert (
                test_case.expected_error.lower() in result.content.lower()
            ), f"Error '{test_case.expected_error}' not found in result for test case {test_case.name}: {result.content}"
    
    finally:
        # Clean up
        shutil.rmtree(temp_dir)
