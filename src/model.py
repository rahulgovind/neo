"""
Model module provides abstraction over LLM clients using the OpenAI API format.
With added support for session-based request tracking and improved function call handling.
"""

import os
import logging
import datetime
import json
import textwrap
import ast
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
import openai

from src.logging import StructuredLogger

# Configure logging
logger = logging.getLogger(__name__)

# Special delimiter constants for function calls and results
FUNCTION_START = "✿FUNCTION✿"
ARGS_START = "✿ARGS✿"
FUNCTION_END = "✿END FUNCTION✿"
RESULT_START = "✿RESULT✿"


class ContentBlock:
    """Base class for different types of content in a message."""
    
    def __str__(self) -> str:
        return ""


class TextBlock(ContentBlock):
    """Represents a text content block in a message."""
    
    def __init__(self, text: str):
        self.text = text
        
    def __str__(self) -> str:
        return self.text


class FunctionCall(ContentBlock):
    """Represents a function call content block in a message."""
    
    def __init__(self, name: str, args: Dict[str, Any]):
        self.name = name
        self.args = args
        
    def __str__(self) -> str:
        args_str = json.dumps(self.args, ensure_ascii=False)
        return f"{FUNCTION_START}: {self.name}\n{ARGS_START}: {args_str}\n{FUNCTION_END}"


class FunctionResult(ContentBlock):
    """Represents a function result content block in a message."""
    
    def __init__(self, result: Any):
        self.result = result
        
    def __str__(self) -> str:
        return f"{RESULT_START}: {self.result}"


class InvalidFunctionArgsError(Exception):
    """Exception raised when function arguments are not a valid Python dictionary."""
    pass


class Message:
    """
    Represents a message in the conversation with role and content blocks.
    """
    
    def __init__(self, role: str, content: List[ContentBlock] = None):
        self.role = role
        self.content = content or []
    
    def add_content(self, content: ContentBlock) -> None:
        self.content.append(content)
    
    def has_function_calls(self) -> bool:
        return any(isinstance(block, FunctionCall) for block in self.content)
    
    def get_function_calls(self) -> List[FunctionCall]:
        return [block for block in self.content if isinstance(block, FunctionCall)]
    
    def __str__(self) -> str:
        """
        Create a properly formatted string representation of the message.
        Handles multi-line content and preserves formatting of each content block.
        """
        parts = []
        for block in self.content:
            block_str = str(block)
            if block_str:
                parts.append(block_str)
        
        content_str = "\n".join(parts)
        return f"[{self.role}] {content_str}"


class Model:
    """
    Abstraction layer over LLM clients using the OpenAI API format.
    """
    
    # The notice to append after function results to clarify the result handling
    RESULT_NOTICE = textwrap.dedent("""
    
    Note: The result above is not directly visible to the user. Process this result 
    based on prior instructions and continue your response accordingly.
    """)
    
    # Maximum number of retries for invalid function arguments
    MAX_RETRIES = 3
    
    def __init__(self, session_id: Optional[str] = None):
        """
        Initialize the LLM client using environment variables.
        
        Args:
            session_id: Optional session ID to organize request logs
            
        Raises:
            ValueError: If required API_KEY environment variable is missing
        """
        api_url = os.environ.get("API_URL")
        api_key = os.environ.get("API_KEY")
        self._model = "anthropic/claude-3.7-sonnet"
        self._session_id = session_id

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
        
        # If session ID is provided, create a session-specific directory
        if session_id:
            self._requests_dir = self._requests_dir / session_id
            
        self._requests_dir.mkdir(parents=True, exist_ok=True)
        logger.debug(f"Request logs directory initialized at {self._requests_dir}")
        
        # Initialize the structured logger
        self.structured_logger = StructuredLogger(str(self._requests_dir))
    
    def set_session_id(self, session_id: str) -> None:
        """
        Update the session ID and create corresponding directory.
        
        Args:
            session_id: New session ID to use for organizing logs
        """
        self._session_id = session_id
        # Update requests directory to include session ID
        self._requests_dir = Path(os.path.expanduser("~")) / ".neo" / "requests" / session_id
        self._requests_dir.mkdir(parents=True, exist_ok=True)
        logger.debug(f"Updated request logs directory to {self._requests_dir}")
        
        # Create a new structured logger with the updated path
        self.structured_logger = StructuredLogger(str(self._requests_dir))
    
    def process(self, messages: List[Message]) -> Message:
        """
        Process a list of messages through the LLM and return the response.
        
        Returns:
            Message: LLM's response as a Message object
            
        Raises:
            Exception: Any error during processing is logged and re-raised
        """
        try:
            # Generate a unique ID for this request-response pair
            request_id = datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            
            # Preprocess messages for API consumption
            processed_messages = self._preprocess(messages)
            
            logger.debug(f"Sending request to LLM with {len(processed_messages)} messages")
            
            # Prepare request data structure for API call
            request_data = {
                "model": self._model,
                "messages": processed_messages,
            }
            
            # Log a summary of the conversation
            logger.info(f"Sending request {request_id} with {len(processed_messages)} messages to {self._model}")
            
            # Send the request to the LLM
            response = self.client.chat.completions.create(**request_data)
            
            # Convert the response to a dictionary
            response_dict = self._response_to_dict(response)
            
            # Prepare log data
            log_data = {
                "request_id": request_id,
                "session_id": self._session_id,
                "timestamp": datetime.datetime.now().isoformat(),
                "request": request_data,
                "response": response_dict,
                "meta": {
                    "message_count": len(processed_messages)
                }
            }
            
            # Log the request and response using the structured logger
            self.structured_logger.record("request", log_data)
            
            # Process the response and return
            return self._postprocess(response, messages)
            
        except Exception as e:
            logger.error(f"Error processing messages: {e}", exc_info=True)
            
            # Log the error with whatever information we have
            error_data = {
                "error": str(e),
                "timestamp": datetime.datetime.now().isoformat(),
                "session_id": self._session_id
            }
            
            if 'request_id' in locals():
                error_data["request_id"] = request_id
            
            if 'request_data' in locals():
                error_data["request"] = request_data
            
            try:
                self.structured_logger.record("error", error_data)
            except Exception as log_error:
                logger.error(f"Failed to log error: {log_error}")
            
            raise
    
    def _response_to_dict(self, response) -> Dict[str, Any]:
        """
        Convert an OpenAI response object to a dictionary for serialization.
        """
        try:
            # Try using the model's built-in dict conversion if available
            if hasattr(response, "model_dump"):
                return response.model_dump()
            elif hasattr(response, "to_dict"):
                return response.to_dict()
            else:
                # Fallback to manually extracting the important parts
                result = {
                    "id": getattr(response, "id", None),
                    "created": getattr(response, "created", None),
                    "model": getattr(response, "model", None),
                    "choices": []
                }
                
                # Extract choices
                if hasattr(response, "choices"):
                    for choice in response.choices:
                        choice_dict = {
                            "index": getattr(choice, "index", None),
                            "finish_reason": getattr(choice, "finish_reason", None),
                        }
                        
                        # Extract message
                        if hasattr(choice, "message"):
                            message = choice.message
                            choice_dict["message"] = {
                                "role": getattr(message, "role", None),
                                "content": getattr(message, "content", None)
                            }
                        
                        result["choices"].append(choice_dict)
                
                return result
        except Exception as e:
            # If all else fails, use the string representation
            logger.warning(f"Failed to convert response to dict: {e}")
            return {"raw_string": str(response)}
    
    def _preprocess(self, messages: List[Message]) -> List[Dict[str, Any]]:
        """
        Convert Message objects to the format expected by the OpenAI API.
        """
        result = []
        
        for message in messages:
            content_parts = []
            
            # Convert content blocks to text parts
            for block in message.content:
                if isinstance(block, TextBlock):
                    content_parts.append(block.text)
                elif isinstance(block, FunctionCall):
                    content_parts.append(str(block))
                elif isinstance(block, FunctionResult):
                    # Add the result followed by a note to clarify its handling
                    result_text = str(block)
                    content_parts.append(result_text + self.RESULT_NOTICE)
            
            # Join all parts with newlines for cleaner formatting
            content = '\n'.join(content_parts).strip()
            
            result.append({
                "role": message.role,
                "content": content
            })
        
        return result
    
    def _validate_args_dict(self, args_str: str) -> Dict[str, Any]:
        """
        Validate and parse function arguments as a Python dictionary.
        
        Args:
            args_str: String representation of function arguments
            
        Returns:
            Dict[str, Any]: Parsed arguments as a dictionary
            
        Raises:
            InvalidFunctionArgsError: If arguments are not a valid Python dictionary
        """
        args_str = args_str.strip()
        
        # First try to parse as JSON
        try:
            args_dict = json.loads(args_str)
            if not isinstance(args_dict, dict):
                raise InvalidFunctionArgsError(
                    f"Function arguments must be a dictionary, got {type(args_dict).__name__}"
                )
            return args_dict
        except json.JSONDecodeError:
            pass
        
        # If JSON fails, try to parse as a Python dict using ast.literal_eval
        try:
            # Only evaluate if it looks like a dict
            if args_str.startswith('{') and args_str.endswith('}'):
                args_dict = ast.literal_eval(args_str)
                if not isinstance(args_dict, dict):
                    raise InvalidFunctionArgsError(
                        f"Function arguments must be a dictionary, got {type(args_dict).__name__}"
                    )
                return args_dict
            else:
                raise InvalidFunctionArgsError(
                    "Function arguments must be a valid Python dictionary enclosed in {}"
                )
        except (SyntaxError, ValueError) as e:
            raise InvalidFunctionArgsError(
                f"Invalid function arguments format: {str(e)}"
            )
    
    def _create_retry_message(self, original_messages: List[Message], 
                             func_name: str, args_str: str, error_msg: str) -> List[Dict[str, Any]]:
        """
        Create a retry message for the LLM to correct the function arguments format.
        
        Args:
            original_messages: Original messages sent to the LLM
            func_name: Name of the function being called
            args_str: Original invalid arguments string
            error_msg: Error message explaining the format issue
            
        Returns:
            List[Dict[str, Any]]: Messages ready for sending to the LLM
        """
        # Preprocess the original messages
        processed_messages = self._preprocess(original_messages)
        
        # Add a system message asking to correct the function arguments
        retry_message = {
            "role": "system",
            "content": textwrap.dedent(f"""
            Your previous response contained a function call to '{func_name}' with invalid arguments format:
            
            ```
            {args_str}
            ```
            
            Error: {error_msg}
            
            Please reformat your function call with valid Python dictionary syntax. 
            Your arguments must be a valid Python dictionary. For example:
            
            {FUNCTION_START}: {func_name}
            {ARGS_START}: {{"key1": "value1", "key2": 123}}
            {FUNCTION_END}
            
            Do not include any other explanatory text, just respond with the corrected function call.
            """)
        }
        
        return processed_messages + [retry_message]
    
    def _extract_function_call(self, content: str) -> Tuple[str, str, str]:
        """
        Extract a single function call from content using string manipulation.
        
        Args:
            content: Response content to extract function call from
            
        Returns:
            Tuple[str, str, str]: Function name, arguments string, and remaining content
            
        Raises:
            ValueError: If no function call is found
        """
        # Find the first function start
        func_start_idx = content.find(f"{FUNCTION_START}:")
        if func_start_idx == -1:
            raise ValueError("No function call found in response")
        
        # Find the related parts
        args_start_idx = content.find(f"{ARGS_START}:", func_start_idx)
        if args_start_idx == -1:
            raise ValueError(f"Function call missing {ARGS_START} marker")
            
        func_end_idx = content.find(FUNCTION_END, args_start_idx)
        if func_end_idx == -1:
            raise ValueError(f"Function call missing {FUNCTION_END} marker")
        
        # Extract function name
        func_name_start = func_start_idx + len(f"{FUNCTION_START}:")
        func_name = content[func_name_start:args_start_idx].strip()
        
        # Extract arguments
        args_start = args_start_idx + len(f"{ARGS_START}:")
        args_str = content[args_start:func_end_idx].strip()
        
        # Extract remaining content
        remaining = content[func_end_idx + len(FUNCTION_END):].strip()
        
        return func_name, args_str, remaining
    
    def _postprocess(self, response, original_messages: List[Message], 
                retry_count: int = 0) -> Message:
        """
        Process LLM response to extract text and function calls using string manipulation.
        
        Args:
            response: LLM response object
            original_messages: Original messages sent to the LLM
            retry_count: Number of retries attempted for invalid function args
            
        Returns:
            Message: Processed response as a Message object
            
        Raises:
            InvalidFunctionArgsError: If function arguments are invalid after max retries
        """
        # Check if response or choices is None
        if response is None or not hasattr(response, 'choices') or response.choices is None or len(response.choices) == 0:
            logger.error("Received invalid or empty response from LLM")
            message = Message(role="assistant")
            message.add_content(TextBlock("I'm sorry, I encountered an error processing your request."))
            return message
        
        # Check if first choice has a message
        choice = response.choices[0]
        if not hasattr(choice, 'message') or choice.message is None:
            logger.error("Response choice doesn't have a message")
            message = Message(role="assistant")
            message.add_content(TextBlock("I'm sorry, I encountered an error processing your request."))
            return message
        
        # Ensure message has content
        if not hasattr(choice.message, 'content') or choice.message.content is None:
            logger.error("Response message doesn't have content")
            message = Message(role="assistant")
            message.add_content(TextBlock("I'm sorry, I encountered an error processing your request."))
            return message
        
        content = choice.message.content
        message = Message(role="assistant")
        
        # Process the content by looking for function calls
        remaining_content = content
        
        while FUNCTION_START in remaining_content:
            # Find the position of the function call
            func_start_pos = remaining_content.find(f"{FUNCTION_START}:")
            
            # If we have text before the function call, add it as a text block
            if func_start_pos > 0:
                text = remaining_content[:func_start_pos].strip()
                if text:
                    message.add_content(TextBlock(text))
            
            try:
                # Extract the function call details
                func_name, args_str, remaining = self._extract_function_call(remaining_content)
                
                # Validate and parse arguments
                try:
                    args_dict = self._validate_args_dict(args_str)
                    message.add_content(FunctionCall(func_name, args_dict))
                except InvalidFunctionArgsError as e:
                    # If max retries reached, raise the error
                    if retry_count >= self.MAX_RETRIES:
                        logger.error(f"Max retries reached for function call '{func_name}' with invalid args: {e}")
                        raise InvalidFunctionArgsError(
                            f"Failed to get valid function arguments after {self.MAX_RETRIES} retries: {e}"
                        )
                    
                    # Create retry message
                    retry_messages = self._create_retry_message(
                        original_messages, func_name, args_str, str(e)
                    )
                    
                    # Send retry request
                    logger.info(f"Retrying with corrected function arguments format (attempt {retry_count + 1}/{self.MAX_RETRIES})")
                    retry_response = self.client.chat.completions.create(
                        model=self._model,
                        messages=retry_messages
                    )
                    
                    # Process the retry response
                    return self._postprocess(retry_response, original_messages, retry_count + 1)
                
                # Update the remaining content to process
                remaining_content = remaining
                
            except ValueError as e:
                # If we can't properly extract a function call, log the error and stop processing
                logger.error(f"Error extracting function call: {e}")
                # Add the remaining content as text and exit the loop
                if remaining_content:
                    message.add_content(TextBlock(remaining_content.strip()))
                break
        
        # Add any remaining content as text
        if remaining_content and FUNCTION_START not in remaining_content:
            # Remove any result blocks
            result_idx = remaining_content.find(f"{RESULT_START}:")
            if result_idx != -1:
                # Find the end of the result block (next function or end of string)
                next_func_idx = remaining_content.find(f"{FUNCTION_START}:", result_idx)
                if next_func_idx != -1:
                    # Remove the result block
                    remaining_content = (
                        remaining_content[:result_idx].strip() + 
                        " " + 
                        remaining_content[next_func_idx:].strip()
                    )
                else:
                    # No more functions, just take the text before the result
                    remaining_content = remaining_content[:result_idx].strip()
            
            # Add any non-empty remaining content
            if remaining_content.strip():
                message.add_content(TextBlock(remaining_content.strip()))
        
        return message