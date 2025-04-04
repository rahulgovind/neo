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
    

# class TestUpdateFileCommand(FileCommandTestBase):
#     """Tests for the UpdateFileCommand class."""
    
#     def setUp(self):
#         """Set up test environment."""
#         super().setUp()
        
#         # Create a test text file to update for non-parametrized tests
#         self.test_file = os.path.join(self.temp_dir, "test_file.txt")
#         with open(self.test_file, "w") as f:
#             f.write("Initial content for update test\n")
            
#         # Create a test Python file to update for non-parametrized tests
#         self.test_py_file = os.path.join(self.temp_dir, "test_file.py")
#         with open(self.test_py_file, "w") as f:
#             f.write(dedent("""#!/usr/bin/env python3
#             # Test file for update command tests

#             def main():
#                 print("Hello, world!")

#             if __name__ == "__main__":
#                 main()
#             """))
    
#     def test_path_parameter(self):
#         """Test the path parameter validation."""
#         # Define a new file path
#         new_file = os.path.join(self.temp_dir, "should_not_be_updated.txt")
        
#         # Create file with initial content
#         with open(new_file, "w") as f:
#             f.write("Original content")
        
#         # Test with missing path parameter - use a known valid existing file
#         # to test only the path parameter validation
#         file_path = self.test_py_file
#         self.assertTrue(os.path.exists(file_path), "Test file should exist")
        
#         # Create a path command with invalid empty path
#         # First parse the command to get parameters and data - don't execute it directly
#         try:
#             # First try a command with empty path string
#             command_input = f"update_file ''{STDIN_SEPARATOR}Add a docstring{COMMAND_END}"
#             parsed_cmd = self.shell.parse(command_input)
#             result = self.shell.execute(parsed_cmd.name, parsed_cmd.parameters, parsed_cmd.data)
#             # If we get here, the empty path didn't throw an error, which is unexpected
#             self.fail("Empty path should have caused an error")
#         except FatalError as e:
#             # We expect a FatalError with a message about the path
#             self.assertIn("path", str(e).lower(), "Error should mention the path problem")
    
#     def test_missing_instructions(self):
#         """Test attempting to update a file without providing instructions."""
#         # Define an existing file path
#         file_path = self.test_py_file
#         self.assertTrue(os.path.exists(file_path), "Test file should exist")
        
#         # Command without data (instructions)
#         command_input = f"update_file {file_path}{COMMAND_END}"
#         logger.debug(f"Command input without instructions: {command_input}")
        
#         # Execute the command - should fail with appropriate error
#         with self.assertRaises(FatalError) as context:
#             # We need to catch the error at the parse stage
#             parsed_cmd = self.shell.parse(command_input)
        
#         # Verify the error message
#         self.assertIn("requires data", str(context.exception).lower())
    
#     def test_file_not_found(self):
#         """Test updating a non-existent file."""
#         # Non-existent file path
#         nonexistent_file = os.path.join(self.temp_dir, "nonexistent.py")
#         self.assertFalse(os.path.exists(nonexistent_file), "Test file should not exist")
        
#         # Use the command line format to test through the shell
#         command_line = f"update_file {nonexistent_file}{STDIN_SEPARATOR}Add a docstring{COMMAND_END}"
        
#         try:
#             # Parse the command - this should work
#             parsed_cmd = self.shell.parse(command_line)
            
#             # Execute the command - this should return a CommandResult with success=False
#             result = self.shell.execute(
#                 parsed_cmd.name,
#                 parsed_cmd.parameters,
#                 parsed_cmd.data
#             )
            
#             # Check that the result contains the expected error
#             self.assertFalse(result.success)
#             self.assertIn("not found", result.error.lower())
            
#         except Exception as e:
#             # If any exception is raised, it should be a controlled one
#             # with proper error messaging
#             if isinstance(e, FatalError):
#                 # If it's a FatalError, check that it has the right message
#                 self.assertIn("not found", str(e).lower())
#             else:
#                 # Otherwise, this is unexpected and should fail the test
#                 self.fail(f"Unexpected exception type: {type(e).__name__}, message: {str(e)}")
    
#     def test_update_process(self):
#         """Test the update file command process method using the shell."""
#         # Use a test file
#         file_path = self.test_py_file
#         self.assertTrue(os.path.exists(file_path), "Test file should exist")
        
#         # Save original content for comparison
#         with open(file_path, 'r') as f:
#             original_content = f.read()
        
#         # Write initial content to file to prepare for the update
#         write_command = f"write_file {file_path}{STDIN_SEPARATOR}{original_content}{COMMAND_END}"
#         write_result = self.execute_command(write_command)
#         self.assertTrue(write_result.success, "Write file setup should succeed")
        
#         # Update instructions
#         instructions = "Add a comment at the top with today's date"
        
#         # Create the update command input
#         command_input = f"update_file {file_path}{STDIN_SEPARATOR}{instructions}{COMMAND_END}"
#         logger.debug(f"Command input: {command_input}")
        
#         # Execute the command via the execute_command helper
#         result = self.execute_command(command_input)
        
#         # Verify the result
#         self.assertIsNotNone(result, "Result should not be None")
        
#         # The test should either return a success message or an error message
#         # We can't guarantee which one since we're using a real model that may or may not succeed
#         # The important thing is that the command completed without raising an exception
        
#         # We can check if the file still exists after the operation
#         self.assertTrue(os.path.exists(file_path), "File should still exist after update attempt")
#             # This validation is implicit since we're using a real shell
    
#     def test_update_with_line_number_mismatch(self):
#         """Test that the update falls back to model when patch fails due to line number mismatch."""
#         # Create a test file with specific content for this test
#         test_file_path = os.path.join(self.temp_dir, "line_mismatch_test.py")
#         with open(test_file_path, "w") as f:
#             f.write("""# This is a simple calculator function
# # It adds two numbers together
# def add(a, b):
#     return a + b
# """)
            
#         # Create a diff with an extra space after the line number
#         # This will cause the patch to fail due to format mismatch, triggering model fallback
#         # But the model should be able to understand the intent from the surrounding context
#         diff = "-1  # This is a simple calculator function\n+1 # This is a calculator function that adds two numbers\n\n-3 def add(a, b):\n+3 def add_numbers(a, b):\n"
        
#         # Create and execute the command
#         command_input = f"update_file {test_file_path}{STDIN_SEPARATOR}{diff}{COMMAND_END}"
#         result = self.execute_command(command_input)
        
#         # The test may pass or fail depending on whether the model saved the file successfully
#         # We're only checking that it didn't raise an unhandled exception
#         self.assertIsNotNone(result)
        
#         # We only care that the command handled the error condition without crashing completely
#         # Even if result is not successful, the test passes as long as it returns something
#         logger.debug(f"Command result: {result.result if hasattr(result, 'result') and result.result else 'No result'}")
#         logger.debug(f"Command success: {result.success if hasattr(result, 'success') else 'Unknown'}")
        
#         # Result should not be None - if we got here without an exception, that's good enough
#         # The important part is that the command didn't crash when dealing with the line number mismatch
        
#         # The file should still exist after the update attempt
#         self.assertTrue(os.path.exists(test_file_path), "File should exist after update attempt")
        
#         # Read the file content after the update attempt
#         with open(test_file_path, "r") as f:
#             updated_content = f.read()
        
#         # The test can only pass if the model successfully updated the file
#         # Check if the function name was changed to add_numbers
#         self.assertIn("def add_numbers", updated_content, 
#                       "Model should have updated function name using contextual information")
#         # Check if the first line comment was updated
#         self.assertIn("calculator function that adds", updated_content,
#                      "Model should have updated the comment using contextual information")
#         # Make sure it didn't just append the new function but actually replaced it
#         self.assertNotIn("def add(a, b):", updated_content,
#                         "Model should have replaced the old function")
    
#     def test_update_with_special_characters(self):
#         """Test updating a file that contains special command characters."""
#         from src.core.constants import COMMAND_START, COMMAND_END, STDIN_SEPARATOR, ERROR_PREFIX, SUCCESS_PREFIX
        
#         # Create a test file with special characters
#         test_file_path = os.path.join(self.temp_dir, "special_chars_test.txt")
#         original_content = f"""This file contains special characters:
# 1. Command start: {COMMAND_START}
# 2. Command end: {COMMAND_END}
# 3. Stdin separator: {STDIN_SEPARATOR}
# 4. Error prefix: {ERROR_PREFIX}
# 5. Success prefix: {SUCCESS_PREFIX}

# These should be properly escaped when processed.
# """
        
#         with open(test_file_path, "w") as f:
#             f.write(original_content)
        
#         # Create a diff for the update - using the format from the examples
#         # Add a new line at the end of the file
#         diff = "+9 Test completed successfully."
        
#         # Create and execute the command
#         command_input = f"update_file {test_file_path}{STDIN_SEPARATOR}{diff}{COMMAND_END}"
#         result = self.execute_command(command_input)
        
#         # Verify the command executed successfully
#         self.assertTrue(result.success, "Command should execute successfully")
        
#         # Read the updated file content
#         with open(test_file_path, "r") as f:
#             updated_content = f.read()
        
#         # Verify that all special characters are still present and weren't corrupted
#         self.assertIn(COMMAND_START, updated_content, "Command start character should be preserved")
#         self.assertIn(COMMAND_END, updated_content, "Command end character should be preserved")
#         self.assertIn(STDIN_SEPARATOR, updated_content, "Stdin separator character should be preserved")
#         self.assertIn(ERROR_PREFIX, updated_content, "Error prefix character should be preserved")
#         self.assertIn(SUCCESS_PREFIX, updated_content, "Success prefix character should be preserved")
        
#         # Verify the update was applied
#         self.assertIn("Test completed successfully.", updated_content, "Update should be applied")
        
#     def test_update_with_special_chars_replace_line(self):
#         """Test updating a file containing special characters by replacing lines."""
#         from src.core.constants import COMMAND_START, COMMAND_END, STDIN_SEPARATOR, ERROR_PREFIX, SUCCESS_PREFIX
        
#         # Create a test file with special characters
#         test_file_path = os.path.join(self.temp_dir, "special_chars_replace_test.txt")
#         original_content = f"""Line 1: Normal text
# Line 2: Command start: {COMMAND_START}
# Line 3: Command end: {COMMAND_END}
# Line 4: Stdin separator: {STDIN_SEPARATOR}
# Line 5: Error and success: {ERROR_PREFIX} {SUCCESS_PREFIX}
# """
        
#         with open(test_file_path, "w") as f:
#             f.write(original_content)
        
#         # Create a diff that replaces Line 2 and keeps Line 3 as is
#         diff = "-2 Line 2: Command start: {0}\n+2 Line 2: REPLACED - Command start: {0}\n 3 Line 3: Command end: {1}".format(COMMAND_START, COMMAND_END)
        
#         # Create and execute the command
#         command_input = f"update_file {test_file_path}{STDIN_SEPARATOR}{diff}{COMMAND_END}"
#         result = self.execute_command(command_input)
        
#         # Verify the command executed successfully
#         self.assertTrue(result.success, "Command should execute successfully")
        
#         # Read the updated file content
#         with open(test_file_path, "r") as f:
#             updated_content = f.read()
        
#         # Verify that all special characters are still present and weren't corrupted
#         self.assertIn(COMMAND_START, updated_content, "Command start character should be preserved")
#         self.assertIn(COMMAND_END, updated_content, "Command end character should be preserved")
#         self.assertIn(STDIN_SEPARATOR, updated_content, "Stdin separator character should be preserved")
#         self.assertIn(ERROR_PREFIX, updated_content, "Error prefix character should be preserved")
#         self.assertIn(SUCCESS_PREFIX, updated_content, "Success prefix character should be preserved")
        
#         # Verify the specific update was applied
#         self.assertIn(f"Line 2: REPLACED - Command start: {COMMAND_START}", updated_content, "Line replacement should be applied")

        
#     def get_failure_test_cases(self):
#         """Return the list of failure test cases."""
#         return [
#             # Test case with invalid line mismatch
#             UpdateFileFailureTestCase(
#                 name="line_mismatch",
#                 initial_content=dedent("""\
#                     line 1
#                     line 2
#                     line 3
#                 """),
#                 diff="-2 wrong content",
#                 expected_error="line mismatch"
#             ),
#             # Test case with an invalid diff format
#             UpdateFileFailureTestCase(
#                 name="invalid_format",
#                 initial_content=dedent("""\
#                     line 1
#                     line 2
#                     line 3
#                 """),
#                 diff="x2 line 2",  # Invalid prefix
#                 expected_error="invalid diff line format"
#             ),
#             # Test case with invalid line numbers
#             UpdateFileFailureTestCase(
#                 name="invalid_line_numbers",
#                 initial_content=dedent("""\

#                     line 1
#                     line 2
#                     line 3
#                 """) + "\n",
#                 diff="-10 nonexistent line",  # Line number out of range
#                 expected_error="line number out of range"
#             ),
#             # Test case with missing file
#             UpdateFileFailureTestCase(
#                 name="missing_file",
#                 initial_content="",  # Empty content as the file won't exist
#                 diff="-1 anything",
#                 expected_error="file not found"
#             )
#         ]
        
#     def test_patch_failures(self):
#         """Test failure cases for the patch function directly."""
#         from src.utils.files import patch
        
#         for test_case in self.get_failure_test_cases():
#             # Handle the missing file test case specially
#             if test_case.name == "missing_file":
#                 # Use a path that doesn't exist
#                 test_file_path = os.path.join(self.temp_dir, "nonexistent_file.txt")
                
#                 # The patch function should fail with the expected error
#                 with self.assertRaises(FatalError) as context:
#                     patch(test_file_path, test_case.diff)
                    
#                 # Verify the error message contains the expected text
#                 self.assertIn(test_case.expected_error.lower(), str(context.exception).lower())
#             elif test_case.name == "invalid_line_numbers":
#                 # Create a test file with the initial content
#                 test_file_path = os.path.join(self.temp_dir, f"{test_case.name}.txt")
#                 with open(test_file_path, "w") as f:
#                     f.write(test_case.initial_content)
                
#                 # For this specific test, we expect an IndexError or a FatalError
#                 # Either is acceptable since the implementation might raise IndexError first
#                 # before it can check and convert to a FatalError
#                 try:
#                     patch(test_file_path, test_case.diff)
#                     self.fail("Expected exception not raised")
#                 except (IndexError, FatalError) as e:
#                     # If it's a FatalError, check the message
#                     if isinstance(e, FatalError):
#                         self.assertIn(test_case.expected_error.lower(), str(e).lower())
#             else:
#                 # Create a test file with the initial content
#                 test_file_path = os.path.join(self.temp_dir, f"{test_case.name}.txt")
#                 with open(test_file_path, "w") as f:
#                     f.write(test_case.initial_content)
                
#                 # The patch function should fail with the expected error
#                 with self.assertRaises(FatalError) as context:
#                     patch(test_file_path, test_case.diff)
                    
#                 # Verify the error message contains the expected text
#                 self.assertIn(test_case.expected_error.lower(), str(context.exception).lower())

        
test_cases = [
    # Basic update test case
    UpdateFileTestCase(
        name="basic_update",
        initial_content=dedent("""\
            line 1
            line 2
            line 3
            line 4
            line 5
        """),
        diff=dedent("""\
            @3 Update line 3
            - line 3
            + new line 3
        """),
        expected_output=dedent("""\
            line 1
            line 2
            new line 3
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
            @2 Add new lines after line 2
              line 2
            + new line after 2
            + another new line
        """),
        expected_output=dedent("""\
            line 1
            line 2
            new line after 2
            another new line
            line 3
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
            @3 Delete line
            - to be deleted
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
            @2 Replace line 2 with two lines
            - line 2
            + new line 2
            + extra line
            
            @4 Remove line 4
            - line 4
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
            @3 Update model reference
            - The Agent builds on top of the Model:
            + The Agent builds on top of the Shell:
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
        # Intentionally using a human-readable instruction that doesn't match exact lines
        # to test model fallback behavior
        diff=_escape_special_chars(dedent("""\
            @0 Overwrite file
            #### Agent (src/agent/agent.py)
            
            The Agent builds on top of the Model and Shell:
            
            - Maintains conversation state across messages
            - Implements hierarchical memory management for enhanced context retention
            - Manages the context window through state pruning mechanisms
            - Orchestrates command execution based on LLM requests
            - Handles the conversation flow and multi-turn interactions
            - Uses a dedicated AgentState data structure to track conversation history
        """)),
        expected_output=dedent("""\
            #### Agent (src/agent/agent.py)
            
            The Agent builds on top of the Model and Shell:
            
            - Maintains conversation state across messages
            - Implements hierarchical memory management for enhanced context retention
            - Manages the context window through state pruning mechanisms
            - Orchestrates command execution based on LLM requests
            - Handles the conversation flow and multi-turn interactions
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
            @1 Add special characters
            + Special characters are preserved by escaping.
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
        # Intentionally using a human-readable instruction to test model fallback
        diff=_escape_special_chars(dedent("""\
            Change the first line to say "This file has a list of special command characters that should be preserved:"
            Do not modify any of the special characters or other lines.
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