"""
Model module provides abstraction for processing messages through an LLM.
Handles command parsing and message processing while delegating client operations.
"""

import logging
import textwrap
from typing import List, Dict, Any, Optional, Tuple, TYPE_CHECKING

from src.core.context import Context
from src.core.client import Client
from src.core.constants import (
    COMMAND_START, COMMAND_END, STDIN_SEPARATOR, 
    ERROR_PREFIX, SUCCESS_PREFIX
)
from src.core.messages import (
    TextBlock, CommandCall, CommandResult,
    Message, ParsedCommand
)

# Configure logging
logger = logging.getLogger(__name__)


class Model:
    """
    Abstraction layer for processing messages through an LLM.
    Handles command parsing and message processing.
    """
    
    def __init__(self, ctx: Context, model_id: str = "anthropic/claude-3.5-sonnet"):
        """
        Initialize the Model for LLM interactions.
        
        Args:
            ctx: Context object
            model_id: The model identifier to use for requests
        """
        self.ctx = ctx
        self.model_id = model_id
        
        # Create the client instance
        self._client = Client()
    
    def _get_command_descriptions(self, commands: List[str]) -> str:
        """
        Get formatted descriptions of available commands.
        
        Args:
            commands: List of command names to include. If None, all commands are included.
            
        Returns:
            Formatted string with command descriptions
        """
        assert commands is not None, "commands must be a non-empty list of command names"
            
        # Get the shell instance from context
        shell = self.ctx.shell
        command_descriptions = []
        for cmd_name in commands:
            try:
                # Use shell.describe to get command documentation
                description = shell.describe(cmd_name)
                command_descriptions.append(description)
            except ValueError:
                # Command not found in shell
                pass

        return (
            "Available commands:\n" + 
            "\n\n".join(command_descriptions)
        )
    
    def process(self, system: str, messages: List[Message], commands: List[str], auto_execute_commands: bool = False) -> Message:
        """
        Process a list of messages through the LLM and return the response.
        
        Args:
            system: System prompt to provide context and instructions
            messages: List of message objects to process
            commands: List of command names to make available
            auto_execute_commands: If True, automatically execute commands and process
                                  until no more commands are found. If False (default),
                                  return immediately after getting the model's response.
            
        Returns:
            Message: LLM's response as a Message object
        """
        complete_system = system
        
        if commands:
            # Get command descriptions
            command_descriptions = self._get_command_descriptions(commands)
            
            # Create a complete system message with commands
            complete_system += "\n\n" + "Available commands:\n" + command_descriptions
        
        # Create a system message
        system_message = Message(
            role="system",
            content=[TextBlock(complete_system)]
        )
        
        # Add system message at the beginning of the messages list
        messages_to_send = [system_message] + messages
        
        # Process the messages with the client
        while True:
            response = self._client.process(
                messages=messages_to_send,
                model=self.model_id,
                stop=[SUCCESS_PREFIX, ERROR_PREFIX],
                session_id=self.ctx.session_id
               )
            
            # If auto_execute_commands is True, continue processing until no more commands
            if auto_execute_commands and response.has_command_executions():
                messages_to_send.append(response)
                
                command_calls = response.get_command_calls()
                
                # Process commands in the response if it has them
                shell = self.ctx.shell
                result_blocks = shell.process_commands(command_calls)
                
                # If we have results, create a single user message with all results
                result_message = Message(
                    role="user",
                    content=result_blocks
                )
                messages_to_send.append(result_message)
            else:
                break
        
        # Return the final response
        return response
