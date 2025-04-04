# Neo Project

## Overview
This is the Neo project workspace. Neo is an AI assistant designed to help users with a wide range of tasks by understanding requirements, providing information, and engaging in thoughtful conversation. Neo offers both CLI and web-based interfaces for user interaction.

## Features
- Understands user requirements and questions
- Provides relevant information and explanations
- Engages in thoughtful conversation
- Can work with files in the workspace
- Multiple interface options (CLI and web-based)
- Persistent chat history across sessions
- Support for multiple concurrent chat sessions
- Session management and browsing

## Usage
Neo can assist you with various tasks in this workspace, including:
- Reading and writing files
- Searching for information
- Updating existing files
- Finding files and directories

### CLI Interface
You can interact with Neo through the command-line interface:

```bash
python -m src.apps.cli [--workspace PATH]
```

### Web Interface
Neo also provides a modern web-based chat interface:

```bash
python -m src.apps.web.app [--host HOST] [--port PORT] [--debug] [--workspace PATH]
```

Options:
- `--host`: Host to run the server on (default: 127.0.0.1)
- `--port`: Port to run the server on (default: 8888)
- `--debug`: Run in debug mode
- `--workspace`: Path to the workspace directory

## Available Commands
Neo can execute the following commands:
- `read_file`: Read and display file contents
- `write_file`: Create a new file or overwrite an existing file
- `update_file`: Update a file using a diff structure
- `grep`: Search for a pattern in files or directories
- `find`: Find files and directories matching specified criteria

## Working Directory
The current working directory is: `/Users/rahulgovind/neo-workdir`

## Project Structure
The Neo project is organized into the following components:

- `src/agent`: Core agent functionality for processing user inputs
- `src/core`: Core components including command handling, context management, and models
- `src/core/commands`: Implementation of individual commands (read_file, write_file, etc.)
- `src/apps`: Application interfaces (CLI and web)
- `src/apps/web`: Web-based interface using Flask
- `src/database`: Database components for persistent storage
- `src/utils`: Utility functions and helpers
- `src/logging`: Structured logging facilities
- `tests`: Test suite for all components

## Best Practices
- Neo explains reasoning and offers context before making command calls
- Changes to files are made incrementally and focused rather than complete rewrites
- Interactions are helpful, accurate, and respectful

## Technical Details

### Agent Architecture
The Neo agent uses a structured approach to process user inputs:
- Maintains conversation state with message history
- Executes commands on behalf of the user when needed
- Handles context management for workspace operations

### Web Interface
The web application features:
- Browser-based chat interface with Neo agent
- Markdown rendering for chat messages
- Command execution and result display
- Persistent chat history using SQLite
- Multiple chat sessions management
- Responsive design for desktop and mobile

### Database Schema
The database includes two main tables:
1. **sessions**: Stores chat session information
   - `id`: Unique session identifier
   - `workspace`: Associated workspace path
   - `created_at`: Creation timestamp
   - `last_active`: Last activity timestamp

2. **messages**: Stores individual messages
   - `id`: Message identifier
   - `session_id`: Associated session
   - `role`: Message sender (user/assistant)
   - `content`: Message content
   - `timestamp`: Message timestamp

## License
[Insert license information here]

## Requirements
- Python 3.8+
- Flask (for web interface)
- Rich (for CLI interface)
- SQLite (for persistent storage)

## Contributors
[Insert contributor information here]
