"""
Client module provides abstraction over LLM clients using the OpenAI API format.
Handles client instantiation and request/response logging.
"""

import os
import logging
import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple

import openai

from src.logging.structured_logger import StructuredLogger
from src.core import context, env
from src.core.constants import COMMAND_START, COMMAND_END
from src.core.messages import TextBlock, CommandCall, Message

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
    
    - The command starts with "▶"
    - "▶" is followed by the command name
    - The command name is followed by a space
    - The command name is followed by the parameters
    - The command data is separated by a pipe (|) from the command name and parameters. The command data is optional.
    
    Examples:
    ```
    ▶command_name v1 -f v2 --foo v3｜Do something■
    ✅File updated successfully■
    
    ▶command_name v1 -f v2 --foo v3｜Erroneous data■
    ❌Error■
    ```
    
    Note that command results start with "✅" if executed successfully or "❌" if executed with an error.
    """
    
    def __init__(self):
        """
        Initialize the LLM client using environment variables.
        
        Raises:
            ValueError: If required API_KEY environment variable is missing
        """
        api_url = os.environ.get("API_URL")
        api_key = os.environ.get("API_KEY")

        if not api_key:
            logger.error("API_KEY environment variable is not set")
            raise ValueError("API_KEY environment variable is required")
        
        # Initialize client with optional custom base URL
        client_kwargs = {"api_key": api_key}
        if api_url:
            client_kwargs["base_url"] = api_url
            
        try:
            self.client = openai.Client(**client_kwargs)
            logger.info("LLM client initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize LLM client: {e}")
            raise
        
        # Initialize structured logger as None - will be set up when needed
        self.structured_logger = None
    
    def _setup_logging(self):
        """
        Set up structured logger.
        Only called when needed.
        """
        # Initialize the structured logger with the logger name only
        # The session_id will be fetched when record() is called
        self.structured_logger = StructuredLogger("requests")
        
    def process(self, messages: List[Message], model: str = "anthropic/claude-3.7-sonnet", 
               stop: List[str] = None, include_command_instructions: bool = True) -> Message:
        """
        Process a conversation with the LLM and return the response.
        
        Args:
            messages: List of messages representing the conversation history
            model: The model identifier to use for the request
            stop: Optional list of stop sequences
            
        Returns:
            Message: LLM's response as a Message object
            
        Raises:
            Exception: Any error during processing is logged and re-raised
        """
        try:
            # Prepare messages list
            processed_messages = []
            
            # If this is a system message and we should include command instructions,
            # append the command instructions to the system message
            if include_command_instructions and messages and messages[0].role == "system":
                system_message = messages[0]
                original_content = system_message.text()
                
                # Add command instructions to the system message
                if self.COMMAND_INSTRUCTIONS not in original_content:
                    system_content = original_content + "\n\n" + self.COMMAND_INSTRUCTIONS
                    processed_messages.append({
                        "role": "system",
                        "content": system_content
                    })
                    # Skip the system message in the loop below
                    messages_to_process = messages[1:]
                else:
                    # If instructions are already included, process normally
                    messages_to_process = messages
            else:
                messages_to_process = messages
            
            # Process all remaining messages
            for message in messages_to_process:
                processed_messages.append({
                    "role": message.role,
                    "content": message.text()
                })
            
            # Prepare request data
            request_data = {
                "model": model,
                "messages": processed_messages,
            }
            
            # Add stop sequences if provided
            if stop:
                request_data["stop"] = stop
            
            # Send the request to the LLM
            response = self._send_request(request_data)
            
            # Process and return the response
            return self._parse_response(response)
            
        except Exception as e:
            logger.error(f"Error processing messages: {e}", exc_info=True)
            raise
    
    def _send_request(self, request_data: Dict[str, Any]) -> Any:
        """
        Send a request to the LLM and return the response.
        
        Args:
            request_data: Dictionary containing the request data
            
        Returns:
            The LLM response object
        """
        # Generate a unique ID for this request-response pair
        request_id = datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        
        # Get model name for logging
        model_name = request_data.get('model', 'unknown')
        
        # Get current context for session_id
        try:
            ctx = context.get()
            session_id = ctx.session_id
        except context.ContextNotSetError:
            # If context is not set, use None for session_id
            session_id = None
        
        # Log request start
        request_log_data = {
            "message": f"Sending request to model {model_name}",
            "operation_type": "request_start",
            "request_id": request_id,
            "session_id": session_id,
            "model": model_name,
            "request": request_data,
            "meta": {
                "message_count": len(request_data.get('messages', []))
            }
        }
        
        # Ensure structured logger is initialized
        if self.structured_logger is None:
            self._setup_logging()
        
        # Log the request using the structured logger
        self.structured_logger.record(request_log_data)
        
        logger.debug(f"Sending request to LLM with {len(request_data.get('messages', []))} messages")
        logger.info(f"Sending request {request_id} with {len(request_data.get('messages', []))} messages to {model_name}")
        
        try:
            # Send the request to the LLM
            response = self.client.chat.completions.create(**request_data)
            
            # Convert the response to a dictionary for logging
            response_dict = self._response_to_dict(response)
            
            # Log successful response
            response_log_data = {
                "message": f"Received response from model {model_name}",
                "operation_type": "response",
                "status": "success",
                "request_id": request_id,
                "session_id": session_id,
                "model": model_name,
                "response": response_dict,
                "meta": {
                    "message_count": len(request_data.get('messages', []))
                }
            }
            
            # Ensure structured logger is initialized
            if self.structured_logger is None:
                self._setup_logging()
                
            # Log the response using the structured logger
            self.structured_logger.record(response_log_data)
            
            return response
            
        except Exception as e:
            # Log failed response
            error_log_data = {
                "message": f"Error response from model {model_name}: {str(e)}",
                "operation_type": "response",
                "status": "failure",
                "request_id": request_id,
                "session_id": session_id,
                "model": model_name,
                "error": str(e),
                "meta": {
                    "message_count": len(request_data.get('messages', []))
                }
            }
            
            # Ensure structured logger is initialized
            if self.structured_logger is None:
                self._setup_logging()
                
            # Log the error using the structured logger
            self.structured_logger.record(error_log_data)
            
            # Re-raise the exception
            raise
    
    def _response_to_dict(self, response) -> Dict[str, Any]:
        """
        Convert an OpenAI response object to a dictionary for serialization.
        """
        return response.to_dict()
    
    def _parse_response(self, response) -> Message:
        """
        Parse LLM response to extract text and command calls.
        
        Args:
            response: LLM response object
            
        Returns:
            Message: Processed response as a Message object
        """
        # Verify command markers are single characters for optimization
        assert len(COMMAND_START) == 1, "COMMAND_START must be a single character"
        assert len(COMMAND_END) == 1, "COMMAND_END must be a single character"
        
        # Validate response and extract content
        try:
            content = response.choices[0].message.content
        except (AttributeError, IndexError, TypeError) as e:
            logger.error(f"Invalid response structure: {e}")
            message = Message(role="assistant")
            message.add_content(TextBlock("I'm sorry, I encountered an error processing your request."))
            return message
            
        if content is None:
            logger.error("Response message content is None")
            message = Message(role="assistant")
            message.add_content(TextBlock("I'm sorry, I encountered an error processing your request."))
            return message
        
        from collections import deque
        
        message = Message(role="assistant")
        blocks = []
        
        # Initialize variables for tracking the current block
        current_block_type = None  # None, "text", or "command"
        current_block_buffer = deque()  # Buffer for characters
        current_block_end_marker = False  # Whether the end marker is set for command calls
        
        # Helper function to flush the current block to blocks list
        def flush_current_block():
            nonlocal current_block_type, current_block_buffer, current_block_end_marker
            
            if current_block_type is None or not current_block_buffer:
                return
                
            # Convert buffer to string
            buffer_content = "".join(current_block_buffer)
            
            # Create appropriate block based on type
            if current_block_type == "command":
                block = CommandCall(content=buffer_content, end_marker_set=current_block_end_marker)
            else:  # text
                block = TextBlock(buffer_content)
                
            blocks.append(block)
                
            # Reset tracking variables
            current_block_type = None
            current_block_buffer.clear()
            current_block_end_marker = False
        
        for char in content:
            # Direct character comparison is much faster than string slicing
            if char == COMMAND_START:
                # Flush any existing block
                flush_current_block()
                # Start a new command block
                current_block_type = "command"
                
            elif char == COMMAND_END:
                if current_block_type == "command":
                    # Mark command as having end marker and flush it
                    current_block_end_marker = True
                    flush_current_block()
                elif current_block_type == "text":
                    # Add COMMAND_END as text
                    current_block_buffer.append(char)
                else:  # No current block
                    # Create a TextBlock with just COMMAND_END
                    blocks.append(TextBlock(char))
                    
            else:  # Regular character
                if current_block_type is None:
                    # Start a new text block
                    current_block_type = "text"
                # Add character to buffer
                current_block_buffer.append(char)
        
        # Flush any remaining block
        flush_current_block()
        
        # Add all blocks to the message
        for block in blocks:
            message.add_content(block)
        
        return message
