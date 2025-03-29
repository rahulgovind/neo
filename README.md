# Neo

Neo is an AI assistant designed to help with a wide range of tasks through both CLI and web interfaces.

## Components

### CLI Interface

The command-line interface provides an interactive terminal session to communicate with the AI agent, process user inputs, and execute commands.

### Web Interface

A browser-based chat interface that implements the same functionality as the CLI-based chat system. The web application allows users to interact with the Neo agent through a modern web UI while maintaining all the capabilities of the command-line version.

#### Web Features

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

### CLI

To start the CLI application:

```bash
python -m src.apps.cli [workspace]
```

### Web Interface

To start the web application:

```bash
python -m src.apps.web.app [--host HOST] [--port PORT] [--debug] [--workspace PATH]
```

Options:
- `--host`: Host to run the server on (default: 127.0.0.1)
- `--port`: Port to run the server on (default: 5000)
- `--debug`: Run in debug mode
- `--workspace`: Path to the workspace directory

## Architecture

The application is built with:

- **Core Components**:
  - `Agent`: Orchestrates conversations with an LLM and handles command invocations
  - `Model`: Abstraction for processing messages through an LLM
  - `Client`: Abstraction over LLM clients using the OpenAI API format
  - `Shell`: Command execution and processing

- **Web Application**:
  - **Flask**: Web framework for serving the application
  - **SQLite**: Database for storing chat history
  - **Marked.js**: Client-side Markdown rendering
  - **Highlight.js**: Code syntax highlighting

## Development

To run tests:

```bash
pytest
```

## Environment Variables

- `API_KEY`: OpenAI API key
- `API_URL`: (Optional) Custom API base URL
