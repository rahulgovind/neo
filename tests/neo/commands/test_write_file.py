"""
Unit tests for the WriteFileCommand class.

This test validates the WriteFileCommand functionality:
1. Creating new files in the test environment
2. Overwriting existing files
3. Creating necessary parent directories
4. Testing error conditions
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
from src.neo.core.constants import COMMAND_END, STDIN_SEPARATOR

# Configure logging
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.DEBUG)


@dataclass
class WriteFileTestCase:
    """Data class representing a test case for file writing operations."""

    name: str
    file_content: str  # Content to write to the file
    command_parameters: str
    expected_output: List[str]  # List of strings that should be in the output
    expected_not_in_output: Optional[List[str]] = None  # List of strings that should NOT be in the output
    check_file_exists: bool = True  # Whether to check if the file exists after the command
    check_file_content: bool = True  # Whether to check the file content after the command

    def __post_init__(self):
        if self.expected_not_in_output is None:
            self.expected_not_in_output = []


@dataclass
class WriteFileFailureTestCase:
    """Data class representing an error test case for file writing operations."""

    name: str
    file_content: Optional[str]  # Content to write (None for missing content)
    command_parameters: str
    expected_error: str


# Define sample file contents for tests
PYTHON_TEST_CONTENT = '''#!/usr/bin/env python3
"""Test file module.

This is a test module used for write_file command tests.
"""

def hello():
    """Return a greeting message.
    
    Returns:
        str: A friendly greeting
    """
    # This is a test function
    return "Hello, world!"
'''

TEXT_TEST_CONTENT = """This is a test file with some text content.
It has multiple lines.
With various content.
Test with mixed case.
And some numbers: 123, 456, 789.
"""

NEW_CONTENT = """Completely replaced content module.

This module replaces the previous content.
"""

# Define test cases
test_cases = [
    # Basic create file test
    WriteFileTestCase(
        name="create_new_file",
        file_content=PYTHON_TEST_CONTENT,
        command_parameters="{file_path}",
        expected_output=[
            "SUCCESS",
            "+",  # Lines added
            "-0",  # No lines deleted
        ],
    ),
    # Test overwriting existing file
    WriteFileTestCase(
        name="overwrite_existing",
        file_content=NEW_CONTENT,
        command_parameters="{file_path}",
        expected_output=[
            "SUCCESS",
            "+",  # Lines added
            "-",  # Lines deleted
        ],
    ),
    # Test creating file in new directory
    WriteFileTestCase(
        name="create_in_new_dir",
        file_content=TEXT_TEST_CONTENT,
        command_parameters="{file_path}",
        expected_output=[
            "SUCCESS",
            "+",  # Lines added
        ],
    ),
]

# Define error test cases
error_test_cases = [
    # Test missing content
    WriteFileFailureTestCase(
        name="missing_content",
        file_content=None,  # No content
        command_parameters="{file_path}",
        expected_error="requires data",  # Updated to match actual error message
    ),
    # Test missing path
    WriteFileFailureTestCase(
        name="missing_path",
        file_content=TEXT_TEST_CONTENT,
        command_parameters="",  # Empty path
        expected_error="arguments are required: path",  # Updated to match actual error message
    ),
]

@pytest.mark.parametrize("test_case", test_cases, ids=lambda tc: tc.name)
def test_write_file_command(test_case):
    """Test successful write file commands using the defined test cases."""
    # Create a temporary directory for the test
    temp_dir = tempfile.mkdtemp()
    
    try:
        # Create a test session
        ctx = Session.builder().session_id("test_session_id").workspace(temp_dir).initialize()
        
        # Determine the file path based on the test case name
        file_path = os.path.join(temp_dir, f"{test_case.name}.txt")
        
        # For overwrite test, create the file first
        if test_case.name == "overwrite_existing":
            with open(file_path, "w") as f:
                f.write(PYTHON_TEST_CONTENT)
        
        # For directory test, use a nested path
        if test_case.name == "create_in_new_dir":
            file_path = os.path.join(temp_dir, "new_dir", "nested_dir", f"{test_case.name}.txt")
        
        # Format the command parameters with the actual file path
        formatted_params = test_case.command_parameters.format(file_path=file_path)
        
        # Execute the command directly
        logger.debug(f"Executing write_file command with parameters: {formatted_params}")
        result = ctx.shell.execute("write_file", formatted_params, test_case.file_content)
        
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
        
        # Check if the file exists if required
        if test_case.check_file_exists:
            assert os.path.exists(file_path), f"File should have been created for test case {test_case.name}"
        
        # Check the file content if required
        if test_case.check_file_content:
            with open(file_path, "r", encoding="utf-8") as f:
                file_content = f.read()
                assert file_content == test_case.file_content, f"File content doesn't match expected for test case {test_case.name}"
    
    finally:
        # Clean up
        shutil.rmtree(temp_dir)


@pytest.mark.parametrize("test_case", error_test_cases, ids=lambda tc: tc.name)
def test_write_file_errors(test_case):
    """Test error conditions in write file commands using the defined error test cases."""
    # Create a temporary directory for the test
    temp_dir = tempfile.mkdtemp()
    
    try:
        # Create a test session
        ctx = Session.builder().session_id("test_session_id").workspace(temp_dir).initialize()
        
        # Determine the file path
        file_path = os.path.join(temp_dir, f"{test_case.name}.txt")
        
        # Format the command parameters with the actual file path
        formatted_params = test_case.command_parameters.format(file_path=file_path)
        
        # Execute the command directly
        logger.debug(f"Executing write_file command with parameters: {formatted_params}")
        result = ctx.shell.execute("write_file", formatted_params, test_case.file_content)
        assert (
            not result.success
        ), f"Command should fail for error test case {test_case.name}"
        # Verify the error message contains the expected text
        assert (
            test_case.expected_error.lower() in result.content.lower()
        ), f"Error '{test_case.expected_error}' not found in result for test case {test_case.name}: {result.content}"

    finally:
        # Clean up
        shutil.rmtree(temp_dir)



