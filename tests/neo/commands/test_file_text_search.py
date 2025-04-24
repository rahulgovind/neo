"""
Unit tests for the FileTextSearch class.

This test validates the FileTextSearch functionality:
1. Searching for patterns in files
2. Testing various parameter options like case sensitivity and file patterns
3. Testing error conditions
"""

import os
import re
import logging
import pytest
import tempfile
import shutil
import argparse
from dataclasses import dataclass
from typing import Optional, List

from src.neo.session import Session
from src.neo.commands.file_text_search import FileTextSearch
from src.neo.exceptions import FatalError

# Configure logging
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.DEBUG)


@dataclass
class FileTextSearchTestCase:
    """Data class representing a test case for grep operations."""

    name: str
    file_content: str
    command_parameters: str
    expected_output: List[str]  # List of strings that should be in the output
    expected_not_in_output: Optional[List[str]] = (
        None  # List of strings that should NOT be in the output
    )

    def __post_init__(self):
        if self.expected_not_in_output is None:
            self.expected_not_in_output = []


@dataclass
class FileTextSearchFailureTestCase:
    """Data class representing an error test case for grep operations."""

    name: str
    file_content: Optional[str]
    command_parameters: str
    expected_error: str


# Define sample file contents for tests
PYTHON_TEST_CONTENT = '''#!/usr/bin/env python3
# Test file for file_text_search command tests

import os
import sys
from typing import Dict, List

def main():
    """Main function that does something."""
    print("Hello, world!")
    
    # Process some data
    data = {
        "name": "Test",
        "value": 42,
        "enabled": True
    }
    
    process_data(data)
    return 0

def process_data(data: Dict) -> List[str]:
    """Process the data and return a list of key-value pairs."""
    # Format key-value pairs
    return [f"{k}={v}" for k, v in data.items()]

if __name__ == "__main__":
    main()
'''

TEXT_TEST_CONTENT = """This is a test file with some text content.
It has multiple lines.
With various content.
Test with mixed case.
And some numbers: 123, 456, 789.
"""

SUBDIR_TEST_CONTENT = """# File in subdirectory

def test_function():
    # This function is for testing
    return "Success"
"""

# Define test cases
test_cases = [
    # Basic search test
    FileTextSearchTestCase(
        name="basic_search",
        file_content=PYTHON_TEST_CONTENT,
        command_parameters="import {file_path}",
        expected_output=[
            "import os",
            "import sys",
        ],
    ),
    # Test case-insensitive search
    FileTextSearchTestCase(
        name="case_insensitive",
        file_content=TEXT_TEST_CONTENT,
        command_parameters="--ignore-case TEST {file_path}",
        expected_output=[
            "This is a test file",
            "Test with mixed case",
        ],
    ),
    # Test with context lines
    FileTextSearchTestCase(
        name="context_lines",
        file_content=PYTHON_TEST_CONTENT,
        command_parameters="--num-context-lines=2 main {file_path}",
        expected_output=[
            "def main():",
            "\"\"\"Main function that does something.\"\"\"",
            "print(\"Hello, world!\")",
        ],
    ),
    # Test with single file pattern
    FileTextSearchTestCase(
        name="single_file_pattern",
        file_content=PYTHON_TEST_CONTENT,
        command_parameters="def {file_path} --file-pattern *.py",
        expected_output=[
            "def main",
            "def process_data"
        ],
        expected_not_in_output=[
            "nonexistent",  # Should not match nonexistent text
        ],
    ),
    # Test with multiple file patterns
    FileTextSearchTestCase(
        name="multiple_file_patterns",
        file_content=PYTHON_TEST_CONTENT,
        command_parameters="def {file_path} --file-pattern *.py --file-pattern *.txt",
        expected_output=[
            "def main",
            "def process_data"
        ],
    ),
    # Test with exclusion file pattern
    FileTextSearchTestCase(
        name="exclusion_file_pattern",
        file_content=PYTHON_TEST_CONTENT,
        command_parameters="def {file_path} --file-pattern !*test*.py",
        expected_output=[
            "def main",
            "def process_data"
        ],
    ),
    # Test searching in subdirectory
    FileTextSearchTestCase(
        name="subdir_search",
        file_content=SUBDIR_TEST_CONTENT,
        command_parameters="test_function {file_path}",
        expected_output=[
            "def test_function():",
        ],
    ),
]

# Define error test cases
error_test_cases = [
    # Test with non-existent file
    FileTextSearchFailureTestCase(
        name="nonexistent_file",
        file_content=None,
        command_parameters="pattern {file_path}/nonexistent.txt",
        expected_error="No such file or directory",
    ),
    # Test with invalid context value
    FileTextSearchFailureTestCase(
        name="invalid_context",
        file_content=PYTHON_TEST_CONTENT,
        command_parameters="--num-context-lines=invalid import {file_path}",
        expected_error="invalid int value",
    ),
]


@pytest.mark.parametrize("test_case", test_cases, ids=lambda tc: tc.name)
def test_file_text_search_command(test_case):
    """Test successful file_text_search commands using the defined test cases."""
    # Create a temporary directory for the test
    temp_dir = tempfile.mkdtemp()
    
    # Create a test session
    ctx = Session.builder().session_id("test_session_id").workspace(temp_dir).initialize()
    
    # Determine the file path based on the test case name - use .py extension for file pattern tests
    if "file_pattern" in test_case.name:
        file_path = os.path.join(temp_dir, f"{test_case.name}.py")
    else:
        file_path = os.path.join(temp_dir, f"{test_case.name}.txt")
    
    # Create directory structure if needed (for any file path)
    dir_path = os.path.dirname(file_path)
    if dir_path:
        os.makedirs(dir_path, exist_ok=True)
    
    # Create the test file with the specified content
    with open(file_path, "w") as f:
        f.write(test_case.file_content)
    
    # Format the command parameters with the actual file path
    formatted_params = test_case.command_parameters.format(file_path=file_path)
    
    # Create direct execute command
    logger.debug(f"Executing file_text_search command with parameters: {formatted_params}")
    
    # Execute the command directly
    result = ctx.shell.execute("file_text_search", formatted_params, None)
    
    # Verify the command executed successfully
    assert result.success, f"Command should execute successfully for test case {test_case.name}. Error: {result.content}"

    # Print the result content for debugging
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
    
    # For exact string matches, check if each expected line is contained in any result line
    # Grep output includes filename and line number before the actual content
    matched_lines = []
    for expected_line in exact_lines:
        for result_line in result_lines:
            # Check if the expected line is a substring of any result line
            if expected_line in result_line:
                matched_lines.append(expected_line)
                break
    
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
            not_expected_line in line
            for line in result_lines
        ), f"Line '{not_expected_line}' found in output but should not be for test case {test_case.name}"
    
    # Clean up
    import shutil
    shutil.rmtree(temp_dir)


@pytest.mark.parametrize("test_case", error_test_cases, ids=lambda tc: tc.name)
def test_file_text_search_errors(test_case):
    """Test error conditions in file_text_search commands using the defined error test cases."""
    # Create a temporary directory for the test
    temp_dir = tempfile.mkdtemp()
    
    try:
        # Create a test session
        ctx = Session.builder().session_id("test_session_id").workspace(temp_dir).initialize()
        
        # Determine the file path
        file_path = os.path.join(temp_dir, f"{test_case.name}.txt")
        
        # Create the test file with appropriate content if provided
        if test_case.file_content is not None:
            with open(file_path, "w") as f:
                f.write(test_case.file_content)
        
        # Format the command parameters with the actual file path
        formatted_params = test_case.command_parameters.format(file_path=file_path)
        
        # Create direct execute command
        logger.debug(f"Executing file_text_search command with parameters: {formatted_params}")
        
        # Execute the command directly for all test cases
        result = ctx.shell.execute("file_text_search", formatted_params, None)
        
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
