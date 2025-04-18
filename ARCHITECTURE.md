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

#### Commands (src/neo/commands/)

Neo implements a consistent command framework for interacting with the file system and other resources:

- Base `Command` class (src/neo/shell/command.py) provides a unified interface for all commands
- Commands use a consistent CLI-like syntax for parameter handling
- Each command includes rich documentation and usage examples with formatted terminal display
- Commands provide structured error handling for reliable execution
- Parameter processing supports both positional and flag arguments with fully declarative definitions

Available commands include:

- **`read_file`** (ReadFileCommand): Read and display file contents with the following features:
  - Line number display with toggle option (--no-line-numbers)
  - Flexible line range selection (--from, --until)
  - Output limiting with configurable maximum lines (--limit)
  - Support for negative indices to count from end of file
  - Special handling for NEO_HOME directory access
  - Workspace-aware path resolution for security
  - Graceful error handling for common file access issues

- **`write_file`** (WriteFileCommand): Create or overwrite files with provided content:
  - Automatic parent directory creation when needed
  - Support for relative and absolute paths within workspace
  - Returns line addition/deletion statistics and success status
  - Workspace-aware path handling for security
  - Optional linting support for code files

- **`update_file`** (UpdateFileCommand): Apply changes to files using a structured diff syntax:
  - Supports multiple operation types (@UPDATE, @DELETE)
  - Sequential application of diff chunks from top to bottom
  - @@BEFORE and @@AFTER subsections for defining changes
  - Model-assisted fallback for complex changes (with optional disable flag)
  - Detailed error reporting and recovery mechanisms
  - Preserves file formatting and style

- **`neogrep`** (NeoGrepCommand): Search for patterns in files:
  - Delegates to the system grep command for efficient searching
  - Case-sensitive and case-insensitive searching (-i/--ignore-case)
  - File pattern filtering to limit search scope (-f/--file-pattern)
  - Context line display around matches (-C/--context)
  - Workspace-aware path resolution
  - Clean and structured output format

- **`neofind`** (NeoFindCommand): Locate files and directories:
  - Delegates to the system find command for efficient searching
  - Name pattern filtering (-n/--name)
  - File type filtering for files or directories (-t/--type)
  - Workspace-aware search paths for security
  - Comprehensive error handling and reporting

- **`bash`** (BashCommand): Execute arbitrary shell commands as a fallback:
  - Maintains a persistent shell session across command invocations
  - Captures both standard output and error streams
  - Exit code capture for proper error reporting
  - Graceful handling of shell termination and error conditions
  - Special handling for exit command
  - Workspace-aware execution environment
  - Should only be used when specialized commands are insufficient

- **`output`** (StructuredOutputCommand): Validate and structure command output data:
  - Used for outputting structured data in various formats
  - Supports raw text output for code snippets
  - Supports JSON schema validation for complex data structures
  - Provides examples in documentation for different output formats
  - Primarily designed for internal use by the LLM

The command architecture follows these design principles:
- **Command Pattern**: Each command implements:
  - A `template()` method that returns a CommandTemplate with parameters and documentation
  - A `process()` method that takes session/context, args, and optional data parameters
  - Returns a CommandResult with content, success status, and operation summary

The command framework also provides:
- **CommandParameter**: Dataclass for defining command parameters with validation
  - Support for required vs. optional parameters
  - Positional parameters and flag arguments (-f, --flag)
  - Default values and hidden parameter options

- **CommandTemplate**: Defines a command's structure and documentation
  - Generates formatted manual pages with NAME, SYNOPSIS, DESCRIPTION sections
  - Provides consistent OPTIONS and EXAMPLES documentation
  - Supports command data input via STDIN-like pipe syntax

- **CommandParser**: Handles parsing of command strings into structured arguments
  - Processes arguments based on parameter definitions
  - Handles quoted values and special characters
  - Separates command arguments from piped data
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

### Service Layer (src/neo/service/)

The Service layer provides a higher-level API for session management and persistent storage:

- **Service** (src/neo/service/service.py): Provides core service functionalities for session management and messaging
  - Creates and manages sessions with persistent state
  - Processes messages through the appropriate agent
  - Supports temporary and named sessions
  - Provides session listing and retrieval capabilities

- **SessionManager** (src/neo/service/session_manager.py): Manages session state persistence
  - Maps session names to session IDs
  - Tracks temporary and permanent sessions
  - Provides session creation, retrieval, and listing
  - Maintains last active session information

- **Database** (src/neo/service/database/): Implements persistent storage for sessions
  - Uses SQLite for storing session metadata
  - SessionRepository provides CRUD operations for sessions
  - Implements connection pooling with singleton pattern
  - Automatic schema creation and migration

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
