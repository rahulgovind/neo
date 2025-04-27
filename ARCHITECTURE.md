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

#### Client (src/neo/client/)

The Client component provides a robust abstraction over LLM services:

**Client** (`src/neo/client/client.py`):

- Orchestrates the communication flow with the LLM
- Preprocesses messages to ensure proper formatting
- Postprocesses responses to extract command calls and text blocks
- Performs command validation before execution
- Handles error recovery with feedback loops for invalid commands
- Transforms responses into structured Message objects with content blocks

**BaseClient** (`src/neo/client/base.py`):

- Core LLM API client implementation
- Handles API authentication and request management
- Implements comprehensive request/response logging with structured data
- Manages token counting and usage tracking
- Handles API-specific adaptations for different providers
- Implements error handling and retry logic

Key features:
- Uses OpenAI's Chat Completions API format for broad compatibility
- Supports structured metadata in requests and responses
- Implements automatic validation and retries for failed command calls
- Provides detailed logging of request/response pairs
- Manages conversation caching with ephemeral message control
- Supports structured output with validation

**BaseClient** (`src/neo/client/base.py`):

- Provides low-level communication with the LLM API
- Abstracts OpenAI-compatible API interactions
- Handles authentication and API configuration
- Implements comprehensive logging of requests and responses
- Calculates token usage and manages rate limits
- Includes error handling and retry logic

#### Client (src/neo/client/)

The Client component provides a robust abstraction over LLM API interactions:

**Client** (`src/neo/client/client.py`):
- Handles processing of messages to and from LLMs
- Validates command calls before execution
- Manages message preprocessing and response postprocessing
- Automatically corrects and retries invalid command calls
- Uses a structured logging system for tracking requests and responses

**BaseClient** (`src/neo/client/base.py`):
- Provides low-level communication with LLM APIs
- Implements OpenAI API format compatibility
- Performs token counting and usage tracking
- Includes detailed request/response logging
- Handles error conditions gracefully
- Supports configurable model selection

**Key Features**:
- **Unified API Format**: Works with both OpenAI and compatible API providers
- **Robust Error Handling**: Graceful recovery from API errors and malformed responses
- **Detailed Logging**: Comprehensive structured logging of all requests and responses
- **Token Usage Tracking**: Monitors token consumption for both prompts and completions
- **Command Validation**: Pre-validates command calls before execution to prevent errors

#### Model (src/core/model.py)

The Model component builds on the Client to provide higher-level LLM interaction:


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

#### Agent (src/neo/agent/)

The Agent component orchestrates the interaction between the user, Model, and Functions through a modular architecture:

**Agent** (`src/neo/agent/agent.py`):

- Core orchestration class that manages the conversation lifecycle
- Loads and provides system instructions and custom rules (from .neorules)
- Processes user messages and returns assistant responses
- Integrates with the session to persist conversation state
- Handles command execution through the Agent State Machine
- Supports both ephemeral (non-persistent) and persistent conversation modes

**AgentState** (`src/neo/agent/state.py`):

- Manages the conversation state with immutable data structures
- Stores system instructions and the message history
- Provides methods for adding messages and manipulating state
- Implements serialization logic for saving/loading conversation state
- Supports message pruning to manage context length
- Includes utilities for turn-based conversation management

**AgentStateMachine** (`src/neo/agent/asm.py`):

- Implements a stateless state machine for processing agent interactions
- Provides the primary stepping logic for advancing conversations
- Manages command execution flow and result handling
- Creates intelligent checkpoints to summarize conversation history
- Implements state pruning to handle long conversations
- Uses configurable thresholds for checkpoint intervals and pruning

**Key Features**:

- **Hierarchical Memory Management**: Implements a sophisticated approach to context retention:
  - Automatic checkpointing of conversations at configurable intervals
  - Generation of conversation summaries to preserve context
  - Smart pruning of older messages while maintaining coherence
  - Configurable thresholds for managing context window size

- **Stateless Processing**: The state machine provides a clean, functional approach to state transitions
- **Immutable State**: All state operations return new state objects rather than modifying existing state
- **Conversation Persistence**: Optional saving and loading of conversations across sessions

#### Service (src/neo/service/)

The Service component provides persistence and session management:

**Service** (`src/neo/service/service.py`):
- Provides high-level API for session and message processing
- Supports both persistent and temporary sessions
- Manages session creation, retrieval, and updates
- Serves as the entry point for non-interactive applications
- Handles workspace configuration for sessions

**SessionManager** (`src/neo/service/session_manager.py`):
- Implements core session management functionality
- Maps session names to unique session IDs
- Tracks session state and persistence
- Manages database interactions through repositories
- Provides functionality for session listing and retrieval

**Database Layer** (`src/neo/service/database/`):
- Uses SQLite for persistent storage of session metadata
- Implements repository pattern for data access
- Manages session state persistence
- Tracks last active session information

**Key Features**:
- **Persistent Sessions**: Allows conversations to continue across application restarts
- **Session Naming**: Users can create named sessions for better organization
- **Workspace Association**: Sessions can be associated with specific filesystem workspaces
- **Last Active Tracking**: Automatically tracks and restores the last active session

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

The Service Layer provides persistent session management and a programming interface for Neo:

**Service** (`src/neo/service/service.py`):

- Provides the primary API for programmatic interaction with Neo
- Exposes methods for session creation, retrieval and messaging
- Manages messaging workflow for non-interactive components
- Handles ephemeral and persistent session states
- Abstracts the session management complexity for API consumers

**SessionManager** (`src/neo/service/session_manager.py`):

- Core implementation for session state management
- Manages session creation, retrieval, and updates
- Handles session persistence through the database layer
- Tracks temporary and permanent sessions
- Provides access to last active and recently created sessions
- Implements session workspace configuration

**Database** (`src/neo/service/database/`):

- Implements SQLite-based persistence for sessions
- Provides repositories for session data access
- Manages database connections and schema
- Implements data models for session state

Key features:
- Separation of API, business logic, and data access layers
- Support for both temporary and persistent sessions
- Workspace-aware session management
- Unique session identification with names and IDs
- Database-backed session persistence
- Enables seamless interaction with both temporary and persistent sessions
- Abstracts away implementation details for application integrations

**SessionManager** (`src/neo/service/session_manager.py`):

- Manages the lifecycle of sessions in the application
- Provides session creation, retrieval and update operations
- Handles persistence through the repository pattern
- Tracks and manages temporary vs. permanent sessions
- Maintains session state across application restarts

**Database** (`src/neo/service/database/`):

- Implements repository pattern for session persistence
- Uses SQLite for efficient local data storage
- Provides data models for session state
- Manages connection pooling and database operations
- Enables scalable, persistent session tracking

The Service Layer is designed to support both CLI and potential web/API interfaces, providing a consistent programming model regardless of the interface being used.

**Testing the Service Layer**:

Testing the Service layer requires special considerations due to:
- Global state in the NEO_HOME variable defined at import time
- Database connections established when modules are imported
- Session IDs based on timestamps with potential for conflicts in test suites

We've implemented two testing strategies:
- Traditional unit tests with setUp/tearDown for normal isolation
- A standalone isolated script that guarantees complete isolation by setting environment variables before any imports

Key insights for testing this layer:
- NEO_HOME must be set before importing any Neo-related modules for true isolation
- Each test should use a unique database file to avoid conflicts
- The Service.list_sessions() method returns List[SessionInfo], which has been fixed to match its implementation 
- Comprehensive test coverage uses real (non-mocked) objects for higher fidelity




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

#### 1. Utilities (src/neo/utils/)

Neo includes utility components that provide core functionality used across the application:

**Clock** (`src/neo/utils/clock.py`): Provides time-related operations and abstractions
- Abstract `Clock` interface defines a consistent API for time operations
- `RealTimeClock` implementation uses actual system time
- `FakeClock` implementation simulates time passage for testing
  - Allows advancing time without waiting for real time to pass
  - Supports concurrent testing with thread synchronization
  - Includes utilities for test coordination with `await_sleeps`

#### 2. Web Application (src/apps/web/)

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
