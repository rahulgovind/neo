import os
import logging
import asyncio
from typing import Iterable, Optional, Dict

from attr import dataclass

# Import from the new module structure
from src.neo.core.messages import Message
from src.neo.service.session_manager import SessionManager, SessionInfo
from src.neo.session import Session

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
                logger.error(f"Service.message: Session with ID '{session_id}' not found.")
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
            logger.info(f"Generated session name: {session_name}")
            
        logger.info(f"Service attempting to create session. Name: {session_name}, Workspace: {workspace}")
        
        try:
            session = SessionManager.create_session(
                name=session_name, workspace=workspace
            )
            logger.info(f"Created session: {session.session_id} (Name: {session.session_name})")
            return SessionInfo(session_id=session.session_id, session_name=session.session_name, workspace=session.workspace)
        except ValueError as e:
            logger.error(f"Failed to create session: {e}")
            raise  # Re-raise the error (e.g., session name conflict)
        except Exception as e:
            logger.error(
                f"Unexpected error creating session: {e}", exc_info=True
            )
            raise RuntimeError(f"Failed to create session: {e}")

    @classmethod
    def get_session(cls, session_id: str) -> Optional[SessionInfo]:
        """Retrieves the persisted state of a session by its ID."""
        logger.debug(f"Service attempting to get session state for ID: {session_id}")
        session = SessionManager.get_session(session_id)
        if not session:
            return None
        
        return SessionInfo(session_id=session.session_id, session_name=session.session_name)

    @classmethod
    def list_sessions(cls) -> Dict[str, str]:
        """Lists all available persistent sessions."""
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
        logger.info(f"Service attempting to update session {session_id}. New workspace: {workspace}")
        
        try:
            session = SessionManager.update_session(session_id=session_id, workspace=workspace)
            if not session:
                logger.warning(f"Failed to update session: Session with ID '{session_id}' not found")
                return None
                
            logger.info(f"Updated session: {session.session_id} (Name: {session.session_name})")
            return SessionInfo(
                session_id=session.session_id, 
                session_name=session.session_name, 
                workspace=session.workspace
            )
        except Exception as e:
            logger.error(f"Unexpected error updating session: {e}", exc_info=True)
            raise RuntimeError(f"Failed to update session: {e}")
        

