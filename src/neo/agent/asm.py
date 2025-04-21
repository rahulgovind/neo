"""Agent State Machine module for managing conversation flows.

Provides a stateless interface for processing agent interactions.
"""

from abc import ABC, abstractmethod
import logging
import os
from dataclasses import replace
from textwrap import dedent
from typing import List, Tuple, Any, Dict

from src.neo.core.messages import Message
from src.neo.agent.state import AgentState
from src.neo.shell import Shell
from src.neo.client import Client
from src.neo.shell.command import Command
from src.neo.core.constants import COMMAND_START, STDIN_SEPARATOR

# Configure logging
logger = logging.getLogger(__name__)


class AgentOutput(ABC):
    @abstractmethod
    def to_messages(self) -> List[Message]:
        """Convert this output to a list of messages."""
        pass

    @abstractmethod
    def is_terminal(self) -> bool:
        """Return True if this output is terminal."""
        pass

class CommandExecution(AgentOutput):
    def __init__(self, command_call: Message, command_results: Message):
        self.command_call = command_call
        self.command_results = command_results

    def to_messages(self) -> List[Message]:
        return [self.command_call, self.command_results]

    def is_terminal(self) -> bool:
        return self.command_results.structured_output() is not None


class AgentResponse(AgentOutput):
    def __init__(self, message: Message):
        self.message = message

    def to_messages(self) -> List[Message]:
        return [self.message]

    def is_terminal(self) -> bool:
        return True


class AgentStateMachine:
    """Stateless machine for processing agent inputs."""

    def __init__(
        self,
        client: Client,
        shell: Shell,
        session_id: str,
        configuration: Dict[str, str],
    ):
        self.client = client
        self.shell = shell
        self.session_id = session_id

        # Interval between checkpoints in number of messages.
        self.checkpoint_interval = int(configuration.get("checkpoint_interval", "40"))

        # Number of messages at which the head of the conversation is truncated.
        self.head_truncation_trigger_threshold = int(
            configuration.get("head_truncation.trigger_threshold", "100")
        )

        # Number of messages to keep after truncation.
        self.head_truncation_retention = int(
            configuration.get("head_truncation.retention", "70")
        )

    def step(
        self, state: AgentState, commands: List[str]
    ) -> Tuple[AgentState, AgentOutput]:

        # Add a "continue" message if the last message is not from the user
        # if not state.messages or state.messages[-1].role not in ["user", "developer"]:
        #     state = state.add_messages(Message("developer", "continue"))

        # Call the client to get a response
        assistant_response = self.client.process(
            messages=state.to_messages(), commands=commands, session_id=self.session_id
        )

        if assistant_response.has_command_executions():

            # Extract and process command calls
            command_calls = assistant_response.get_command_calls()

            # Create a message with the command results
            command_results = self.shell.process_commands(command_calls)
            output = CommandExecution(
                assistant_response, Message(role="developer", content=command_results)
            )
        else:
            # Return the state and the assistant response
            output = AgentResponse(assistant_response)

        return state.add_messages(*output.to_messages()), output

    def checkpoint_state(self, state: AgentState) -> AgentState:
        """
        Returns a new AgentState with the checkpoint added.
        """
        # Check number of messages since the last checkpoint
        last_checkpoint_index = -1
        for i, msg in enumerate(state.messages):
            if msg.metadata.get("is_checkpoint") == "true":
                last_checkpoint_index = i

        num_messages_since_checkpoint = len(state.messages) - last_checkpoint_index + 1
        if num_messages_since_checkpoint < self.checkpoint_interval:
            return state

        logger.info(f"Checkpointing after {num_messages_since_checkpoint} messages")

        # Read checkpoint instructions from file
        checkpoint_file = os.path.join(
            os.path.dirname(__file__), "prompts/checkpoint.md"
        )
        with open(checkpoint_file, "r") as f:
            checkpoint_instructions = f.read()

        num_attempts = 0

        while True:

            num_attempts += 1

            # Add a user message requesting the checkpoint
            logger.info(f"Checkpointing attempt {num_attempts}")
            checkpoint_request_state = state.add_messages(
                Message("developer", checkpoint_instructions),
                Message("assistant", f"Generating the latest checkpoint - {COMMAND_START}output -d checkpoint{STDIN_SEPARATOR}")
            )
            # checkpoint_request_state = state.clear_messages().add_messages(
            #     Message(
            #         "developer",
            #         checkpoint_instructions
            #         + "\nHere is a history of the conversation so far: ```\n"
            #         + "\n".join(
            #             ("system" if message.role == "developer" else message.role) + 
            #             ": " + message.model_text()
            #             for message in state.messages
            #         )
            #         + "```\n\n" 
            #         + "Follow the initial instructions to generate a checkpoint and send it over by running output -d checkpoint`"
            #     )
            # )
            _, checkpoint_response = self.step(checkpoint_request_state, [])
            if (
                isinstance(checkpoint_response, CommandExecution)
                and checkpoint_response.command_results.structured_output() is not None
                and checkpoint_response.command_results.structured_output().destination
                == "checkpoint"
            ):
                break

        # Return the original state with the checkpoint added.
        return state.add_messages(
            Message(
                "developer",
                "Here is a checkpoint of this conversation so far.",
                metadata={"is_checkpoint": "true"},
            ),
            Message(
                role="assistant",
                content=str(checkpoint_response.command_results.structured_output().value),
            ),
            Message(
                role="developer",
                content="continue",
            ),
        )

    def prune_state(self, state: AgentState) -> AgentState:
        """
        Returns a new AgentState with the state pruned if necessary.

        This method checks if the conversation has grown too large and,
        if it has, truncates older messages while keeping the most recent ones.
        """
        # Count the number of messages (except system message)
        message_count = len(state.messages)

        # If below threshold, no pruning needed
        if message_count <= self.head_truncation_trigger_threshold:
            return state

        # Find the latest checkpoint that has at least head_truncation_retention messages after it
        checkpoint_index = -1
        for i, msg in enumerate(reversed(state.messages)):
            num_messages_after = i
            if msg.metadata.get("is_checkpoint") != "true":
                continue

            # One message after this will contain actual checkpoint
            num_messages_after_checkpoint = num_messages_after - 2
            if num_messages_after_checkpoint < self.head_truncation_retention:
                continue
            checkpoint_index = len(state.messages) - i - 1
            break

        # If no valid checkpoint found, return original state
        if checkpoint_index == -1:
            return state

        # Drop messages before the checkpoint
        logger.info(
            f"Pruning state with the following checkpoint: "
            + f"{state.messages[checkpoint_index].model_text()}"
            + f"{state.messages[checkpoint_index + 1].model_text()}"
        )
        return state.drop(checkpoint_index)
