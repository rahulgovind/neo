"""
LSP client for Python code navigation features.

Provides a streamlined interface for connecting to Python LSP servers and
querying code intelligence like definitions and hover information.
"""

import json
import logging
import os
import socket
import sys
import threading
import time
from typing import Any, Dict, List, Optional, Union, Tuple

# Internal imports
from .server import create_lsp_server, LSPServer
from .models import (
    LspPosition, LspRange, LspLocation, 
    LspHoverContent, LspHoverResult,
    LspDefinitionResult, LspReferencesResult
)

# Configure logging
logger = logging.getLogger(__name__)

# Set a default level for this module
if logger.level == logging.NOTSET:  # Only set level if not already configured
    logger.setLevel(logging.INFO)


class LSPClient:
    """Client for Language Server Protocol.

    Provides core code navigation capabilities:
    - Go to definition
    - Get hover information
    - Document synchronization
    """

    def __init__(self):
        """Initialize LSP client."""
        # Socket connection
        self._socket = None

        # State tracking
        self._initialized = False
        self._running = False
        self._reader_thread = None
        self._pending_requests = {}
        self._next_request_id = 1
        
        # Progress tracking
        self._progress_states = {}
        self._progress_tokens = set()

    def connect(self, host: str, port: int) -> bool:
        """Connect to an LSP server and initialize the session."""
        try:
            # Clean up existing connection if any
            self._cleanup_connection()

            # Establish new connection with timeout
            logger.info(f"Attempting to connect to LSP server at {host}:{port}")
            self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self._socket.settimeout(5.0)  # Connection timeout
            self._socket.connect((host, port))

            # Configure socket after connection established
            self._socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)  # Disable Nagle's algorithm
            self._socket.settimeout(None)  # Switch to blocking mode for normal operation

            logger.info(f"Socket connected to LSP server at {host}:{port}")

            # Start message reader thread
            self._running = True
            self._start_reader_thread()

            # Initialize connection with server
            init_result = self._initialize()
            if init_result:
                logger.info("LSP connection initialized successfully")
            else:
                logger.error("LSP initialization failed")
                self._cleanup_connection()  # Clean up on failure

            return init_result

        except socket.timeout:
            logger.error(f"Timeout connecting to LSP server at {host}:{port}")
            return False
        except ConnectionRefusedError:
            logger.error(f"Connection refused by LSP server at {host}:{port}")
            return False
        except Exception as e:
            logger.error(f"Failed to connect to LSP server: {str(e)}")
            return False

    def _cleanup_connection(self):
        """Release socket and thread resources."""
        # Signal reader thread to stop
        self._running = False

        # Close socket if open
        if self._socket:
            try:
                self._socket.close()
            except Exception as e:
                logger.debug(f"Error closing socket: {e}")
            self._socket = None

        # Reset state
        self._initialized = False

        # Wait briefly for reader thread to clean up
        if self._reader_thread and self._reader_thread.is_alive():
            time.sleep(0.2)  # Give thread time to exit

    def _initialize(self) -> bool:
        """Perform LSP initialization handshake."""
        # Set up minimal initialization parameters
        params = {
            "processId": os.getpid(),
            "clientInfo": {
                "name": "SimplifiedPythonLSPClient",
                "version": "1.0.0",
            },
            "capabilities": {
                # Only request capabilities we actually use
                "textDocument": {
                    "hover": {
                        "contentFormat": ["markdown", "plaintext"]
                    },
                    "definition": {
                        "linkSupport": True
                    },
                },
            },
            # Skip workspace folder configuration
            "workspaceFolders": None,
        }

        # Send initialization request with extended timeout
        logger.info("Initializing LSP server connection (with extended timeout)")
        response = self.send_request(
            "initialize", params, timeout=30.0, allow_uninitialized=True
        )

        # Validate response
        if not response:
            logger.error("Invalid initialization response: None")
            return False

        # Check for errors
        if "error" in response:
            error = response["error"]
            error_msg = error.get('message', 'Unknown error')
            logger.error(f"LSP initialization error: {error_msg}")
            return False

        # Process server capabilities
        result = response.get("result", {})
        capabilities = result.get("capabilities", {})

        # Log available capabilities
        capability_list = list(capabilities.keys())
        if capability_list:
            logger.info(f"Server capabilities received: {', '.join(capability_list)}")
        else:
            logger.warning("Server returned no capabilities")

        # Send initialized notification to complete handshake
        if not self._send_notification("initialized", {}):
            logger.error("Failed to send 'initialized' notification")
            return False

        # Update client state
        logger.info("LSP server initialized successfully")
        self._initialized = True
        return True

    def shutdown(self) -> None:
        """Terminate LSP session and clean up resources."""
        if not self._initialized:
            return

        logger.info("Shutting down LSP session")

        try:
            # Send shutdown request
            self.send_request("shutdown", {})
            self._send_notification("exit", {})
        except Exception as e:
            logger.error(f"Error during shutdown: {e}")

        # Clean up resources
        self._running = False
        if self._reader_thread:
            self._reader_thread.join()

        if self._socket:
            self._socket.close()
            self._socket = None

        logger.info("LSP session shut down")

    def send_request(
        self, method: str, params: Dict[str, Any], timeout: float = 10.0, allow_uninitialized: bool = False
    ) -> Optional[Dict[str, Any]]:
        """Send a request to the LSP server and wait for the response.

        Args:
            method: The LSP method to call
            params: Parameters for the request
            timeout: Maximum time to wait for response in seconds
            allow_uninitialized: Whether to allow sending request when not initialized

        Returns:
            The response from the server or None if the request failed
        """
        # Validate connection state
        if not self._socket:
            logger.error(f"Cannot send request {method}: No connection")
            return None

        if not self._initialized and not allow_uninitialized:
            logger.error(f"Cannot send request {method}: Connection not initialized")
            return None

        # Use simple timeout strategy: increase timeout for initialization
        if method == "initialize" and timeout < 30.0:
            timeout = 30.0  # Allow more time for initialization

        # Create a unique request ID
        request_id = self._next_request_id
        self._next_request_id += 1

        # Create JSON-RPC message
        message = {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": method,
            "params": params
        }

        # Set up synchronization primitives
        response_event = threading.Event()
        response_container = [None]  # Using list as mutable container

        # Register request for response tracking
        self._pending_requests[request_id] = (response_event, response_container)

        # Log the request for debugging
        logger.info(f"Preparing request {request_id}: {method} (timeout: {timeout}s)")

        # Send the message
        if not self._send_message(message):
            logger.error(f"Failed to send {method} request to server")
            del self._pending_requests[request_id]
            return None

        # Wait for response with timeout
        start_time = time.time()
        if response_event.wait(timeout):
            # Response received
            response = response_container[0]
            # Clean up
            del self._pending_requests[request_id]
            return response
        else:
            # Timeout occurred
            elapsed = time.time() - start_time
            logger.error(f"{method} request (id={request_id}) timed out after {elapsed:.1f} seconds")
            del self._pending_requests[request_id]
            return None

    def _send_notification(self, method: str, params: Dict[str, Any]) -> bool:
        """Send notification without expecting a response.

        Args:
            method: The LSP method name
            params: Parameters for the notification

        Returns:
            True if the notification was sent successfully, False otherwise
        """
        notification = {"jsonrpc": "2.0", "method": method, "params": params}

        return self._send_message(notification)

    def _send_message(self, message: Dict[str, Any]) -> bool:
        """Encode and send a message to the server.

        Args:
            message: The message to send

        Returns:
            True if the message was sent successfully, False otherwise
        """
        if not self._socket:
            logger.error("Cannot send message: Not connected to LSP server")
            return False

        # Encode message as JSON
        try:
            message_id = message.get("id", "(notification)")
            method = message.get("method", "unknown")
            logger.debug(f"Sending message {message_id} method={method}")

            content = json.dumps(message)
            content_bytes = content.encode("utf-8")

            # Construct header
            header = f"Content-Length: {len(content_bytes)}\r\n\r\n"
            header_bytes = header.encode("ascii")

            # Send message
            try:
                message_data = header_bytes + content_bytes
                logger.debug(f"Sending {len(message_data)} bytes")
                self._socket.sendall(message_data)
                logger.debug(f"Message {message_id} sent successfully")
                return True
            except ConnectionResetError:
                logger.error("Connection reset by server while sending message")
                self._socket = None
                return False
            except BrokenPipeError:
                logger.error("Broken pipe while sending message - server may have disconnected")
                self._socket = None
                return False
            except socket.error as e:
                logger.error(f"Socket error while sending message: {e}")
                # Connection is broken, mark as disconnected
                self._socket = None
                return False

        except Exception as e:
            logger.error(f"Failed to encode/send message: {e}")
            return False

    def _start_reader_thread(self):
        """Launch background thread for message processing."""
        def reader_func():
            """Thread function that reads messages from the socket."""
            # Buffer for accumulating message fragments
            buffer = bytearray()

            try:
                while self._running:
                    if not self._socket:
                        logger.error("Reader thread: socket is closed")
                        break

                    # Add timeout to make the thread responsive to shutdown requests
                    self._socket.settimeout(0.5)

                    try:
                        # Read data from socket
                        data = self._socket.recv(4096)

                        # Check for connection closure
                        if not data:
                            logger.warning("Connection closed by server (empty data received)")
                            break

                        # Add data to buffer and process messages
                        buffer.extend(data)
                        buffer = self._process_buffer(buffer)

                    except socket.timeout:
                        # Expected during normal operation due to our timeout
                        continue
                    except (ConnectionResetError, ConnectionAbortedError, BrokenPipeError) as e:
                        # Connection issues
                        if self._running:
                            logger.error(f"Connection error: {e}")
                        break
                    except Exception as e:
                        # Other unexpected errors
                        logger.error(f"Error in reader thread: {e}")
                        # Brief pause to avoid CPU spinning in case of persistent errors
                        time.sleep(0.1)
            except Exception as e:
                logger.error(f"Fatal error in reader thread: {e}")
            finally:
                logger.info("Reader thread exiting")
                # Ensure cleanup happens if the thread exits
                self._running = False

        # Create and start the reader thread
        self._reader_thread = threading.Thread(
            target=reader_func,
            daemon=True,
            name="lsp-reader-thread"
        )
        self._reader_thread.start()

    def _process_buffer(self, buffer: bytearray) -> bytearray:
        """Extract complete LSP messages from the buffer and process them."""
        remaining_buffer = buffer

        while True:
            # Check if we have a complete header section
            header_sep = b'\r\n\r\n'
            if header_sep not in remaining_buffer:
                break

            # Split into header and content sections
            header, rest = remaining_buffer.split(header_sep, 1)

            # Find Content-Length in the header
            content_length = None
            for line in header.decode('ascii', errors='replace').splitlines():
                if line.lower().startswith('content-length:'):
                    try:
                        content_length = int(line.split(':', 1)[1].strip())
                        break
                    except (ValueError, IndexError):
                        pass

            if content_length is None:
                logger.error("No valid Content-Length header found")
                # Skip this malformed header and try to resync
                remaining_buffer = rest
                continue

            # Check if we have received the complete message content
            if len(rest) < content_length:
                # Incomplete message, wait for more data
                break

            # Extract and process the complete message
            content = rest[:content_length]
            remaining_buffer = rest[content_length:]

            try:
                message = json.loads(content.decode('utf-8'))
                self._handle_message(message)
            except json.JSONDecodeError:
                logger.error(f"Invalid JSON in message content: {content[:100]}...")
            except Exception as e:
                logger.error(f"Error processing message: {str(e)}")

        return remaining_buffer

    def _handle_message(self, message: Dict[str, Any]) -> None:
        """Route incoming messages to appropriate handlers."""
        # Handle responses to pending requests
        if "id" in message and ("result" in message or "error" in message):
            request_id = message["id"]
            if request_id in self._pending_requests:
                logger.debug(f"Received response for request {request_id}")
                self._pending_requests[request_id][1][0] = message
                self._pending_requests[request_id][0].set()
            else:
                logger.warning(f"Received response for unknown request ID: {request_id}")

        # Handle server notifications
        elif "method" in message and "id" not in message:
            method = message.get("method", "unknown")
            params = message.get("params", {})
            logger.debug(f"Received notification: {method}")

            # Handle various server notifications
            if method == "window/logMessage":
                # Server log messages
                msg_type = params.get("type", 3)  # Default to 'info' level
                msg_text = params.get("message", "")

                # Map LSP message types to Python logging levels
                level_map = {1: logging.ERROR, 2: logging.WARNING, 3: logging.INFO, 4: logging.DEBUG}
                level = level_map.get(msg_type, logging.INFO)

                logger.log(level, f"[LSP Server] {msg_text}")

            elif method == "window/showMessage":
                # Server messages to show to the user
                msg_type = params.get("type", 3)
                msg_text = params.get("message", "")
                level_map = {1: logging.ERROR, 2: logging.WARNING, 3: logging.INFO, 4: logging.DEBUG}
                level = level_map.get(msg_type, logging.INFO)
                logger.log(level, f"[LSP Message] {msg_text}")

            elif method == "$/progress":
                # Enhanced progress notifications with detailed logging
                token = params.get("token", "")
                value = params.get("value", {})
                kind = value.get("kind")
                
                # Get progress details with fallbacks for missing fields
                title = value.get("title", "")
                message = value.get("message", "")
                percentage = value.get("percentage")
                
                # Format percentage if available
                percentage_str = f" ({percentage}%)" if percentage is not None else ""
                
                if kind == "begin":
                    logger.info(f"[LSP Progress] Started: {title}")
                    if message:
                        logger.info(f"[LSP Progress]   {message}{percentage_str}")
                        
                elif kind == "report":
                    logger.info(f"[LSP Progress] {message or title}{percentage_str}")
                    
                elif kind == "end":
                    logger.info(f"[LSP Progress] Completed: {message or title}")
                    
                # Store progress state for potential UI integration
                self._store_progress_state(token, kind, title, message, percentage)

            elif method == "window/workDoneProgress/create":
                # Server is requesting to create a progress token
                token = params.get("token", "")
                self._progress_tokens.add(token)
                logger.debug(f"Server created progress token: {token}")

    def _store_progress_state(self, token: str, kind: str, title: str, message: str, percentage: Optional[int] = None) -> None:
        """Store progress information for tracking and potential UI integration."""
        if not token:
            return
            
        # Initialize token state if not exists
        if token not in self._progress_states:
            self._progress_states[token] = {
                "kind": None,
                "title": "",
                "message": "",
                "percentage": None,
            }
            
        state = self._progress_states[token]
        
        # Update state with new information
        if kind:
            state["kind"] = kind
        if title:
            state["title"] = title
        if message:
            state["message"] = message
        if percentage is not None:
            state["percentage"] = percentage
            
        # Clean up completed progress
        if kind == "end":
            self._progress_tokens.discard(token)
            if token in self._progress_states:
                del self._progress_states[token]
                
        # Handle server requests (rare)
        elif "method" in message and "id" in message:
            # Server is expecting a response
            logger.warning(f"Received server request (not implemented): {message.get('method')}")

        else:
            logger.warning(f"Received unrecognized message format: {message.keys()}")

    def text_document_definition(
        self, uri: str, line: int, character: int
    ) -> LspDefinitionResult:
        """Find definition locations for symbol at position.
        
        Args:
            uri: Document URI
            line: One-indexed line number (converted to zero-indexed for LSP)
            character: Zero-indexed character position
        
        Raises:
            ValueError: If the client is not initialized or the request fails
        """
        if not self._initialized:
            raise ValueError("Cannot get definition: LSP not initialized")

        # Convert one-indexed line number to zero-indexed for LSP
        zero_based_line = max(0, line - 1)

        params = {
            "textDocument": {"uri": uri},
            "position": {"line": zero_based_line, "character": character},
        }

        response = self.send_request("textDocument/definition", params)
        if response is None:
            raise ValueError("Failed to get definition from language server")

        # Process and convert response to structured result
        if isinstance(response, list):
            # Direct list of locations (rare but possible)
            result = response
        elif isinstance(response, dict) and "result" in response:
            # Standard JSON-RPC response with result field
            result = response.get("result", [])
        else:
            logger.warning(f"Unexpected definition response format: {type(response)}")
            result = []
            
        # Normalize result to list
        if not isinstance(result, list):
            result = [result] if result else []
            
        # Convert dictionaries to structured Location objects and adjust line numbers to one-indexed
        locations = [self._convert_location(loc) for loc in result if isinstance(loc, dict)]
        return LspDefinitionResult(locations=locations)

    def _convert_position(self, pos_dict: Dict[str, Any]) -> LspPosition:
        """Convert a position dictionary to an LspPosition object.
        
        Converts zero-indexed line numbers from LSP to one-indexed for client code.
        """
        if not isinstance(pos_dict, dict) or "line" not in pos_dict or "character" not in pos_dict:
            return LspPosition(line=1, character=0)  # Default to line 1 (one-indexed)
        
        # Convert zero-indexed line from LSP to one-indexed for client
        return LspPosition(
            line=pos_dict.get("line", 0) + 1,  # Add 1 to convert from zero-indexed to one-indexed
            character=pos_dict.get("character", 0)
        )

    def _convert_range(self, range_dict: Dict[str, Any]) -> LspRange:
        """Convert a range dictionary to an LspRange object."""
        if not isinstance(range_dict, dict) or "start" not in range_dict or "end" not in range_dict:
            return LspRange(
                start=LspPosition(line=0, character=0),
                end=LspPosition(line=0, character=0)
            )
        return LspRange(
            start=self._convert_position(range_dict.get("start", {})),
            end=self._convert_position(range_dict.get("end", {}))
        )

    def _convert_location(self, loc_dict: Dict[str, Any]) -> LspLocation:
        """Convert a location dictionary to an LspLocation object."""
        if not isinstance(loc_dict, dict) or "uri" not in loc_dict or "range" not in loc_dict:
            return LspLocation(
                uri="",
                range=LspRange(
                    start=LspPosition(line=0, character=0),
                    end=LspPosition(line=0, character=0)
                )
            )
        return LspLocation(
            uri=loc_dict.get("uri", ""),
            range=self._convert_range(loc_dict.get("range", {}))
        )

    def _extract_hover_content(self, contents) -> Optional[LspHoverContent]:
        """Extract hover content from various possible formats."""
        if contents is None:
            return None
        
        if isinstance(contents, dict) and "value" in contents:
            return LspHoverContent(
                value=contents.get("value", ""),
                kind=contents.get("kind")
            )
        elif isinstance(contents, str):
            return LspHoverContent(value=contents)
        elif isinstance(contents, list) and len(contents) > 0:
            first_item = contents[0]
            if isinstance(first_item, dict) and "value" in first_item:
                return LspHoverContent(
                    value=first_item.get("value", ""),
                    kind=first_item.get("kind")
                )
            elif isinstance(first_item, str):
                return LspHoverContent(value=first_item)
        
        return LspHoverContent(value="")

    def text_document_hover(
        self, uri: str, line: int, character: int
    ) -> LspHoverResult:
        """Get hover information for symbol at position.
        
        Args:
            uri: Document URI
            line: One-indexed line number (converted to zero-indexed for LSP)
            character: Zero-indexed character position
        
        Raises:
            ValueError: If the client is not initialized or the request fails
        """
        if not self._initialized:
            raise ValueError("Cannot get hover info: LSP not initialized")

        # Convert one-indexed line number to zero-indexed for LSP
        zero_based_line = max(0, line - 1)

        params = {
            "textDocument": {"uri": uri},
            "position": {"line": zero_based_line, "character": character},
        }

        response = self.send_request("textDocument/hover", params)
        if response is None:
            raise ValueError("Failed to get hover information from language server")

        # Process and convert response to structured result
        result = response.get("result")
        if result is None or "contents" not in result:
            return LspHoverResult()
            
        contents = result.get("contents")
        hover_content = self._extract_hover_content(contents)
        
        range_data = result.get("range")
        hover_range = self._convert_range(range_data) if range_data else None
        
        return LspHoverResult(contents=hover_content, range=hover_range)

    def text_document_references(
        self, uri: str, line: int, character: int, include_declaration: bool = True
    ) -> LspReferencesResult:
        """Find references to the symbol at position.
        
        Args:
            uri: Document URI
            line: One-indexed line number (converted to zero-indexed for LSP)
            character: Zero-based character position
            include_declaration: Whether to include the declaration in results
        
        Returns:
            Structured result containing a list of reference locations
            
        Raises:
            ValueError: If the client is not initialized or the request fails
        """
        if not self._initialized:
            raise ValueError("Cannot get references: LSP not initialized")

        # Convert one-indexed line number to zero-indexed for LSP
        zero_based_line = max(0, line - 1)

        params = {
            "textDocument": {"uri": uri},
            "position": {"line": zero_based_line, "character": character},
            "context": {"includeDeclaration": include_declaration}
        }

        response = self.send_request("textDocument/references", params)
        if response is None:
            raise ValueError("Failed to get references from language server")
            
        # Process and convert response to structured result
        if isinstance(response, list):
            # Direct list of locations (rare but possible)
            result = response
        elif isinstance(response, dict) and "result" in response:
            # Standard JSON-RPC response with result field
            result = response.get("result", [])
        else:
            logger.warning(f"Unexpected references response format: {type(response)}")
            result = []
            
        # Normalize result to list
        if not isinstance(result, list):
            result = []
            
        # Convert dictionaries to structured Location objects and adjust line numbers to one-indexed
        locations = [self._convert_location(loc) for loc in result if isinstance(loc, dict)]
        return LspReferencesResult(locations=locations)

# Global server instance for reuse across multiple clients
_global_lsp_server: Optional[LSPServer] = None
_server_lock = threading.RLock()  # Thread-safe access to global server


def create_lsp_client(language: str = "python") -> LSPClient:
    """Create an LSP client connected to a shared server instance.

    Only supports Python language servers.

    Raises:
        ValueError: If a language other than Python is requested
    """
    if language.lower() != "python":
        raise ValueError(f"Unsupported language: {language}. Only Python is supported.")

    global _global_lsp_server

    # Create the shared server instance if it doesn't exist (thread-safe)
    with _server_lock:
        if _global_lsp_server is None:
            _global_lsp_server = create_lsp_server()
            logger.info("Created global LSP server instance")

    # Create a new client
    client = LSPClient()
    
    try:
        # Set up a local Python server
        with _server_lock:
            port = _global_lsp_server.setup_local_server("python")
        
        if port is not None:
            logger.info(f"Started Python language server on port {port}")
            
            # Connect the client to the server
            success = client.connect("127.0.0.1", port)
            if success:
                logger.info("Client connected to Python language server")
            else:
                logger.error("Failed to connect client to Python language server")
        else:
            logger.error("Failed to start Python language server")
    except Exception as e:
        logger.error(f"Error setting up Python LSP client: {e}")
    
    return client
