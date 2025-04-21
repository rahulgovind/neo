"""
Client module provides abstraction over LLM clients using the OpenAI API format.
Handles client instantiation and request/response logging.
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
from openai.types import Completion

# Configure logging
logger = logging.getLogger(__name__)


class BaseClient:
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
        include_command_instructions: bool = True,
    ) -> Dict[str, Any]:
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
            request_data = self._build_request(
                messages=messages,
                model=model_id,
                stop=stop,
            )

            # Send the request to the LLM
            response = self._send_request(request_data, session_id=session_id or "unknown")

            # Process and return the response
            logger.debug(f"Received response:\n{response}")
            try:
                return self._parse_response(messages, response, request_data)
            except Exception as e:
                logger.exception(f"Failed to parse response {response}")
                raise

        except Exception as e:
            logger.exception(f"Error processing messages: {e}")
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
            logger.exception(f"Error counting tokens: {str(e)}")
            return None

    def _send_request(
        self, request_data: Dict[str, Any], session_id: str
    ) -> Completion:
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
        model_name = request_data.get("model", "unknown")

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
                "message_count": len(request_data.get("messages", [])),
                "approx_num_tokens": self.count_tokens(request_data),
            },
        }

        # Log the request using the structured logger
        self._logger.record("requests", request_log_data)

        logger.debug(
            f"Sending request to LLM with {len(request_data.get('messages', []))} messages"
        )
        logger.info(
            f"Sending request {request_id} with {len(request_data.get('messages', []))} messages to {model_name}"
        )
        
        start_time = time.time()

        try:
            # Send the request to the LLM
            response = self._client.chat.completions.create(**request_data)
            # Process response with updated _parse_response that takes request_data

            # Convert the response to a dictionary for logging
            response_dict = response.to_dict()

            # Calculate elapsed time
            elapsed_time = time.time() - start_time

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
                    "message_count": len(request_data.get("messages", [])),
                    "approx_num_tokens": self.count_tokens(request_data),
                    "elapsed_time": elapsed_time,
                },
            }

            # Log the response using the structured logger
            self._logger.record("requests", response_log_data)

            logger.info(f"Request processed in {elapsed_time:.2f} seconds")

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
                    "message_count": len(request_data.get("messages", [])),
                    "approx_num_tokens": self.count_tokens(request_data),
                },
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
        Parse LLM response to extract text and command calls.

        Args:
            response: LLM response object
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
            if messages[-1].role == "assistant":
                content = messages[-1].model_text() + content
            if COMMAND_END in content:
                content = content[:content.find(COMMAND_END) + 1]
            
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