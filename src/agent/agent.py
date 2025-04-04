"""Agent module for managing conversations and command invocations with LLMs.
With added support for hierarchical memory management for enhanced context retention.
"""

from dataclasses import dataclass
import logging
from typing import List

from src.core.context import Context
from src.core.messages import Message, TextBlock

# Configure logging
logger = logging.getLogger(__name__)

@dataclass
class AgentState:
    messages: List[Message]

class Agent:
    """
    Agent orchestrates conversations with an LLM and handles command invocations.
    """
    
    # Default system instructions for the agent
    DEFAULT_INSTRUCTIONS = """
    You are Neo, an AI assistant that can help with a wide range of tasks.
    
    You can assist users by:
    1. Understanding their requirements and questions
    2. Providing relevant information and explanations
    3. Engaging in thoughtful conversation
    
    - You SHOULD explain your reasoning clearly and offer context for your suggestions. Do this prior to making any command calls.
    - You MUST not write anything after a command call.
    - YOU SHOULD make incremental, focused changes when modifying files rather than rewriting everything.
    
    Be helpful, accurate, and respectful in your interactions.
    """
    
    def __init__(self, ctx: Context):
        self._instructions = self.DEFAULT_INSTRUCTIONS
        self.ctx = ctx
        
        # Initialize state with empty message list
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
        if len(self.state.messages) < 15:
            return

        # Only keep the last 6 messages on pruning
        self.state.messages = self.state.messages[-6:]
    
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
            current_response = model.process(
                system=self._instructions,
                messages=self.state.messages,
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