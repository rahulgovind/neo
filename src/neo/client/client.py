"""
Client module provides abstraction over LLM clients using the OpenAI API format.
Handles client instantiation and request/response logging.
"""

import logging
from typing import List, Optional

from openai.types import Completion

from src.neo.client.base import BaseClient
from src.neo.core.constants import COMMAND_END, COMMAND_START, SUCCESS_PREFIX, ERROR_PREFIX
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
    COMMAND_INSTRUCTIONS = """
    When executing commands, follow this exact format:
    
    - The command starts with "\u25b6"
    - "\u25b6" is followed by the command name and then a space.
    - Named arguments (-f, --foo) should come before positional arguments
    - If STDIN is required it can be specified with a pipe (\uff5c) after the parameters. STDIN is optional.
    
    Examples:
    ```
    \u25b6command_name -f v2 --foo v3 v1\uff5cDo something\u25a0
    \u2705File updated successfully\u25a0
    
    \u25b6command_name -f v2 --foo v3 v1\uff5cErroneous data\u25a0
    \u274cError\u25a0
    ```
    
    VERY VERY IMPORTANT:
    - ALWAYS add the \u25b6 at the start of the command call
    - ALWAYS add the \u25a0 at the end of the command call
    - DO NOT make multiple command calls in parallel. Wait for the results to complete first.
    - Results MUST start with "\u2705" if executed successfully or "\u274c" if executed with an error.
    """

    def __init__(self, shell: Shell):
        self._client = BaseClient()
        self._shell = shell

    def process(
        self,
        messages: List[Message],
        commands: List[str] = None,
        model: Optional[str] = None,
        session_id: Optional[str] = None,
    ) -> Message:
        messages_to_send = messages.copy()
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
            validation_results = [self._shell.validate(command) for command in command_calls]
            validation_failures = [result for result in validation_results if not result.success]
            
            if len(validation_failures) == 0:
                return response

            messages_to_send = messages.copy() + [
                response,
                Message(role="user", content=validation_failures)
            ]

    def _process(
        self,
        messages: List[Message],
        commands: List[str] = None,
        model: Optional[str] = None,
        session_id: Optional[str] = None,
    ) -> Message:
        messages = self._preprocess_messages(messages, commands)
        response = self._client.process(
            messages=messages,
            model=model,
            stop=[SUCCESS_PREFIX, ERROR_PREFIX],
            session_id=session_id,
        )
        return self._postprocess_response(response)

    def _preprocess_messages(
        self, messages: List[Message], commands: List[str]
    ) -> List[Message]:
        processed_messages = []

        assert messages[0].role == "system", "System message must be first"
        processed_messages.append(
            Message(
                role="system",
                content=messages[0].content,
                metadata=messages[0].metadata,
            )
        )

        if commands:
            processed_messages[0].add_content(
                TextBlock(
                    "\n\n".join(
                        [self.COMMAND_INSTRUCTIONS]
                        + [self._shell.describe(cmd_name) for cmd_name in commands]
                    )
                )
            )

        # Convert all message blocks to TextBlock
        for message in messages[1:]:
            processed_messages.append(
                Message(
                    role=message.role,
                    content=[
                        TextBlock(text=block.model_text()) for block in message.content
                    ],
                    metadata=message.metadata,
                )
            )

        return processed_messages

    def _postprocess_response(self, response: Message) -> Message:
        # Verify command markers are single characters for optimization
        assert len(COMMAND_START) == 1, "COMMAND_START must be a single character"
        assert len(COMMAND_END) == 1, "COMMAND_END must be a single character"

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
