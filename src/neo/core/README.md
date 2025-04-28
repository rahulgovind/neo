# Core Component

## Overview

The Core component provides foundational structures and definitions used throughout Neo. It includes the message structure system, constants, and common types used across other components. This module forms the backbone of Neo's data communication model.

## Key Components

### Messages (`messages.py`)

Defines structured message formats for conversations:

- `Message` class: Container for conversation messages
- `ContentBlock` hierarchy: Different types of content within messages
- Serialization/deserialization for message persistence
- Support for mixed content types in a single message

```python
# Creating a message with text content
message = Message(role="assistant", blocks=[TextBlock("Hello, I'm Neo!")])

# Accessing content
text = message.text()

# Converting to/from dictionary for storage
message_dict = message.to_dict()
restored_message = Message.from_dict(message_dict)
```

### Content Blocks

The content block system enables rich message content:

- **TextBlock**: Plain text content for normal conversation
- **CommandCall**: Represents command execution requests
- **CommandResult**: Contains command execution results with success/failure status
- **StructuredOutput**: Formatted, schema-validated output data

Each block type has specialized methods for processing and rendering its content.

### Constants (`constants.py`)

Central definitions for configuration values:

- System paths and directories
- Default configuration settings
- Role definitions (user, assistant, system)
- Content type identifiers
- Special tokens and markers

## Features

### Mixed Content Support

Messages can contain multiple types of content:

- Text blocks for natural language
- Command calls for execution requests
- Command results for execution responses
- Structured output for formatted data
- Specialized metadata blocks

### Serialization

Full serialization support for persistence:

- JSON-compatible dictionary conversion
- Roundtrip message reconstruction
- Versioned serialization format
- Backward compatibility handling

### Content Processing

Utilities for message content manipulation:

- Text extraction from complex messages
- Block filtering by type
- Content concatenation and formatting
- Special formatting for different output contexts

## Integration Points

- **Agent**: Uses messages to represent conversation state
- **Client**: Processes messages to/from LLMs
- **Commands**: Return command results as content blocks
- **Service**: Persists messages for session continuity

## Usage Example

```python
from src.neo.core.messages import Message, TextBlock, CommandCall, CommandResult

# Create a complex message with different content types
message = Message(
    role="assistant",
    blocks=[
        TextBlock("I'll check what Python files are in this directory."),
        CommandCall("file_path_search . --file-pattern '*.py'"),
        CommandResult(
            command="file_path_search",
            content="example.py\nutils.py",
            success=True
        ),
        TextBlock("I found 2 Python files: example.py and utils.py.")
    ]
)

# Extract plain text (concatenates all TextBlocks)
print(message.text())

# Check for command execution
commands = [block for block in message.blocks if isinstance(block, CommandCall)]
print(f"Commands executed: {len(commands)}")

# Serialize the message
message_dict = message.to_dict()
print(message_dict)

# Reconstruct from dictionary
restored = Message.from_dict(message_dict)
```

## Message Format

Messages use a structured format internally:

```python
{
    "role": "assistant",  # user, assistant, or system
    "blocks": [
        {
            "type": "text",
            "content": "Hello, I'm Neo!"
        },
        {
            "type": "command_call",
            "command": "read_file",
            "args": "example.py"
        },
        {
            "type": "command_result",
            "command": "read_file",
            "status": "success",
            "content": "def hello():\n    print('Hello world!')"
        }
    ],
    "metadata": {
        "timestamp": "2023-06-15T12:34:56Z",
        "ephemeral": False
    }
}
```

## Future Considerations

- Additional content block types for rich media (images, charts)
- Enhanced metadata for message tracking and analytics
- Streaming support for incremental message building
- Schema validation for all message structures
