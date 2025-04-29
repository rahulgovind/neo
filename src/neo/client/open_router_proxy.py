"""
OpenRouter proxy implementation for LLM client.
Handles communication with OpenRouter's API using the OpenAI API format.
"""

from collections import deque
import os
import logging
import datetime
import requests
import time
from pathlib import Path
from typing import Iterable, List, Dict, Any, Optional, Tuple, Union

import tiktoken

import openai

from src.logging.structured_logger import StructuredLogger
from src.neo.core.constants import COMMAND_START, COMMAND_END
from src.neo.core.messages import TextBlock, Message
from src.neo.client.proxy import Proxy
from openai.types import Completion

# Configure logging
logger = logging.getLogger(__name__)


class OpenRouterProxy(Proxy):
    """
    OpenRouter implementation of the Proxy interface.
    Handles client instantiation, request/response logging, and response parsing.
    """

    def __init__(self):
        """
        Initialize the OpenRouter client using environment variables.

        Raises:
            ValueError: If required API_KEY environment variable is missing
        """
        self.api_url = os.environ.get("API_URL")
        self.api_key = os.environ.get("API_KEY")
        self.default_model = os.environ.get("MODEL_ID", "anthropic/claude-3.7-sonnet:thinking")

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

    def _build_request(
        self,
        messages: List[Message],
        model: str,
        stop: List[str] = None,
    ) -> Dict[str, Any]:
        """
        Build a request for the OpenRouter API.

        Args:
            messages: List of messages representing the conversation history
            model: The model identifier to use for the request
            stop: Optional list of stop sequences

        Returns:
            Dict: The prepared request data for the OpenRouter API
        """
        processed_messages = []

        # Process all messages
        for message in messages:
            additional_params = {}
            if message.metadata.get("cache-control", False):
                additional_params["cache_control"] = {"type": "ephemeral"}
            processed_messages.append(
                {
                    "role": message.role,
                    "content": [
                        {"type": "text", "text": message.model_text(), **additional_params}
                    ],
                }
            )

        # Prepare request data
        request_data = {
            "model": model,
            "messages": processed_messages,
        }

        # Add stop sequences if provided
        if stop:
            request_data["stop"] = stop

        return request_data

    def process(
        self,
        messages: List[Message],
        model: Optional[str] = None,
        stop: List[str] = None,
        session_id: Optional[str] = None,
    ) -> Message:
        """
        Process a conversation with the LLM and return the response.

        Args:
            messages: List of messages representing the conversation history
            model: Optional model identifier to override the default model
            stop: Optional list of stop sequences
            session_id: Optional session identifier for tracking

        Returns:
            Message: LLM's response as a Message object

        Raises:
            Exception: Any error during processing is logged and re-raised
        """
        try:
            # Use the provided model or fall back to default model
            model_id = model if model is not None else self.default_model

            # Build the request data
            request_data = self._build_request(messages, model_id, stop)

            # Add debugging information
            logger.debug(
                f"Sending LLM request with {len(messages)} messages to model: {model_id}"
            )

            # Count tokens before sending
            token_count = self.count_tokens(request_data)
            if token_count:
                logger.info(f"Estimated token count for request: {token_count}")

            # Send the request and get response
            response = self._send_request(request_data, session_id or "default")

            # Parse and return the response
            return self._parse_response(messages, response, request_data)

        except Exception as e:
            logger.exception(f"Error in LLM client: {e}")
            
            # Create error message
            message = Message(role="assistant")
            message.add_content(
                TextBlock(
                    f"I'm sorry, I encountered an error while processing your request: {str(e)}"
                )
            )
            return message

    def count_tokens(self, request_data: Dict[str, Any]) -> Optional[int]:
        """Calculate token count for messages using tiktoken.

        Args:
            request_data: Dict containing the request data with messages

        Returns:
            Optional[int]: Token count or None if there was an error
        """
        try:
            # Use tiktoken to count tokens
            encoding = tiktoken.encoding_for_model("gpt-4")
            
            # Count tokens for each message
            total_tokens = 0
            for message in request_data.get("messages", []):
                role_tokens = len(encoding.encode(message["role"]))
                
                # Count tokens in content which could be string or list of content blocks
                content_tokens = 0
                content = message.get("content", "")
                
                # Handle both string content and structured content
                if isinstance(content, str):
                    content_tokens = len(encoding.encode(content))
                else:
                    for block in content:
                        if isinstance(block, dict) and "text" in block:
                            content_tokens += len(encoding.encode(block["text"]))
                        elif isinstance(block, str):
                            content_tokens += len(encoding.encode(block))
                
                total_tokens += role_tokens + content_tokens + 4  # Add formatting tokens
            
            # Add completion token estimate based on message count and complexity
            total_tokens += 50 + 5 * len(request_data.get("messages", []))
            
            return total_tokens
        except Exception as e:
            logger.warning(f"Error counting tokens: {e}")
            return None

    def _send_request(
        self, request_data: Dict[str, Any], session_id: str
    ) -> Any:
        """
        Send a request to the OpenRouter and return the response.

        Args:
            request_data: Dictionary containing the request data
            session_id: Session identifier for tracking

        Returns:
            The OpenRouter response object
        """
        start_time = time.time()
        try:
            # Log request details
            logger.info(
                f"Sending request to {request_data.get('model', 'unknown')} model with {len(request_data.get('messages', []))} messages"
            )
            
            # Try to extract the first and last few characters of the last message for context
            if request_data.get("messages") and len(request_data["messages"]) > 0:
                last_message = request_data["messages"][-1]
                last_content = ""
                
                # Extract content text based on format
                if isinstance(last_message.get("content"), str):
                    last_content = last_message["content"]
                elif isinstance(last_message.get("content"), list) and len(last_message["content"]) > 0:
                    if isinstance(last_message["content"][0], dict) and "text" in last_message["content"][0]:
                        last_content = last_message["content"][0]["text"]
                    elif isinstance(last_message["content"][0], str):
                        last_content = last_message["content"][0]
                
                # Log a preview of the last message
                if last_content:
                    max_preview_len = 50
                    if len(last_content) > max_preview_len * 2:
                        preview = f"{last_content[:max_preview_len]}...{last_content[-max_preview_len:]}"
                    else:
                        preview = last_content
                    logger.info(f"Last message preview: {preview}")
            
            # Prepare a directory to save debug logs if DEBUG is set
            if os.environ.get("DEBUG", "").lower() == "true":
                debug_dir = Path("./logs/llm_debug")
                debug_dir.mkdir(parents=True, exist_ok=True)
                timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                debug_file = debug_dir / f"request_{timestamp}_{session_id}.json"
                
                with open(debug_file, "w") as f:
                    import json
                    json.dump(request_data, f, indent=2)
                    
                logger.debug(f"Saved debug request to {debug_file}")

            # Create and execute a chat completion with the OpenAI client
            response = self._client.chat.completions.create(**request_data)
            
            # Log response time
            duration = time.time() - start_time
            logger.info(f"Received response in {duration:.2f} seconds")
            
            # Optionally log full response in debug mode
            if os.environ.get("DEBUG", "").lower() == "true":
                debug_file = debug_dir / f"response_{timestamp}_{session_id}.json"
                with open(debug_file, "w") as f:
                    f.write(str(response))
                logger.debug(f"Saved debug response to {debug_file}")
                
            return response

        except Exception as e:
            duration = time.time() - start_time
            logger.error(f"Error sending request after {duration:.2f} seconds: {e}")
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

        retry_delay = 0.1  # seconds
        max_retry_duration = 10  # seconds
        start_time = time.time()

        while True:
            try:
                api_response = requests.get(url, headers=headers, params=params)
                api_response.raise_for_status()
                response_data = api_response.json()
                assert (
                    "data" in response_data
                ), f"OpenRouter API response missing 'data' field"
                logger.info(
                    f"Took {time.time() - start_time} seconds to fetch OpenRouter metadata"
                )
                return response_data["data"]
            except requests.HTTPError as e:
                curr_duration = time.time() - start_time
                # Only retry for 404 or 5xx errors
                if curr_duration > max_retry_duration or not (
                    e.response.status_code == 404 or e.response.status_code >= 500
                ):
                    raise
                time.sleep(retry_delay)

    def _add_openrouter_metadata(
        self, response, metadata: Dict[str, Any]
    ) -> Dict[str, Any]:
        metadata = {
            **metadata,
            **{
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens,
            },
            **self._fetch_openrouter_metadata(response.id),
        }
        return metadata

    def _parse_response(
        self, messages: List[Message], response, request_data: Dict[str, Any]
    ) -> Message:
        """
        Parse OpenRouter response to extract text.

        Args:
            messages: Original messages sent to the model
            response: OpenRouter response object
            request_data: Request data dictionary

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
            logger.exception(f"Invalid response structure: {response}")
            message = Message(role="assistant")
            message.add_content(
                TextBlock("I'm sorry, I encountered an error processing your request.")
            )
            return message

        if content is None:
            logger.exception("Response message content is None")
            message = Message(role="assistant")
            message.add_content(
                TextBlock("I'm sorry, I encountered an error processing your request.")
            )
            return message

        # Basic metadata with usage stats
        metadata = {"approx_num_tokens": self.count_tokens(request_data)}
        # Add additional metadata for OpenRouter completions
        if self.api_url and "openrouter.ai" in self.api_url:
            metadata = self._add_openrouter_metadata(response, metadata)
        
        if isinstance(content, str):
            content = [TextBlock(content)]
        # Add all blocks to the message
        message = Message(role="assistant", metadata=metadata, content=content)

        logger.info(
            f"Received the following response from ({request_data.get('model', 'unknown')}): {message.text()}"
        )
        
        return message
