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
from src.neo.commands.base import FileUpdate

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
        
        # Save original content for overwrite test
        original_content = None
        if test_case.name == "overwrite_existing":
            original_content = PYTHON_TEST_CONTENT
            with open(file_path, "w") as f:
                f.write(original_content)
        
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
                ), f"Unwanted regex pattern '{not_expected_str}' found in output for test case {test_case.name}"
            else:
                assert (
                    not_expected_str not in result.content
                ), f"Unwanted string '{not_expected_str}' found in output for test case {test_case.name}"
        
        # Check that the file exists if expected
        if test_case.check_file_exists:
            assert os.path.exists(
                file_path
            ), f"File was not created for test case {test_case.name}"
        
        # Check file content if expected
        if test_case.check_file_content and test_case.check_file_exists:
            with open(file_path, "r") as f:
                file_content = f.read()
                assert file_content == test_case.file_content, f"File content doesn't match expected for test case {test_case.name}"
        
        # Validate the FileUpdate output
        assert hasattr(result, 'command_output'), "Command result should have command_output attribute"
        assert result.command_output is not None, "Command output should not be None"
        assert isinstance(result.command_output, FileUpdate), f"Command output should be FileUpdate instance, got {type(result.command_output)}"
        
        # Validate FileUpdate fields
        file_update = result.command_output
        assert file_update.name == "write_file", "Command name should be 'write_file'"
        
        # For a new file, message should contain "Created"
        if test_case.name == "create_new_file" or test_case.name == "create_in_new_dir":
            assert "Created" in file_update.message, f"Message should indicate file creation for test case {test_case.name}"
        # For overwriting, message should contain "Updated"
        elif test_case.name == "overwrite_existing":
            assert "Updated" in file_update.message, f"Message should indicate file update for test case {test_case.name}"
        
        # Validate diff content
        assert hasattr(file_update, 'diff'), "FileUpdate should have diff attribute"
        assert file_update.diff.strip(), "Diff should not be empty"
        
        # Validate diff content based on the format we're generating
        # Ensure diff shows file name and has a diff header
        assert os.path.basename(file_path) in file_update.diff, "Diff should include the file name"
        assert "+++" in file_update.diff, "Diff should show additions marker"
        assert "@@" in file_update.diff, "Diff should contain a header with line numbers"
        
        # Verify that the diff contains the actual content changes
        if test_case.name == "overwrite_existing":
            # For overwrite tests, make sure the diff contains both old and new content markers
            assert original_content is not None, "Original content should be set for overwrite test"
            
            # Check that at least some content from both files is represented in the diff
            sample_old_line = original_content.splitlines()[3].strip() if len(original_content.splitlines()) > 3 else original_content.splitlines()[0].strip()
            sample_new_line = test_case.file_content.splitlines()[0].strip()
            
            # Look for content markers - minus sign for old content, plus sign for new content
            has_old_content = any(line.strip().endswith(sample_old_line) and line.startswith('-') for line in file_update.diff.splitlines())
            has_new_content = any(line.strip().endswith(sample_new_line) and line.startswith('+') for line in file_update.diff.splitlines())
            
            assert has_old_content, f"Diff should contain markers for old content: {sample_old_line}"
            assert has_new_content, f"Diff should contain markers for new content: {sample_new_line}"
        
        # For new files, diff should show only additions
        if test_case.name == "create_new_file" or test_case.name == "create_in_new_dir":
            # The diff header should show something like @@ -1,0 +1,5 @@ indicating new lines added
            assert "+1," in file_update.diff, "Diff should show line additions in the header"
            # There should be addition markers for the new content
            assert "\n+" in file_update.diff, "Diff should mark added lines with +"
            
        # For overwritten files, diff should show modifications
        elif test_case.name == "overwrite_existing":
            assert "--- a/" in file_update.diff, "Diff for modified file should show source file"
            assert "+++ b/" in file_update.diff, "Diff should show destination file"
    
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



