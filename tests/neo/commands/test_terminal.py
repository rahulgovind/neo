"""
Unit tests for the Terminal commands.

This test validates the Terminal commands functionality:
1. Executing terminal commands in different directories
2. Viewing terminal output
3. Writing input to terminal processes
4. Terminating terminal processes
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

from textwrap import dedent

from src.neo.session import Session
from src.neo.core.constants import (
    STDIN_SEPARATOR,
)
from src.utils.terminal_manager import TerminalManager

from pathlib import Path

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
    TerminalManager.cleanup()


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


# Test cases for various shell commands
shell_command_test_cases = [
    ShellCommandTestCase(
        "echo_test",
        [
            Run("echo 'Hello, world!'", expected_output="Hello, world!\n"),
            View(expected_output="Hello, world!\n"),
            Run("printf 'Hello, world!'", expected_output="Hello, world!"),
            Terminate(),
        ],
    ),
    ShellCommandTestCase(
        "multiple_commands",
        [
            Run("echo 'First command'", expected_output="First command\n"),
            Run("echo 'Second command'", expected_output="Second command\n"),
            View(expected_output="Second command\n"),
            Terminate(),
        ],
    ),
    ShellCommandTestCase(
        "command_with_error",
        [
            Run("nonexistent_command", expected_success=False),
            Terminate(),
        ],
    ),
    ShellCommandTestCase(
        "change_directory",
        [
            Run("pwd", expected_output="{session.workspace}\n"),
            Run("mkdir -p testdir"),
            Run("cd testdir && pwd", expected_output="{session.workspace}/testdir\n"),
            Terminate(),
        ],
    ),
    ShellCommandTestCase(
        "environment_variables",
        [
            Run("export TEST_VAR='test value'"),
            Run("echo $TEST_VAR", expected_output="test value\n"),
            Terminate(),
        ],
    ),
    ShellCommandTestCase(
        "file_creation",
        [
            Run("echo 'File content' > test_file.txt"),
            Run("cat test_file.txt", expected_output="File content\n"),
            Terminate(),
        ],
    ),
    ShellCommandTestCase(
        "shell_write_test",
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
            Run("cat shell_write_no_enter.txt", expected_output="Partial content\n"),
        ],
    ),
    ShellCommandTestCase(
        "shell_write_to_nonexistent",
        [
            # Try to write to a shell that doesn't exist
            Write(
                content="This should fail",
                expected_success=False,
                expected_output=re.compile("No terminal found"),
            ),
        ],
    ),
]


@pytest.mark.parametrize("test_case", shell_command_test_cases, ids=lambda tc: tc.name)
def test_shell_command_sequence(session, shell, temp_dir, test_case):
    """Test a sequence of shell commands that are executed in order."""
    shell_id = f"test-{test_case.name}"

    # Execute each command in sequence
    for i, command in enumerate(test_case.commands):
        # Handle different command types
        if isinstance(command, Run):
            result = shell.execute("shell_run", f"{shell_id}", command.command)
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
            if isinstance(command.expected_output, Pattern):
                assert command.expected_output.search(
                    result.content
                ), f"Output should match pattern {command.expected_output.pattern}"
            else:
                expected_output = eval(
                    f'f"""{command.expected_output}"""',
                    globals=globals(),
                    locals=locals(),
                )
                assert result.content == expected_output, f"Expected: '{expected_output}', Got: '{result.content}'"


def test_shell_run_continuous_output(session, shell):
    """Test continuous output from a long-running shell command.

    This test verifies that:
    1. We can capture initial output from a continuous command
    2. Additional output is generated over time
    3. View command shows updated output with new numbers
    4. Process can be terminated successfully
    """
    # Create a simple counter program that outputs immediately and keeps running
    # First create a simple bash script that will run continuously
    script_path = "counter.sh"
    with open(Path(session.workspace) / script_path, "w") as f:
        f.write(
            dedent(
                """
                #!/bin/bash
                echo "Script starting"
                counter=0
                while [ $counter -lt 10 ]; do
                    echo "Counter: $counter"
                    counter=$((counter + 1))
                    sleep 1
                done
                echo "Script complete"
                """
            )
        )

    # Make it executable
    os.chmod(script_path, 0o755)

    # 1. Run the script - this should return before the script completes
    shell_id = "continuous-test"
    result = shell.execute("shell_run", f"{shell_id}", f"bash {script_path}")
    assert_command_success(result)

    # Check for initial output
    assert "Script starting" in result.content

    # Might already have some counter values, but probably not all
    assert "Counter: 0" in result.content

    # 2. Wait a moment to let the script run more
    time.sleep(3)

    # 3. View the output to see progress
    result = shell.execute("shell_view", shell_id)
    assert_command_success(result)

    # Should now have more counter values
    # We should see at least counters 0-2 (but might have more depending on timing)
    assert "Counter: 0" in result.content
    assert "Counter: 1" in result.content
    assert "Counter: 2" in result.content

    # 4. Terminate the shell before it completes
    result = shell.execute("shell_terminate", shell_id)
    assert_command_success(result, "Shell termination should succeed")

    # 5. Try to view the output after termination
    # This should still work but indicate the process has terminated
    result = shell.execute("shell_view", shell_id)
    assert_command_failure(result, "View should fail after termination")
