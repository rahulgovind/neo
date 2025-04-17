import unittest
from unittest.mock import MagicMock, patch, call
import pytest
import os
import openai
from datetime import datetime

from src.neo.client.client import Client
from src.neo.client.base import BaseClient
from src.neo.core.messages import Message, TextBlock, CommandCall, ContentBlock, CommandResult
from src.neo.shell.shell import Shell
from src.neo.core.constants import COMMAND_START, COMMAND_END, SUCCESS_PREFIX, ERROR_PREFIX
from src.logging.structured_logger import StructuredLogger


class TestClient(unittest.TestCase):
    """Tests for the Client class functionality."""

    def setUp(self):
        """Set up test fixtures before each test method."""
        # Mock Shell instance
        self.mock_shell = MagicMock(spec=Shell)
        self.mock_shell.describe.return_value = "Mock command description"
        
        # Create environment variables required for BaseClient
        os.environ["API_KEY"] = "test-api-key"
        os.environ["MODEL_ID"] = "test-model"
        
        # Patch the _add_openrouter_metadata method to prevent API calls
        self.add_openrouter_metadata_patcher = patch.object(BaseClient, '_add_openrouter_metadata')
        self.mock_add_openrouter_metadata = self.add_openrouter_metadata_patcher.start()
        self.mock_add_openrouter_metadata.return_value = {
            "timestamp": datetime.now().isoformat(),
            "native_tokens_prompt": 10,
            "native_tokens_completion": 5,
            "approx_num_tokens": 15,
            "cache_discount": 0,
            "usage": 0.000123
        }
        
        # Patch structured logger to prevent serialization errors
        self.logger_patcher = patch("src.neo.client.base.StructuredLogger")
        self.mock_logger_class = self.logger_patcher.start()
        self.mock_logger = self.mock_logger_class.return_value
        self.mock_logger.record = MagicMock()  # No-op for the record method
        
        # Create a patcher for the openai.Client
        self.openai_client_patcher = patch("openai.Client")
        self.mock_openai_client_class = self.openai_client_patcher.start()
        self.mock_openai_client = self.mock_openai_client_class.return_value
        
        # Setup mock chat completion response
        mock_completion = MagicMock()
        mock_completion.id = "mock-completion-id"
        mock_completion.created = int(datetime.now().timestamp())
        mock_completion.model = "test-model"
        
        # Setup mock choice
        mock_choice = MagicMock()
        mock_choice.message = MagicMock(content="Response content")
        mock_choice.finish_reason = "stop"
        mock_completion.choices = [mock_choice]
        
        # Setup usage metrics
        mock_completion.usage = MagicMock()
        mock_completion.usage.prompt_tokens = 10
        mock_completion.usage.completion_tokens = 5
        mock_completion.usage.total_tokens = 15
        
        # Set the return value for chat.completions.create
        self.mock_openai_client.chat.completions.create.return_value = mock_completion
        
        # Create the Client instance with the mocked dependencies
        self.client = Client(self.mock_shell)

    def tearDown(self):
        """Clean up after each test method."""
        self.openai_client_patcher.stop()
        self.logger_patcher.stop()
        self.add_openrouter_metadata_patcher.stop()
        
        # Clean up environment variables
        if "API_KEY" in os.environ:
            del os.environ["API_KEY"]
        if "MODEL_ID" in os.environ:
            del os.environ["MODEL_ID"]
            
    def _create_completion_mock(self, response_factory):
        """
        Create a mock for OpenAI chat completions that uses a factory function to generate responses.
        
        Args:
            response_factory: A function that takes the request parameters and returns a response object
                             or a list of response objects to be used as side_effects.
        
        Returns:
            A configured mock for the openai.Client.chat.completions.create method
        """
        # Reset our openai client mock to get a fresh state
        self.mock_openai_client_class.reset_mock()
        self.mock_openai_client = self.mock_openai_client_class.return_value
        
        # Configure the create method to use our factory function
        def side_effect_function(**kwargs):
            # Just pass the kwargs directly to avoid duplicate parameters
            return response_factory(**kwargs)
            
        self.mock_openai_client.chat.completions.create.side_effect = side_effect_function
        return self.mock_openai_client.chat.completions.create

    def test_content_block_conversion_to_text(self):
        """Test that different ContentBlock types are correctly converted to text."""
        # Create a custom content block type for testing
        class CustomBlock(ContentBlock):
            def model_text(self):
                return "custom block text"
        
        # Create test messages with different ContentBlock types
        system_message = Message(
            role="system",
            content=[TextBlock("System instruction")]
        )
        
        user_message = Message(
            role="user",
            content=[
                TextBlock("Text block content"),
                CommandCall(f"{COMMAND_START}command args{COMMAND_END}"),
                CustomBlock()
            ]
        )
        
        # We're already setting up the mock response in setUp
        
        # Process messages
        self.client.process([system_message, user_message])
        
        # Get the call arguments for the mocked openai.Client.chat.completions.create
        call_args = self.mock_openai_client.chat.completions.create.call_args
        processed_messages = call_args[1]["messages"]
        
        # Check system message (first message) content is preserved
        self.assertEqual(processed_messages[0]["content"][0]["text"], "System instruction")
        
        # Check that the message content has been converted to text
        self.assertEqual(processed_messages[1]["content"][0]["text"], 
                         "Text block content\n" + 
                         f"{COMMAND_START}command args{COMMAND_END}\n" + 
                         "custom block text")

    def test_command_instructions_in_system_message(self):
        """Test that command instructions are correctly added to the system message."""
        # Create a system message
        system_message = Message(
            role="system",
            content=[TextBlock("System instruction")]
        )
        
        # Create a user message
        user_message = Message(
            role="user",
            content=[TextBlock("User message")]
        )
        
        # Define commands to include
        commands = ["cmd1", "cmd2"]
        
        # Configure mock shell to return descriptions
        self.mock_shell.describe.side_effect = [
            "Description of cmd1",
            "Description of cmd2"
        ]
        
        # We're already setting up the mock response in setUp
        
        # Process messages with commands
        self.client.process([system_message, user_message], commands=commands)
        
        # Get the call arguments for the mocked openai client
        call_args = self.mock_openai_client.chat.completions.create.call_args
        processed_system_message = call_args[1]["messages"][0]
        
        # Extract the system message content
        system_content = processed_system_message["content"][0]["text"]
        
        # Verify command instructions are included in system message
        self.assertIn(Client.COMMAND_INSTRUCTIONS, system_content)
        self.assertIn("Description of cmd1", system_content)
        self.assertIn("Description of cmd2", system_content)
        
        # Verify the shell.describe method was called correctly
        self.mock_shell.describe.assert_has_calls([
            call("cmd1"),
            call("cmd2")
        ])

    def test_parsing_command_calls_from_response(self):
        """Test that completion API responses with command calls are correctly parsed."""
        # Create a mock response from the API containing command calls
        command_text = f"{COMMAND_START}list files{COMMAND_END}"
        success_result = f"{SUCCESS_PREFIX}Files: file1.txt, file2.txt{COMMAND_END}"
        error_result = f"{ERROR_PREFIX}File not found{COMMAND_END}"
        
        response_text = f"Here's the output:\n{command_text}\n{success_result}\nAnd another:\n{command_text}\n{error_result}\nDone."
        
        # Setup the mock OpenAI client to return a response with command calls
        mock_choice = MagicMock()
        mock_choice.message = MagicMock(content=response_text)
        mock_choice.finish_reason = "stop"
        self.mock_openai_client.chat.completions.create.return_value.choices = [mock_choice]
        
        # Process a simple message
        system_message = Message(role="system", content=[TextBlock("System instruction")])
        user_message = Message(role="user", content=[TextBlock("List my files")])
        response = self.client.process([system_message, user_message])
        
        # Check that command calls are correctly identified
        command_calls = response.get_command_calls()
        self.assertEqual(len(command_calls), 2)
        
        # Check content of first command call
        self.assertEqual(command_calls[0].model_text(), f"{COMMAND_START}list files{COMMAND_END}")
        
        # Check content of second command call
        self.assertEqual(command_calls[1].model_text(), f"{COMMAND_START}list files{COMMAND_END}")
        
        # Verify that the response contains appropriate text blocks before/after commands
        text_blocks = [block for block in response.content if isinstance(block, TextBlock)]
        self.assertGreaterEqual(len(text_blocks), 3)  # At least 3 text blocks
        
        # Check for the presence of success and error markers in the text
        full_response_text = response.text()
        self.assertIn(SUCCESS_PREFIX, full_response_text)
        self.assertIn(ERROR_PREFIX, full_response_text)
        
        # Check that we passed the appropriate stop sequences to the API
        call_args = self.mock_openai_client.chat.completions.create.call_args
        self.assertIn("stop", call_args[1])
        stop_sequences = call_args[1]["stop"]
        self.assertIn(SUCCESS_PREFIX, stop_sequences)
        self.assertIn(ERROR_PREFIX, stop_sequences)
        
    def test_command_validation(self):
        """Test that client.process correctly handles invalid commands with retry logic."""
        # Setup messages for the test
        system_message = Message(role="system", content=[TextBlock("You are an AI assistant.")])
        user_message = Message(role="user", content=[TextBlock("Please help me")])
        messages = [system_message, user_message]
        
        # Setup our validation for the Shell
        def validate_side_effect(cmd):
            # Check if command is a CommandCall object (in which case we need to get the text)
            # or a string (which is what we're expecting from COMMAND_START...COMMAND_END)
            cmd_text = cmd.model_text() if hasattr(cmd, 'model_text') else cmd
            return (CommandResult(content="Invalid command: not found", success=False) 
                   if "invalid_command" in cmd_text 
                   else CommandResult(content="Valid command", success=True))
                   
        self.mock_shell.validate.side_effect = validate_side_effect
        
        # Keep track of API calls to verify retry logic
        api_call_count = 0
        
        # Helper function to create mock completions responses
        def create_mock_completion(messages, **kwargs):
            nonlocal api_call_count
            api_call_count += 1
            
            # Create a mock completion object
            mock_completion = MagicMock()
            mock_completion.id = f"mock-completion-{api_call_count}"
            mock_completion.created = int(datetime.now().timestamp())
            mock_completion.model = kwargs.get('model', 'test-model')
            mock_completion.usage = MagicMock(prompt_tokens=10, completion_tokens=5, total_tokens=15)
            
            # Create the choice with appropriate content based on call count
            mock_choice = MagicMock()
            
            # First call - return response with invalid command
            if api_call_count == 1:
                mock_choice.message.content = "Let me run a command:\n\n" + \
                                           f"{COMMAND_START}invalid_command --param value{COMMAND_END}\n\n" + \
                                           "Did that work?"
            else:
                # Second call - return response with valid command
                # This should include the validation message in the input
                # Check that we have at least 4 messages (original + response + validation feedback)
                self.assertGreaterEqual(len(messages), 4, 
                                       "Second API call should include validation feedback")
                
                # Verify that validation message is included
                self.assertTrue(any("Invalid command: not found" in str(m.get('content', '')) 
                                  for m in messages),
                              "Validation feedback should be included in messages")
                
                mock_choice.message.content = f"{COMMAND_START}valid_command --param value{COMMAND_END}"
            
            mock_choice.finish_reason = "stop"
            mock_completion.choices = [mock_choice]
            
            return mock_completion
        
        # Set up the mock for OpenAI completions
        self._create_completion_mock(create_mock_completion)
        
        # Call the client's process method which should handle validation and retry
        result = self.client.process(messages)
        
        # Verify the expected behavior
        # 1. Should have made 2 API calls (original + retry)
        self.assertEqual(api_call_count, 2, "Should make 2 API calls due to validation failure")
        
        # 2. The validate method should be called - we can't check exact arguments because
        # they are CommandCall objects, but we can check the call count and inspect call args
        self.assertGreaterEqual(self.mock_shell.validate.call_count, 1, 
                             "Shell.validate should be called at least once")
        
        # Check that one of the validate calls contains 'invalid_command'
        has_invalid_command_call = False
        for call_args in self.mock_shell.validate.call_args_list:
            cmd_obj = call_args[0][0]  # First positional arg of the call
            if hasattr(cmd_obj, 'model_text') and 'invalid_command' in cmd_obj.model_text():
                has_invalid_command_call = True
                break
                
        self.assertTrue(has_invalid_command_call, "Shell.validate should be called for the invalid command")
        
        # 3. The result should contain the valid command
        command_calls = result.get_command_calls()
        self.assertEqual(len(command_calls), 1, "Result should have one command")
        # CommandCall.model_text() includes the command markers, so check if it contains our command string
        self.assertIn("valid_command --param value", command_calls[0].model_text())


if __name__ == "__main__":
    unittest.main()
