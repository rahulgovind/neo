"""
Client module provides abstraction over LLM clients using the OpenAI API format.
Handles client instantiation and request/response logging.
"""

import os
import logging
import datetime
import requests
import time
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple, Union

import tiktoken

import openai

from src.logging.structured_logger import StructuredLogger
from src.core.constants import COMMAND_START, COMMAND_END
from src.core.messages import TextBlock, CommandCall, Message
from openai.types import Completion

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
    - "▶" is followed by the command name and then a space.
    - Named arguments (-f, --foo) should come before positional arguments
    - If STDIN is required it can be specified with a pipe (｜) after the parameters. STDIN is optional.
    
    Examples:
    ```
    ▶command_name -f v2 --foo v3 v1｜Do something■
    ✅File updated successfully■
    
    ▶command_name -f v2 --foo v3 v1｜Erroneous data■
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
        self.api_url = os.environ.get("API_URL")
        self.api_key = os.environ.get("API_KEY")

        if not self.api_key:
            logger.error("API_KEY environment variable is not set")
            raise ValueError("API_KEY environment variable is required")
        
        # Initialize client with optional custom base URL
        client_kwargs = {"api_key": self.api_key}
        if self.api_url:
            client_kwargs["base_url"] = self.api_url
            
        self._client = openai.Client(**client_kwargs)
        
        # Initialize structured logger
        self._logger = StructuredLogger()
    

        
    def _build_request(self, messages: List[Message], model: str, stop: List[str] = None, 
                     include_command_instructions: bool = True) -> Dict[str, Any]:
        """
        Build a request for the LLM API.
        
        Args:
            messages: List of messages representing the conversation history
            model: The model identifier to use for the request
            stop: Optional list of stop sequences
            include_command_instructions: Whether to include command instructions in system message
            
        Returns:
            Dict: The prepared request data for the LLM API
        """
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
            additional_params = {}
            if message.metadata.get("cache-control", False):
                additional_params["cache_control"] = {
                    "type": "ephemeral"
                }
            processed_messages.append({
                "role": message.role,
                "content": [{
                    "type": "text", 
                    "text": message.text(),
                    **additional_params
                }]
            })
        
        # Prepare request data
        request_data = {
            "model": model,
            "messages": processed_messages,
        }
        
        # Add stop sequences if provided
        if stop:
            request_data["stop"] = stop
            
        return request_data
    
    def process(self, messages: List[Message], model: str = "anthropic/claude-3.7-sonnet", 
           stop: List[str] = None, include_command_instructions: bool = True,
           session_id: Optional[str] = None) -> Message:
        """
        Process a conversation with the LLM and return the response.
        
        Args:
            messages: List of messages representing the conversation history
            model: The model identifier to use for the request
            stop: Optional list of stop sequences
            include_command_instructions: Whether to include command instructions
            session_id: Optional session identifier for tracking
            
        Returns:
            Message: LLM's response as a Message object
            
        Raises:
            Exception: Any error during processing is logged and re-raised
        """
        try:
            # Build the request data
            request_data = self._build_request(
                messages=messages,
                model=model,
                stop=stop,
                include_command_instructions=include_command_instructions
            )
            
            # Send the request to the LLM
            # Default session_id to "unknown" if not provided
            current_session_id = session_id if session_id is not None else "unknown"
            response = self._send_request(request_data, session_id=current_session_id)
            
            # Process and return the response
            logger.debug(f"Received response: {response}")
            return self._parse_response(response, session_id, request_data)
            
        except Exception as e:
            logger.error(f"Error processing messages: {e}", exc_info=True)
            raise
    
    def count_tokens(self, request_data: Dict[str, Any]) -> Optional[int]:
        """Calculate token count for messages using tiktoken.
        
        Args:
            request_data: Dict containing the request data with messages
            
        Returns:
            Optional[int]: Token count or None if there was an error
        """
        try:
            # Use gpt-4o encoding by default
            encoding = tiktoken.encoding_for_model("gpt-4o")
            
            # Concatenate all messages into a single string for token counting
            all_text = ""
            
            # Process the messages array from the request data
            for msg in request_data.get("messages", []):
                role = msg.get("role", "")
                content = msg.get("content", "")
                
                # Add role and content to the text
                all_text += f"{role}: {content}\n\n"
            
            # Count tokens using tiktoken
            num_tokens = len(encoding.encode(all_text))
            
            return num_tokens
        except Exception as e:
            logger.error(f"Error counting tokens: {str(e)}")
            return None
        
    def _send_request(self, request_data: Dict[str, Any], session_id: str) -> Completion:
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
        
        # Log request start
        request_log_data = {
            "message": f"Sending request to model {model_name}",
            "operation_type": "request_start",
            "request_id": request_id,
            "session_id": session_id,
            "model": model_name,
            "request": request_data,
            "meta": {
                "timestamp": datetime.datetime.now().isoformat(),
                "session_id": session_id,
                "message_count": len(request_data.get('messages', [])),
                "approx_num_tokens": self.count_tokens(request_data)
            }
        }
        
        # Log the request using the structured logger
        self._logger.record("requests", request_log_data)
        
        logger.debug(f"Sending request to LLM with {len(request_data.get('messages', []))} messages")
        logger.info(f"Sending request {request_id} with {len(request_data.get('messages', []))} messages to {model_name}")
        
        try:
            # Send the request to the LLM
            response = self._client.chat.completions.create(**request_data)
            # Process response with updated _parse_response that takes request_data
            
            # Convert the response to a dictionary for logging
            response_dict = response.to_dict()
            
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
                    "message_count": len(request_data.get('messages', [])),
                    "approx_num_tokens": self.count_tokens(request_data)
                }
            }
            
            # Log the response using the structured logger
            self._logger.record("requests", response_log_data)
            
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
                    "message_count": len(request_data.get('messages', [])),
                    "approx_num_tokens": self.count_tokens(request_data)
                }
            }
            
            # Log the error using the structured logger
            self._logger.record("requests", error_log_data)
            
            # Re-raise the exception
            raise
    
    def _fetch_openrouter_metadata(self, completion_id: str) -> Dict[str, Any]:
        """
        Fetch metadata from OpenRouter API with retry logic.
        
        Args:
            completion_id: The ID of the completion to fetch metadata for
            
        Returns:
            Metadata dictionary
        """
        url = "https://openrouter.ai/api/v1/generation"
        headers = {"Authorization": f"Bearer {self.api_key}"}
        params = {"id": completion_id}
        
        retry_delay = 0.1 # seconds
        max_retry_duration = 10  # seconds
        start_time = time.time()

        while True:
            try:
                api_response = requests.get(url, headers=headers, params=params)
                api_response.raise_for_status()
                response_data = api_response.json()
                assert "data" in response_data, f"OpenRouter API response missing 'data' field"
                logger.info(f"Took {time.time() - start_time} seconds to fetch OpenRouter metadata")
                return response_data["data"]
            except requests.HTTPError as e:
                curr_duration = time.time() - start_time
                # Only retry for 404 or 5xx errors
                if curr_duration > max_retry_duration or not (e.response.status_code == 404 or e.response.status_code >= 500):
                    raise
                time.sleep(retry_delay)

    def _add_openrouter_metadata(self, response, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """
        Add OpenRouter metadata to the existing metadata dictionary.
        
        Args:
            response: LLM response object
            metadata: Existing metadata dictionary to update
            
        Returns:
            Updated metadata dictionary
        """
        metadata = {
            **metadata, 
            **{
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens, 
            },
            **self._fetch_openrouter_metadata(response.id)
        }
        return metadata

    def _parse_response(self, response, session_id: str, request_data: Dict[str, Any]) -> Message:
        """
        Parse LLM response to extract text and command calls.
        
        Args:
            response: LLM response object
            session_id: Session identifier for logging
            
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
        
        # Basic metadata with usage stats
        metadata = {
            "approx_num_tokens": self.count_tokens(request_data)
        }
        
        # Add additional metadata for OpenRouter completions
        if self.api_url and "openrouter.ai" in self.api_url:
            metadata = self._add_openrouter_metadata(response, metadata)
        
        message = Message(
            role="assistant",
            metadata=metadata
        )
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
