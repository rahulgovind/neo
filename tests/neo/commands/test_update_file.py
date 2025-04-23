"""
Unit tests for the UpdateFileCommand class.

This test validates the UpdateFileCommand functionality:
1. Updating existing files using a diff structure
2. Testing error conditions like missing files or invalid diff content
3. Testing model fallback when diff cannot be applied
"""

import os
import re
import logging
import pytest
import tempfile
import shutil
import textwrap
from dataclasses import dataclass
from typing import Optional, List

from src.neo.session import Session
from src.neo.exceptions import FatalError
from src.neo.core.constants import COMMAND_END, STDIN_SEPARATOR

# Configure logging
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.DEBUG)


@dataclass
class UpdateFileTestCase:
    """Data class representing a test case for file update operations."""

    name: str
    initial_content: str  # Content to initially write to the file
    changes: str  # Changes content to apply to the file
    expected_output: List[str]  # List of strings that should be in the output
    expected_final_content: str  # Expected final content after the update
    expected_not_in_output: Optional[List[str]] = None  # List of strings that should NOT be in the output

    def __post_init__(self):
        if self.expected_not_in_output is None:
            self.expected_not_in_output = []


@dataclass
class UpdateFileFailureTestCase:
    """Data class representing an error test case for file update operations."""

    name: str
    initial_content: Optional[str]  # Content to initially write to the file (None for no file)
    changes: Optional[str]  # Changes content to apply (None for missing changes)
    command_parameters: str  # Command parameters
    expected_error: str  # Expected error message


# Test cases start here

# Define test cases for successful updates
test_cases = [
    # Test case for simple UPDATE operation
    UpdateFileTestCase(
        name="simple_update",
        initial_content=textwrap.dedent('''
            #!/usr/bin/env python3
            """Test file module.
            
            This is a test module used for update_file command tests.
            """
            
            def hello():
                """Return a greeting message.
                
                Returns:
                    str: A friendly greeting
                """
                # This is a test function
                return "Hello, world!"
            '''),
        changes=textwrap.dedent('''
            @UPDATE
            @@BEFORE
            2:"""Test file module.
            @@AFTER
            2:"""Updated test file module.
            '''),
        expected_output=[
            "File updated successfully",
        ],
        expected_final_content=textwrap.dedent('''
            #!/usr/bin/env python3
            """Updated test file module.
            
            This is a test module used for update_file command tests.
            """
            
            def hello():
                """Return a greeting message.
                
                Returns:
                    str: A friendly greeting
                """
                # This is a test function
                return "Hello, world!"
            '''),
    ),
    # Test case for DELETE operation
    UpdateFileTestCase(
        name="delete_operation",
        initial_content=textwrap.dedent('''
            This is a test file with some text content.
            It has multiple lines.
            With various content.
            Test with mixed case.
            And some numbers: 123, 456, 789.
            '''),
        changes=textwrap.dedent('''
            @DELETE
            2:It has multiple lines.
            '''),
        expected_output=[
            "File updated successfully",
        ],
        expected_final_content=textwrap.dedent('''
            This is a test file with some text content.
            With various content.
            Test with mixed case.
            And some numbers: 123, 456, 789.
            '''),
    ),
    # Test case with multiple operations
    UpdateFileTestCase(
        name="multiple_operations",
        initial_content=textwrap.dedent('''
            #!/usr/bin/env python3
            """Test file module.
            
            This is a test module used for update_file command tests.
            """
            
            def hello():
                """Return a greeting message.
                
                Returns:
                    str: A friendly greeting
                """
                # This is a test function
                return "Hello, world!"
            '''),
        changes=textwrap.dedent('''
            @UPDATE
            @@BEFORE
            2:"""Test file module.
            @@AFTER
            2:"""Updated test file module.
            
            @UPDATE
            @@BEFORE
            12:    # This is a test function
            @@AFTER
            12:    # This is an updated test function
            '''),
        expected_output=[
            "File updated successfully",
        ],
        expected_final_content=textwrap.dedent('''
            #!/usr/bin/env python3
            """Updated test file module.
            
            This is a test module used for update_file command tests.
            """
            
            def hello():
                """Return a greeting message.
                
                Returns:
                    str: A friendly greeting
                """
                # This is an updated test function
                return "Hello, world!"
            '''),
    ),
]

# Define error test cases
error_test_cases = [
    # Test missing changes content
    UpdateFileFailureTestCase(
        name="missing_diff",
        initial_content=textwrap.dedent('''
            #!/usr/bin/env python3
            """Test file module.
            
            This is a test module used for update_file command tests.
            """
            
            def hello():
                """Return a greeting message.
                
                Returns:
                    str: A friendly greeting
                """
                # This is a test function
                return "Hello, world!"
            '''),
        changes=None,  # No changes content
        command_parameters="{file_path}",
        expected_error="requires diff content",
    ),
    # Test file not found
    UpdateFileFailureTestCase(
        name="file_not_found",
        initial_content=None,  # No file created
        changes=textwrap.dedent('''
            @UPDATE
            @@BEFORE
            1:First line
            @@AFTER
            1:Updated line
            '''),
        command_parameters="{file_path}",
        expected_error="not found",
    ),
    # Test invalid diff format
    UpdateFileFailureTestCase(
        name="invalid_diff",
        initial_content=textwrap.dedent('''
            #!/usr/bin/env python3
            """Test file module.
            
            This is a test module used for update_file command tests.
            """
            
            def hello():
                """Return a greeting message.
                
                Returns:
                    str: A friendly greeting
                """
                # This is a test function
                return "Hello, world!"
            '''),
        changes="Invalid diff format that doesn't follow the required structure",
        command_parameters="{file_path}",
        expected_error="invalid",
    ),
]


@pytest.mark.parametrize("test_case", test_cases, ids=lambda tc: tc.name)
def test_update_file_command(test_case):
    """Test successful update file commands using the defined test cases."""
    # Create a temporary directory for the test
    temp_dir = tempfile.mkdtemp()
    
    try:
        # Create a test session
        ctx = Session.builder().session_id("test_session_id").workspace(temp_dir).initialize()
        
        # Create the file with initial content
        file_path = os.path.join(temp_dir, f"{test_case.name}.txt")
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(test_case.initial_content)
        
        # Format the command parameters
        formatted_params = file_path
        
        # Execute the command directly
        logger.debug(f"Executing update_file command for file: {file_path}")
        result = ctx.shell.execute("update_file", file_path, test_case.changes)
        
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
        
        # Check that the file exists and has the expected content
        assert os.path.exists(file_path), f"File should have been created for test case {test_case.name}"
        
        # Verify the file content matches the expected result
        with open(file_path, "r", encoding="utf-8") as f:
            file_content = f.read()
            assert file_content == test_case.expected_final_content, (
                f"File content doesn't match expected for test case {test_case.name}\n"
                f"Expected:\n{test_case.expected_final_content}\n"
                f"Actual:\n{file_content}"
            )
    
    finally:
        # Clean up
        shutil.rmtree(temp_dir)


@pytest.mark.parametrize("test_case", error_test_cases, ids=lambda tc: tc.name)
def test_update_file_errors(test_case):
    """Test error conditions in update file commands using the defined error test cases."""
    # Create a temporary directory for the test
    temp_dir = tempfile.mkdtemp()
    
    try:
        # Create a test session
        ctx = Session.builder().session_id("test_session_id").workspace(temp_dir).initialize()
        
        # Determine the file path
        file_path = os.path.join(temp_dir, f"{test_case.name}.txt")
        
        # Create the file with initial content if provided
        if test_case.initial_content is not None:
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(test_case.initial_content)
        
        # Format the command parameters with the actual file path
        formatted_params = test_case.command_parameters.format(file_path=file_path)
        
        # Create direct execute command
        logger.debug(f"Executing update_file command with parameters: {formatted_params}")
        result = ctx.shell.execute("update_file", formatted_params, test_case.changes)
        
        # Verify the command failed as expected
        assert not result.success, f"Command should fail for error test case {test_case.name}"
        
        # Verify the error message contains the expected text
        error_text = result.content.lower()
            
        # Also check the error field if it exists and is a string
        if isinstance(result.error, str):
            error_text += " " + result.error.lower()
                
        assert (
            test_case.expected_error.lower() in error_text
        ), (
            f"Error '{test_case.expected_error}' not found in result for "
            f"test case {test_case.name}: {result.content} / {result.error}"
        )

    finally:
        # Clean up
        shutil.rmtree(temp_dir)
