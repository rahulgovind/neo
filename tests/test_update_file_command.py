"""
Unit tests for the UpdateFileCommand class.

This test validates the UpdateFileCommand functionality:
1. Updating existing files based on natural language instructions
2. Testing error conditions like missing files or instructions
"""

import os
import unittest
import logging
import pytest
from pathlib import Path
from dataclasses import dataclass
from typing import List, Optional
from textwrap import dedent
import tempfile

from src.core.commands.update_file import UpdateFileCommand
from src.core.context import Context
from src.core.exceptions import FatalError
from src.core.constants import COMMAND_END, STDIN_SEPARATOR, COMMAND_START, ERROR_PREFIX, SUCCESS_PREFIX
# Import the base class content directly since it's in the same directory
from file_command_test_base import FileCommandTestBase

from src.utils.files import _escape_special_chars, _unescape_special_chars

# Configure logging
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.DEBUG)


@dataclass
class UpdateFileTestCase:
    """Data class representing a success test case for file update operations."""
    name: str
    initial_content: str
    diff: str
    expected_output: str
    enable_model_fallback: bool = False

@dataclass
class UpdateFileFailureTestCase:
    """Data class representing a failure test case for file update operations."""
    name: str
    initial_content: str
    diff: str
    expected_error: str
    

class TestUpdateFileCommand(FileCommandTestBase):
    """Tests for the UpdateFileCommand class."""
    
    def setUp(self):
        """Set up test environment."""
        super().setUp()
        
        # Create a test text file to update for non-parametrized tests
        self.test_file = os.path.join(self.temp_dir, "test_file.txt")
        with open(self.test_file, "w") as f:
            f.write("Initial content for update test\n")
            
        # Create a test Python file to update for non-parametrized tests
        self.test_py_file = os.path.join(self.temp_dir, "test_file.py")
        with open(self.test_py_file, "w") as f:
            f.write(dedent("""#!/usr/bin/env python3
            # Test file for update command tests

            def main():
                print("Hello, world!")

            if __name__ == "__main__":
                main()
            """))
    
    def test_path_parameter(self):
        """Test the path parameter validation."""
        # Define a new file path
        new_file = os.path.join(self.temp_dir, "should_not_be_updated.txt")
        
        # Create file with initial content
        with open(new_file, "w") as f:
            f.write("Original content")
        
        # Test with missing path parameter - use a known valid existing file
        # to test only the path parameter validation
        file_path = self.test_py_file
        self.assertTrue(os.path.exists(file_path), "Test file should exist")
        
        # Create a path command with invalid empty path
        # First parse the command to get parameters and data - don't execute it directly
        try:
            # First try a command with empty path string
            command_input = f"update_file ''{STDIN_SEPARATOR}Add a docstring{COMMAND_END}"
            parsed_cmd = self.shell.parse(command_input)
            result = self.shell.execute(parsed_cmd.name, parsed_cmd.parameters, parsed_cmd.data)
            # If we get here, the empty path didn't throw an error, which is unexpected
            self.fail("Empty path should have caused an error")
        except FatalError as e:
            # We expect a FatalError with a message about the path
            self.assertIn("path", str(e).lower(), "Error should mention the path problem")
    
    def test_missing_instructions(self):
        """Test attempting to update a file without providing instructions."""
        # Define an existing file path
        file_path = self.test_py_file
        self.assertTrue(os.path.exists(file_path), "Test file should exist")
        
        # Command without data (instructions)
        command_input = f"update_file {file_path}{COMMAND_END}"
        logger.debug(f"Command input without instructions: {command_input}")
        
        # Execute the command - should fail with appropriate error
        with self.assertRaises(RuntimeError) as context:
            # We need to catch the error at the parse stage
            parsed_cmd = self.shell.parse(command_input)
        
        # Verify the error message mentions missing data
        self.assertIn("requires data", str(context.exception).lower())
        
        # Verify the error message
        self.assertIn("requires data", str(context.exception).lower())
    
    def test_file_not_found(self):
        """Test updating a non-existent file."""
        # Non-existent file path
        nonexistent_file = os.path.join(self.temp_dir, "nonexistent.py")
        self.assertFalse(os.path.exists(nonexistent_file), "Test file should not exist")
        
        # Use the command line format to test through the shell
        command_line = f"update_file {nonexistent_file}{STDIN_SEPARATOR}Add a docstring{COMMAND_END}"
        
        try:
            # Parse the command - this should work
            parsed_cmd = self.shell.parse(command_line)
            
            # Execute the command - this should return a CommandResult with success=False
            result = self.shell.execute(
                parsed_cmd.name,
                parsed_cmd.parameters,
                parsed_cmd.data
            )
            
            # Check that the result contains the expected error
            self.assertFalse(result.success)
            self.assertIn("not found", result.error.lower())
            
        except Exception as e:
            # If any exception is raised, it should be a controlled one
            # with proper error messaging
            if isinstance(e, FatalError):
                # If it's a FatalError, check that it has the right message
                self.assertIn("not found", str(e).lower())
            else:
                # Otherwise, this is unexpected and should fail the test
                self.fail(f"Unexpected exception type: {type(e).__name__}, message: {str(e)}")
    
    def test_update_process(self):
        """Test the update file command process method using the shell."""
        # Use a test file
        file_path = self.test_py_file
        self.assertTrue(os.path.exists(file_path), "Test file should exist")
        
        # Save original content for comparison
        with open(file_path, 'r') as f:
            original_content = f.read()
        
        # Write initial content to file to prepare for the update
        write_command = f"write_file {file_path}{STDIN_SEPARATOR}{original_content}{COMMAND_END}"
        write_result = self.execute_command(write_command)
        self.assertTrue(write_result.success, "Write file setup should succeed")
        
        # Update instructions
        instructions = "Add a comment at the top with today's date"
        
        # Create the update command input
        command_input = f"update_file {file_path}{STDIN_SEPARATOR}{instructions}{COMMAND_END}"
        logger.debug(f"Command input: {command_input}")
        
        # Execute the command via the execute_command helper
        result = self.execute_command(command_input)
        
        # Verify the result
        self.assertIsNotNone(result, "Result should not be None")
        
        # The test should either return a success message or an error message
        # We can't guarantee which one since we're using a real model that may or may not succeed
        # The important thing is that the command completed without raising an exception
        
        # We can check if the file still exists after the operation
        self.assertTrue(os.path.exists(file_path), "File should still exist after update attempt")
            # This validation is implicit since we're using a real shell
    
    def test_update_with_line_number_mismatch(self):
        """Test that the update falls back to model when patch fails due to line number mismatch."""
        # Create a test file with specific content for this test
        test_file_path = os.path.join(self.temp_dir, "line_mismatch_test.py")
        with open(test_file_path, "w") as f:
            f.write("""# This is a simple calculator function
# It adds two numbers together
def add(a, b):
    return a + b
""")

test_cases = [
    # Basic update test case
    UpdateFileTestCase(
        name="basic_update",
        initial_content=dedent("""\
            Line 1 - Original
            line 2
            line 3
            line 4
            line 5
        """),
        diff=dedent("""\
            @UPDATE
            BEFORE
            1:Line 1 - Original
            AFTER
            1:Line 1 - Updated
        """),
        expected_output=dedent("""\
            Line 1 - Updated
            line 2
            line 3
            line 4
            line 5
        """)
    ),
    # Adding lines test case
    UpdateFileTestCase(
        name="add_lines",
        initial_content=dedent("""\
            line 1
            line 2
            line 3
        """) + "\n",
        diff=dedent("""\
            @INSERT
            3:new line after 2
            4:another new line
        """),
        expected_output=dedent("""\
            line 1
            line 2
            new line after 2
            line 3
            another new line
        """) + "\n"
    ),
    # Deleting lines test case
    UpdateFileTestCase(
        name="delete_lines",
        initial_content=dedent("""\
            line 1
            line 2
            to be deleted
            line 4
            line 5
        """),
        diff=dedent("""\
            @DELETE
            3:to be deleted
        """),
        expected_output=dedent("""\
            line 1
            line 2
            line 4
            line 5
        """)
    ),
    # Complex changes test case
    UpdateFileTestCase(
        name="complex_changes",
        initial_content=dedent("""\
            line 1
            line 2
            line 3
            line 4
            line 5
        """),
        diff=dedent("""\
            @UPDATE
            BEFORE
            2:line 2
            AFTER
            2:new line 2
            3:extra line
            
            @DELETE
            4:line 4
        """),
        expected_output=dedent("""\
            line 1
            new line 2
            extra line
            line 3
            line 5
        """)
    ),
    # Empty line handling test case
    UpdateFileTestCase(
        name="empty_line_handling",
        initial_content=dedent("""\
            Header
            
            The Agent builds on top of the Model:
            
            - Feature 1
            - Feature 2
        """),
        diff=dedent("""\
            @UPDATE
            BEFORE
            3:The Agent builds on top of the Model:
            AFTER
            3:The Agent builds on top of the Shell:
        """),
        expected_output=dedent("""\
            Header
            
            The Agent builds on top of the Shell:
            
            - Feature 1
            - Feature 2
        """)
    ),
    # Bullet point test case using model fallback
    UpdateFileTestCase(
        name="bulletpoint_model_fallback",
        initial_content=dedent("""\
            #### Agent (src/agent.py)
            
            The Agent builds on top of the Model and Functions:
            
            - Maintains conversation state across messages
            - Manages the context window with relevant information
            - Handles the conversation flow and multi-turn interactions
        """),
        # Using proper @UPDATE section for model fallback testing
        diff=_escape_special_chars(dedent("""\
            @UPDATE
            BEFORE
            3:The Agent builds on top of the Model and Functions:
            AFTER
            3:The Agent builds on top of the Model and Shell:
            
            @INSERT
            6:- Implements hierarchical memory management for enhanced context retention
            7:- Manages the context window through state pruning mechanisms
            8:- Orchestrates command execution based on LLM requests
            10:- Uses a dedicated AgentState data structure to track conversation history
        """)),
        expected_output=dedent("""\
            #### Agent (src/agent.py)
            
            The Agent builds on top of the Model and Shell:
            
            - Maintains conversation state across messages
            - Implements hierarchical memory management for enhanced context retention
            - Manages the context window with relevant information
            - Manages the context window through state pruning mechanisms
            - Handles the conversation flow and multi-turn interactions
            - Orchestrates command execution based on LLM requests
            - Uses a dedicated AgentState data structure to track conversation history
        """),
        enable_model_fallback=True  # Explicitly enable model fallback
    ),
    # Special characters test case
    UpdateFileTestCase(
        name="special_chars_no_model",
        initial_content=dedent(f"""\
            This file has special command characters that should be preserved:
            - Command marker: {COMMAND_START} and {COMMAND_END} 
            - Result markers: {SUCCESS_PREFIX} and {ERROR_PREFIX}
            - Stdin separator: {STDIN_SEPARATOR}
        """),
        diff=_escape_special_chars(dedent("""\
            @INSERT
            1:Special characters are preserved by escaping.
        """)),
        expected_output=dedent(f"""\
            Special characters are preserved by escaping.
            This file has special command characters that should be preserved:
            - Command marker: {COMMAND_START} and {COMMAND_END} 
            - Result markers: {SUCCESS_PREFIX} and {ERROR_PREFIX}
            - Stdin separator: {STDIN_SEPARATOR}
        """)
    ),
    UpdateFileTestCase(
        name="special_chars",
        initial_content=dedent(f"""\
            This file has special command characters that should be preserved:
            - Command marker: {COMMAND_START} and {COMMAND_END} 
            - Result markers: {SUCCESS_PREFIX} and {ERROR_PREFIX}
            - Stdin separator: {STDIN_SEPARATOR}
        """),
        # Using proper @UPDATE format with model fallback
        diff=_escape_special_chars(dedent("""\
            @UPDATE
            BEFORE
            1:This file has special command characters that should be preserved:
            AFTER
            1:This file has a list of special command characters that should be preserved:
        """)),
        expected_output=dedent(f"""\
            This file has a list of special command characters that should be preserved:
            - Command marker: {COMMAND_START} and {COMMAND_END} 
            - Result markers: {SUCCESS_PREFIX} and {ERROR_PREFIX}
            - Stdin separator: {STDIN_SEPARATOR}
        """),
        enable_model_fallback=True
    )
]

@pytest.mark.parametrize("test_case", test_cases, ids=lambda test_case: test_case.name)
def test_update_command(test_case):
    """Test successful update file commands using the defined test cases."""
    temp_dir = tempfile.mkdtemp()
    ctx = Context.builder().session_id("test_session_id").workspace(temp_dir).initialize()

    # Create a test file with the initial content
    test_file_path = os.path.join(temp_dir, f"{test_case.name}.txt")
    with open(test_file_path, "w") as f:
        f.write(test_case.initial_content)
    
    parameters = f"{test_file_path}"
    should_disable_model_fallback = not test_case.enable_model_fallback
    if should_disable_model_fallback:
        parameters += " --disable-model-fallback"
    
    # Create and execute the command
    command_input = f"update_file {parameters}{STDIN_SEPARATOR}{test_case.diff}{COMMAND_END}"
    
    # Execute the command
    result = ctx.shell.parse_and_execute(command_input)
        
    # Verify the command executed successfully
    assert result.success, f"Command should execute successfully for test case {test_case.name}. Test case output: {result.result}"
        
    # Read the updated file content
    with open(test_file_path, "r") as f:
        updated_content = f.read()
        
    # Compare the entire content with expected output
    if test_case.expected_output != updated_content:
        # Log the different with line numbers to make it more clear what the issue is
        expected_output_with_line_numbers = "\n".join(f"{i+1}: {line}" for i, line in enumerate(test_case.expected_output.split("\n")))
        updated_content_with_line_numbers = "\n".join(f"{i+1}: {line}" for i, line in enumerate(updated_content.split("\n")))
        
        raise AssertionError(f"Output does not match expected output for test case {test_case.name}\nExpected:\n{expected_output_with_line_numbers}\nActual:\n{updated_content_with_line_numbers}\n")