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
┌─────────────────┐     ┌─────────────────┐
│      CLI        │     │      Web        │  Application entry points
└────────┬────────┘     └────────┬────────┘
         │                       │
         └───────────┬───────────┘
                     │
                     ▼
┌─────────────────────────────────┐
│           Service               │  Session management and persistence
└────────────────┬────────────────┘
                 │
                 ▼
┌─────────────────────────────────┐
│            Agent                │  Orchestrates conversation and commands
└────────┬──────────────┬─────────┘
         │              │
         ▼              ▼
┌─────────────┐  ┌─────────────────┐
│   Client    │  │      Shell      │
└──────┬──────┘  └────────┬────────┘
       │                  │
       ▼                  ▼
┌─────────────┐  ┌─────────────────┐
│    LLM      │  │    Commands     │
└─────────────┘  └─────────────────┘
                        │
                        ▼
              ┌─────────────────────┐
              │  Message Structure  │  Content blocks for different data types
              └─────────────────────┘
```

### Key Components

#### Client (src/neo/client/)

The Client component provides a robust abstraction over LLM API interactions:

**Client** (`src/neo/client/client.py`):
- Handles processing of messages to and from LLMs
- Validates command calls before execution
- Manages message preprocessing and response postprocessing
- Automatically corrects and retries invalid command calls

**BaseClient** (`src/neo/client/base.py`):
- Provides low-level communication with LLM APIs
- Implements OpenAI API format compatibility
- Performs token counting and usage tracking
- Handles authentication and request/response management

**Key Features**:
- **Unified API Format**: Works with both OpenAI and compatible API providers
- **Robust Error Handling**: Graceful recovery from API errors and malformed responses
- **Detailed Logging**: Comprehensive structured logging of all requests and responses
- **Token Usage Tracking**: Monitors token consumption for both prompts and completions
- **Command Validation**: Pre-validates command calls before execution to prevent errors

#### Message Structure (src/neo/core/messages.py)

Neo uses a sophisticated message structure to handle different content types and conversation flows:

**Message** class:
- Container for conversation messages (user, assistant, system)
- Supports rich content through various `ContentBlock` types
- Handles metadata for message processing and caching
- Provides serialization/deserialization for persistence

**ContentBlock** implementations:
- **TextBlock**: Plain text content for normal conversation
- **CommandCall**: Represents command execution requests
- **CommandResult**: Contains command execution results with success/failure status
- **StructuredOutput**: Formatted, schema-validated output data

**Key Features**:
- Support for mixed content types in a single message
- Special handling for system-level communications
- Command execution parsing and processing
- Error handling and recovery mechanisms


#### Shell (src/neo/shell/)

The Shell component manages command execution and validation:

**Shell** (`src/neo/shell/shell.py`):
- Maintains registry of available commands
- Processes and validates command calls
- Handles command execution and result formatting
- Provides command documentation through describe() method
- Manages persistent shell sessions for terminal operations

#### Commands (src/neo/commands/)

Neo implements a consistent command framework for interacting with the file system and other resources:

**Command Framework**:
- Base `Command` class provides a unified interface with CLI-like syntax
- Declarative parameter definitions with validation (positional and flag arguments)
- Structured error handling and reporting
- Command execution returns CommandResult with success status and content
- Rich documentation with usage examples for each command

**File Operations**:
- **`read_file`**: Read file contents with line selection and formatting options
- **`write_file`**: Create or overwrite files with automatic directory creation
- **`update_file`**: Apply structured diffs with @UPDATE/@DELETE operations

**Search Operations**:
- **`file_text_search`**: Search file contents with pattern matching and context display
- **`file_path_search`**: Find files based on patterns, types, and content filters

**Shell Operations**:
- **`shell_run`**: Execute shell commands in managed environment
- **`shell_view`**: Access shell output from previous commands
- **`shell_write`**: Send input to active shell processes

**Utility Commands**:
- **`wait`**: Sleep for specified duration using session clock
- **`output`**: Format structured data in various output formats

**Design Principles**:
- **Workspace Security**: All file operations are workspace-aware for security
- **Command Pattern**: Consistent interface with template() and process() methods
- **Rich Feedback**: Detailed success/error information and operation statistics
- **Composability**: Commands can be combined through the Agent for complex operations

#### Agent (src/neo/agent/)

The Agent component orchestrates conversations and command execution:

**Core Components**:
- **Agent** (`src/neo/agent/agent.py`): Conversation lifecycle manager that:
  - Loads system instructions and custom rules (.neorules)
  - Processes user messages through the state machine
  - Supports both ephemeral and persistent conversation modes

- **AgentState** (`src/neo/agent/state.py`): Immutable conversation state container that:
  - Manages message history with functional update patterns
  - Provides serialization for persistence
  - Supports turn-based conversation structures

- **AgentStateMachine** (`src/neo/agent/asm.py`): Stateless processor that:
  - Advances conversation with step() method
  - Creates intelligent checkpoints for context summarization
  - Prunes older messages to manage context length
  - Handles command execution flow and results

**Key Features**:
- **Hierarchical Memory Management**: Sophisticated context retention with automatic checkpointing
- **Stateless Processing**: Clean, functional approach to state transitions
- **Immutable State**: State operations return new objects rather than modifying existing state
- **Conversation Persistence**: Optional saving/loading of conversations across sessions
- **Custom Rules**: Support for project-specific customization via .neorules files

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

**Interface Enhancements**:
- IDE Integration: Plugins for VSCode, JetBrains, and other popular editors
- Collaborative Features: Multi-user support with shared sessions

**Core Functionality**:
- Enhanced File Diffing: Better visualization and application of complex changes
- Version Control Integration: Direct Git integration for change tracking
- Advanced Checkpoint Management: More sophisticated conversation summarization

**Architecture Extensions**:
- Project Templates: Support for project-specific configurations
- Command Framework Extensions: Specialized commands for additional operations
- Message Structure Extensions: Support for rich content types (charts, diagrams)

### Service Layer (src/neo/service/)

The Service Layer provides persistent session management and a programming interface for Neo:

**Service** (`src/neo/service/service.py`):
- Provides the primary API for programmatic interaction with Neo
- Exposes methods for session creation, retrieval and messaging
- Processes messages through the appropriate agent
- Supports both ephemeral and persistent session states

**SessionManager** (`src/neo/service/session_manager.py`):
- Core implementation for session state management
- Maps session names to unique session IDs
- Tracks temporary and permanent sessions
- Maintains last active session information
- Handles workspace configuration for sessions

**Database** (`src/neo/service/database/`):
- Implements SQLite-based persistence for sessions
- Provides repositories for session data access
- Manages database connections and schema
- Automatic schema creation and migration

**Key Features**:
- Supports both CLI and web/API interfaces with consistent programming model
- Workspace-aware session management with security boundaries
- Database-backed session persistence for continuous conversations
- Unique session identification with names and IDs

**Testing Considerations**:
- Special handling for NEO_HOME global state
- Isolation techniques for database connections
- Strategies for timestamp-based session ID conflicts

### Additional Components

**Utilities** (src/neo/utils/):
- **Clock** (`src/neo/utils/clock.py`): Time-related operations with two implementations:
  - `RealTimeClock`: Wraps Python's time module for production use
  - `FakeClock`: Simulates time passage for deterministic testing

**Web Application** (src/apps/web/):
- Provides browser-based interface as alternative to CLI
- Shares core functionality with CLI through Service Layer

**Structured Logging** (src/logging/):
- Implements detailed, structured logging for requests and operations
- Enables analysis of model performance and application behavior
