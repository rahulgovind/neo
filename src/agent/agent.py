"""Agent module for managing conversations and command invocations with LLMs.
With added support for session-based interactions and context management.
"""

import logging
import json
import os
import re
from typing import List, Dict, Any, Optional, Tuple, TYPE_CHECKING

from src.core import env
from src.core.model import Model
from src.core.messages import Message, TextBlock, CommandCall, CommandResult
from src.core.context import Context
from .memory import AgentMemory

# Configure logging
logger = logging.getLogger(__name__)

class Agent:
    """
    Agent orchestrates conversations with an LLM and handles command invocations.
    """
    
    def __init__(
        self,
        instructions: str,
        max_command_calls: int = 10,
        model_name: str = "anthropic/claude-3.7-sonnet",
        session_id: Optional[str] = None
    ):
        """
        Initialize the agent with instructions, and command settings.
        
        Args:
            instructions: Base instructions for the agent
            max_command_calls: Maximum number of command call iterations
            model_name: The model identifier to use for requests
            session_id: Optional session ID for memory persistence
        """
        self._instructions = instructions
        self._max_command_calls = max_command_calls
        self._model = Model(model=model_name)
        self._session_id = session_id or f"session_{os.urandom(8).hex()}"
        
        # Initialize memory manager
        self._memory = AgentMemory(self._session_id)
        
        # Get available commands from the shell
        shell = env.load_shell()
        self._command_names = shell.list_commands()
        logger.info(f"Agent initialized with {len(self._command_names)} available commands: {', '.join(self._command_names)}")
    
    def process(self, user_message: str) -> str:
        """
        Process a user message and generate a response.
        
        Returns:
            Text response from the assistant (excluding command calls)
        """
        logger.info("Processing user message")
        
        try:
            # Construct initial messages with context
            messages = self._build_initial_messages(user_message)
            
            # Process messages, handling any command calls
            response = self._process_internal(messages)
            
            # Update memory with this exchange
            self._memory.update_memory(user_message, response.text())
            
            logger.info("User message processed successfully")
            return response.text()
            
        except Exception as e:
            logger.error(f"Error processing user message: {e}")
            # Provide a user-friendly error message
            return "I encountered an error processing your request. Please try again or rephrase your message."
    
    def _build_initial_messages(self, user_message: str) -> List[Message]:
        """
        Build the list of messages for the LLM, excluding the system message.
        Includes up to 5 previous message pairs and the current user message.
        """
        # Initialize messages list (without system message)
        messages = []
        
        # Get most recent exchanges from memory
        recent_exchanges = self._memory.get_recent_exchanges(5)
        
        # Add previous message pairs from memory
        for msg_pair in recent_exchanges:
            user_msg = Message(role="user")
            user_msg.add_content(TextBlock(msg_pair["user"]))
            messages.append(user_msg)
            
            assistant_msg = Message(role="assistant")
            assistant_msg.add_content(TextBlock(msg_pair["assistant"]))
            messages.append(assistant_msg)
        
        # Add current user message
        user_msg = Message(role="user")
        user_msg.add_content(TextBlock(user_message))
        messages.append(user_msg)
        
        logger.debug(f"Built initial messages: {len(messages)} messages")
        return messages
    
    def _process_internal(self, messages: List[Message]) -> Message:
        """
        Process messages and handle any command calls.
        
        The Model class will automatically handle command execution through its
        _process_commands method, which uses the Shell to execute commands.
        
        Raises:
            RuntimeError: If maximum command call iterations are exceeded
        """
        iterations = 0
        
        while iterations < self._max_command_calls:
            iterations += 1
            logger.debug(f"Process iteration {iterations}/{self._max_command_calls}")
            
            # Process the messages with the model
            # This will automatically process any command calls in the response
            response = self._model.process(
                system=self._instructions,
                messages=messages,
                commands=self._command_names
            )
            
            # Check if response has command calls
            if not response.has_command_executions():
                logger.debug("No command calls in response, returning")
                return response
            
            # The model automatically executes commands and adds results
            # as a user message. The updated messages are returned from model.process
            # We don't need to do anything else here - just continue the loop
            # to handle any follow-up command calls
            messages.append(response)
        
        # If we reach here, we've hit the maximum iterations
        logger.warning(f"Reached maximum command call iterations ({self._max_command_calls})")
        # Return the last response we got
        return response
    
    def get_session_id(self) -> str:
        """Return the current session ID"""
        return self._session_id
    
    def clear_memory(self) -> None:
        """Clear the agent's memory"""
        self._memory.clear_memory()
        logger.info(f"Memory cleared for session {self._session_id}")
