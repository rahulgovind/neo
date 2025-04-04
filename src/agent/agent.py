"""Agent module for managing conversations and command invocations with LLMs.
With added support for hierarchical memory management for enhanced context retention.
"""

from dataclasses import dataclass
import json
import os.path
import os
import logging
from typing import List

from src.core.context import Context
from src.core.messages import Message, TextBlock

# Configure logging
logger = logging.getLogger(__name__)

@dataclass
class AgentState:
    messages: List[Message]
    
    def to_dict(self):
        """Convert AgentState to a dictionary for serialization."""
        return {
            "messages": [message.to_dict() for message in self.messages]
        }
    
    @classmethod
    def from_dict(cls, data):
        """Create AgentState from a dictionary."""
        return cls(
            messages=[Message.from_dict(msg) for msg in data["messages"]]
        )

class Agent:
    """
    Agent orchestrates conversations with an LLM and handles command invocations.
    """
    
    # Default system instructions for the agent
    DEFAULT_INSTRUCTIONS_TEMPLATE = """
    You are Neo, an AI assistant that can help with a wide range of tasks.
    
    You can assist users by:
    1. Understanding their requirements and questions
    2. Providing relevant information and explanations
    3. Engaging in thoughtful conversation
    
    Your current working directory is: {workspace}
    
    - You SHOULD explain your reasoning clearly and offer context for your suggestions. Do this prior to making any command calls.
    - You MUST not write anything after a command call.
    - YOU SHOULD make incremental, focused changes when modifying files rather than rewriting everything.
    
    Be helpful, accurate, and respectful in your interactions.
    """
    
    def __init__(self, ctx: Context):
        # Start with the default instructions
        instructions = self.DEFAULT_INSTRUCTIONS_TEMPLATE.format(workspace=ctx.workspace)
        
        # Check if .neorules exists in the workspace directory
        neorules_path = os.path.join(ctx.workspace, '.neorules')
        if os.path.exists(neorules_path) and os.path.isfile(neorules_path):
            try:
                # Read the .neorules file
                with open(neorules_path, 'r') as f:
                    neorules_content = f.read().strip()
                
                # Append the content to the instructions if not empty
                if neorules_content:
                    instructions = f"{instructions}\n\nCustom rules from .neorules:\n{neorules_content}"
                    logger.info(f"Loaded custom rules from {neorules_path}")
            except Exception as e:
                logger.error(f"Error reading .neorules file: {e}")
        
        self._instructions = instructions
        self.ctx = ctx
        
        # Ensure session directory exists
        try:
            session_dir = self.ctx.internal_session_dir
            # Create the ~/.neo directory structure if it doesn't exist
            if not os.path.exists(session_dir):
                os.makedirs(session_dir, exist_ok=True)
                logger.info(f"Created session directory: {session_dir}")
        except Exception as e:
            logger.error(f"Error creating session directory: {e}")
            # If directory creation fails, use a fallback temporary location
            session_dir = os.path.join(os.path.expanduser('~'), '.neo', 'temp')
            if not os.path.exists(session_dir):
                os.makedirs(session_dir, exist_ok=True)
        
        # Path to state file
        self.state_file = os.path.join(session_dir, "agent_state.json")
        
        # Try to load state from file if it exists
        if os.path.exists(self.state_file):
            try:
                with open(self.state_file, 'r') as f:
                    state_data = json.load(f)
                self.state = AgentState.from_dict(state_data)
                logger.info(f"Loaded agent state from {self.state_file}")
            except Exception as e:
                logger.error(f"Error loading agent state: {e}")
                # Initialize with empty state if loading fails
                self.state = AgentState(messages=[])
        else:
            # Initialize with empty state if no state file exists
            self.state = AgentState(messages=[])
        
        # Get available commands
        self._command_names = self.ctx.shell.list_commands()
        logger.info(f"Agent initialized with {len(self._command_names)} available commands: {', '.join(self._command_names)}")
    
    def process(self, user_message: str) -> str:
        """
        Process a user message and generate a response.
        
        Returns:
            Text response from the assistant (excluding command calls)
        """
        logger.info("Processing user message")
        
        try:
            self.state.messages.append(Message(role="user", content=[TextBlock(user_message)]))
            
            # Process messages, handling any command calls
            self._process()
            
            # Save the updated state
            self._save_state()
            
            # Get the final response (should be the last message from the assistant)
            final_response = self.state.messages[-1]
            if final_response.role != "assistant":
                logger.warning("Last message in state is not from assistant")
                return "I had an issue processing your request. Please try again."
                
            logger.info("User message processed successfully")
            return final_response.text()
            
        except Exception as e:
            logger.error(f"Error processing user message: {e}")
            # Provide a user-friendly error message
            return "I encountered an error processing your request. Please try again or rephrase your message."
    
    def _prune_state(self) -> None:
        """
        Prune the state by removing old messages.
        
        This method ensures that the state does not grow indefinitely.
        """
        # Only expected to be called when last message is from assistant
        assert self.state.messages[-1].role == "assistant", f"Expected last message to be from assistant, got {self.state.messages[-1].role}"

        # Only trigger if state has more than 15 messages
        if len(self.state.messages) < 100:
            return

        # Only keep the last 6 messages on pruning
        self.state.messages = self.state.messages[-6:]
        self._save_state()
    
    def _process(self) -> None:
        """
        Process messages and manually handle any command calls.
        
        Executes commands as needed and updates memory after each model processing step.
        """
        # Get the model from the context
        model = self.ctx.model
        
        # Keep processing until last message in state is from assistant and does not have command calls
        while not (self.state.messages[-1].role == "assistant" and not self.state.messages[-1].has_command_executions()):
            # Process the messages with the model (without auto-executing commands)
            messages_to_send = self.state.messages.copy()
            messages_to_send[-1] = messages_to_send[-1].copy(metadata={"cache-control": True})
            if len(messages_to_send) >= 3:
                messages_to_send[-3] = messages_to_send[-3].copy(metadata={"cache-control": True})
            current_response = model.process(
                system=self._instructions,
                messages=messages_to_send,
                commands=self._command_names,
                auto_execute_commands=False
            )
            
            # Add the response to state
            self.state.messages.append(current_response)
            self._prune_state()

            # Extract command calls from the last message
            if not current_response.has_command_executions():
                break

            command_calls = current_response.get_command_calls()
            # Process commands manually using the shell
            command_results = self.ctx.shell.process_commands(command_calls)
            # Create a single user message with all results
            result_message = Message(
                role="user",
                content=command_results
            )
            self.state.messages.append(result_message)

    def _save_state(self):
        """Save the current agent state to a file."""
        try:
            with open(self.state_file, 'w') as f:
                json.dump(self.state.to_dict(), f)
            logger.info(f"Saved agent state to {self.state_file}")
        except Exception as e:
            logger.error(f"Error saving agent state: {e}")
