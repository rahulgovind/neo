"""
Model module provides abstraction for processing messages through an LLM.
Handles command parsing and message processing while delegating client operations.
"""

import logging
import textwrap
from typing import List, Dict, Any, Optional, Tuple

from src.core import env
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
    
    def __init__(self, model: str = "anthropic/claude-3.7-sonnet"):
        """
        Initialize the Model for LLM interactions.
        
        Args:
            model: The model identifier to use for requests
        """
        self._model = model
        
        # Create the client instance
        self._client = Client()
    
    def _process_commands(self, messages: List[Message]) -> List[Message]:
        """
        Process command calls in the last message if it's from the assistant.
        All command results are collected into a single user message.
        
        Args:
            messages: List of messages to process
            
        Returns:
            Updated list of messages with command results
        """
        # Check if the last message is from the assistant and has command calls
        if not messages or messages[-1].role != "assistant" or not messages[-1].has_command_executions():
            return messages
            
        # Get all command calls from the last message
        command_calls = messages[-1].get_command_calls()
        
        # Create a list to collect all command results
        result_blocks = []
        
        # Get the shell instance from env
        shell = env.load_shell()
        
        # Execute each command and collect the results
        for cmd_call in command_calls:
            try:
                # Skip command calls without end markers
                if not cmd_call.end_marker_set:
                    error_result = CommandResult(
                        result=None,
                        success=False,
                        error="Command call missing end marker"
                    )
                    result_blocks.append(error_result)
                    continue
                    
                # Parse the command using the shell
                command_text = cmd_call.content() + COMMAND_END
                parsed_cmd = shell.parse(command_text)
                
                # Execute the command
                result = shell.execute(
                    parsed_cmd.name,
                    parsed_cmd.parameters,
                    parsed_cmd.data
                )
                
                # Add the result to our collection
                result_blocks.append(result)
                
            except Exception as e:
                # Create an error result and add it to our collection
                error_result = CommandResult(
                    result=None,
                    success=False,
                    error=str(e)
                )
                result_blocks.append(error_result)
        
        # If we have results, create a single user message with all results
        if result_blocks:
            result_message = Message(
                role="user",
                content=result_blocks
            )
            messages.append(result_message)
            
        return messages
    
    def _get_command_descriptions(self, commands: Optional[List[str]] = None) -> str:
        """
        Get formatted descriptions of available commands.
        
        Args:
            commands: List of command names to include. If None, all commands are included.
            
        Returns:
            Formatted string with command descriptions
        """
        shell = env.load_shell()
        
        # If no specific commands are provided, use all available commands
        if commands is None:
            commands = shell.list_commands()
            
        command_descriptions = []
        for cmd_name in commands:
            try:
                # Use shell.describe to get command documentation
                description = shell.describe(cmd_name)
                command_descriptions.append(description)
            except ValueError:
                # Command not found in shell
                pass
                
        return "\n\n".join(command_descriptions)
    
    def process(self, system: str, messages: List[Message], commands: List[str], auto_execute_commands: bool = False) -> Message:
        """
        Process a list of messages through the LLM and return the response.
        If the last message is from the assistant and contains command calls,
        execute those commands and add the results to the messages.
        
        Args:
            system: System prompt to provide context and instructions
            messages: List of messages to process
            commands: List of command names to make available
            auto_execute_commands: If True, automatically execute commands and process
                                  until no more commands are found. If False (default),
                                  return immediately after getting the model's response.
            
        Returns:
            Message: LLM's response as a Message object
        """
        # Process any command calls in the messages
        messages = self._process_commands(messages)
        
        # Get command descriptions
        command_descriptions = self._get_command_descriptions(commands)
        
        # Create a complete system message with commands
        complete_system = system
        if command_descriptions:
            complete_system += "\n\n" + "Available commands:\n" + command_descriptions
        
        # Create a system message
        system_message = Message(
            role="system",
            content=[TextBlock(complete_system)]
        )
        
        # Add system message at the beginning of the messages list
        all_messages = [system_message] + messages
        
        # Process the messages with the client
        response = self._client.process(
            messages=all_messages,
            model=self._model,
            stop=[SUCCESS_PREFIX, ERROR_PREFIX]
        )
        
        # If auto_execute_commands is True, continue processing until no more commands
        if auto_execute_commands:
            current_response = response
            current_messages = messages.copy()
            
            # Continue processing as long as there are command executions
            while current_response.has_command_executions():
                # Add the response to messages
                current_messages.append(current_response)
                
                # Process commands in the response
                current_messages = self._process_commands(current_messages)
                
                # If no command results were added, break the loop
                if not current_messages[-1].role == "user":
                    break
                    
                # Prepare messages for next iteration (skip system message)
                all_messages = [system_message] + current_messages
                
                # Get next response
                current_response = self._client.process(
                    messages=all_messages,
                    model=self._model,
                    stop=[SUCCESS_PREFIX, ERROR_PREFIX]
                )
            
            # Return the final response
            return current_response
        
        return response
    

    

    

    

    

    