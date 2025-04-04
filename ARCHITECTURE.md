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
- Processes commands and their results through the LLM
- Supports auto-execution of multiple commands in sequence
- Extracts command calls from LLM responses

#### Client (src/core/client.py)

The Client component handles direct communication with LLM providers:

- Abstracts away provider-specific details using the OpenAI API format
- Manages API connections, request formatting, and response handling
- Handles token counting and request logging
- Processes special command markers in responses
- Supports robust error handling and recovery

#### Shell (src/core/shell.py)

The Shell component serves as the central hub for command execution:

- Registers and manages available commands
- Parses command input strings into structured commands
- Executes commands with appropriate arguments
- Processes command calls from the LLM
- Returns command results in a standardized format

#### Command (src/core/command.py)

The Command component defines the interface for executable commands:

- Provides an abstract base class that all commands implement
- Supports parameter parsing for positional and flag arguments
- Handles documentation generation for command usage
- Manages error handling and command result formatting
- Enables a CLI-like command execution pattern

#### Context (src/core/context.py)

The Context component manages application state and dependencies:

- Provides access to the workspace, model, shell, and agent
- Uses a builder pattern for easy initialization
- Manages session identification and tracking
- Serves as the central point for component references
- Enforces dependency availability through property getters

#### Messages (src/core/messages.py)

The Messages component defines data structures for communication:

- Implements various content block types (TextBlock, CommandCall, CommandResult)
- Handles special character escaping and unescaping
- Provides consistent formatting for commands and their results
- Maintains structured representation of conversation history
- Supports extraction of command calls from messages

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
<SPECIAL_TOKEN>FUNCTION<SPECIAL_TOKEN>: function_name
<SPECIAL_TOKEN>ARGS<SPECIAL_TOKEN>: {"arg1": "value1", "arg2": "value2"}
<SPECIAL_TOKEN>END FUNCTION<SPECIAL_TOKEN>
```

where <SPECIAL_TOKEN> = ✿

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

## Command Implementation

Neo implements a set of powerful file operation commands through a consistent Command interface:

### Command Structure

Each command follows a consistent pattern defined by the Command abstract base class:

1. **Template Definition**: Commands define their parameters, documentation, and examples through a CommandTemplate
2. **Parameter Types**: Support for both positional arguments and flag-based options 
3. **Process Implementation**: Core logic that executes the command and returns results
4. **Error Handling**: Standardized error reporting with appropriate context

### Built-in Commands

The following built-in commands are automatically registered in the Shell:

1. **read_file**: Reads and displays file contents with optional line numbering
2. **write_file**: Creates or overwrites files with provided content
3. **update_file**: Modifies existing files using a diff structure
4. **grep**: Searches for patterns in files with filtering capabilities
5. **find**: Locates files and directories matching specific criteria

### Command Registration

New commands can be added to the system by:
1. Creating a new class that inherits from the Command base class
2. Implementing the required template() and process() methods
3. Registering the command with the Shell instance

The command system is designed to be extensible, allowing developers to add new functionality without modifying the core framework.