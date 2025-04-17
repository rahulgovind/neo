"""
Unit tests for the NeoGrepCommand class.

This test validates the NeoGrepCommand functionality:
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
from dataclasses import dataclass
from typing import Optional, List

from src.neo.session import Session
from src.neo.exceptions import FatalError

# Configure logging
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.DEBUG)


@dataclass
class NeoGrepTestCase:
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
class NeoGrepFailureTestCase:
    """Data class representing an error test case for grep operations."""

    name: str
    file_content: Optional[str]
    command_parameters: str
    expected_error: str


# Define sample file contents for tests
PYTHON_TEST_CONTENT = '''#!/usr/bin/env python3
# Test file for neogrep command tests

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
    NeoGrepTestCase(
        name="basic_search",
        file_content=PYTHON_TEST_CONTENT,
        command_parameters="import {file_path}",
        expected_output=[
            "import os",
            "import sys",
        ],
    ),
    # Test case-insensitive search
    NeoGrepTestCase(
        name="case_insensitive",
        file_content=TEXT_TEST_CONTENT,
        command_parameters="--ignore-case TEST {file_path}",
        expected_output=[
            "This is a test file",
            "Test with mixed case",
        ],
    ),
    # Test with context lines
    NeoGrepTestCase(
        name="context_lines",
        file_content=PYTHON_TEST_CONTENT,
        command_parameters="--context=2 main {file_path}",
        expected_output=[
            "def main():",
            "Main function that does something",
            "print(\"Hello, world!\")",
        ],
    ),
    # Test with file pattern
    NeoGrepTestCase(
        name="file_pattern",
        file_content=PYTHON_TEST_CONTENT,
        command_parameters="def {file_path}",
        expected_output=[
            "def main",
            "def process_data",
        ],
        expected_not_in_output=[
            "nonexistent",  # Should not match nonexistent text
        ],
    ),
    # Test searching in subdirectory
    NeoGrepTestCase(
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
    NeoGrepFailureTestCase(
        name="nonexistent_file",
        file_content=None,
        command_parameters="pattern {file_path}/nonexistent.txt",
        expected_error="No such file or directory",
    ),
    # Test with invalid context value
    NeoGrepFailureTestCase(
        name="invalid_context",
        file_content=PYTHON_TEST_CONTENT,
        command_parameters="--context=invalid import {file_path}",
        expected_error="Context must be a valid integer",
    ),
]


@pytest.mark.parametrize("test_case", test_cases, ids=lambda tc: tc.name)
def test_neogrep_command(test_case):
    """Test successful neogrep commands using the defined test cases."""
    # Create a temporary directory for the test
    temp_dir = tempfile.mkdtemp()
    
    # Create a test session
    ctx = Session.builder().session_id("test_session_id").workspace(temp_dir).initialize()
    
    # Determine the file path based on the test case name
    file_path = os.path.join(temp_dir, f"{test_case.name}.txt")
    
    # Create any required subdirectories for this test
    if "subdir" in test_case.name:
        subdir_path = os.path.join(temp_dir, "subdir")
        os.makedirs(subdir_path, exist_ok=True)
        file_path = os.path.join(subdir_path, f"{test_case.name}.txt")
    
    # Create the test file with the specified content
    with open(file_path, "w") as f:
        f.write(test_case.file_content)
    
    # Format the command parameters with the actual file path
    formatted_params = test_case.command_parameters.format(file_path=file_path)
    
    # Create and execute the command
    command_input = f"neogrep {formatted_params}"
    
    # Execute the command
    result = ctx.shell.parse_and_execute(command_input)
    
    # Verify the command executed successfully
    assert result.success, f"Command should execute successfully for test case {test_case.name}. Error: {result.content}"
    
    # Check for expected output strings
    for expected_str in test_case.expected_output:
        # Handle regex patterns
        if expected_str.startswith("^"):
            assert any(
                re.match(expected_str, line)
                for line in result.content.split("\n")
                if line
            ), f"Regex pattern '{expected_str}' not found in output for test case {test_case.name}"
        else:
            assert (
                expected_str in result.content
            ), f"Expected string '{expected_str}' not found in output for test case {test_case.name}"
    
    # Check that unwanted strings are not in the output
    for not_expected_str in test_case.expected_not_in_output:
        # Handle regex patterns
        if not_expected_str.startswith("^"):
            assert not any(
                re.match(not_expected_str, line)
                for line in result.content.split("\n")
                if line
            ), f"Regex pattern '{not_expected_str}' found in output but should not be for test case {test_case.name}"
        else:
            assert (
                not_expected_str not in result.content
            ), f"String '{not_expected_str}' found in output but should not be for test case {test_case.name}"
    
    # Clean up
    import shutil
    shutil.rmtree(temp_dir)


@pytest.mark.parametrize("test_case", error_test_cases, ids=lambda tc: tc.name)
def test_neogrep_errors(test_case):
    """Test error conditions in neogrep commands using the defined error test cases."""
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
        
        # Create and execute the command
        command_input = f"neogrep {formatted_params}"
                
        # Execute the command for other error cases
        result = ctx.shell.parse_and_execute(command_input)
        
        # Verify the command failed as expected
        assert not result.success, f"Command should fail for error test case {test_case.name}"
        
        # Verify the error message contains the expected text
        if result.content is None:
            # For exceptions that are raised and don't set result.result
            print(f"Warning: result.result is None for test case {test_case.name}")
        else:
            assert (
                test_case.expected_error.lower() in result.content.lower()
            ), f"Error '{test_case.expected_error}' not found in result for test case {test_case.name}: {result.content}"

    finally:
        # Clean up
        shutil.rmtree(temp_dir)
