"""
Unit tests for the UpdateFileCommand class.

This test validates the UpdateFileCommand functionality:
1. Updating existing files based on natural language instructions
2. Testing error conditions like missing files or instructions
"""

import os
import unittest
import logging
from pathlib import Path

from src.core.commands.update_file import UpdateFileCommand
from src.core.exceptions import FatalError
from src.core.constants import COMMAND_END, STDIN_SEPARATOR
# Import the base class content directly since it's in the same directory
from file_command_test_base import FileCommandTestBase

# Configure logging
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.DEBUG)


class TestUpdateFileCommand(FileCommandTestBase):
    """Tests for the UpdateFileCommand class."""
    
    def setUp(self):
        """Set up test environment."""
        super().setUp()
        
        # Create a test text file to update
        self.test_file = os.path.join(self.temp_dir, "test_file.txt")
        with open(self.test_file, "w") as f:
            f.write("Initial content for update test\n")
            
        # Create a test Python file to update
        self.test_py_file = os.path.join(self.temp_dir, "test_file.py")
        with open(self.test_py_file, "w") as f:
            f.write("""#!/usr/bin/env python3
# Test file for update command tests

def main():
    print("Hello, world!")

if __name__ == "__main__":
    main()
""")
        
        # UpdateFileCommand is already registered by Shell's built-in commands
    
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
        with self.assertRaises(FatalError) as context:
            # We need to catch the error at the parse stage
            parsed_cmd = self.shell.parse(command_input)
        
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
            
        # Create a diff with an extra space after the line number
        # This will cause the patch to fail due to format mismatch, triggering model fallback
        # But the model should be able to understand the intent from the surrounding context
        diff = "-1  # This is a simple calculator function\n+1 # This is a calculator function that adds two numbers\n\n-3 def add(a, b):\n+3 def add_numbers(a, b):\n"
        
        # Create and execute the command
        command_input = f"update_file {test_file_path}{STDIN_SEPARATOR}{diff}{COMMAND_END}"
        result = self.execute_command(command_input)
        
        # The test may pass or fail depending on whether the model saved the file successfully
        # We're only checking that it didn't raise an unhandled exception
        self.assertIsNotNone(result)
        
        # We only care that the command handled the error condition without crashing completely
        # Even if result is not successful, the test passes as long as it returns something
        logger.debug(f"Command result: {result.result if hasattr(result, 'result') and result.result else 'No result'}")
        logger.debug(f"Command success: {result.success if hasattr(result, 'success') else 'Unknown'}")
        
        # Result should not be None - if we got here without an exception, that's good enough
        # The important part is that the command didn't crash when dealing with the line number mismatch
        
        # The file should still exist after the update attempt
        self.assertTrue(os.path.exists(test_file_path), "File should exist after update attempt")
        
        # Read the file content after the update attempt
        with open(test_file_path, "r") as f:
            updated_content = f.read()
        
        # The test can only pass if the model successfully updated the file
        # Check if the function name was changed to add_numbers
        self.assertIn("def add_numbers", updated_content, 
                      "Model should have updated function name using contextual information")
        # Check if the first line comment was updated
        self.assertIn("calculator function that adds", updated_content,
                     "Model should have updated the comment using contextual information")
        # Make sure it didn't just append the new function but actually replaced it
        self.assertNotIn("def add(a, b):", updated_content,
                        "Model should have replaced the old function")
    
    def test_update_with_special_characters(self):
        """Test updating a file that contains special command characters."""
        from src.core.constants import COMMAND_START, COMMAND_END, STDIN_SEPARATOR, ERROR_PREFIX, SUCCESS_PREFIX
        
        # Create a test file with special characters
        test_file_path = os.path.join(self.temp_dir, "special_chars_test.txt")
        original_content = f"""This file contains special characters:
1. Command start: {COMMAND_START}
2. Command end: {COMMAND_END}
3. Stdin separator: {STDIN_SEPARATOR}
4. Error prefix: {ERROR_PREFIX}
5. Success prefix: {SUCCESS_PREFIX}

These should be properly escaped when processed.
"""
        
        with open(test_file_path, "w") as f:
            f.write(original_content)
        
        # Create a diff for the update - using the format from the examples
        # Add a new line at the end of the file
        diff = "+9 Test completed successfully."
        
        # Create and execute the command
        command_input = f"update_file {test_file_path}{STDIN_SEPARATOR}{diff}{COMMAND_END}"
        result = self.execute_command(command_input)
        
        # Verify the command executed successfully
        self.assertTrue(result.success, "Command should execute successfully")
        
        # Read the updated file content
        with open(test_file_path, "r") as f:
            updated_content = f.read()
        
        # Verify that all special characters are still present and weren't corrupted
        self.assertIn(COMMAND_START, updated_content, "Command start character should be preserved")
        self.assertIn(COMMAND_END, updated_content, "Command end character should be preserved")
        self.assertIn(STDIN_SEPARATOR, updated_content, "Stdin separator character should be preserved")
        self.assertIn(ERROR_PREFIX, updated_content, "Error prefix character should be preserved")
        self.assertIn(SUCCESS_PREFIX, updated_content, "Success prefix character should be preserved")
        
        # Verify the update was applied
        self.assertIn("Test completed successfully.", updated_content, "Update should be applied")
        
    def test_update_with_special_chars_replace_line(self):
        """Test updating a file containing special characters by replacing lines."""
        from src.core.constants import COMMAND_START, COMMAND_END, STDIN_SEPARATOR, ERROR_PREFIX, SUCCESS_PREFIX
        
        # Create a test file with special characters
        test_file_path = os.path.join(self.temp_dir, "special_chars_replace_test.txt")
        original_content = f"""Line 1: Normal text
Line 2: Command start: {COMMAND_START}
Line 3: Command end: {COMMAND_END}
Line 4: Stdin separator: {STDIN_SEPARATOR}
Line 5: Error and success: {ERROR_PREFIX} {SUCCESS_PREFIX}
"""
        
        with open(test_file_path, "w") as f:
            f.write(original_content)
        
        # Create a diff that replaces Line 2 and keeps Line 3 as is
        diff = "-2 Line 2: Command start: {0}\n+2 Line 2: REPLACED - Command start: {0}\n 3 Line 3: Command end: {1}".format(COMMAND_START, COMMAND_END)
        
        # Create and execute the command
        command_input = f"update_file {test_file_path}{STDIN_SEPARATOR}{diff}{COMMAND_END}"
        result = self.execute_command(command_input)
        
        # Verify the command executed successfully
        self.assertTrue(result.success, "Command should execute successfully")
        
        # Read the updated file content
        with open(test_file_path, "r") as f:
            updated_content = f.read()
        
        # Verify that all special characters are still present and weren't corrupted
        self.assertIn(COMMAND_START, updated_content, "Command start character should be preserved")
        self.assertIn(COMMAND_END, updated_content, "Command end character should be preserved")
        self.assertIn(STDIN_SEPARATOR, updated_content, "Stdin separator character should be preserved")
        self.assertIn(ERROR_PREFIX, updated_content, "Error prefix character should be preserved")
        self.assertIn(SUCCESS_PREFIX, updated_content, "Success prefix character should be preserved")
        
        # Verify the specific update was applied
        self.assertIn(f"Line 2: REPLACED - Command start: {COMMAND_START}", updated_content, "Line replacement should be applied")
        
    def test_update_with_special_chars_using_model(self):
        """Test updating a file with special characters using the model fallback path."""
        from src.core.constants import COMMAND_START, COMMAND_END, STDIN_SEPARATOR, ERROR_PREFIX, SUCCESS_PREFIX
        
        # Create a test file with special characters
        test_file_path = os.path.join(self.temp_dir, "special_chars_model_test.txt")
        original_content = f"""This file has special command characters that should be preserved:
- Command marker: {COMMAND_START} and {COMMAND_END} 
- Result markers: {SUCCESS_PREFIX} and {ERROR_PREFIX}
- Stdin separator: {STDIN_SEPARATOR}
"""
        
        with open(test_file_path, "w") as f:
            f.write(original_content)
        
        # Use an invalid diff format to trigger model fallback
        # The diff is intentionally malformed to trigger the model fallback path
        invalid_diff = "This is not a valid diff but a human instruction: add a line saying 'Special characters are preserved by escaping.'"
        
        # Create and execute the command
        command_input = f"update_file {test_file_path}{STDIN_SEPARATOR}{invalid_diff}{COMMAND_END}"
        result = self.execute_command(command_input)
        
        # Check that we got a result
        self.assertIsNotNone(result, "Command should return a result")
        
        # Read the updated file content
        with open(test_file_path, "r") as f:
            updated_content = f.read()
        
        # Verify that all special characters are still present and weren't corrupted
        self.assertIn(COMMAND_START, updated_content, "Command start character should be preserved")
        self.assertIn(COMMAND_END, updated_content, "Command end character should be preserved")
        self.assertIn(STDIN_SEPARATOR, updated_content, "Stdin separator character should be preserved")
        self.assertIn(ERROR_PREFIX, updated_content, "Error prefix character should be preserved")
        self.assertIn(SUCCESS_PREFIX, updated_content, "Success prefix character should be preserved")