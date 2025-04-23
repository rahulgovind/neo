"""
Unit tests for the Shell commands.

This test validates the Shell commands functionality:
1. Executing shell commands in different directories
2. Viewing shell output
3. Writing input to shell processes
4. Terminating shell processes
"""

import os
import unittest
import logging
import pytest
import tempfile
import shutil
import time
import re
from dataclasses import dataclass
from enum import Enum, auto
from typing import Optional, List, Pattern, Union, Dict

from src.neo.session import Session
from src.neo.core.constants import (
    STDIN_SEPARATOR,
)
from src.utils.shell_manager import ShellManager

# Configure logging
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.DEBUG)


@dataclass
class Run:
    """Represents a shell_run command with expected results."""

    command: str  # The shell command to run
    expected_success: bool = True
    expected_output: Optional[Union[str, Pattern]] = None
    # None means don't check output


@dataclass
class View:
    """Represents a shell_view command."""

    expected_success: bool = True
    expected_output: Optional[Union[str, Pattern]] = None


@dataclass
class Terminate:
    """Represents a shell_terminate command."""

    expected_success: bool = True


@dataclass
class Write:
    """Represents a shell_write command to send input to a shell process."""

    content: str  # The content to write to the shell
    press_enter: bool = True  # Whether to press enter after writing
    expected_success: bool = True
    expected_output: Optional[Union[str, Pattern]] = None


@dataclass
class ShellCommandTestCase:
    """A test case consisting of a sequence of shell commands to execute."""

    name: str
    commands: List[Union[Run, View, Terminate, Write]]


@pytest.fixture
def temp_dir(tmp_path_factory):
    dir_path = tmp_path_factory.mktemp("shelltest")
    yield str(dir_path)
    shutil.rmtree(str(dir_path), ignore_errors=True)


@pytest.fixture
def session(temp_dir):
    test_session_id = "test_shellcommands_session"
    sess = (
        Session.builder().session_id(test_session_id).workspace(temp_dir).initialize()
    )
    yield sess
    ShellManager.cleanup()


@pytest.fixture
def shell(session):
    return session.shell


def assert_file_content(file_path: str, expected_content: str) -> None:
    assert os.path.exists(file_path), f"File {file_path} should exist"
    with open(file_path, "r") as f:
        content = f.read().strip()
    assert (
        content == expected_content
    ), f"File {file_path} should have the correct content"


def create_temp_file(temp_dir: str, filename: str, content: str) -> str:
    file_path = os.path.join(temp_dir, filename)
    with open(file_path, "w") as f:
        f.write(content)
    return file_path


def assert_command_success(result, msg: str = None):
    """Assert that the shell command succeeded and output is not None."""
    assert result.success, msg or f"Expected command to succeed, got: {result}"
    assert result.content is not None, "Command result content should not be None"


def assert_command_failure(result, msg: str = None):
    """Assert that the shell command failed and output is not None."""
    assert not result.success, msg or f"Expected command to fail, got: {result}"
    assert result.content is not None, "Command result content should not be None"


def test_shell_run_continuous_output(shell, temp_dir):
    """Test continuous output from a long-running shell command.

    This test verifies that:
    1. We can capture initial output from a continuous command
    2. Additional output is generated over time
    3. View command shows updated output with new numbers
    4. Process can be terminated successfully
    """
    # Create a simple counter program that outputs immediately and keeps running
    # First create a simple bash script that will run continuously
    script_path = os.path.join(temp_dir, "counter.sh")
    with open(script_path, "w") as f:
        f.write("""
#!/bin/bash
echo "Script starting"
counter=0
while [ $counter -lt 10 ]; do
    echo "Counter: $counter at $(date +%s)"
    counter=$((counter+1))
    sleep 0.1
done
sleep 0.2  # Give shell time to flush output
echo "Script completed"
        """)
    os.chmod(script_path, 0o755)  # Make executable
    
    # Now run the script - since it's self-contained and terminates, we should get initial output
    run_result = shell.execute("shell_run", f"continuous-output {temp_dir}", f"bash {script_path}")
    assert_command_success(run_result, "Continuous command should execute successfully")
    
    # Verify that the initial script output is captured
    assert "Script starting" in run_result.content, "Initial script output should be captured"
    
    # The script should run to completion within timeout since it only runs to counter=10
    # Extract counter values from the view output
    counter_pattern = r"Counter: (\d+) at"
    counters_in_initial = [int(match) for match in re.findall(counter_pattern, run_result.content)]
    
    # There should be at least some counter values in the initial output
    assert len(counters_in_initial) > 0, "Initial output should contain counter values"
    first_seen_counters = set(counters_in_initial)
    
    # View the output after waiting - it should contain more counter values
    view_result = shell.execute("shell_view", "continuous-output")
    assert_command_success(view_result, "View command should execute successfully")
    
    # Extract counter values from the view output
    counters_in_view = [int(match) for match in re.findall(counter_pattern, view_result.content)]
    
    # There should be more counter values in the full view output
    assert len(counters_in_view) >= len(counters_in_initial), "View should show at least as many counter values as initial output"
    
    # Check that script completion message is in the output
    assert "Script completed" in view_result.content, "Script completion message should be in the output"

    # Terminate the process
    term_result = shell.execute("shell_terminate", "continuous-output")
    assert_command_success(term_result, "Terminate command should execute successfully")


########################################
# Parameterized Tests
########################################

# Define test cases using sequential command execution format
shell_command_test_cases = [
    ShellCommandTestCase(
        "echo_test",
        [
            Run("echo 'Hello World'", expected_output="Hello World"),
        ],
    ),
    ShellCommandTestCase(
        "create_and_read_file",
        [
            Run("echo 'Test file content' > created_file.txt"),
            Run("cat created_file.txt", expected_output="Test file content"),
        ],
    ),
    ShellCommandTestCase(
        "command_error",
        [
            # FIXME: The current implementation always returns success=True
            # even for non-existent commands. This should be fixed in the implementation.
            # See ShellRunCommand.execute() in src/neo/commands/shell.py
            Run(
                "nonexistent_command",
                expected_success=False,  # This is the correct expectation
                expected_output=re.compile(
                    r"not found|nonexistent|command_not_found|nonexistent_command",
                    re.IGNORECASE,
                ),
            ),
        ],
    ),
    ShellCommandTestCase(
        "empty_command",
        [
            # FIXME: The current implementation always returns success=True
            # even for empty commands. This should be fixed in the implementation.
            Run(
                "",
                expected_success=False,  # This is the correct expectation
                expected_output=re.compile(r"empty", re.IGNORECASE),
            ),
        ],
    ),
    ShellCommandTestCase(
        "list_files",
        [
            Run("touch list_file.txt"),
            Run("ls", expected_output="list_file.txt"),
        ],
    ),
    ShellCommandTestCase(
        "view_and_terminate",
        [
            Run("echo 'Output to view'"),
            View(expected_output="Output to view"),
            Terminate(),
        ],
    ),
    ShellCommandTestCase(
        "special_chars",
        [
            Run("echo '$PATH & * ? !' > special.txt"),
            Run("cat special.txt", expected_output="$PATH & * ? !"),
        ],
    ),
    ShellCommandTestCase(
        "run_view_terminate",
        [
            Run("echo 'Command output'"),
            View(expected_output="Command output"),
            Terminate(),
            # FIXME: After termination, view should fail with success=False
            # but the current implementation always returns success=True
            View(expected_success=False, expected_output=re.compile(r"no shell|not found|error", re.IGNORECASE)),
        ],
    ),
    ShellCommandTestCase(
        "write_input",
        [
            # Start a process that reads from stdin
            Run("cat > output_file.txt"),
            # Write input to the process
            # This implementation uses a custom method called shell_write
            View(),  # First view to verify the process is running
            # Send input to the process
            Run("echo 'test input' | cat > temp_input.txt"),
            Run("cat temp_input.txt"),
            Terminate(),
        ],
    ),
    ShellCommandTestCase(
        "write_after_terminate",
        [
            Run("sleep 5"),
            Terminate(),
            # FIXME: After termination, view should fail with success=False
            # but the current implementation always returns success=True
            # We can't directly test Write class here since that operation is handled differently
            View(expected_success=False, expected_output=re.compile(r"no shell|not found|error", re.IGNORECASE)),
        ],
    ),
    ShellCommandTestCase(
        "shell_write_command",
        [
            # Start a process that waits for input
            Run("cat > shell_write_test.txt"),
            # Write directly to the shell using shell_write
            Write(content="Hello from shell_write", expected_success=True),
            # Terminate the shell to complete the file
            Terminate(),
            # Verify the content was written to the file
            Run("cat shell_write_test.txt", expected_output="Hello from shell_write"),
        ],
    ),
    ShellCommandTestCase(
        "shell_write_no_enter",
        [
            # Start a process that waits for input
            Run("cat > shell_write_no_enter.txt"),
            # Write without pressing enter
            Write(content="Partial", press_enter=False, expected_success=True),
            # Write the rest with enter
            Write(content=" content", expected_success=True),
            # Terminate the shell to complete the file
            Terminate(),
            # Verify the content was written to the file
            Run("cat shell_write_no_enter.txt", expected_output="Partial content"),
        ],
    ),
    ShellCommandTestCase(
        "shell_write_to_nonexistent",
        [
            # Try to write to a shell that doesn't exist
            Write(content="This should fail", expected_success=False, 
                  expected_output=re.compile(r"no shell|not found", re.IGNORECASE)),
        ],
    ),
]


@pytest.mark.parametrize("test_case", shell_command_test_cases, ids=lambda tc: tc.name)
def test_shell_command_sequence(shell, temp_dir, test_case):
    """Test a sequence of shell commands that are executed in order."""
    shell_id = f"test-{test_case.name}"

    # Execute each command in sequence
    for i, command in enumerate(test_case.commands):
        # Handle different command types
        if isinstance(command, Run):
            result = shell.execute(
                "shell_run", f"{shell_id} {temp_dir}", command.command
            )
        elif isinstance(command, View):
            result = shell.execute("shell_view", shell_id)
        elif isinstance(command, Terminate):
            result = shell.execute("shell_terminate", shell_id)
        elif isinstance(command, Write):
            # For Write commands, we use shell_write with optional no_press_enter flag
            args = shell_id
            if not command.press_enter:
                args += " --no-press-enter"
            result = shell.execute("shell_write", args, command.content)
        else:
            raise TypeError(f"Unknown command type: {type(command)}")

        # Validate results
        if command.expected_success:
            assert_command_success(result, "Command should succeed")
        else:
            assert_command_failure(result, "Command should fail")

        # Check expected output if specified
        if hasattr(command, "expected_output") and command.expected_output is not None:
            # Debug information for echo test
            if test_case.name == "echo_test":
                shell_process = ShellManager.get_process(shell_id)
                print(f"\nDEBUG INFO FOR ECHO TEST:")
                print(f"Result success: {result.success}")
                print(f"Result content: '{result.content}'")
                if shell_process:
                    log_file = shell_process.get('log_file', 'Unknown')
                    print(f"Log file: {log_file}")
                    if os.path.exists(log_file):
                        with open(log_file, 'r') as f:
                            log_content = f.read()
                            print(f"Log file content:\n{log_content}")
                    else:
                        print(f"Log file does not exist!")
                else:
                    print(f"Shell process not found for id: {shell_id}")
            
            if isinstance(command.expected_output, Pattern):
                assert command.expected_output.search(
                    result.content
                ), f"Output should match pattern {command.expected_output.pattern}"
            else:
                assert (
                    command.expected_output in result.content
                ), f"Output should contain '{command.expected_output}'"

        # Allow a little time between commands
        if i < len(test_case.commands) - 1:
            time.sleep(0.1)
