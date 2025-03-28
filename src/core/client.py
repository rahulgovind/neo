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
        
        # Initialize the requests directory for storing LLM requests
        self._requests_dir = Path(os.path.expanduser("~")) / ".neo" / "requests"
        self._setup_logging()
    
    def _setup_logging(self):
        """
        Set up logging directories based on current context.
        """
        # Get current context
        ctx = context.get()
        session_id = ctx.session_id
        
        # Create a session-specific directory
        self._requests_dir = self._requests_dir / session_id
        
        self._requests_dir.mkdir(parents=True, exist_ok=True)
        logger.debug(f"Request logs directory initialized at {self._requests_dir}")
        
        # Initialize the structured logger
        self.structured_logger = StructuredLogger(str(self._requests_dir))
        
    def process(self, messages: List[Message], model: str = "anthropic/claude-3.7-sonnet", 
               stop: List[str] = None) -> Message:
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
            
            # Process all messages
            for message in messages:
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
        
        logger.debug(f"Sending request to LLM with {len(request_data.get('messages', []))} messages")
        
        # Log a summary of the conversation
        model_name = request_data.get('model', 'unknown')
        logger.info(f"Sending request {request_id} with {len(request_data.get('messages', []))} messages to {model_name}")
        
        # Send the request to the LLM
        response = self.client.chat.completions.create(**request_data)
        
        # Convert the response to a dictionary for logging
        response_dict = self._response_to_dict(response)
        
        # Get current context for session_id
        try:
            ctx = context.get()
            session_id = ctx.session_id
        except context.ContextNotSetError:
            # If context is not set, use None for session_id
            session_id = None
        
        # Prepare log data
        log_data = {
            "request_id": request_id,
            "session_id": session_id,
            "timestamp": datetime.datetime.now().isoformat(),
            "request": request_data,
            "response": response_dict,
            "meta": {
                "message_count": len(request_data.get('messages', []))
            }
        }
        
        # Log the request and response using the structured logger
        self.structured_logger.record("request", log_data)
        
        return response
    
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
