"""
Agent module for managing conversations and function invocations with LLMs.
With added support for session-based interactions.
"""

import logging
import json
import os
import re
from typing import List, Dict, Any, Optional, Tuple, TYPE_CHECKING

from src.model import Model, Message, TextBlock, FunctionCall, FunctionResult
from collections import deque
from src.function import FunctionRegistry, Example
from src.utils.parse_prompt import load_and_interpolate_prompt

# Note: Import Session class inside the create_session method to avoid circular imports

# Configure logging
logger = logging.getLogger(__name__)


class Agent:
    """
    Agent orchestrates conversations with an LLM and handles function invocations.
    """
    
    def __init__(
        self, 
        model: Model, 
        function_registry: FunctionRegistry, 
        instructions: str,
        max_function_calls: int = 10,
    ):
        """
        Initialize the agent with model, functions, and instructions.
        
        Raises:
            ValueError: If required configuration is missing
        """
        self.model = model
        self.function_registry = function_registry
        self.instructions = instructions
        # Store history as a deque to efficiently manage conversation rounds
        self.message_history = deque(maxlen=10)  # 5 rounds = 10 messages (user + assistant pairs)
        self.state = ""  # Initialize with empty state
        
        # Build function descriptions during initialization
        try:
            # Get function information from the registry
            self.function_info = self.function_registry.get_formatted_info()
            
            function_names = list(self.function_registry.functions.keys()) if hasattr(self.function_registry, 'functions') else []
            logger.info(f"Agent initialized with {len(function_names)} functions: {', '.join(function_names)}")
        except Exception as e:
            logger.exception(f"Failed to prepare function descriptions: {e}")
            # Fail fast on initialization errors
            raise RuntimeError(f"Agent initialization failed: {e}") from e
    
    def create_session(self) -> "Session":
        """
        Starts a new session.
        """
        from src.session import Session
        
        # Create a new session
        session = Session(self)
        
        # Configure the model with the session ID
        self.model.set_session_id(session.get_session_id())
        self.message_history.clear()
        # Reset state for new session
        self.state = ""
        
        logger.info(f"Created new session with ID: {session.get_session_id()}")
        return session
    
    def process(self, user_message: str) -> str:
        """
        Process a user message and generate a response.
        
        Returns:
            Text response from the assistant (excluding function calls)
        """
        logger.info("Processing user message")
        
        try:
            # Construct initial messages with context
            messages = self._build_initial_messages(user_message)
            
            # Process messages, handling any function calls
            response = self._process_internal(messages)
            
            # Extract text response (filtering out function calls)
            text_response = self._extract_text_response(response)
            self._update_history(user_message, text_response)
            # Update conversation state
            self._update_state(user_message, text_response)
            
            logger.info("User message processed successfully")
            return text_response
            
        except Exception as e:
            logger.error(f"Error processing user message: {e}")
            # Provide a user-friendly error message
            return "I encountered an error processing your request. Please try again or rephrase your message."
    
    def _build_initial_messages(self, user_message: str) -> List[Message]:
        """
        Build the initial list of messages with context for the LLM.
        """
        # System message with instructions and function info (if available)
        system_message = Message(role="system")
        system_message.add_content(TextBlock(self.instructions))
        
        # Only add function info if we have functions registered
        if self.function_info:
            system_message.add_content(TextBlock(self.function_info))
        messages = [system_message]
        
        # Add up to 5 previous message pairs (user and assistant) to provide context
        if self.message_history:
            # Convert deque to list for easier slicing from the end
            history_list = list(self.message_history)
            
            # Add up to the last 5 user/assistant message pairs (10 messages total)
            for msg in history_list:
                user_msg = Message(role=msg["role"])
                user_msg.add_content(TextBlock(msg["content"]))
                messages.append(user_msg)
                
            logger.debug(f"Added {len(history_list)} messages from history")
        
        # Add user message
        user_msg = Message(role="user")
        user_msg.add_content(TextBlock(user_message))
        messages.append(user_msg)
        
        logger.debug(f"Built initial messages: {len(messages)} messages")
        return messages
    
    def _process_internal(self, messages: List[Message]) -> Message:
        """
        Process messages and recursively handle function calls.
        
        Raises:
            RuntimeError: If maximum function call iterations are exceeded
        """
        iterations = 0
        
        while iterations < self.max_function_calls:
            iterations += 1
            logger.debug(f"Process iteration {iterations}/{self.max_function_calls}")
            
            # Get response from model
            response = self.model.process(messages)
            
            # Check if response has function calls
            if not response.has_function_calls():
                logger.debug("No function calls in response, returning")
                return response
            
            # Process function calls
            function_calls = response.get_function_calls()
            logger.info(f"Processing {len(function_calls)} function calls")
            
            # Add the assistant's response to messages
            messages.append(response)
            
            # Create a message for function results
            function_results_msg = Message(role="user")
            
            # Process each function call
            for func_call in function_calls:
                result = self._process_function(func_call)
                function_results_msg.add_content(FunctionResult(result))
            
            # Add function results to messages
            messages.append(function_results_msg)
        
        # If we reach here, we've hit the maximum iterations
        logger.warning(f"Reached maximum function call iterations ({self.max_function_calls})")
        # Return the last response we got
        return response
    
    def _process_function(self, function_call: FunctionCall) -> str:
        """
        Process a single function call from the LLM.
        
        Returns the function result as a string, or an error message if execution fails.
        """
        function_name = function_call.name
        args = function_call.args
        
        logger.info(f"Processing function call: {function_name} with args: {args}")
        
        try:
            # Attempt to invoke the function
            result = self.function_registry.invoke(function_name, args)
            
            # Convert result to string if it's not already
            if not isinstance(result, str):
                result = str(result)
                
            logger.debug(f"Function {function_name} returned: {result[:100]}..." if len(result) > 100 else result)
            return result
            
        except ValueError as e:
            # Handle case where function doesn't exist or required args are missing
            error_msg = f"Error: {str(e)}"
            logger.error(f"Value error in function {function_name}: {e}")
            return error_msg
            
        except Exception as e:
            # Handle any other errors during function execution
            error_msg = f"Error executing function {function_name}: {str(e)}"
            logger.error(error_msg)
            return error_msg
    
    def _extract_text_response(self, response: Message) -> str:
        """
        Extract only the text content from a response, filtering out function calls.
        """
        text_parts = []
    def _update_history(self, user_message: str, assistant_response: str) -> None:
        for block in response.content:
        Update the conversation history with the latest exchange.
        Maintains up to 5 rounds (user + assistant pairs) of conversation.
    
        # Skip history update if either message is empty
        """
            logger.debug("Skipping history update due to empty message")
        
        The state maintenance is delegated to the LLM itself, allowing for
        # Add user message and assistant response to history
        self.message_history.append({"role": "user", "content": user_message})
        self.message_history.append({"role": "assistant", "content": assistant_response})
        
        logger.debug(f"Updated conversation history, now contains {len(self.message_history)} messages")
            else:
                logger.warning("State update did not contain properly formatted state, keeping current state")
                
        except Exception as e:
            # Don't update state if there was an error
            # This preserves the previous valid state
            logger.error(f"Error updating state: {e}")