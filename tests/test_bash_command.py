"""
Unit tests for the BashCommand class.

This test validates the BashCommand functionality:
1. Executing shell commands through the data parameter
2. Handling output and errors from commands
3. Testing various shell command scenarios
"""

import os
import unittest
import logging
import pytest
import tempfile
from dataclasses import dataclass
from typing import Optional

from src.core.commands.bash import BashCommand
from src.core.context import Context
from src.core.exceptions import FatalError
from src.core.constants import COMMAND_END, STDIN_SEPARATOR, COMMAND_START, ERROR_PREFIX, SUCCESS_PREFIX
from file_command_test_base import FileCommandTestBase

# Configure logging
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.DEBUG)


@dataclass
class BashTestCase:
    """Data class representing a test case for bash command operations."""
    name: str
    command: str
    expected_output: str
    setup_files: Optional[dict] = None  # Dict of filename: content to create before test


@dataclass
class BashFailureTestCase:
    """Data class representing a failure test case for bash command operations."""
    name: str
    command: str
    expected_error: str


class TestBashCommand(FileCommandTestBase):
    """Tests for the BashCommand class using the FileCommandTestBase."""
    
    def test_bash_echo(self):
        """Test a simple echo command."""
        # Create and execute the command
        command_input = f"bash{STDIN_SEPARATOR}echo 'Hello, world!'{COMMAND_END}"
        result = self.execute_command(command_input)
        
        # Verify the command executed successfully
        self.assertTrue(result.success, "Command should execute successfully")
        self.assertEqual(result.result.strip(), "Hello, world!")
    
    def test_bash_create_file(self):
        """Test creating a file with bash."""
        test_file = os.path.join(self.temp_dir, "bash_created_file.txt")
        self.assertFalse(os.path.exists(test_file), "File should not exist before the test")
        
        # Create and execute the command
        command_input = f"bash{STDIN_SEPARATOR}echo 'Content created by bash' > bash_created_file.txt{COMMAND_END}"
        result = self.execute_command(command_input)
        
        # Verify the command executed successfully
        self.assertTrue(result.success, "Command should execute successfully")
        
        # Check that the file was created
        self.assertTrue(os.path.exists(test_file), "File should have been created")
        
        # Check the file content
        with open(test_file, 'r') as f:
            content = f.read()
            self.assertEqual(content.strip(), "Content created by bash")
    
    def test_bash_command_error(self):
        """Test handling of command errors."""
        # Create and execute a command that should fail
        command_input = f"bash{STDIN_SEPARATOR}nonexistent_command{COMMAND_END}"
        
        # The command should be parsed and return a failure result
        result = self.execute_command(command_input)
        
        # Verify the command failed
        self.assertFalse(result.success, "Command should have failed")
        self.assertIsNotNone(result.error, "Error should not be None")
        self.assertIn("command not found", result.error)
    
    def test_bash_empty_command(self):
        """Test with an empty command."""
        # Note: We need to provide empty string as data since the bash command requires data
        command_input = f"bash{STDIN_SEPARATOR} {COMMAND_END}"
        
        # Create and execute the command (with space as data to pass parsing)
        result = self.execute_command(command_input)
        
        # Verify the command failed due to empty command
        self.assertFalse(result.success, "Command should have failed")
        self.assertIsNotNone(result.error, "Error should not be None")
        self.assertIn("empty", result.error.lower())
    
    def test_bash_list_files(self):
        """Test listing files with ls command."""
        test_file = os.path.join(self.temp_dir, "test_for_ls.txt")
        with open(test_file, 'w') as f:
            f.write("Test content for ls")
        
        # Create and execute the command
        command_input = f"bash{STDIN_SEPARATOR}ls{COMMAND_END}"
        result = self.execute_command(command_input)
        
        # Verify the command executed successfully
        self.assertTrue(result.success, "Command should execute successfully")
        self.assertIn("test_for_ls.txt", result.result)


# Parametrized test cases
bash_test_cases = [
    BashTestCase(
        name="echo_simple",
        command="echo 'Simple echo test'",
        expected_output="Simple echo test"
    ),
    BashTestCase(
        name="cat_file",
        command="cat test_file.txt",
        expected_output="Content to be read with cat",
        setup_files={"test_file.txt": "Content to be read with cat"}
    ),
    BashTestCase(
        name="pwd_command",
        command="pwd",
        # We don't test the exact output since it depends on the temp directory
        expected_output=""  # Will be checked specially
    ),
    BashTestCase(
        name="multiline_output",
        command="echo 'Line 1\nLine 2\nLine 3'",
        expected_output="Line 1\nLine 2\nLine 3"
    ),
    BashTestCase(
        name="pipe_commands",
        command="echo 'count this line' | wc -w",
        expected_output="3"  # 3 words in the echo output
    )
]

# Parametrized failure test cases
bash_failure_test_cases = [
    BashFailureTestCase(
        name="nonexistent_command",
        command="command_that_does_not_exist",
        expected_error="Command failed"
    ),
    BashFailureTestCase(
        name="file_not_found",
        command="cat /etc/nonexistent_file",
        expected_error="No such file or directory"
    )
]


@pytest.mark.parametrize("test_case", bash_test_cases, ids=lambda test_case: test_case.name)
def test_bash_command(test_case):
    """Test successful bash commands using the defined test cases."""
    temp_dir = tempfile.mkdtemp()
    ctx = Context.builder().session_id("test_session_id").workspace(temp_dir).initialize()
    
    # Set up test files if needed
    if test_case.setup_files:
        for filename, content in test_case.setup_files.items():
            file_path = os.path.join(temp_dir, filename)
            with open(file_path, "w") as f:
                f.write(content)
    
    # Create and execute the command
    command_input = f"bash{STDIN_SEPARATOR}{test_case.command}{COMMAND_END}"
    
    # Execute the command
    result = ctx.shell.parse_and_execute(command_input)
    
    # Verify the command executed successfully
    assert result.success, f"Command should execute successfully for test case {test_case.name}"
    
    # Special case for pwd command (just check that the result is not empty and contains the temp_dir)
    if test_case.name == "pwd_command":
        assert temp_dir in result.result, f"PWD output should contain the temp directory path for test case {test_case.name}"
    # Special case for cat_file (check content match)
    elif test_case.name == "cat_file":
        assert "Content to be read with cat" in result.result, f"Cat should show file content for test case {test_case.name}"
    # Check expected output for other cases if specified
    elif test_case.expected_output:
        assert test_case.expected_output in result.result, f"Output should contain expected string for test case {test_case.name}"


@pytest.mark.parametrize("test_case", bash_failure_test_cases, ids=lambda test_case: test_case.name)
def test_bash_failure_command(test_case):
    """Test bash commands that should fail."""
    temp_dir = tempfile.mkdtemp()
    ctx = Context.builder().session_id("test_session_id").workspace(temp_dir).initialize()
    
    # Create and execute the command
    command_input = f"bash{STDIN_SEPARATOR}{test_case.command}{COMMAND_END}"
    
    # Execute the command, which should return a failure result
    result = ctx.shell.parse_and_execute(command_input)
    
    # Verify the command failed
    assert not result.success, f"Command should have failed for test case {test_case.name}"
    assert result.error is not None, f"Error should not be None for test case {test_case.name}"
    
    # Verify the error message contains the expected substring
    assert test_case.expected_error.lower() in result.error.lower(), f"Error message should contain expected string for test case {test_case.name}"
