# Neo Web Application API Reference

This document serves as a reference for the backend Flask API endpoints available in the Neo Web application.

## Session Management

### Get Latest Session or Create New
- **Endpoint**: `/` (index)
- **Method**: GET
- **Description**: Renders the main chat interface with the latest session. If no session exists in cookie, it finds the latest session or creates a new one.
- **Response**: Renders the index.html template

### List All Sessions
- **Endpoint**: `/sessions`
- **Method**: GET
- **Description**: Renders the sessions page showing all available chat sessions.
- **Response**: Renders the sessions.html template

### Get Sessions (API)
- **Endpoint**: `/api/sessions`
- **Method**: GET
- **Description**: API endpoint to get all sessions for the sidebar.
- **Response**: JSON array of session objects

### View Specific Session
- **Endpoint**: `/session/<session_id>`
- **Method**: GET
- **Description**: Renders the chat interface for a specific session by ID.
- **Response**: Renders the index.html template with the specified session active

### Create New Session
- **Endpoint**: `/new_session`
- **Method**: GET
- **Description**: Creates a new session.
- **Response**: Redirects to the index page

## Chat Functionality

### Get Chat History (Current Session)
- **Endpoint**: `/api/history`
- **Method**: GET
- **Description**: API endpoint to get chat history for the current session (from the session cookie).
- **Response**: JSON array of message objects with format:
  ```json
  [
    {
      "id": "message_id",
      "session_id": "session_id",
      "timestamp": "ISO timestamp",
      "role": "user|assistant",
      "content": "Message content"
    }
  ]
  ```

### Get Chat History (Specific Session)
- **Endpoint**: `/api/history/<session_id>`
- **Method**: GET
- **Description**: API endpoint to get chat history for a specific session by ID.
- **Response**: JSON array of message objects with the same format as above

### Get Latest Session
- **Endpoint**: `/api/latest_session`
- **Method**: GET
- **Description**: API endpoint to get the most recent session if one exists.
- **Response**: JSON object with session information:
  ```json
  {
    "session_id": "session_id",
    "name": "Session name",
    "timestamp": "ISO timestamp"
  }
  ```
- **Error Response**: 404 status with error message if no sessions exist

### Send Message
- **Endpoint**: `/api/chat`
- **Method**: POST
- **Description**: API endpoint to send a message and get a response.
- **Request Body**:
  ```json
  {
    "message": "User message content",
    "session_id": "Optional session ID" 
  }
  ```
- **Response**: JSON object with the assistant's response:
  ```json
  {
    "response": "Assistant response content",
    "session_id": "Session ID used for this message"
  }
  ```

## Log Management

### View Logs
- **Endpoint**: `/logs`
- **Method**: GET
- **Description**: Renders the logs page showing available log files.
- **Response**: Renders the logs.html template

### View Specific Log
- **Endpoint**: `/logs/<logger_name>`
- **Method**: GET
- **Description**: Renders a specific log file.
- **Response**: Renders the log content

## Important Implementation Details

### Message Structure
- Messages in the frontend are structured as:
  ```typescript
  interface Message {
    id: string;
    role: 'user' | 'assistant';
    content: string;
    timestamp: string;
    session_id?: string; // Added for cross-session support
  }
  ```

### Database Mapping
- The backend stores messages in SQLite with the following fields:
  - `id`: Message ID
  - `session_id`: Session ID
  - `timestamp`: ISO timestamp
  - `role`: "user" or "assistant"
  - `message`: Message content

### Field Mapping
- Note that the backend and frontend use slightly different field names:
  - Backend: `message` → Frontend: `content`
  - API endpoints automatically handle this transformation for compatibility

### Timestamp Display Logic
- Timestamps are shown only for user messages
- A timestamp is shown only when it's been more than 15 minutes since the previous message or when it's the first message
