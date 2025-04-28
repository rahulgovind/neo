# Service Component

## Overview

The Service component provides session management and persistence for Neo, serving as the bridge between the user interfaces (CLI, web) and the core functionality. It manages session lifecycle, message processing, and database interactions, allowing conversations to persist across multiple sessions.

## Key Components

### Service (`service.py`)

The high-level service API for Neo:

- Creates and manages sessions with persistent state
- Processes messages through the appropriate agent
- Provides a programming interface for application integration
- Handles ephemeral and persistent sessions

```python
service = Service()
session = service.get_or_create_session("my-session", workspace="/path/to/workspace")
response = service.process_message(session, "Hello, Neo!")
```

### SessionManager (`session_manager.py`)

Core implementation for session state management:

- Maps session names to unique session IDs
- Tracks temporary and permanent sessions
- Handles session creation, retrieval, and updates
- Maintains workspace association for sessions
- Manages the last active session information

### Database Layer (`database/`)

Implements persistent storage for sessions:

- Uses SQLite for session metadata and state
- Provides repository pattern implementation
- Manages database connections and schema
- Implements automatic schema creation

## Features

### Session Management

Comprehensive session lifecycle handling:

- Named sessions for organization and retrieval
- Unique session ID generation and tracking
- Workspace association for security boundaries
- Last active session tracking for convenience
- Session listing and enumeration

### Message Persistence

Maintains conversation history across application restarts:

- Saves message history in the database
- Loads existing conversations when resuming sessions
- Supports pruning and summarization for long-running sessions
- Efficient storage of message content

### Workspace Context

Associates sessions with specific workspaces:

- Each session operates within a defined workspace
- Enforces workspace boundaries for security
- Supports default workspace from configuration
- Maintains workspace association across restarts

### Database Integration

Clean database abstraction layer:

- Repository pattern for data access
- Connection pooling with singleton design
- Automatic schema migration
- Efficient query patterns for session data

## Integration Points

- **Agent**: Created and managed by the service
- **Session**: Central object managed by the service
- **User Interfaces**: Use the service as their entry point
- **Database**: Accessed through the repository layer

## Usage Example

```python
from src.neo.service import Service

# Initialize the service
service = Service()

# Create a new session or get an existing one
session = service.get_or_create_session(
    "project-research", 
    workspace="/path/to/project",
    ephemeral=False  # Persist this session
)

# Process a message through the session's agent
response = service.process_message(session, "What files are in this directory?")
print(response.text())

# List all available sessions
sessions = service.list_sessions()
for session_info in sessions:
    print(f"Session: {session_info.name}, Last active: {session_info.last_active}")

# Get the last active session
last_session = service.get_last_active_session()
if last_session:
    print(f"Last active session: {last_session.name}")
```

## Database Schema

The database includes these key tables:

1. **sessions**: Stores session metadata
   - `id`: Unique session identifier
   - `name`: User-friendly session name
   - `workspace`: Associated workspace path
   - `created_at`: Creation timestamp
   - `last_active`: Last activity timestamp

2. **session_state**: Stores serialized agent state
   - `session_id`: Associated session
   - `state`: Serialized agent state JSON
   - `updated_at`: Last update timestamp

## Testing Considerations

The Service layer requires special testing approaches:

- Setting NEO_HOME before importing modules
- Using unique database files for test isolation
- Managing environment variables for configuration
- Testing with both temporary and persistent sessions

## Future Considerations

- Enhanced session organization with tags and groups
- Improved session search and filtering
- Multi-user support with permission models
- Advanced workspace configuration options
