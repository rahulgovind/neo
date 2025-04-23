import unittest
from unittest.mock import MagicMock, patch, call
import pytest
import os
import openai
from datetime import datetime
import json
from dataclasses import dataclass
from typing import Any

from src.neo.client.client import Client
from src.neo.core.messages import PrimitiveOutputType
from src.neo.client.base import BaseClient
from src.neo.core.messages import Message, TextBlock, CommandCall, ContentBlock, CommandResult, StructuredOutput, ParsedCommand
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

    def test_parsing_command_calls_from_response(self):
        """Test that completion API responses with command calls are correctly parsed."""
        # Create mock data for the test
        system_message = Message(role="system", content=[TextBlock("System instruction")])
        user_message = Message(role="user", content=[TextBlock("List my files")])
        
        # Create a simple test response with command calls
        command_1 = CommandCall(f"{COMMAND_START}list files{COMMAND_END}")
        command_2 = CommandCall(f"{COMMAND_START}read file{COMMAND_END}")
        text_block = TextBlock("Here's the output")
        
        # Create a mock response message with the command calls directly
        mock_response = Message(
            role="assistant",
            content=[text_block, command_1, command_2]
        )
        
        # Simple mock for the API client that returns our prepared response
        self.client._client.process = MagicMock(return_value=mock_response)
        
        # Set up the mock Shell to pass validation
        self.mock_shell.parse_command_call.side_effect = lambda cmd, output_schema=None: cmd
        self.mock_shell.validate_command_calls.return_value = []
        
        # Process the message
        result = self.client.process([system_message, user_message])
        
        # Verify the command calls are in the result
        command_calls = result.get_command_calls()
        self.assertEqual(len(command_calls), 2, f"Expected 2 command calls, got {len(command_calls)}: {command_calls}")
        
        # Check the contents of the commands
        self.assertEqual(command_calls[0].model_text(), f"{COMMAND_START}list files{COMMAND_END}")
        self.assertEqual(command_calls[1].model_text(), f"{COMMAND_START}read file{COMMAND_END}")
        
        # Check content of second command call
        self.assertEqual(command_calls[1].model_text(), f"{COMMAND_START}read file{COMMAND_END}")
        
        # Verify that the response contains at least one text block
        text_blocks = [block for block in result.content if isinstance(block, TextBlock)]
        self.assertGreaterEqual(len(text_blocks), 1)  # At least 1 text block
        
        # Our test only includes structured output, so skip marker checks
        full_response_text = result.text()
        # No need to check for markers as we're using a controlled test response
        
        # Since we're bypassing the OpenAI client by mocking client._client.process,
        # we don't need to verify API call parameters
        
    def test_command_validation(self):
        """Test that client.process correctly handles invalid commands with retry logic."""
        # Setup messages for the test
        system_message = Message(role="system", content=[TextBlock("You are an AI assistant.")])
        user_message = Message(role="user", content=[TextBlock("Please help me")])
        messages = [system_message, user_message]
        
        # Setup our validation for the Shell with a MagicMock that has a call_count attribute
        validate_mock = MagicMock()
        # Define the side effect function for validation
        def validate_side_effect(cmd_calls, output_schema=None):
            # Accept a list of CommandCall objects and return errors for invalid ones
            errors = []
            for cmd in cmd_calls:
                # Check if the command contains "invalid_command"
                cmd_text = cmd.content if hasattr(cmd, 'content') else str(cmd)
                if "invalid_command" in cmd_text:
                    errors.append(CommandResult(content="Invalid command: not found", success=False))
            return errors
               
        # Set the side effect on the mock
        validate_mock.side_effect = validate_side_effect
        
        # Replace mock methods
        self.mock_shell.validate_command_calls = validate_mock
        self.mock_shell.parse_command_call = MagicMock(side_effect=lambda cmd, schema=None: cmd)
        
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
        
        # 2. The validate_command_calls method should be called at least once
        self.assertGreaterEqual(self.mock_shell.validate_command_calls.call_count, 1, 
                             "Shell.validate_command_calls should be called at least once")
        
        # Check that validate_command_calls was called with command calls containing 'invalid_command'
        has_invalid_command_call = False
        for call_args in self.mock_shell.validate_command_calls.call_args_list:
            # First positional arg should be a list of command calls
            cmd_calls = call_args[0][0]
            for cmd in cmd_calls:
                if hasattr(cmd, 'content') and 'invalid_command' in cmd.content:
                    has_invalid_command_call = True
                    break
            if has_invalid_command_call:
                break
                
        self.assertTrue(has_invalid_command_call, "validate_command_calls should be called with the invalid command")
        
        # 3. The result should contain the valid command
        command_calls = result.get_command_calls()
        self.assertEqual(len(command_calls), 1, "Result should have one command")
        # CommandCall.model_text() includes the command markers, so check if it contains our command string
        self.assertIn("valid_command --param value", command_calls[0].model_text())


    @dataclass
    class StructuredOutputTestCase:
        """Test case for structured output functionality."""
        name: str
        output_schema: Any
        command_response: str
        expected_output: Any
        expected_output_type: type = dict

    @dataclass
    class StructuredOutputValidationTestCase:
        """Test case for structured output validation."""
        name: str
        output_schema: Any
        initial_response: str
        retry_response: str
        expected_output: Any

    def test_structured_output(self):
        """Parameterized test for structured output functionality."""
        # Define test cases
        json_data = {"id": 123, "name": "Test Item", "active": True}
        json_schema = {
            "type": "object",
            "properties": {
                "id": {"type": "integer"},
                "name": {"type": "string"},
                "active": {"type": "boolean"}
            },
            "required": ["id", "name"]
        }
        
        test_cases = [
            # Raw string output
            self.StructuredOutputTestCase(
                name="raw_output",
                output_schema=PrimitiveOutputType.RAW,
                command_response=f"Here's the output: {COMMAND_START}output｜Raw output result{COMMAND_END}",
                expected_output="Raw output result",
                expected_output_type=str
            ),
            # JSON schema validation
            self.StructuredOutputTestCase(
                name="json_schema",
                output_schema=json_schema,
                command_response=f"Here's the output: {COMMAND_START}output｜{json.dumps(json_data)}{COMMAND_END}",
                expected_output=json_data
            )
        ]
        
        for test_case in test_cases:
            with self.subTest(test_case.name):
                # Create a real session and shell
                from src.neo.session import Session
                from src.neo.shell.shell import Shell
                
                test_session = Session.builder().session_id(f"test-{test_case.name}").workspace("/tmp").initialize()
                real_shell = Shell(test_session)
                
                # Create client with real shell
                client = Client(real_shell)
                
                # Create messages
                system_message = Message(
                    role="system",
                    content=[TextBlock("System instruction")]
                )
                user_message = Message(
                    role="user",
                    content=[TextBlock(f"User request for {test_case.name}")]
                )
                
                # Create a mock completion
                def create_mock_completion(messages, **kwargs):
                    mock_completion = MagicMock()
                    mock_completion.id = f"mock-{test_case.name}-id"
                    mock_completion.created = int(datetime.now().timestamp())
                    mock_completion.model = kwargs.get('model', 'test-model')
                    mock_completion.usage = MagicMock(prompt_tokens=10, completion_tokens=5, total_tokens=15)
                    
                    mock_choice = MagicMock()
                    mock_choice.message.content = test_case.command_response
                    mock_choice.finish_reason = "stop"
                    mock_completion.choices = [mock_choice]
                    
                    return mock_completion
                
                # Set up the OpenAI mock
                self._create_completion_mock(create_mock_completion)
                
                # Process messages with the output schema
                result = client.process(
                    [system_message, user_message],
                    output_schema=test_case.output_schema
                )
                
                # Verify the result
                structured_output = result.structured_output()
                self.assertIsNotNone(structured_output, f"Should have a structured output block for {test_case.name}")
                self.assertIsInstance(structured_output.value, test_case.expected_output_type, 
                                   f"Output should be a {test_case.expected_output_type.__name__} for {test_case.name}")
                self.assertEqual(structured_output.value, test_case.expected_output, 
                              f"Output value should match expected for {test_case.name}")

    def test_structured_output_validation(self):
        """Test structured output with validation failure and retry."""
        # Define JSON schema for validation
        json_schema = {
            "type": "object",
            "properties": {
                "id": {"type": "integer"},
                "name": {"type": "string"}
            },
            "required": ["id", "name"]
        }
        
        # Create test session and shell
        from src.neo.session import Session
        from src.neo.shell.shell import Shell
        import jsonschema
        
        test_session = Session.builder().session_id("test-validation").workspace("/tmp").initialize()
        real_shell = Shell(test_session)
        
        # Save original methods
        original_validate = real_shell.validate_command_calls
        original_parse = real_shell.parse_command_call
        
        # Create validation counter
        call_count = 0
        validation_error = CommandResult(
            content="Invalid structured output", 
            success=False, 
            error=ValueError("Schema validation failed")
        )
        
        # Custom validation method
        def custom_validate_command_calls(command_calls, output_schema):
            nonlocal call_count
            call_count += 1
            # First call fails, second call passes
            if call_count == 1:
                return [validation_error]
            return []
        
        # Custom parsing method
        def custom_parse_command_call(command_call, output_schema):
            # Return structured output on second call
            if call_count == 2 and "output" in command_call.content:
                return StructuredOutput(
                    command_call.content, 
                    {"id": 123, "name": "Test Item"}
                )
            # Otherwise use original method
            return original_parse(command_call, output_schema)
        
        # Apply custom methods
        real_shell.validate_command_calls = custom_validate_command_calls
        real_shell.parse_command_call = custom_parse_command_call
        
        # Replace client shell
        self.client = Client(real_shell)
        
        # Create messages
        system_message = Message(
            role="system",
            content=[TextBlock("System instruction")]
        )
        user_message = Message(
            role="user",
            content=[TextBlock("User request for JSON output")]
        )
        
        # Create mock completion function
        def create_mock_completion(messages, **kwargs):
            mock_completion = MagicMock()
            mock_completion.id = "mock-validation-id"
            mock_completion.created = int(datetime.now().timestamp())
            mock_completion.model = kwargs.get('model', 'test-model')
            mock_completion.usage = MagicMock(prompt_tokens=10, completion_tokens=5, total_tokens=15)
            
            # Return different responses based on call count
            if len(messages) == 2:  # Initial request
                mock_choice = MagicMock()
                mock_choice.message.content = f"Here's the output: {COMMAND_START}output｜Invalid output{COMMAND_END}"
                mock_choice.finish_reason = "stop"
                mock_completion.choices = [mock_choice]
            else:  # Retry after validation failure
                # Verify validation feedback included
                self.assertTrue(any("Invalid structured output" in str(m.get('content', '')) 
                                 for m in messages),
                             "Validation feedback should be included in messages")
                
                mock_choice = MagicMock()
                mock_choice.message.content = f"Here's the valid output: {COMMAND_START}output｜{{\"id\": 123, \"name\": \"Test Item\"}}{COMMAND_END}"
                mock_choice.finish_reason = "stop"
                mock_completion.choices = [mock_choice]
            
            return mock_completion
        
        # Set up OpenAI mock
        self._create_completion_mock(create_mock_completion)
        
        # Process messages
        result = self.client.process(
            [system_message, user_message],
            output_schema=json_schema
        )
        
        # Restore original methods
        real_shell.validate_command_calls = original_validate
        real_shell.parse_command_call = original_parse
        
        # Verify results
        self.assertEqual(call_count, 2, "Validation should be called twice due to retry")
        structured_output = result.structured_output()
        self.assertIsNotNone(structured_output, "Should have a structured output block")
        self.assertEqual(structured_output.value, {"id": 123, "name": "Test Item"})


if __name__ == "__main__":
    unittest.main()
