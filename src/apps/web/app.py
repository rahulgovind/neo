"""
Web application for Neo that provides a web interface to the chat system.
"""

import os
import sys
import logging
import json
import datetime
import uuid
import yaml
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple

from flask import (
    Flask,
    render_template,
    request,
    jsonify,
    session,
    redirect,
    url_for,
    abort,
)

from src.neo.session import Session
from src.neo.agent.agent import Agent
from src.neo.shell.shell import Shell
from src.neo.core.messages import Message, TextBlock
from src.neo.service.service import Service
from src.database.database import Database  # Kept temporarily for migration to Service
from src import NEO_HOME

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# Create Flask app
app = Flask(__name__)
app.secret_key = os.urandom(24)  # For session management
app.config["SESSION_TYPE"] = "filesystem"
app.config["SESSION_PERMANENT"] = True
app.config["PERMANENT_SESSION_LIFETIME"] = datetime.timedelta(days=7)

# Default system instructions for the agent
DEFAULT_INSTRUCTIONS = """
You are Neo, an AI assistant that can help with a wide range of tasks.

You can assist users by:
1. Understanding their requirements and questions
2. Providing relevant information and explanations
3. Engaging in thoughtful conversation

- You SHOULD explain your reasoning clearly and offer context for your suggestions. Do this prior to making any command calls.
- You MUST not write anything after a command call.
- YOU SHOULD make incremental, focused changes when modifying files rather than rewriting everything.

Be helpful, accurate, and respectful in your interactions.
"""


class WebChat:
    """Interface between the web application and Agent."""

    def __init__(self, workspace: str, db_path: str):
        """
        Initialize the WebChat interface.

        Args:
            workspace: Path to the code workspace
            db_path: Path to the SQLite database file (kept for backwards compatibility)
        """
        self.workspace = workspace
        # Database is no longer directly used, will use Service class instead
        self._model_name = None
        self._agent_cache: Dict[str, Agent] = {}

    def _get_agent(self, session_id: str) -> Agent:
        """
        Get or create an Agent for the given session ID.

        Args:
            session_id: Session identifier

        Returns:
            Agent instance for the session
        """
        # Note: This method should be called from within a Context block

        if session_id not in self._agent_cache:
            # Create a session first
            session = Session.builder()\
                .session_id(session_id)\
                .workspace(self.workspace)\
                .initialize()
            
            # Create agent with the session
            agent = Agent(
                session=session, 
                ephemeral=True
            )
            self._agent_cache[session_id] = agent

            # Note: We don't need to load message history as Agent should be interacted with
            # only via the process method

        return self._agent_cache[session_id]

    def process_message(self, session_id: str, message: str) -> str:
        """
        Process a user message and get a response from the agent.

        Args:
            session_id: Session identifier
            message: User message to process

        Returns:
            Response from the agent
        """
        # Process the message
        try:
            # Get session info using Service
            session_info = Service.get_session(session_id)
            
            # If session doesn't exist, create it
            if not session_info:
                logger.info("Session %s not found, creating it", session_id)
                Service.create_session(session_name=session_id, workspace=self.workspace)
            
            # Get the agent for this session
            agent = self._get_agent(session_id)
            
            # Process the message
            response = agent.process(message)
            
            # Store messages in database through fallback mechanism
            # This is needed until messages are properly managed through Service
            from src.database.database import Database
            db = Database()
            db.add_message(session_id, "user", message)
            db.add_message(session_id, "assistant", response)
            
            return response
        except Exception as e:
            logger.error("Error in process_message: %s", str(e), exc_info=True)
            raise

    def get_chat_history(self, session_id: str) -> List[Dict[str, Any]]:
        """
        Get the chat history for a session.

        Args:
            session_id: Session identifier

        Returns:
            List of message dictionaries
        """
        try:
            logger.debug(f"Starting get_chat_history for session {session_id}")

            # Check if the session exists using the Service
            logger.debug(f"Checking if session {session_id} exists")
            session_info = Service.get_session(session_id)

            if not session_info:
                logger.warning(
                    f"Attempted to get history for non-existent session: {session_id}"
                )
                return []

            logger.debug(f"Session {session_id} exists, proceeding to get messages")

            try:
                # Use Service.history to get messages
                messages = Service.history(session_id=session_id, limit=100)
                logger.debug(f"Retrieved {len(messages)} messages for session {session_id}")
                return messages
            except Exception as e:
                logger.error(f"Error retrieving messages for session {session_id}: {str(e)}")
                logger.debug("Falling back to direct database access")
                import traceback
                logger.debug(f"Error traceback: {traceback.format_exc()}")

                # Fallback to direct database access if Service method fails
                from src.database.database import Database
                db = Database()
                messages = db.get_session_messages(session_id)
                logger.debug(
                    f"Retrieved {len(messages)} messages for session {session_id} using fallback"
                )
                return messages
        except Exception as e:
            logger.error(
                f"Error retrieving chat history for session {session_id}: {str(e)}"
            )
            import traceback
            logger.error(f"History retrieval error traceback: {traceback.format_exc()}")
            return []

    def get_sessions(self) -> List[Dict[str, Any]]:
        """
        Get list of recent sessions.

        Returns:
            List of session dictionaries
        """
        try:
            # Use the Service class to list sessions
            sessions_info = Service.list_sessions()
            
            # Convert SessionInfo objects to dictionaries
            sessions = [
                {
                    "session_id": s.session_id,
                    "session_name": s.session_name,
                    "workspace": s.workspace,
                    "created_at": "",  # These fields aren't available in SessionInfo
                    "updated_at": "",  # but are expected by the web interface
                    "description": s.session_name  # Use name as description for now
                }
                for s in sessions_info
            ]
            
            return sessions
        except Exception as e:
            logger.error(f"Error getting sessions: {str(e)}", exc_info=True)
            # Fallback to direct database access
            from src.database.database import Database
            db = Database()
            return db.get_sessions()


# Initialize WebChat with cwd as workspace
web_chat = WebChat(workspace=os.path.abspath("."), db_path=None)


@app.route("/")
def index():
    """Render the main chat interface with the latest session."""
    if "session_id" not in session:
        # Try to get the latest session
        latest_session = Service.get_last_active_session()

        if latest_session is not None:
            # Use the latest session
            session["session_id"] = latest_session["session_id"]
            logger.info(f"Using latest session: {latest_session['session_id']}")
        else:
            # Create a new session if no previous sessions exist
            new_session_id = str(uuid.uuid4())
            session["session_id"] = new_session_id
            Service.create_session(session_name=new_session_id, workspace=web_chat.workspace)
            logger.info("Created new session: %s", session["session_id"])

    return render_template("index.html")


@app.route("/sessions")
def sessions():
    """Render the sessions page."""
    sessions_list = web_chat.get_sessions()
    return render_template("sessions.html", sessions=sessions_list)


@app.route("/api/sessions")
def api_sessions():
    """API endpoint to get all sessions for the sidebar."""
    sessions_list = web_chat.get_sessions()
    return jsonify(sessions_list)


@app.route("/session/<session_id>")
def session_view(session_id):
    """View a specific session page."""
    # Set the session ID in the cookie
    session["session_id"] = session_id
    logger.info(f"Viewing session {session_id}")
    return render_template("index.html", session_id=session_id)


@app.route("/logs")
def logs():
    """Render the logs page showing available log files."""
    if "session_id" not in session:
        return redirect(url_for("index"))

    session_id = session["session_id"]
    
    # Simply get log files without a context
    log_files = _get_log_files(session_id)

    return render_template("logs.html", log_files=log_files, session_id=session_id)


@app.route("/logs/<logger_name>")
def view_log(logger_name):
    """Render a specific log file."""
    if "session_id" not in session:
        return redirect(url_for("index"))

    session_id = session["session_id"]
    
    # Get log entries without a session context
    log_entries = _get_log_entries(session_id, logger_name)

    return render_template(
        "log_detail.html",
        log_entries=log_entries,
        logger_name=logger_name,
        session_id=session_id,
    )


def _get_log_files(session_id: str) -> List[Dict[str, Any]]:
    """Get list of log files for a session.

    Args:
        session_id: Session identifier

    Returns:
        List of log file information dictionaries
    """
    log_dir = Path(NEO_HOME) / f"session-{session_id}"
    if not log_dir.exists():
        return []

    log_files = []
    for file_path in log_dir.glob("*.yaml"):
        stats = file_path.stat()
        log_files.append(
            {
                "name": file_path.stem,  # filename without extension
                "path": str(file_path),
                "size": stats.st_size,
                "modified": datetime.datetime.fromtimestamp(stats.st_mtime).isoformat(),
            }
        )

    # Sort by modification time (newest first)
    log_files.sort(key=lambda x: x["modified"], reverse=True)
    return log_files


def _get_log_entries(session_id: str, logger_name: str) -> List[Dict[str, Any]]:
    """Get log entries from a specific log file.

    Args:
        session_id: Session identifier
        logger_name: Name of the logger (filename without extension)

    Returns:
        List of log entry dictionaries
    """
    import os

    # Match path construction logic in StructuredLogger._initialize
    log_file = (
        Path(os.path.expanduser("~"))
        / ".neo"
        / f"session-{session_id}"
        / f"{logger_name}.yaml"
    )
    if not log_file.exists():
        return []

    try:
        # Read the file content
        with open(log_file, "r", encoding="utf-8") as f:
            content = f.read()

        # Split the content into YAML documents
        documents = content.split("---")

        # Parse each document as YAML
        entries = []
        for doc in documents:
            if doc.strip():
                # Skip the header comment if present
                if doc.strip().startswith("#"):
                    doc = "\n".join(doc.split("\n")[1:])

                try:
                    entry = yaml.safe_load(doc)
                    if entry and isinstance(entry, dict):
                        entries.append(entry)
                except yaml.YAMLError as e:
                    logger.error(f"Error parsing YAML document: {e}")
        return entries
    except Exception as e:
        logger.error(f"Error reading log file {log_file}: {e}")
        return []


@app.route("/new_session")
def new_session():
    """Create a new session."""
    new_session_id = str(uuid.uuid4())
    session["session_id"] = new_session_id
    Service.create_session(session_name=new_session_id, workspace=web_chat.workspace)
    logger.info("Created new session: %s", new_session_id)
    return redirect(url_for("index"))


@app.route("/api/history")
def get_history():
    """API endpoint to get chat history for the current session."""
    if "session_id" not in session:
        logger.warning("No session_id in session, returning empty history")
        return jsonify([])

    session_id = session["session_id"]
    logger.info(f"Fetching chat history for current session {session_id}")

    try:
        # Get the history
        history = web_chat.get_chat_history(session_id)
        logger.info(f"Retrieved {len(history)} messages for session {session_id}")

        # Transform message fields for frontend compatibility
        transformed_history = []
        for msg in history:
            transformed_msg = {
                "id": msg["id"],
                "role": msg["role"],
                "content": msg["message"],  # Rename message to content
                "timestamp": msg["timestamp"],
                "session_id": msg["session_id"],
            }
            transformed_history.append(transformed_msg)

        logger.info(f"Transformed {len(transformed_history)} messages for frontend")
        if transformed_history:
            logger.info(f"First transformed message sample: {transformed_history[0]}")

        return jsonify(transformed_history)
    except Exception as e:
        error_details = f"Error loading chat history for session {session_id}: {str(e)}"
        logger.error(error_details)
        import traceback

        logger.error(f"Traceback: {traceback.format_exc()}")

        # Return detailed error information to help with debugging
        return (
            jsonify(
                {
                    "error": "Failed to load chat history",
                    "details": str(e),
                    "session_id": session_id,
                }
            ),
            500,
        )


@app.route("/api/history/<session_id>")
def get_session_history(session_id):
    """API endpoint to get chat history for a specific session."""
    logger.info(f"Fetching chat history for specific session {session_id}")

    try:
        # Check if the session exists
        session_info = Service.get_session(session_id)
        if not session_info:
            logger.warning("Session %s not found", session_id)
            logger.warning(f"Session {session_id} not found in database sessions list")
            return jsonify([]), 404

        # Get the history
        history = web_chat.get_chat_history(session_id)
        logger.info(f"Retrieved {len(history)} messages for session {session_id}")

        # Transform message fields for frontend compatibility
        transformed_history = []
        for msg in history:
            transformed_msg = {
                "id": msg["id"],
                "role": msg["role"],
                "content": msg["message"],  # Rename message to content
                "timestamp": msg["timestamp"],
                "session_id": msg["session_id"],
            }
            transformed_history.append(transformed_msg)

        return jsonify(transformed_history)
    except Exception as e:
        error_details = f"Error loading chat history for session {session_id}: {str(e)}"
        logger.error(error_details)
        import traceback

        logger.error(f"Traceback: {traceback.format_exc()}")

        # Return detailed error information to help with debugging
        return (
            jsonify(
                {
                    "error": "Failed to load chat history",
                    "details": str(e),
                    "session_id": session_id,
                }
            ),
            500,
        )


@app.route("/api/latest_session")
def get_latest_session():
    """API endpoint to get the latest session if one exists."""
    try:
        # Try to get the latest session
        latest_session_info = Service.get_last_active_session()
        
        # Convert SessionInfo to dictionary format expected by frontend
        latest_session = None
        if latest_session_info:
            latest_session = {
                "session_id": latest_session_info.session_id,
                "session_name": latest_session_info.session_name,
                "workspace": latest_session_info.workspace,
                "created_at": "", 
                "updated_at": "",
                "description": latest_session_info.session_name
            }

        if latest_session is not None:
            logger.info(f"Found latest session: {latest_session['session_id']}")
            return jsonify(latest_session)
        else:
            logger.info("No sessions found")
            return jsonify({"error": "No sessions found"}), 404
    except Exception as e:
        error_details = f"Error getting latest session: {str(e)}"
        logger.error(error_details)
        import traceback

        logger.error(f"Traceback: {traceback.format_exc()}")

        return (
            jsonify({"error": "Failed to get latest session", "details": str(e)}),
            500,
        )


@app.route("/api/chat", methods=["POST"])
def chat():
    """API endpoint to send a message and get a response."""
    data = request.json
    user_message = data.get("message", "")
    session_id = data.get("session_id", None)

    # If no session_id provided in request, use the one from session cookie or create new
    if not session_id:
        if "session_id" not in session:
            session_id = str(uuid.uuid4())
            session["session_id"] = session_id
            Service.create_session(session_name=session_id, workspace=web_chat.workspace)
            logger.info("Created new session: %s", session_id)
        else:
            session_id = session["session_id"]
            logger.info(f"Using session from cookie: {session_id}")
    else:
        # If session_id was provided in request, update the session cookie
        session["session_id"] = session_id
        logger.info(f"Using session from request: {session_id}")

    if not user_message.strip():
        return jsonify({"error": "Message cannot be empty"}), 400

    try:
        # Process the message without a Session context manager
        response = web_chat.process_message(session_id, user_message)
        return jsonify({"response": response, "session_id": session_id})
    except Exception as e:
        logger.error("Error processing message: %s", str(e), exc_info=True)
        return jsonify({"error": str(e)}), 500


def main():
    """Main entry point for the web application."""
    import argparse
    import random
    import datetime

    parser = argparse.ArgumentParser(description="Neo Web Chat")
    parser.add_argument("--host", default="127.0.0.1", help="Host to run the server on")
    parser.add_argument(
        "--port", type=int, default=8888, help="Port to run the server on"
    )
    parser.add_argument("--debug", action="store_true", help="Run in debug mode")
    parser.add_argument("--workspace", help="Path to workspace")

    args = parser.parse_args()

    # Process workspace path if provided
    if args.workspace:
        workspace_path = os.path.abspath(os.path.expanduser(args.workspace))
        if not os.path.isdir(workspace_path):
            print(f"Error: Workspace directory does not exist: {workspace_path}")
            sys.exit(1)
        web_chat.workspace = workspace_path

    # The shell and model are now initialized by the Session
    # These are no longer needed as we access them through
    # the WebChat class which creates properly configured sessions

    # Commented out legacy code
    # shell = Shell() 
    # model = Model()

    # Set the model and shell in the environment
    # env.set_model(model)
    # env.set_shell(shell)

    # Run the Flask app
    app.run(host=args.host, port=args.port, debug=args.debug)


if __name__ == "__main__":
    main()
