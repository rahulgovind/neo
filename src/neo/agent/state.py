"""State management for the agent module.

Handles the conversation state, including message storage, serialization, and checkpoints.
"""

from dataclasses import dataclass, field, replace
import json
import os
from typing import List, Optional

from src.neo.core.messages import Message

# Configuration constants for message summarization
MAX_TURNS = 100           # Number of turns before triggering summarization
SUMMARY_RATIO = 0.2       # Percentage of older turns to summarize


@dataclass
class AgentState:
    system: str
    messages: List[Message] = field(default_factory=list)
    
    def add_messages(self, *messages: Message) -> "AgentState":
        """Add messages to the state and return a new AgentState."""
        new_messages = self.messages.copy()
        new_messages.extend(messages)
        return replace(self, messages=new_messages)
    
    def clear_messages(self) -> "AgentState":
        return replace(self, messages=[])
    
    def drop(self, num_messages: int) -> "AgentState":
        """Drop the specified number of messages from the state and return a new AgentState."""
        if num_messages == 0:
            return self
        
        new_messages = self.messages[num_messages:]
        return replace(self, messages=new_messages)
    
    def to_messages(self) -> List[Message]:
        """Get the full list of messages including system message."""
        return [
            Message("system", self.system)
        ] + self.messages
    
    def slice_turns(self, start: Optional[int], end: Optional[int]) -> "AgentState":
        """Get a copy of the state with message pairs (turns) sliced from start to end.
        
        A turn consists of a user message followed by an assistant message.
        
        Args:
            start: Optional starting turn index (inclusive). None means start from beginning.
            end: Optional ending turn index (exclusive). None means go to the end.
            
        Returns:
            New AgentState object with the specified turn slice
        """
        # Calculate message indices from turn indices
        msg_start = None if start is None else start * 2
        msg_end = None if end is None else end * 2
        
        sliced_messages = self.messages[msg_start:msg_end]
        return replace(self, messages=sliced_messages)

    @classmethod
    def load(cls, filepath: str, system: str) -> "AgentState":
        """Load agent state from a file."""
        print(f"Loading agent state from {filepath}")
        if not os.path.exists(filepath):
            return cls(system=system, messages=[])

        with open(filepath, "r") as f:
            state_data = json.load(f)
            assert "messages" in state_data, "State data must have 'messages' key"
            assert "system" in state_data, "State data must have 'system' key"

            persisted_messages = state_data["messages"]
            persisted_system = state_data["system"]
            persisted_messages = [Message.from_dict(msg) for msg in persisted_messages]

            if system != persisted_system:
                logger.info(f"System message does not match: {system} != {persisted_system}")

            return cls(system=system, messages=persisted_messages)
    
    def dump(self, filepath: str) -> None:
        """Save agent state to a file."""
        # Convert state to dictionary
        state_data = {
            "system": self.system,
            "messages": [msg.to_dict() for msg in self.messages]
        }

        # Ensure directory exists
        os.makedirs(os.path.dirname(filepath), exist_ok=True)

        # Write to file (with pretty printing for readability)
        with open(filepath, "w") as f:
            json.dump(state_data, f, indent=2)

    def is_terminal(self) -> bool:
        if len(self.messages) == 0:
            return True

        last_message = self.messages[-1]

        if last_message.role == "assistant" and last_message.has_command_executions() and last_message.structured_output() is None:
            return False
        
        if last_message.role in ["user", "developer"]:
            return False
        
        return True