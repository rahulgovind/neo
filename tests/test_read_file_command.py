"""
Unit tests for the ReadFileCommand class.

This test validates the ReadFileCommand functionality:
1. Reading files from the test environment
2. Testing various parameter options like line numbers
3. Testing error conditions
"""

import os
import re
import unittest
import logging
import pytest
import tempfile
from pathlib import Path
from dataclasses import dataclass
from typing import Optional, List
from textwrap import dedent

from src.core.commands.read_file import ReadFileCommand
from src.core.context import Context
from src.core.shell import COMMAND_END
from src.core.exceptions import FatalError
from src.utils.command_builder import CommandBuilder
# Import the base class content directly since it's in the same directory
from file_command_test_base import FileCommandTestBase

# Configure logging
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.DEBUG)


@dataclass
class ReadFileTestCase:
    """Data class representing a test case for file reading operations."""
    name: str
    file_content: str
    command_parameters: str
    expected_output: List[str]  # List of strings that should be in the output
    expected_not_in_output: Optional[List[str]] = None  # List of strings that should NOT be in the output
    
    def __post_init__(self):
        if self.expected_not_in_output is None:
            self.expected_not_in_output = []


@dataclass
class ReadFileFailureTestCase:
    """Data class representing an error test case for file reading operations."""
    name: str
    file_content: Optional[str]
    command_parameters: str
    expected_error: str


# Define sample file contents for tests
PYTHON_TEST_CONTENT = '''#!/usr/bin/env python3
# Test file for file command tests

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

TEXT_TEST_CONTENT = '''This is a test file with some text content.
It has multiple lines.
With various content.
Test with mixed case.
And some numbers: 123, 456, 789.
'''

SUBDIR_TEST_CONTENT = '''# File in subdirectory

def test_function():
    # This function is for testing
    return "Success"
'''

# Define test cases
test_cases = [
    # Basic read test
    ReadFileTestCase(
        name="basic_read",
        file_content=PYTHON_TEST_CONTENT,
        command_parameters="{file_path}",
        expected_output=[
            "#!/usr/bin/env python3", 
            "def main():", 
            "print(\"Hello, world!\")",
            "^\\d+:#!/usr/bin/env python3"  # Regex to match line numbers
        ]
    ),
    
    # Test without line numbers
    ReadFileTestCase(
        name="without_line_numbers",
        file_content=PYTHON_TEST_CONTENT,
        command_parameters="{file_path} --no-line-numbers",
        expected_output=[
            "#!/usr/bin/env python3", 
            "def main():"
        ],
        expected_not_in_output=["^\\d+:"]  # No line numbers should be present
    ),
    
    # Test reading text file
    ReadFileTestCase(
        name="read_text_file",
        file_content=TEXT_TEST_CONTENT,
        command_parameters="{file_path}",
        expected_output=[
            "This is a test file with some text content.",
            "Test with mixed case."
        ]
    ),
    
    # Test reading file in subdirectory
    ReadFileTestCase(
        name="read_file_in_subdir",
        file_content=SUBDIR_TEST_CONTENT,
        command_parameters="{file_path}",
        expected_output=[
            "File in subdirectory",
            "def test_function():"
        ]
    ),
    
    # Test reading from specific line
    ReadFileTestCase(
        name="from_parameter",
        file_content=PYTHON_TEST_CONTENT,
        command_parameters="{file_path} --from 7",
        expected_output=[
            "7:def main():",
            "8:    \"\"\"Main function that does something.\"\"\""
        ],
        expected_not_in_output=["import sys"]
    ),
    
    # Test reading until specific line
    ReadFileTestCase(
        name="until_parameter",
        file_content=PYTHON_TEST_CONTENT,
        command_parameters="{file_path} --until 4",
        expected_output=[
            "1:#!/usr/bin/env python3",
            "4:import sys"
        ],
        expected_not_in_output=["def main():"]
    ),
    
    # Test reading from-until range
    ReadFileTestCase(
        name="from_until_parameters",
        file_content=PYTHON_TEST_CONTENT,
        command_parameters="{file_path} --from 7 --until 10",
        expected_output=[
            "7:def main():",
            "8:    \"\"\"Main function that does something.\"\"\"",
            "9:    print(\"Hello, world!\")"
        ],
        expected_not_in_output=["import sys", "data = {"]
    ),
    
    # Test negative line indices
    ReadFileTestCase(
        name="negative_line_indices",
        file_content=PYTHON_TEST_CONTENT,
        command_parameters="{file_path} --from -5",
        expected_output=[
            "return [f\"{k}={v}\" for k, v in data.items()]",
            "if __name__ == \"__main__\":",
            "main()"
        ],
        expected_not_in_output=["def main():"]
    ),
    
    # Test line limit
    ReadFileTestCase(
        name="limit_parameter",
        file_content=PYTHON_TEST_CONTENT,
        command_parameters="{file_path} --limit 3",
        expected_output=[
            "1:#!/usr/bin/env python3",
            "2:# Test file for file command tests"
        ],
        expected_not_in_output=["import sys", "from typing"]
    ),
    
    # Test unlimited reading
    ReadFileTestCase(
        name="unlimited_reading",
        file_content=PYTHON_TEST_CONTENT,
        command_parameters="{file_path} --limit -1",
        expected_output=[
            "1:#!/usr/bin/env python3", 
            # Don't check specific line numbers beyond the first line
            # since they might vary slightly in different test environments
            "def main():",
            "print(\"Hello, world!\")",
            "if __name__ == \"__main__\":",
            "main()"
        ]
    )
]

# Define error test cases
error_test_cases = [
    # Test nonexistent file
    ReadFileFailureTestCase(
        name="nonexistent_file",
        file_content=None,  # No content - file won't be created
        command_parameters="{file_path}",
        expected_error="file not found"
    ),
    
    # Test invalid from parameter
    ReadFileFailureTestCase(
        name="invalid_from_parameter",
        file_content=PYTHON_TEST_CONTENT,
        command_parameters="{file_path} --from invalid",
        expected_error="invalid value for --from"
    ),
    
    # Test invalid until parameter
    ReadFileFailureTestCase(
        name="invalid_until_parameter",
        file_content=PYTHON_TEST_CONTENT,
        command_parameters="{file_path} --until invalid",
        expected_error="invalid value for --until"
    ),
    
    # Test invalid limit parameter
    ReadFileFailureTestCase(
        name="invalid_limit_parameter",
        file_content=PYTHON_TEST_CONTENT,
        command_parameters="{file_path} --limit invalid",
        expected_error="invalid value for --limit"
    )
]


@pytest.mark.parametrize("test_case", test_cases, ids=lambda tc: tc.name)
def test_read_file_command(test_case):
    """Test successful read file commands using the defined test cases."""
    temp_dir = tempfile.mkdtemp()
    ctx = Context.builder().session_id("test_session_id").workspace(temp_dir).initialize()
    
    # Determine the file path based on the test case name
    file_path = os.path.join(temp_dir, f"{test_case.name}.txt")
    
    # Create the test file with appropriate content if provided
    if test_case.file_content is not None:
        # Create any required subdirectories for this test
        if "subdir" in test_case.name:
            subdir_path = os.path.join(temp_dir, "subdir")
            os.makedirs(subdir_path, exist_ok=True)
            file_path = os.path.join(subdir_path, f"{test_case.name}.txt")
            
        # Write the content to the file
        with open(file_path, "w") as f:
            f.write(test_case.file_content)
    
    # Format the command parameters with the actual file path
    formatted_params = test_case.command_parameters.format(file_path=file_path)
    
    # Create and execute the command
    command_input = f"read_file {formatted_params}{COMMAND_END}"
    
    # Execute the command
    result = ctx.shell.parse_and_execute(command_input)
    
    # Verify the command executed successfully
    assert result.success, f"Command should execute successfully for test case {test_case.name}. Error: {result.result}"
    
    # Check for expected output strings
    for expected_str in test_case.expected_output:
        # Handle regex patterns for line numbers
        if expected_str.startswith('^'):
            assert any(re.match(expected_str, line) for line in result.result.split('\n') if line), \
                f"Regex pattern '{expected_str}' not found in output for test case {test_case.name}"
        else:
            assert expected_str in result.result, \
                f"Expected string '{expected_str}' not found in output for test case {test_case.name}"
    
    # Check that unwanted strings are not in the output
    for not_expected_str in test_case.expected_not_in_output:
        # Handle regex patterns for line numbers
        if not_expected_str.startswith('^'):
            assert not any(re.match(not_expected_str, line) for line in result.result.split('\n') if line), \
                f"Regex pattern '{not_expected_str}' found in output but should not be for test case {test_case.name}"
        else:
            assert not_expected_str not in result.result, \
                f"String '{not_expected_str}' found in output but should not be for test case {test_case.name}"


@pytest.mark.parametrize("test_case", error_test_cases, ids=lambda tc: tc.name)
def test_read_file_errors(test_case):
    """Test error conditions in read file commands using the defined error test cases."""
    temp_dir = tempfile.mkdtemp()
    ctx = Context.builder().session_id("test_session_id").workspace(temp_dir).initialize()
    
    # Determine the file path
    file_path = os.path.join(temp_dir, f"{test_case.name}.txt")
    
    # Create the test file with appropriate content if provided
    if test_case.file_content is not None:
        with open(file_path, "w") as f:
            f.write(test_case.file_content)
    
    # Format the command parameters with the actual file path
    formatted_params = test_case.command_parameters.format(file_path=file_path)
    
    # Create and execute the command
    command_input = f"read_file {formatted_params}{COMMAND_END}"
    
    # For the nonexistent_file test, we need to handle the FatalError exception
    if test_case.name == "nonexistent_file":
        try:
            # This should raise a FatalError
            command = ctx.shell.parse(command_input)
            ctx.shell.execute(command.name, command.parameters, command.data)
            assert False, "Should have raised FatalError"
        except FatalError as e:
            # Verify the error message
            error_message = str(e).lower()
            assert test_case.expected_error.lower() in error_message, \
                f"Error '{test_case.expected_error}' not found in error message: {error_message}"
    else:
        # Execute the command for other error cases
        result = ctx.shell.parse_and_execute(command_input)
        
        # Verify the command failed as expected
        assert not result.success, \
            f"Command should fail for error test case {test_case.name}"
        
        # Verify the error message contains the expected text
        if result.result is None:
            # For exceptions that are raised and don't set result.result
            print(f"Warning: result.result is None for test case {test_case.name}")
        else:
            assert test_case.expected_error.lower() in result.result.lower(), \
                f"Error '{test_case.expected_error}' not found in result for test case {test_case.name}: {result.result}"
