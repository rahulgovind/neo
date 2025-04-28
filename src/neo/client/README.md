# Client Component

## Overview

The Client component is responsible for communication with LLMs using the OpenAI API format. It provides a robust abstraction that handles request formatting, response parsing, error recovery, and command validation. The Client supports various API providers while maintaining a consistent interface.

## Key Components

### Client (`client.py`)

The main client interface with high-level functionality:

- Processes messages to and from LLMs
- Validates command calls before execution
- Manages message preprocessing and response postprocessing
- Implements automatic retry logic for invalid command calls
- Handles structured logging of requests and responses

```python
client = Client(shell)
response = client.process(
    messages=[Message("user", "Hello, world!")],
    commands=["read_file", "write_file"],
    session_id="session-123"
)
```

### BaseClient (`base.py`)

Low-level implementation for API communication:

- Provides direct integration with LLM APIs (OpenAI, Claude, etc.)
- Implements OpenAI API format compatibility
- Performs token counting and usage tracking
- Handles environment-based configuration
- Manages request/response lifecycle

## Features

### Unified API Format

The client presents a consistent interface regardless of the underlying LLM provider:

- Works with OpenAI, Anthropic, and other compatible API endpoints
- Hides provider-specific implementation details
- Configurable through environment variables (API_KEY, API_URL, MODEL_ID)

### Command Validation and Retry

Robust handling of command execution:

- Pre-validates command calls before execution
- Automatically retries with corrective feedback for invalid commands
- Limits retry attempts to prevent infinite loops
- Provides clear error information for debugging

### Comprehensive Logging

Detailed logging of all interactions with LLMs:

- Records complete request and response content
- Tracks token usage and API call statistics
- Supports structured logging with session correlation
- Enables debugging and performance analysis

### Message Processing

Sophisticated handling of message content:

- Preprocesses messages to ensure proper formatting for the LLM
- Postprocesses responses to extract command calls and text blocks
- Supports ephemeral caching through metadata controls
- Handles specialized content (system messages, developer communications)

## Integration Points

- **Agent**: Uses the client to process conversations
- **Shell**: Provides command validation capabilities to the client
- **Messages**: Works with structured Message objects for input/output
- **Structured Logger**: Uses the logging system for request/response tracking

## Usage Example

```python
from src.neo.client import Client
from src.neo.core.messages import Message
from src.neo.shell import Shell

# Create a shell instance (required by the client)
shell = Shell(workspace="/path/to/workspace")

# Initialize the client with the shell
client = Client(shell)

# Process messages through the LLM
response = client.process(
    messages=[
        Message("system", "You are a helpful assistant."),
        Message("user", "What files are in this directory?")
    ],
    commands=shell.list_commands(),
    session_id="test-session"
)

# Access the assistant's response
print(response.text())
```

## Error Handling

The client implements comprehensive error handling:

- Graceful recovery from API errors and rate limits
- Proper handling of malformed responses
- Timeouts and retry mechanisms for transient issues
- Clear error reporting for debugging

## Future Considerations

- Support for streaming responses
- Adaptive token management for large context windows
- Advanced caching strategies for improved performance
- Multi-provider routing for load balancing and fallback
