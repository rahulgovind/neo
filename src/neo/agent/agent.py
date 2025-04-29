"""Agent module for managing conversations and command invocations with LLMs.
With added support for hierarchical memory management for enhanced context retention.
"""

import logging
import os
from textwrap import dedent
from typing import Any, Callable, Dict, Iterator, List, Optional, Tuple, Union

from numpy import isin

from src.neo.agent.asm import AgentStateMachine
from src.neo.agent.state import MAX_TURNS, SUMMARY_RATIO, AgentState
from src.neo.core.messages import ContentBlock, Message, TextBlock
from src.neo.session import Session

# Configure logging
logger = logging.getLogger(__name__)


class Agent:
    """
    Agent orchestrates conversations with an LLM and handles command invocations.
    """

    COMMAND_INSTRUCTIONS = dedent(
        """
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
    )

    def __init__(
        self,
        session: Session,
        ephemeral: bool = True,
        configuration: Dict[str, str] = None,
    ):
        self.configuration = configuration or {}

        # Read the default instructions template from file
        template_file = os.path.join(os.path.dirname(__file__), "prompts/neo.txt")
        with open(template_file, "r") as f:
            template = f.read()

        # Format the template with the workspace path
        instructions = template.format(workspace=session._workspace)

        # Check if .neorules exists in the workspace directory
        neorules_path = os.path.join(session.workspace, ".neorules")
        if os.path.exists(neorules_path) and os.path.isfile(neorules_path):
            try:
                # Read the .neorules file
                with open(neorules_path, "r") as f:
                    neorules_content = f.read().strip()

                # Append the content to the instructions if not empty
                if neorules_content:
                    instructions = f"{instructions}\n\nCustom rules from .neorules:\n{neorules_content}"
                    logger.info(f"Loaded custom rules from {neorules_path}")
            except Exception as e:
                logger.error(f"Error reading .neorules file: {e}")

        self.instructions = instructions
        self.session = session
        self.asm = AgentStateMachine(
            client=session.client,
            session_id=session.session_id,
            shell=session.shell,
            configuration=self.configuration,
        )

        # Ensure session directory exists
        try:
            session_dir = self.session.internal_session_dir
            if not os.path.exists(session_dir):
                os.makedirs(session_dir, exist_ok=True)
                logger.info(f"Created session directory: {session_dir}")
        except Exception as e:
            logger.error(f"Error creating session directory: {e}")
            # If directory creation fails, use a fallback temporary location
            session_dir = os.path.join(os.path.expanduser("~"), ".neo", "temp")
            if not os.path.exists(session_dir):
                os.makedirs(session_dir, exist_ok=True)

        # Path to state file
        self.state_file = os.path.join(session_dir, "agent_state.json")

        self.ephemeral = ephemeral
        # Load state from file or create a fresh state

        # Configure command names
        self._command_names = session.shell.list_commands()

        if self._command_names:
            instructions = instructions + "\n\n".join(
                [
                    self.COMMAND_INSTRUCTIONS,
                    *[
                        self.session.shell.describe(cmd_name)
                        for cmd_name in self._command_names
                    ],
                ]
            )

        if ephemeral:
            self.state = AgentState(system=instructions)
        else:
            self.state = AgentState.load(self.state_file, system=instructions)

        # Log agent initialization
        logger.info(
            f"Agent initialized with {len(self._command_names)} available commands: {', '.join(self._command_names)}"
        )

    def process(self, user_message: str) -> Iterator[Message]:
        """
        Process a user message and update the agent's state.

        Args:
            user_message: The text message from the user

        Returns:
            Iterator of messages from the assistant and command results
        """

        state = self.state
        asm = self.asm
        state = state.add_messages(Message(role="user", content=user_message))

        logger.info("Processing user message")

        while True:
            state, output = asm.step(state, self._command_names)

            logger.info(
                "Agent state:\n\n"
                + "\n\n".join(
                    [f"{msg.role}: {msg.model_text()}" for msg in state.messages]
                )
            )
            state = asm.checkpoint_state(state)
            state = asm.prune_state(state)

            if not self.ephemeral:
                state.dump(self.state_file)

            self.state = state

            for msg in output.to_messages():
                logger.info(f"ASSISTANT: {msg.model_text()}")
                yield msg

            if output.is_terminal():
                break
