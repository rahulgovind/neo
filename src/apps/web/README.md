# Neo Web Chat

A web-based interface for Neo that implements the same functionality as the CLI-based chat system. This web application allows users to interact with the Neo agent through a modern web UI while maintaining all the capabilities of the command-line version.

## Features

- Browser-based chat interface with Neo agent
- Markdown rendering for chat messages
- Command execution and result display
- Persistent chat history using SQLite
- Multiple chat sessions management
- Responsive design for desktop and mobile

## Installation

1. Make sure you have Python 3.8+ installed
2. Install the required dependencies:

```bash
pip install -r requirements.txt
```

## Usage

To start the web application:

```bash
python app.py [--host HOST] [--port PORT] [--debug] [--workspace PATH]
```

Options:
- `--host`: Host to run the server on (default: 127.0.0.1)
- `--port`: Port to run the server on (default: 5000)
- `--debug`: Run in debug mode
- `--workspace`: Path to the workspace directory

## Architecture

The application uses:
- **Flask**: Web framework for serving the application
- **SQLite**: Database for storing chat history
- **Marked.js**: Client-side Markdown rendering
- **Highlight.js**: Code syntax highlighting

## Database Schema

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

## Technology Stack

- **Backend**: Python with Flask
- **Database**: SQLite
- **Frontend**: HTML, CSS, JavaScript
- **Libraries**: Marked.js, Highlight.js, Font Awesome

## Integration with Neo

This web application integrates with the existing Neo architecture:
- Uses the same `Agent` class for message processing
- Maintains compatibility with the command execution system
- Preserves the same interaction model but through a web interface
