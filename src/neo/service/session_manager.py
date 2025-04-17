"""
Session management module for Neo application.

This module provides functionality for managing session state, including:
- Creating and retrieving sessions
- Mapping session names to session IDs
- Tracking temporary and permanent sessions
- Storing session metadata in SQLite database
"""

import logging
from dataclasses import dataclass
from typing import Optional, Dict, List, TYPE_CHECKING

from src.neo.session import Session
from src.neo.service.database.session_repository import SessionRepository
from src.neo.service.database.models import SessionState

if TYPE_CHECKING:
    from src.neo.session import Session

# Configure logging
logger = logging.getLogger(__name__)


@dataclass
class SessionInfo:
    session_id: str
    session_name: str
    workspace: Optional[str] = None

class SessionManager:
    """
    Manages session state for the Neo application using SQLite database.

    Handles:
    - Session ID generation
    - Session name to ID mapping
    - Last active session tracking
    - Temporary session management
    """

    @classmethod
    def _get_repository(cls):
        """Get the session repository instance."""
        return SessionRepository()

    @classmethod
    def find_session(cls, name: str) -> Optional["Session"]:
        """
        Find an existing session by name.

        Args:
            name: The name of the session to find

        Returns:
            Session object if found, otherwise None
        """
        repository = cls._get_repository()
        session_data = repository.find_session_by_name(name)

        if not session_data:
            return None

        return cls._create_session_from_data(session_data)

    @classmethod
    def get_session(cls, session_id: str) -> Optional["Session"]:
        """
        Get an existing session by its unique ID.

        Args:
            session_id: The ID of the session to retrieve

        Returns:
            Session object if found, otherwise None
        """
        repository = cls._get_repository()
        session_data = repository.find_session_by_id(session_id)

        if not session_data:
            return None

        return cls._create_session_from_data(session_data)

    @classmethod
    def list_sessions(cls, include_temporary: bool = False) -> list[SessionInfo]:
        """
        List all existing sessions.

        Args:
            include_temporary: Whether to include temporary sessions in the results

        Returns:
            List of SessionInfo objects
        """
        repository = cls._get_repository()
        sessions = repository.list_sessions(include_temporary)

        return [SessionInfo(session_id=session["session_id"], session_name=session["session_name"], workspace=session.get("workspace")) for session in sessions if session["session_id"]]

    @classmethod
    def create_session(cls, name: str, workspace: Optional[str] = None) -> "Session":
        """
        Create a new session.

        Args:
            name: Name for the session
            workspace: Optional workspace for the session

        Returns:
            Session object for the new session

        Raises:
            ValueError: If a session with the given name already exists
        """
        repository = cls._get_repository()

        # Check if session already exists
        existing_session = repository.find_session_by_name(name)
        if existing_session:
            raise ValueError(f"Session with name '{name}' already exists")

        # Create a new session without an ID first
        # The Session builder will generate an ID
        session = Session.builder() \
            .session_name(name) \
            .workspace(workspace) \
            .initialize()

        # Now save the session with the generated ID
        repository.create_session(
            session_id=session.session_id,
            name=name,
            is_temporary=False,
            workspace=workspace
        )

        # Set as last active
        repository.set_last_active_session(session.session_id)

        logger.info(f"Created new session '{name}' with ID {session.session_id}")
        return session

    @classmethod
    def get_last_active_session(cls) -> Optional["Session"]:
        """
        Get the last active session.

        Returns:
            Session object for the last active session, or None if no active session exists
        """
        repository = cls._get_repository()
        session_id = repository.get_last_active_session_id()

        if not session_id:
            return None

        return cls.get_session(session_id)

    @classmethod
    def get_last_created_session(cls, include_temporary: bool = False) -> Optional["Session"]:
        """
        Get the most recently created session.

        Args:
            include_temporary: Whether to include temporary sessions

        Returns:
            Most recently created Session object, or None if no sessions exist
        """
        repository = cls._get_repository()
        session_data = repository.get_last_created_session(include_temporary)

        if not session_data:
            return None

        return cls._create_session_from_data(session_data)

    @classmethod
    def create_temporary_session(cls, workspace: Optional[str] = None) -> "Session":
        """
        Create a temporary session that doesn't persist between runs.

        Args:
            workspace: Optional workspace path for the session

        Returns:
            Session object for the temporary session
        """
        repository = cls._get_repository()

        # Create a temporary session with generated name
        from datetime import datetime
        now = datetime.now()
        name = f"temp-{now.strftime('%m%d-%H%M%S')}"

        # Create a session directly using the SessionBuilder
        session = Session.builder() \
            .session_name(name) \
            .workspace(workspace) \
            .initialize()

        # Save to database as temporary
        repository.create_session(
            session_id=session.session_id,
            name=name,
            is_temporary=True,
            workspace=workspace
        )

        logger.info(f"Created temporary session '{name}' with ID {session.session_id}")
        return session

    @classmethod
    def _create_session_from_data(cls, session_data: Dict) -> "Session":
        """
        Create a Session object from database session data.

        Args:
            session_data: Dictionary containing session data from the database

        Returns:
            Initialized Session object
        """
        return Session.builder() \
            .session_id(session_data["session_id"]) \
            .session_name(session_data["session_name"]) \
            .workspace(session_data.get("workspace")) \
            .initialize()