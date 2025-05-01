import logging
from typing import Iterable, Optional, List, Dict, Any

# Import from the new module structure
from src.neo.core.messages import Message
from src.neo.service.session_manager import SessionManager, SessionInfo


logger = logging.getLogger(__name__)


class Service:
    """
    Provides core service functionalities for session management and messaging.
    Designed to be used by APIs or other non-interactive components.
    """

    @classmethod
    def message(cls, msg: str, session_id: Optional[str] = None) -> Iterable[Message]:
        """Sends a user message to the specified session's agent.
        
        If session_id is None, creates a temporary session.
        
        Args:
            msg: The message to process
            session_id: Session ID to use, or None to create a temporary session
            
        Returns:
            Generator yielding response messages
        """
        session = None
        
        if session_id:
            session = SessionManager.get_session(session_id)
            if not session:
                logger.error("Service.message: Session with ID '%s' not found.", session_id)
                raise ValueError(f"Session not found: {session_id}")
        else:
            # Create a temporary session
            logger.info("Service.message: Creating temporary session for message")
            session = SessionManager.create_temporary_session()

        yield from session.agent.process(msg)

    @classmethod
    def create_session(cls, session_name: Optional[str] = None, workspace: Optional[str] = None) -> SessionInfo:
        """Creates a new session (persistent or temporary).
        
        If session_name is not specified, automatically generates a name in the format
        'session-N' where N is incremented to ensure uniqueness.
        
        Args:
            session_name: Optional name for the session
            workspace: Optional workspace path for the session
            
        Returns:
            SessionInfo object with details about the created session
            
        Raises:
            ValueError: If a session with the given name already exists
            RuntimeError: If session creation fails for another reason
        """
        # Generate a session name if none was provided
        if session_name is None:
            # Get all existing sessions to find the highest numbered 'session-N'
            existing_sessions = SessionManager.list_sessions()
            
            # Find the highest N in existing session-N pattern
            highest_n = 0
            for session in existing_sessions:
                name = session.session_name
                if name.startswith("session-"):
                    try:
                        n = int(name.split("-")[1])
                        highest_n = max(highest_n, n)
                    except (IndexError, ValueError):
                        # Not a valid session-N format, skip it
                        continue
            
            # Create new session name with incremented number
            session_name = f"session-{highest_n + 1}"
            logger.info("Generated session name: %s", session_name)
            
        logger.info("Service attempting to create session. Name: %s, Workspace: %s", session_name, workspace)
        
        try:
            session = SessionManager.create_session(
                name=session_name, workspace=workspace
            )
            logger.info("Created session: %s (Name: %s)", session.session_id, session.session_name)
            return SessionInfo(session_id=session.session_id, session_name=session.session_name, workspace=session.workspace)
        except ValueError as e:
            logger.error("Failed to create session: %s", e)
            raise  # Re-raise the error (e.g., session name conflict)
        except Exception as e:
            logger.error(
                "Unexpected error creating session: %s", e, exc_info=True
            )
            raise RuntimeError(f"Failed to create session: {e}") from e

    @classmethod
    def get_session(cls, session_id: str) -> Optional[SessionInfo]:
        """Retrieves the persisted state of a session by its ID."""
        logger.debug("Service attempting to get session state for ID: %s", session_id)
        session = SessionManager.get_session(session_id)
        if not session:
            return None
        
        return SessionInfo(session_id=session.session_id, session_name=session.session_name)

    @classmethod
    def list_sessions(cls) -> list[SessionInfo]:
        """Lists all available persistent sessions.
        
        Returns:
            A list of SessionInfo objects representing all persistent sessions.
        """
        logger.info("Service listing sessions.")
        return SessionManager.list_sessions()

        
    @classmethod
    def get_last_active_session(cls) -> Optional[SessionInfo]:
        """Gets the last active session, or None if no active session exists.
        
        Returns:
            SessionInfo with details about the last active session, or None if no active session exists
        """
        logger.info("Service getting last active session.")
        session = SessionManager.get_last_active_session()
        
        if not session:
            return None
            
        return SessionInfo(
            session_id=session.session_id, 
            session_name=session.session_name, 
            workspace=session.workspace
        )
    
    @classmethod
    def history(cls, session_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Retrieves message history for a given session.
        
        Args:
            session_id: The ID of the session to retrieve messages for
            limit: Maximum number of messages to retrieve (default: 50)
            
        Returns:
            List of message dictionaries ordered by timestamp (oldest first)
            
        Raises:
            ValueError: If session with the given ID doesn't exist
        """
        logger.info("Service retrieving message history for session %s", session_id)
        
        # First verify the session exists
        session = SessionManager.get_session(session_id)
        if not session:
            logger.error("Service.history: Session with ID '%s' not found.", session_id)
            raise ValueError(f"Session not found: {session_id}")
            
        # Get the message history from the database
        from src.database.database import Database
        db = Database()
        
        messages = db.get_session_messages(session_id=session_id, limit=limit)
        logger.info("Retrieved %d messages for session %s", len(messages), session_id)
        
        return messages


    @classmethod
    def update_session(cls, session_id: str, workspace: Optional[str] = None) -> Optional[SessionInfo]:
        """Updates an existing session with new attributes.
        
        Args:
            session_id: The ID of the session to update
            workspace: New workspace path for the session
            
        Returns:
            Updated SessionInfo object if successful, None if session not found
            
        Raises:
            RuntimeError: If updating the session fails unexpectedly
        """
        logger.info("Service attempting to update session %s. New workspace: %s", session_id, workspace)
        
        try:
            session = SessionManager.update_session(session_id=session_id, workspace=workspace)
            if not session:
                logger.warning("Failed to update session: Session with ID '%s' not found", session_id)
                return None
                
            logger.info("Updated session: %s (Name: %s)", session.session_id, session.session_name)
            return SessionInfo(
                session_id=session.session_id, 
                session_name=session.session_name, 
                workspace=session.workspace
            )
        except Exception as e:
            logger.error("Unexpected error updating session: %s", e, exc_info=True)
            raise RuntimeError(f"Failed to update session: {e}") from e
    
    @classmethod
    def execute_shell_command(cls, session_id: str, command: str) -> Message:
        """Executes a shell command in the specified session.
        
        Args:
            session_id: The ID of the session to use
            command: The shell command to execute (with markers)
            
        Returns:
            Message object containing the command result
            
        Raises:
            ValueError: If session with the given ID doesn't exist
            RuntimeError: If command execution fails
        """
        logger.info("Service executing shell command in session %s: %s", session_id, command)
        
        # First verify the session exists
        session = SessionManager.get_session(session_id)
        if not session:
            logger.error("Service.execute_shell_command: Session with ID '%s' not found", session_id)
            raise ValueError(f"Session not found: {session_id}")
        
        # Parse the command to extract the command name and arguments
        from src.neo.core.messages import Message, TextBlock
        
        # Parse the command into parts
        parts = command.split(maxsplit=1)
        command_name = parts[0] if parts else ""
        statement = parts[1] if len(parts) > 1 else ""
        
        # Execute the command directly using the shell
        result = session.shell.execute(command_name, statement)
        
        # Return a message containing the command result
        return Message(
            role="user",
            content=[TextBlock(text=result.model_text())],
        )
        

