import pytest
from unittest.mock import MagicMock, patch, call
import os
import openai
from datetime import datetime
import json
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Callable

from src.neo.client.client import Client
from src.neo.core.messages import PrimitiveOutputType
from src.neo.client.base import BaseClient
from src.neo.core.messages import (
    Message,
    TextBlock,
    CommandCall,
    ContentBlock,
    CommandResult,
    StructuredOutput,
    ParsedCommand,
)
from src.neo.shell.shell import Shell
from src.neo.core.constants import (
    COMMAND_START,
    COMMAND_END,
    SUCCESS_PREFIX,
    ERROR_PREFIX,
)
from src.logging.structured_logger import StructuredLogger


# Helper function to create standardized mock completions
def create_mock_completion(
    content: str, id_prefix: str = "mock", model: str = "test-model"
):
    """Create a standardized mock completion with the given content."""
    mock_completion = MagicMock()
    mock_completion.id = f"{id_prefix}-{datetime.now().timestamp()}"
    mock_completion.created = int(datetime.now().timestamp())
    mock_completion.model = model
    mock_completion.usage = MagicMock(
        prompt_tokens=10, completion_tokens=5, total_tokens=15
    )

    mock_choice = MagicMock()
    mock_choice.message.content = content
    mock_choice.finish_reason = "stop"
    mock_completion.choices = [mock_choice]

    return mock_completion


@pytest.fixture
def mock_client_dependencies():
    """Set up all mock dependencies needed for testing the Client."""
    # Mock Shell instance
    mock_shell = MagicMock(spec=Shell)
    mock_shell.describe.return_value = "Mock command description"

    # Create environment variables required for BaseClient
    os.environ["API_KEY"] = "test-api-key"
    os.environ["MODEL_ID"] = "test-model"

    # Patch methods
    with patch.object(
        BaseClient, "_add_openrouter_metadata"
    ) as mock_add_metadata, patch(
        "src.neo.client.base.StructuredLogger"
    ) as mock_logger_class, patch(
        "openai.Client"
    ) as mock_openai_client_class:

        # Configure metadata mock
        mock_add_metadata.return_value = {
            "timestamp": datetime.now().isoformat(),
            "native_tokens_prompt": 10,
            "native_tokens_completion": 5,
            "approx_num_tokens": 15,
            "cache_discount": 0,
            "usage": 0.000123,
        }

        # Configure logger mock
        mock_logger = mock_logger_class.return_value
        mock_logger.record = MagicMock()

        # Configure OpenAI client mock
        mock_openai_client = mock_openai_client_class.return_value
        mock_openai_client.chat.completions.create.return_value = (
            create_mock_completion("Default response")
        )

        # Create the Client instance with the mocked dependencies
        client = Client(mock_shell)

        # Return all the mocks so tests can configure them
        yield {
            "client": client,
            "shell": mock_shell,
            "openai_client": mock_openai_client,
            "logger": mock_logger,
        }

    # Clean up environment variables (fixture teardown)
    if "API_KEY" in os.environ:
        del os.environ["API_KEY"]
    if "MODEL_ID" in os.environ:
        del os.environ["MODEL_ID"]


def configure_completion_factory(mock_openai_client, response_factory: Callable):
    """Configure the mock OpenAI client to use a factory function for responses."""
    mock_openai_client.chat.completions.create.side_effect = response_factory


def test_command_validation(mock_client_dependencies):
    """Test that client.process correctly handles invalid commands with retry logic."""
    # Extract dependencies from fixture
    client = mock_client_dependencies["client"]
    mock_shell = mock_client_dependencies["shell"]
    mock_openai_client = mock_client_dependencies["openai_client"]

    # Setup messages for the test
    system_message = Message(
        role="system", content=[TextBlock("You are an AI assistant.")]
    )
    user_message = Message(role="user", content=[TextBlock("Please help me")])
    messages = [system_message, user_message]

    # Setup our validation for the Shell with a MagicMock
    validate_mock = MagicMock()

    # Define the side effect function for validation
    def validate_side_effect(cmd_calls, output_schema=None):
        # Accept a list of CommandCall objects and return errors for invalid ones
        errors = []
        for cmd in cmd_calls:
            # Check if the command contains "invalid_command"
            cmd_text = cmd.content if hasattr(cmd, "content") else str(cmd)
            if "invalid_command" in cmd_text:
                errors.append(
                    CommandResult(content="Invalid command: not found", success=False)
                )
        return errors

    # Set the side effect on the mock
    validate_mock.side_effect = validate_side_effect

    # Replace mock methods
    mock_shell.validate_command_calls = validate_mock
    mock_shell.parse_command_call = MagicMock(side_effect=lambda cmd, schema=None: cmd)

    # Create responses for first and second API calls
    responses = [
        f"Let me run a command:\n\n{COMMAND_START}invalid_command --param value{COMMAND_END}\n\nDid that work?",
        f"Let me run a valid command instead:\n\n{COMMAND_START}valid_command --param value{COMMAND_END}\n\nThat should work!"
    ]

    # Create a response factory that cycles through responses
    def response_factory(**kwargs):
        nonlocal responses
        content = responses.pop(0)
        return create_mock_completion(content, id_prefix="validation")

    # Configure the OpenAI client to use our response factory
    configure_completion_factory(mock_openai_client, response_factory)

    # Process messages
    result = client.process(messages)

    # Verify that validation was called
    assert validate_mock.called, "Validation should be called"

    # Verify that it retried after validation failure
    assert mock_openai_client.chat.completions.create.call_count == 2, "Should have called the API twice due to retry"

    # Verify the final command call contains the valid command
    command_calls = result.get_command_calls()
    assert len(command_calls) == 1, "Should have one command call"
    assert "valid_command --param value" in command_calls[0].model_text()


def test_content_block_conversion_to_text(mock_client_dependencies):
    """Test that different ContentBlock types are correctly converted to text."""
    # Extract dependencies from fixture
    client = mock_client_dependencies["client"]
    mock_openai_client = mock_client_dependencies["openai_client"]

    # Create a custom content block type for testing
    class CustomBlock(ContentBlock):
        def model_text(self):
            return "custom block text"

    # Create test messages with different ContentBlock types
    system_message = Message(
        role="system", content=[TextBlock("System instruction")]
    )

    user_message = Message(
        role="user",
        content=[
            TextBlock("Text block content"),
            CommandCall(f"{COMMAND_START}command args{COMMAND_END}"),
            CustomBlock(),
        ],
    )

    # Configure a simple response
    mock_response = create_mock_completion("Response with mixed content types", id_prefix="content-blocks")
    mock_openai_client.chat.completions.create.return_value = mock_response

    # Process messages - should handle different content block types without errors
    result = client.process([system_message, user_message])

    # Verify we got a response
    assert result is not None

    # Get the call arguments for the mocked openai.Client.chat.completions.create
    call_args = mock_openai_client.chat.completions.create.call_args
    processed_messages = call_args[1]["messages"]

    # Check system message (first message) content is preserved
    assert (
        processed_messages[0]["content"][0]["text"] == "System instruction"
    )

    # Check that the message content has been converted to text
    assert (
        processed_messages[1]["content"][0]["text"]
        == "Text block content\n"
        + f"{COMMAND_START}command args{COMMAND_END}\n"
        + "custom block text"
    )


def test_parsing_command_calls_from_response(mock_client_dependencies):
    """Test that command calls in responses are correctly parsed."""
    # Extract dependencies from fixture
    client = mock_client_dependencies["client"]
    mock_shell = mock_client_dependencies["shell"]
    mock_openai_client = mock_client_dependencies["openai_client"]

    # Create test messages
    system_message = Message(
        role="system", content=[TextBlock("System instruction")]
    )
    user_message = Message(
        role="user", content=[TextBlock("List my files")]
    )

    # Create a response with both text and command blocks directly
    mock_response_message = Message(
        role="assistant",
        content=[
            TextBlock("Here's the output:"),
            CommandCall(f"{COMMAND_START}list files{COMMAND_END}"),
            TextBlock("And now another command:"),
            CommandCall(f"{COMMAND_START}read file{COMMAND_END}"),
        ]
    )
    
    # Mock the OpenAI client's process method to return our pre-constructed message
    with patch.object(client._client, 'process', return_value=mock_response_message):
        # Configure shell mock for command validation
        mock_shell.parse_command_call.side_effect = lambda cmd, schema=None: cmd
        mock_shell.validate_command_calls.return_value = []
        
        # Process messages
        result = client.process([system_message, user_message])
        
        # Verify the command calls were parsed correctly
        command_calls = result.get_command_calls()
        assert len(command_calls) == 2
        assert "list files" in command_calls[0].model_text() 
        assert "read file" in command_calls[1].model_text()
        
        # Verify that the response contains text blocks
        text_blocks = [
            block for block in result.content if isinstance(block, TextBlock)
        ]
        assert len(text_blocks) > 0, "Response should contain at least one text block"


def test_assistant_prefill_basic(mock_client_dependencies):
    """Test that assistant_prefill in a user message is prepended to the response."""
    # Extract dependencies from fixture
    client = mock_client_dependencies["client"]
    mock_openai_client = mock_client_dependencies["openai_client"]

    # Create messages
    system_message = Message(role="system", content=[TextBlock("System instruction")])

    # User message with assistant_prefill
    user_message = Message(
        role="user", content=[TextBlock("User question")], assistant_prefill="I think "
    )

    # Configure the response
    mock_response = create_mock_completion(
        "the answer is 42.", id_prefix="prefill-basic"
    )
    mock_openai_client.chat.completions.create.return_value = mock_response

    # Process messages
    result = client.process([system_message, user_message])

    # Verify the prefill was prepended
    assert result.text() == "I think the answer is 42."


def test_assistant_prefill_with_command(mock_client_dependencies):
    """Test that assistant_prefill works correctly with command calls in the response."""
    # Extract dependencies from fixture
    client = mock_client_dependencies["client"]
    mock_shell = mock_client_dependencies["shell"]
    mock_openai_client = mock_client_dependencies["openai_client"]

    # Create messages
    system_message = Message(role="system", content=[TextBlock("System instruction")])

    # User message with assistant_prefill
    user_message = Message(
        role="user",
        content=[TextBlock("Run a command")],
        assistant_prefill="Let me run that for you. ",
    )

    # Configure the response with command and text
    content = f"Here's the command: {COMMAND_START}run --param value{COMMAND_END} Done."
    mock_response = create_mock_completion(content, id_prefix="prefill-command")
    mock_openai_client.chat.completions.create.return_value = mock_response

    # Add validation for the command call
    mock_shell.validate_command_calls.return_value = []
    parsed_command = ParsedCommand(name="run", parameters={"param": "value"})
    mock_shell.parse_command_call.return_value = parsed_command

    # Process messages
    result = client.process([system_message, user_message])

    # Verify the response text contains the prefill
    assert "Let me run that for you." in result.text()

    # Verify the command was included
    command_calls = result.get_command_calls()
    assert len(command_calls) == 1
    assert "run --param value" in command_calls[0].model_text()


def test_assistant_prefill_not_used(mock_client_dependencies):
    """Test that messages without assistant_prefill work normally."""
    # Extract dependencies from fixture
    client = mock_client_dependencies["client"]
    mock_openai_client = mock_client_dependencies["openai_client"]

    # Create messages without prefill
    system_message = Message(role="system", content=[TextBlock("System instruction")])

    user_message = Message(
        role="user",
        content=[TextBlock("Regular question")],
        # No assistant_prefill
    )

    # Configure the response
    mock_response = create_mock_completion("Regular response.", id_prefix="no-prefill")
    mock_openai_client.chat.completions.create.return_value = mock_response

    # Process messages
    result = client.process([system_message, user_message])

    # Verify the response is unchanged
    assert result.text() == "Regular response."


def test_assistant_prefill_multi_turn_conversation(mock_client_dependencies):
    """Test that assistant_prefill only applies to the current turn in a multi-turn conversation."""
    # Extract dependencies from fixture
    client = mock_client_dependencies["client"]
    mock_openai_client = mock_client_dependencies["openai_client"]

    # Create a multi-turn conversation
    system_message = Message(role="system", content=[TextBlock("System instruction")])

    # First turn - no prefill
    first_user_message = Message(role="user", content=[TextBlock("First question")])

    # Mock first assistant response
    first_assistant_response = Message(
        role="assistant", content=[TextBlock("First response.")]
    )

    # Second turn - with prefill
    second_user_message = Message(
        role="user",
        content=[TextBlock("Second question")],
        assistant_prefill="Actually, ",
    )

    # Configure the response for the second turn
    mock_response = create_mock_completion(
        "I think you're right.", id_prefix="multi-turn"
    )
    mock_openai_client.chat.completions.create.return_value = mock_response

    # Process the second turn of the conversation
    result = client.process(
        [
            system_message,
            first_user_message,
            first_assistant_response,
            second_user_message,
        ]
    )

    # Verify the prefill was applied only to the current turn
    assert result.text() == "Actually, I think you're right."


if __name__ == "__main__":
    unittest.main()
