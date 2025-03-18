# Neo Architecture

This document provides an overview of Neo's architecture, design decisions, and implementation details to help developers understand and extend the codebase.

## System Overview

Neo is a CLI application that integrates Large Language Models (LLMs) to provide an interactive assistant, with optional file operations capabilities. It provides a versatile chat interface where users can:

1. Have general conversations and ask questions
2. Get information, explanations, and creative assistance
3. Work with files in an optional workspace directory
4. Receive code assistance and apply changes when needed

The application uses the OpenAI API format for LLM interactions, which allows it to work with both OpenAI models and compatible alternatives.

## Component Architecture

Neo follows a layered architecture with clear separation of concerns:

```
┌─────────────────┐
│      CLI        │  Command-line interface and application entry point
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│      Chat       │  Interactive user interface and session management
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│      Agent      │  Orchestrates LLM interactions and function execution
└────────┬────────┘
         │
         ▼
┌─────────────────┐                 ┌─────────────────┐
│      Model      │◄────────────────▶   Functions     │
└─────────────────┘                 └─────────────────┘
  LLM interaction                      File operations
```

### Key Components

#### Model (src/model.py)

The Model component provides an abstraction over the LLM client API:

- Manages communication with the LLM using the OpenAI API format
- Handles message preprocessing and response postprocessing
- Extracts function calls from LLM responses
- Formats function results for the LLM

#### Function (src/function.py)

The Function component defines operations that can be invoked by the LLM:

- `ReadFiles`: Reads file content from the workspace
- `UpdateFile`: Creates or modifies files in the workspace
- `FunctionRegistry`: Manages available functions and their descriptions

#### Agent (src/agent.py)

The Agent builds on top of the Model and Functions:

- Maintains conversation state across messages
- Manages the context window with relevant information
- Orchestrates function execution based on LLM requests
- Handles the conversation flow and multi-turn interactions

#### Chat (src/chat.py)

The Chat component provides the user interface:

- Manages the interactive terminal session
- Processes user inputs and special commands
- Displays formatted responses
- Handles history and session management

#### CLI (src/cli.py)

The CLI component ties everything together:

- Parses command-line arguments
- Sets up the application environment
- Initializes all components with appropriate configurations
- Provides the main entry point for the application

## Key Design Decisions

### 1. Function Calling Implementation

Neo implements a custom function calling format instead of using OpenAI's native function calling:

```
✿FUNCTION✿: function_name
✿ARGS✿: {"arg1": "value1", "arg2": "value2"}
✿END FUNCTION✿
```

**Rationale**: This approach provides flexibility to work with various LLM providers while maintaining a consistent interface, regardless of whether the underlying API supports function calling natively.

### 2. State Management

Conversation state is maintained by the LLM itself, rather than using a hardcoded approach:

```python
STATE_PROMPT = """
You are responsible for maintaining the state of an ongoing conversation.
The state should include all important information but remain concise.

Current state:
{state}

Here is the latest exchange:
User: {user_message}
Assistant: {assistant_response}

Based on this exchange, update the state to include any new relevant information.
Provide only the updated state, nothing else.
"""
```

**Rationale**: This leverages the LLM's understanding of context and relevance, allowing for flexible and intelligent tracking of important conversation elements without hard-coding what should be remembered.

### 3. Flexible Operation With or Without Workspace

The system can operate in two modes:

1. **General Assistant Mode**: Without a specified workspace, Neo functions as a conversational assistant without file operations.

2. **Workspace Mode**: With a specified workspace, Neo gains file operation capabilities while maintaining security boundaries:

```python
def _normalize_path(self, path: str) -> str:
    # Ensure the path is within the workspace for security
    if not os.path.commonpath([self.workspace, os.path.realpath(full_path)]) == self.workspace:
        # Path is outside workspace, restrict to basename
        return os.path.join(self.workspace, os.path.basename(path))
```

**Rationale**: This dual-mode operation provides flexibility for different use cases while still ensuring security boundaries when file operations are enabled. Users can start with basic conversations and later add workspace capabilities as needed.

### 4. Error Boundaries and Recovery

Each component implements appropriate error handling with fallbacks:

```python
try:
    # Process user input...
except Exception as e:
    logger.error(f"Error processing message: {e}", exc_info=True)
    return "I encountered an error processing your request. Please try again."
```

**Rationale**: This ensures that failures in one part of the system (like a specific function call) don't crash the entire application, providing a more resilient user experience.

## Extension Points

Neo is designed to be extended in several ways:

### 1. Adding New Functions

To add a new function that can be called by the LLM:

1. Create a new class that inherits from `Function` in `src/function.py`
2. Implement the required methods: `name()`, `describe()`, and `invoke()`
3. Register the function in the `FunctionRegistry` in `cli.py`

### 2. Supporting Different LLM Providers

To support a different LLM provider:

1. Modify the `Model` class in `src/model.py` to use the desired client
2. Update the environment variables and authentication as needed
3. Ensure the response format is compatible with the existing postprocessing logic

### 3. Enhancing the Chat Interface

To add new features to the chat interface:

1. Add new command handlers in the `_handle_command()` method in `src/chat.py`
2. Extend the `COMMANDS` dictionary with new command descriptions
3. Implement the corresponding functionality within the Chat class

## Future Considerations

### Potential Improvements

1. **Web Interface**: Add a web-based UI as an alternative to the terminal interface
2. **Project Templates**: Support for project-specific templates and configurations
3. **IDE Integration**: Extensions for popular IDEs like VSCode or JetBrains
4. **Collaborative Mode**: Support for multiple users working with the same assistant
5. **Version Control Integration**: Direct integration with Git for tracking changes

### Performance Considerations

1. **Large Workspace Optimization**: For large codebases, implement indexing or caching
2. **Token Usage Optimization**: Implement strategies to compress context or selectively include relevant files
3. **Parallel Function Execution**: Process multiple function calls concurrently when appropriate

## Conclusion

Neo's architecture provides a solid foundation for an LLM-powered code assistant with a clear separation of concerns and well-defined interfaces between components. The design prioritizes flexibility, robustness, and extensibility while maintaining a straightforward user experience.