"""
Client module provides abstraction over LLM clients using the OpenAI API format.
Handles client instantiation and request/response logging.
"""

import logging
from typing import List, Optional, Dict, Any, Union

from openai._utils import transform
from openai.types import Completion

from src.neo.client.proxy import Proxy
from src.neo.core.constants import (
    COMMAND_END,
    COMMAND_START,
    SUCCESS_PREFIX,
    ERROR_PREFIX,
)
from src.neo.core.messages import CommandCall, Message, TextBlock
from src.neo.shell import Shell

# Configure logging
logger = logging.getLogger(__name__)


class Client:
    """
    Abstraction layer over LLM clients using the OpenAI API format.
    Handles client instantiation, request/response logging, and command parsing.
    """

    # Instructions for command execution format

    def __init__(self, shell: Shell):
        self._client = Proxy.get_proxy()
        self._shell = shell

    def process(
        self,
        messages: List[Message],
        commands: List[str] = None,
        model: Optional[str] = None,
        output_schema: Union[str, Dict[str, Any]] = None,
        session_id: Optional[str] = None,
    ) -> Message:
        messages_to_send = messages.copy()

        for message in messages_to_send:
            message.metadata["cache-control"] = False

        messages_to_send[-1].metadata["cache-control"] = True
        if len(messages_to_send) >= 3:
            messages_to_send[-3].metadata["cache-control"] = True

        num_requests = 0

        while True:
            response = self._process(
                messages=messages_to_send,
                commands=commands,
                model=model,
                session_id=session_id,
            )
            num_requests += 1

            if not response.has_command_executions():
                return response

            if num_requests > 3:
                return response

            command_calls = response.get_command_calls()
            validation_results = self._shell.validate_command_calls(
                command_calls, output_schema
            )
            validation_failures = [
                result for result in validation_results if not result.success
            ]

            if len(validation_failures) == 0:
                transformed_blocks = []
                for block in response.content:
                    if isinstance(block, CommandCall):
                        block.parsed_cmd = self._shell.parse_command_call(
                            block, output_schema
                        )
                        transformed_blocks.append(block)
                    else:
                        transformed_blocks.append(block)
                return Message(
                    role="assistant",
                    content=transformed_blocks,
                    metadata=response.metadata,
                )

            num_valid_commands = len(command_calls) - len(validation_failures)
            correction_message = "Commands are not valid. Correct them."
            if num_valid_commands > 0:
                correction_message += f"\n{num_valid_commands} were valid but have not been executed. Send them again too."

            messages_to_send = messages.copy() + [
                response,
                Message(
                    role="user",
                    content=[*validation_failures, TextBlock(correction_message)],
                ),
            ]

    def _get_assistant_prefill(self, messages: List[Message]) -> Optional[str]:
        """Extract assistant_prefill from the last user message if present."""
        if (
            len(messages) > 1
            and messages[-1].role != "assistant"
            and hasattr(messages[-1], "assistant_prefill")
        ):
            return messages[-1].assistant_prefill
        return None

    def _process(
        self,
        messages: List[Message],
        commands: List[str] = None,
        model: Optional[str] = None,
        session_id: Optional[str] = None,
    ) -> Message:
        processed_messages = self._preprocess_messages(messages, commands)
        response = self._client.process(
            messages=processed_messages,
            model=model,
            stop=[SUCCESS_PREFIX, ERROR_PREFIX],
            session_id=session_id,
        )
        return self._postprocess_response(response, messages)

    def _preprocess_messages(
        self, messages: List[Message], commands: List[str]
    ) -> List[Message]:
        processed_messages = []

        assert messages[0].role == "system", "System message must be first"
        processed_messages.append(
            Message(
                role="system",
                content=[
                    *messages[0].content,
                ],
                metadata=messages[0].metadata,
            )
        )

        # Convert all message blocks to TextBlock
        for message in messages[1:]:
            if message.role == "developer":
                prefix = "<SYSTEM>"
                suffix = "</SYSTEM>"
                role = "user"
            else:
                prefix = ""
                suffix = ""
                role = message.role

            processed_messages.append(
                Message(
                    role=role,
                    content=[
                        TextBlock(text=prefix + block.model_text() + suffix)
                        for block in message.content
                    ],
                    metadata=message.metadata,
                    assistant_prefill=message.assistant_prefill,
                )
            )

        assistant_prefill = self._get_assistant_prefill(processed_messages)
        if assistant_prefill:
            processed_messages.append(
                Message(
                    role="assistant",
                    content=assistant_prefill,
                )
            )

        return processed_messages

    def _postprocess_response(
        self, response: Message, messages: List[Message]
    ) -> Message:
        # Verify command markers are single characters for optimization
        assert len(COMMAND_START) == 1, "COMMAND_START must be a single character"
        assert len(COMMAND_END) == 1, "COMMAND_END must be a single character"

        # Get assistant_prefill from the last user message if present
        assistant_prefill = self._get_assistant_prefill(messages)

        # If we have assistant_prefill, prepend it to the content
        if assistant_prefill and response.content:
            # Prepend to the first content block
            response.content[0] = TextBlock(
                text=assistant_prefill + response.content[0].model_text()
            )
            
        # Process each content block to check for COMMAND_END truncation
        processed_content = []
        for block in response.content:
            content_text = block.model_text()
            # If COMMAND_END is found, truncate the content
            if COMMAND_END in content_text:
                content_text = content_text[:content_text.find(COMMAND_END) + 1]
                processed_content.append(TextBlock(text=content_text))
                # Stop processing after COMMAND_END is found
                break
            else:
                processed_content.append(block)
                
        # Update response with processed content
        response.content = processed_content

        blocks = []
        for block in response.content:
            curr_block_buffer = []
            prev_char = None
            for char in block.model_text():
                if char == COMMAND_START or prev_char == COMMAND_END:
                    blocks.append("".join(curr_block_buffer))
                    curr_block_buffer = []

                curr_block_buffer.append(char)
                prev_char = char

            blocks.append("".join(curr_block_buffer))

        parsed_blocks = []
        for block in blocks:
            # Skip empty blocks
            if not block.strip():
                continue
            if block.startswith(COMMAND_START):
                parsed_blocks.append(CommandCall(block))
            else:
                parsed_blocks.append(TextBlock(block))

        return Message(
            role="assistant", metadata=response.metadata, content=parsed_blocks
        )
