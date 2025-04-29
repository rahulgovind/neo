# Apps Component

## Overview

The Apps component contains the user interface applications for Neo. It includes both the command-line interface (CLI) and web-based interface, providing users with different ways to interact with Neo's core functionality. These applications serve as the entry points for end users, connecting to the Service layer for session management and conversation processing.

## Key Components

### CLI Interface (`cli.py`)

The command-line interface for Neo:

- Provides an interactive terminal-based chat experience
- Processes command-line arguments for configuration
- Supports session management commands
- Displays formatted assistant responses
- Handles keyboard interrupts and graceful shutdown

```bash
# Basic usage
python -m src.apps.cli

# With workspace specification
python -m src.apps.cli --workspace /path/to/workspace
```

### Web Application (`web/`)

A browser-based interface for Neo:

- Modern web chat interface using Flask
- Real-time interaction with Neo
- Session management UI
- Markdown rendering for messages
- Responsive design for desktop and mobile use

More details in the [web application README](web/README.md).

## Features

### CLI Features

The command-line interface offers:

- **Interactive Sessions**: Continuous chat with Neo
- **Rich Text Formatting**: Using the Rich library for colored output
- **Command History**: Navigate through previous commands
- **Session Commands**: Create, switch between, and manage sessions
- **Special Commands**: Help, exit, and other utility operations
- **Configuration**: Command-line options for customization

### Web Features

The web interface provides:

- **Modern Chat UI**: Clean, responsive chat interface
- **Session Management**: Create and switch between sessions
- **Persistent Storage**: Chat history saved between visits
- **Markdown Support**: Rich text formatting with Markdown
- **Mobile Support**: Works on both desktop and mobile devices
- **Real-time Updates**: Immediate response display

## Integration Points

- **Service**: Both interfaces connect to the Service component
- **Agent**: Indirectly used through the Service for processing
- **Sessions**: Created and managed through the interfaces
- **Database**: Session persistence handled through the Service

## Usage Examples

### Using the CLI

```bash
# Start with default settings
python -m src.apps.cli

# Specify a workspace directory
python -m src.apps.cli --workspace ~/projects/mywork

# Special commands within CLI
/new my-session   # Create a new session
/list             # List available sessions
/switch session2  # Switch to another session
/clear            # Clear current conversation
/help             # Show help information
/exit             # Exit the application
```

### Using the Web Interface

```bash
# Start the web server
python -m src.apps.web.app

# With custom host and port
python -m src.apps.web.app --host 0.0.0.0 --port 5000

# In debug mode
python -m src.apps.web.app --debug
```

## Configuration

Both interfaces support various configuration options:

### CLI Options

- `--workspace`: Path to the workspace directory
- `--session`: Initial session name to use or create
- `--ephemeral`: Use a temporary session that won't be saved
- `--debug`: Enable debug logging

### Web Options

- `--host`: Host address to bind the server to
- `--port`: Port to run the server on
- `--debug`: Run in Flask debug mode
- `--workspace`: Default workspace path for new sessions

## Accessing Help

Both interfaces provide help information:

- CLI: Enter `/help` at the prompt
- Web: Click the help icon in the interface

## Future Considerations

- **Enhanced Terminal UI**: More interactive terminal features
- **Desktop Application**: Native desktop wrapper
- **Mobile Applications**: Native mobile clients
- **Authentication**: User authentication for web interface
- **Collaborative Features**: Multi-user support
