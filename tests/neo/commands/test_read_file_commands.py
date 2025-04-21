"""
Integration tests for read_file command.

This test file focuses on testing the ReadFileCommand through the Session interface
to avoid circular imports.
"""

import os
import re
import tempfile
import pytest
from dataclasses import dataclass
from typing import Optional, List

from src.neo.session import Session


@dataclass
class ReadFileTestCase:
    """Data class representing a test case for file reading operations."""

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
class ReadFileFailureTestCase:
    """Data class representing an error test case for file reading operations."""

    name: str
    file_content: Optional[str]
    command_parameters: str
    expected_error: str


# Test content samples
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

TEXT_TEST_CONTENT = """This is a test file with some text content.
It has multiple lines.
With various content.
Test with mixed case.
And some numbers: 123, 456, 789.
"""

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
            'print("Hello, world!")',
            "^\\d+:#!/usr/bin/env python3",  # Regex to match line numbers
        ],
    ),
    # Test without line numbers
    ReadFileTestCase(
        name="without_line_numbers",
        file_content=PYTHON_TEST_CONTENT,
        command_parameters="{file_path} --no-line-numbers",
        expected_output=["#!/usr/bin/env python3", "def main():"],
        expected_not_in_output=["^\\d+:"],  # No line numbers should be present
    ),
    # Test reading from specific line
    ReadFileTestCase(
        name="from_parameter",
        file_content=PYTHON_TEST_CONTENT,
        command_parameters="{file_path} --from 7",
        expected_output=[
            "7:def main():",
            '8:    """Main function that does something."""',
        ],
        expected_not_in_output=["import sys"],
    ),
    # Test reading until specific line
    ReadFileTestCase(
        name="until_parameter",
        file_content=PYTHON_TEST_CONTENT,
        command_parameters="{file_path} --until 4",
        expected_output=["1:#!/usr/bin/env python3", "4:import sys"],
        expected_not_in_output=["def main():"],
    ),
]

# Define error test cases
error_test_cases = [
    # Test nonexistent file
    ReadFileFailureTestCase(
        name="nonexistent_file",
        file_content=None,  # No content - file won't be created
        command_parameters="{file_path}",
        expected_error="file not found",
    ),
    # Test invalid from parameter
    ReadFileFailureTestCase(
        name="invalid_from_parameter",
        file_content=PYTHON_TEST_CONTENT,
        command_parameters="{file_path} --from invalid",
        expected_error="invalid value for --from",
    ),
]


@pytest.mark.parametrize("test_case", test_cases, ids=lambda tc: tc.name)
def test_read_file_command(test_case):
    """Test successful read file commands using the defined test cases."""
    temp_dir = tempfile.mkdtemp()
    try:
        print(f"\nRunning test case: {test_case.name}")
        print(f"Temporary directory: {temp_dir}")
        
        # Initialize session
        ctx = Session.builder().session_id(f"test_{test_case.name}").workspace(temp_dir).initialize()
        print("Session initialized successfully")

        # Determine the file path based on the test case name
        file_path = os.path.join(temp_dir, f"{test_case.name}.txt")
        print(f"Test file path: {file_path}")

        # Create the test file with appropriate content if provided
        if test_case.file_content is not None:
            # Write the content to the file
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(test_case.file_content)
            print(f"Created test file with {len(test_case.file_content)} bytes")

        # Format the command parameters with the actual file path
        formatted_params = test_case.command_parameters.format(file_path=file_path)
        command_input = f"read_file {formatted_params}"
        print(f"Command to execute: {command_input}")

        # Execute the command
        result = ctx.shell.parse_and_execute(command_input)
        print(f"Command executed. Success: {result.success}")
        
        if not result.success:
            print(f"Error content: {result.content}")

        # Verify the command executed successfully
        assert (
            result.success
        ), f"Command should execute successfully for test case {test_case.name}. Error: {result.content}"
        
        print("Command was successful")
    except Exception as e:
        print(f"Exception during test: {str(e)}")
        import traceback
        traceback.print_exc()
        raise
    finally:
        # Clean up
        import shutil
        shutil.rmtree(temp_dir, ignore_errors=True)
        print(f"Cleaned up temporary directory: {temp_dir}")


    # Check for expected output strings
    for expected_str in test_case.expected_output:
        # Handle regex patterns for line numbers
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
        # Handle regex patterns for line numbers
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


@pytest.mark.parametrize("test_case", error_test_cases, ids=lambda tc: tc.name)
def test_read_file_errors(test_case):
    """Test error conditions in read file commands using the defined error test cases."""
    temp_dir = tempfile.mkdtemp()
    try:
        print(f"\nRunning error test case: {test_case.name}")
        print(f"Temporary directory: {temp_dir}")
        
        # Initialize session
        ctx = Session.builder().session_id(f"test_err_{test_case.name}").workspace(temp_dir).initialize()
        print("Session initialized successfully")

        # Determine the file path
        file_path = os.path.join(temp_dir, f"{test_case.name}.txt")
        print(f"Test file path: {file_path}")

        # Create the test file with appropriate content if provided
        if test_case.file_content is not None:
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(test_case.file_content)
            print(f"Created test file with {len(test_case.file_content)} bytes")
        else:
            print("No test file created (testing file not found case)")

        # Format the command parameters with the actual file path
        formatted_params = test_case.command_parameters.format(file_path=file_path)
        command_input = f"read_file {formatted_params}"
        print(f"Command to execute: {command_input}")

        # Execute the command for error cases
        result = ctx.shell.parse_and_execute(command_input)
        print(f"Command executed. Success (should be False): {result.success}")
        print(f"Result content: {result.content}")

        # Verify the command failed as expected
        assert (
            not result.success
        ), f"Command should fail for error test case {test_case.name}"
        print("Command failed as expected")


        # Verify the error message contains the expected text
        assert (
            test_case.expected_error.lower() in result.content.lower()
        ), f"Error '{test_case.expected_error}' not found in result for test case {test_case.name}: {result.content}"
        print(f"Error message contained expected text: '{test_case.expected_error}'")
        
    except Exception as e:
        print(f"Exception during test: {str(e)}")
        import traceback
        traceback.print_exc()
        raise
    finally:
        # Clean up
        import shutil
        shutil.rmtree(temp_dir, ignore_errors=True)
        print(f"Cleaned up temporary directory: {temp_dir}")

