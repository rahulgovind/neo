"""
Session management module for Neo application.

This module provides functionality for managing session state, including:
- Creating and retrieving session IDs
- Mapping session names to session IDs
- Tracking the last active session
"""

from dataclasses import dataclass
import os
import logging
import json
from typing import Optional, Dict, TYPE_CHECKING, List
from src.core.context import Context

# Configure logging
logger = logging.getLogger(__name__)

@dataclass
class PersistentSessionState:
    session_id: Optional[str]
    session_name: str
    workspace: Optional[str]

    def to_dict(self) -> Dict[str, str]:
        return {
            "session_id": self.session_id,
            "session_name": self.session_name,
            "workspace": self.workspace
        }

    @classmethod
    def from_dict(cls, data: Dict[str, str]) -> "PersistentSessionState":
        return cls(
            session_id=data["session_id"],
            session_name=data.get("session_name"),
            workspace=data.get("workspace")
        )

class SessionManager:
    """
    Manages session state for the Neo application.
    
    Handles:
    - Session ID generation
    - Session name to ID mapping
    - Last active session tracking
    """
    
    # Directory constants
    NEO_DIR = os.path.expanduser("~/.neo")
    ACTIVE_SESSIONS_DIR = os.path.join(NEO_DIR, "active-sessions")
    LAST_ACTIVE_SESSION_FILE = os.path.join(NEO_DIR, "last-active-session")
    
    @classmethod
    def _ensure_directories(cls) -> None:
        """Ensure that required directories exist."""
        os.makedirs(cls.NEO_DIR, exist_ok=True)
        os.makedirs(cls.ACTIVE_SESSIONS_DIR, exist_ok=True)
    
    @classmethod
    def get_session(cls, name: str) -> Optional["Context"]:
        """
        Get an existing session by name.
        """
        return cls._load_session(name)
    
    @classmethod
    def list_sessions(cls) -> List[str]:
        """
        List all existing sessions.
        
        Returns:
            List of session names
        """
        return cls._list_session_names()
    
    @classmethod
    def create_session(cls, name: Optional[str] = None, workspace: Optional[str] = None) -> "Context":
        """
        Create a new session.
        
        Args:
            name: Optional name for the session. If not provided, a name will be generated.
            workspace: Optional workspace for the session
            
        Returns:
            Context object for the new session
            
        Raises:
            ValueError: If a session with the given name already exists
        """
        if name:
            if cls._session_exists(name):
                raise ValueError(f"Session '{name}' already exists")
            return cls._load_session(name)
        
        session_num = 1
        while True:
            session = cls._try_create_session(name=f"session-{session_num}", workspace=workspace)
            if session:
                return session
            session_num += 1
    
    @classmethod
    def get_last_active_session(cls) -> Optional["Context"]:
        """
        Get the last active session.
        
        Returns:
            Context object for the last active session, or None if no active session exists
        """
        # Get the last active session name
        session_name = cls._get_last_active_session_name()
        return cls._load_session(session_name) if session_name else None
        
    @classmethod
    def create_temporary_session(cls, workspace: Optional[str] = None) -> "Context":
        """
        Create a temporary session that doesn't persist between runs.
        
        Args:
            workspace: Optional workspace path for the session
            
        Returns:
            Context object for the temporary session
        """
        # Create a context directly using the ContextBuilder without saving session state
        return Context.builder().workspace(workspace).initialize()

    @classmethod
    def _load_session(cls, name: str) -> Optional["Context"]:
        if not cls._session_exists(name):
            return None
        
        session_state = cls._load_session_state(name)
        context = Context.builder()\
                    .session_id(session_state.session_id)\
                    .session_name(session_state.session_name)\
                    .workspace(session_state.workspace)\
                    .initialize()
        cls._save_session_state(
            PersistentSessionState(
                session_id=context.session_id,
                session_name=context.session_name,
                workspace=context.workspace
            )
        )
        return context
    
    @classmethod
    def _try_create_session(cls, name: str, workspace: Optional[str] = None) -> Optional["Context"]:
        if cls._session_exists(name):
            return None

        cls._save_session_state(
            PersistentSessionState(
                session_id=None,
                session_name=name,
                workspace=workspace
            )
        )
        return cls._load_session(name)

    @classmethod
    def _session_exists(cls, name: str) -> bool:
        cls._ensure_directories()
        session_file = os.path.join(cls.ACTIVE_SESSIONS_DIR, name)
        return os.path.exists(session_file)

    @classmethod
    def _load_session_state(cls, name: str) -> PersistentSessionState:
        cls._ensure_directories()
        session_file = os.path.join(cls.ACTIVE_SESSIONS_DIR, name)
        if not os.path.exists(session_file):
            raise ValueError(f"Session '{name}' does not exist")
        
        with open(session_file, "r") as f:
            return PersistentSessionState.from_dict(json.loads(f.read()))

    @classmethod
    def _save_session_state(cls, state: PersistentSessionState) -> None:
        cls._ensure_directories()
        session_file = os.path.join(cls.ACTIVE_SESSIONS_DIR, state.session_name)
        with open(session_file, "w") as f:
            f.write(json.dumps(state.to_dict()))
        cls._update_last_active_session(state.session_name)

    @classmethod
    def _list_session_names(cls) -> List[str]:
        cls._ensure_directories()
        return [f for f in os.listdir(cls.ACTIVE_SESSIONS_DIR)]

    @classmethod
    def _update_last_active_session(cls, session_name: str) -> None:
        cls._ensure_directories()
        with open(cls.LAST_ACTIVE_SESSION_FILE, "w") as f:
            f.write(session_name)

    @classmethod
    def _get_last_active_session_name(cls) -> Optional[str]:
        if not os.path.exists(cls.LAST_ACTIVE_SESSION_FILE):
            return None
        with open(cls.LAST_ACTIVE_SESSION_FILE, "r") as f:
            return f.read().strip()
    