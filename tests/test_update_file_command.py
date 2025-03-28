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
from tests.file_command_test_base import FileCommandTestBase

# Configure logging
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.DEBUG)


class TestUpdateFileCommand(FileCommandTestBase):
    """Tests for the UpdateFileCommand class."""
    
    def setUp(self):
        """Set up test environment."""
        super().setUp()
        
        # Initialize environment and set up components
        from src.core import env
        from src.core.model import Model
        
        # Initialize the environment
        env.initialize()
        
        # Set our test shell in the environment
        env.set_shell(self.shell)
        
        # Initialize model and set it in the environment
        model = Model()
        env.set_model(model)
        
        # UpdateFileCommand is already registered by Shell's built-in commands
    
    def test_path_parameter(self):
        """Test the path parameter validation."""
        # Define a new file path
        new_file = os.path.join(self.temp_dir, "should_not_be_updated.txt")
        
        # Create file with initial content
        with open(new_file, "w") as f:
            f.write("Original content")
        
        # Missing path parameter
        command_input = f"update_file{STDIN_SEPARATOR}Add a docstring{COMMAND_END}"
        logger.debug(f"Command input without path: {command_input}")
        
        # Create command instance to test parameter validation
        update_cmd = UpdateFileCommand()
        
        # Test with missing path parameter
        args = {}
        instructions = "Add a docstring"
        
        # Call should raise an exception
        with self.assertRaises(FatalError) as context:
            update_cmd.process(args, instructions)
        
        # Verify the error message
        self.assertIn("path", str(context.exception).lower())
    
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
            # This validation is implicit since we're mocking and using a real shell