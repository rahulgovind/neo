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
│      Model      │◄────────────────│   Functions     │
└─────────────────┘                 └─────────────────┘
  LLM interaction                      File operations
```

### Key Components

#### Model (src/core/model.py)

The Model component provides an abstraction over the LLM client API:

- Manages communication with the LLM using the OpenAI API format
- Handles message preprocessing and response postprocessing
- Processes commands and their results through the LLM
- Supports auto-execution of multiple commands in sequence
- Extracts command calls from LLM responses

#### Commands (src/core/commands/)

Neo implements a consistent command framework for interacting with the file system and other resources:

- Base `Command` class (src/core/command.py) provides a unified interface for all commands
- Commands use a consistent CLI-like syntax for parameter handling
- Each command includes rich documentation and usage examples with formatted terminal display
- Commands provide structured error handling for reliable execution
- Parameter processing supports both positional and flag arguments with fully declarative definitions

Available commands include:
- `read_file`: Read and display file contents with flexible line number options, range selection, and line limiting
- `write_file`: Create or overwrite files with provided content, with automatic parent directory creation and code linting
- `update_file`: Apply changes to files using a structured diff syntax, with model-assisted fallback for complex changes
- `neogrep` (grep): Search for patterns in files with filtering by file types and support for context lines
- `neofind` (find): Locate files and directories based on name patterns and file types
- `bash`: Execute arbitrary shell commands as a fallback for operations not covered by specialized commands. Maintains 
  a persistent shell session across command invocations with graceful handling of shell termination and error conditions.

The command architecture follows these design principles:
- **Command Pattern**: Each command implements:
  - A `template()` method that defines parameters and documentation
  - A `process()` method that implements the command's functionality
- **Consistent Command Interface**: All commands follow a unified model with CLI-like syntax
- **Rich Documentation**: Documentation includes descriptions, parameter details, and interactive examples
- **Robust Error Handling**: Commands provide detailed error feedback to users and system components
- **Workspace Awareness**: Commands respect workspace boundaries for security

#### Agent (src/agent/agent.py)

The Agent component orchestrates the interaction between the user, Model, and Functions:

- Delegates user requests to appropriate components
- Manages execution flow between user input and LLM responses
- Handles command execution and result formatting
- Provides context management for conversations
- Implements safety measures and execution boundaries

#### Chat (src/apps/chat.py)

The Chat component provides the user interface:

- Manages the interactive terminal session
- Processes user inputs and special commands
- Displays formatted responses
- Handles history and session management

#### CLI (src/apps/cli.py)

The CLI component ties everything together:

- Parses command-line arguments
- Sets up the application environment
- Initializes all components with appropriate configurations
- Provides the main entry point for the application

### Quality Assurance and Linting

Neo integrates code quality checks directly into file operations:

- **Linting Framework**: A modular, extensible linting system checks code quality during write operations
  - Implemented using a registry pattern to support multiple file types
  - Initially supports Python files with pylint, easily extendable to other languages
  - Files are written even when lint fails, but users receive detailed error reports

- **Design Principles**:
  - Separation of concerns: Linting logic is isolated from file operations
  - Extensibility: Adding support for new file types requires minimal code changes
  - Non-blocking: Linting issues warn users but don't prevent writing files

## Future Considerations

### Potential Improvements

1. **Web Interface**: Add a web-based UI as an alternative to the terminal interface
2. **Project Templates**: Support for project-specific templates and configurations
3. **IDE Integration**: Extensions for popular IDEs like VSCode or JetBrains
4. **Collaborative Mode**: Support for multiple users working with the same assistant
5. **Version Control Integration**: Direct integration with Git for tracking changes

### Additional Components

The project includes several components not detailed above:

#### 1. Web Application (src/apps/web/)

Neo includes a web-based interface as an alternative to the terminal:
- `app.py`: Implements the web server and routes
- `launcher.py`: Provides entry points for starting the web application

#### 2. Database (src/database/)

A database component for persistent storage:
- Supports storing conversation history and context between sessions
- Provides data access abstractions for the rest of the application

#### 3. Structured Logging (src/logging/)

A dedicated logging infrastructure:
- Implements structured logging for better analysis
- Provides consistent log formatting across the application

[... rest of the content remains the same ...]
123