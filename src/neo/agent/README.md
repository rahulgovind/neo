# Agent Component

## Overview

The Agent component is the core orchestrator of Neo's conversation system. It manages conversations with LLMs, processes user messages, executes commands, and maintains conversation state. The Agent uses a state machine approach with immutable state objects for predictable behavior.

## Key Components

### Agent (`agent.py`)

The primary class that serves as the entry point for conversation management:

- Initializes with a session and configuration parameters
- Loads system instructions and custom rules (from `.neorules` files)
- Processes user messages and returns assistant responses
- Integrates with the session for state persistence
- Supports both ephemeral and persistent conversation modes

```python
agent = Agent(session, ephemeral=True)
for message in agent.process(user_message):
    # Handle the assistant's message
```

### AgentState (`state.py`)

An immutable container for conversation state:

- Stores system instructions and the message history
- Uses functional update patterns (returns new state objects)
- Provides serialization methods for persistence
- Implements methods for state manipulation (add_messages, clear_messages, etc.)
- Supports turn-based conversation structures

### AgentStateMachine (`asm.py`)

Implements the stateless processing logic:

- Provides the core `step()` method to advance conversations
- Handles command execution flow and results
- Creates intelligent checkpoints for context summarization
- Prunes older messages to manage context length
- Supports configurable thresholds for checkpointing and pruning

## Features

### Hierarchical Memory Management

The agent implements a sophisticated approach to context retention:

- Automatic conversation checkpointing at configurable intervals
- Generation of AI-powered conversation summaries to preserve context
- Smart pruning of older messages while maintaining coherence
- Configurable thresholds for managing context window size

### Immutable State Design

The agent uses immutable data structures for predictable behavior:

- All state operations return new objects rather than modifying existing state
- Clean functional approach to state transitions
- Thread-safe operation due to immutability

### Custom Rules Support

The agent can load project-specific custom rules:

- Automatically detects and loads `.neorules` files from the workspace
- Extends system instructions with project-specific guidance
- Ensures consistent agent behavior across different sessions

## Integration Points

- **Session**: The agent receives a session object and uses it to access the client, shell, and other components
- **Client**: Used to communicate with LLMs and process responses
- **Shell**: Used to execute commands based on LLM responses
- **Message Structure**: Processes and generates structured messages with various content blocks

## Usage Example

```python
from src.neo.session import Session
from src.neo.agent import Agent

# Create a session
session = Session(workspace="/path/to/workspace")

# Initialize the agent with the session
agent = Agent(session, ephemeral=False)  # Uses persistent state

# Process a user message
for message in agent.process("Can you list all Python files in this directory?"):
    print(f"Assistant: {message.text()}")
```

## Future Considerations

- Advanced checkpoint management with more sophisticated summarization techniques
- Enhanced control flow for complex, multi-step operations
- Support for structured planning and reasoning steps
- Integration with external knowledge bases and tools
