# Web Application

## Overview

The Neo web application provides a browser-based interface for interacting with Neo. It offers a modern chat experience with session management, Markdown rendering, and a responsive design that works on both desktop and mobile devices.

## Key Components

### App (`app.py`)

The Flask application that serves the web interface:

- Defines API routes and view functions
- Manages the Neo service integration
- Handles session management via Flask sessions
- Provides real-time message processing

### Web Server

Built on Flask with additional components:

- HTTP server with websocket support
- JSON API endpoints for messaging
- Static file serving for frontend assets
- Session cookie management

### Frontend

Modern JavaScript application:

- **HTML Templates**: Jinja2 templates for page structure
- **CSS Styling**: Clean, responsive design
- **JavaScript**: Interactive chat functionality
- **Components**: Modular UI elements
- **Utilities**: Helper functions for UI operations

## Features

### Chat Interface

A rich, interactive chat experience:

- Real-time message display
- Markdown rendering for rich text
- Code syntax highlighting
- Command execution visualization
- Conversation history browsing

### Session Management

Comprehensive session handling:

- Create new chat sessions
- Switch between existing sessions
- Rename and delete sessions
- Session persistence across browser sessions
- Last active session restoration

### Responsive Design

Works on various devices and screen sizes:

- Mobile-friendly interface
- Desktop optimization
- Dynamic layout adjustments
- Touch and click interactions
- Accessible interface elements

## Directory Structure

```
src/apps/web/
├── app.py              # Flask application
├── launcher.py         # Entry point script
├── static/             # Static assets
│   ├── css/            # Stylesheets
│   │   └── style.css   # Main CSS file
│   ├── js/             # JavaScript
│   │   ├── chat.js     # Chat functionality
│   │   ├── components/ # UI components
│   │   └── utils/      # Helper functions
│   └── img/            # Images
└── templates/          # HTML templates
    ├── base.html       # Base template
    ├── index.html      # Main chat interface
    └── components/     # Reusable HTML components
```

## API Endpoints

The web application exposes these key endpoints:

- **`/`**: Main chat interface
- **`/api/sessions`**: List, create, and manage sessions
- **`/api/messages`**: Send and receive messages
- **`/api/message/<id>`**: Get specific message details
- **`/api/session/<id>`**: Get session details or switch sessions

## Integration Points

- **Service**: The web app uses the Neo service for core functionality
- **Agent**: Indirectly accessed through the service layer
- **Session**: Manages user sessions separate from Flask sessions
- **Database**: Accessed through the service layer for persistence

## Usage

Start the web server with the following command:

```bash
python -m src.apps.web.app [--host HOST] [--port PORT] [--debug] [--workspace PATH]
```

Options:
- `--host`: Host to run the server on (default: 127.0.0.1)
- `--port`: Port to run the server on (default: 8888)
- `--debug`: Run in debug mode
- `--workspace`: Path to the workspace directory

## Frontend Development

The frontend uses a modular JavaScript approach:

```javascript
// Example: Creating a new message component
function createMessageElement(message, role) {
    const msgElement = document.createElement('div');
    msgElement.className = `message ${role}`;
    
    const contentElement = document.createElement('div');
    contentElement.className = 'content';
    contentElement.innerHTML = marked.parse(message);
    
    msgElement.appendChild(contentElement);
    return msgElement;
}

// Example: Sending a message
async function sendMessage(content) {
    try {
        const response = await fetch('/api/messages', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                content: content,
                session_id: currentSessionId
            })
        });
        
        if (!response.ok) {
            throw new Error('Failed to send message');
        }
        
        const data = await response.json();
        return data;
    } catch (error) {
        console.error('Error sending message:', error);
        throw error;
    }
}
```

## Future Considerations

- **User Authentication**: Login system for multi-user support
- **Real-time Collaboration**: Shared sessions between users
- **Enhanced UI**: Additional visualization tools
- **File Upload**: Direct file upload capabilities
- **Theme Support**: Light and dark mode options
- **Notifications**: System for alerts and notifications
- **Export/Import**: Conversation export and import functionality
