"""
Repository for session data in the SQLite database.

Provides methods for managing session data in the database.
"""

import logging
import sqlite3
from datetime import datetime
from typing import Optional, List, Dict, Any

from src.neo.service.database.connection import DatabaseConnection

logger = logging.getLogger(__name__)

class SessionRepository:
    """Repository for session data in the SQLite database."""
    
    def __init__(self):
        self._db = DatabaseConnection().get_connection()
    
    def find_session_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        """
        Find a session by name.
        
        Args:
            name: The name of the session to find
            
        Returns:
            Session data as a dictionary, or None if not found
        """
        cursor = self._db.cursor()
        cursor.execute(
            "SELECT * FROM sessions WHERE session_name = ?", 
            (name,)
        )
        session_data = cursor.fetchone()
        return dict(session_data) if session_data else None
    
    def find_session_by_id(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        Find a session by ID.
        
        Args:
            session_id: The ID of the session to find
            
        Returns:
            Session data as a dictionary, or None if not found
        """
        cursor = self._db.cursor()
        cursor.execute(
            "SELECT * FROM sessions WHERE session_id = ?", 
            (session_id,)
        )
        session_data = cursor.fetchone()
        return dict(session_data) if session_data else None
    
    def create_session(self, session_id: str, name: str, is_temporary: bool = False, 
                      workspace: Optional[str] = None) -> Dict[str, Any]:
        """
        Create a new session.
        
        Args:
            session_id: The ID of the session
            name: The name of the session
            is_temporary: Whether the session is temporary
            workspace: Optional workspace path
            
        Returns:
            The newly created session data
            
        Raises:
            sqlite3.IntegrityError: If a session with the given name already exists
        """
        cursor = self._db.cursor()
        current_time = datetime.now().isoformat()
        
        cursor.execute(
            """
            INSERT INTO sessions (
                session_id, session_name, is_temporary, workspace, 
                created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (session_id, name, 1 if is_temporary else 0, workspace, current_time, current_time)
        )
        self._db.commit()
        
        return self.find_session_by_id(session_id)
    
    def update_session(self, session_id: str, name: Optional[str] = None, 
                      is_temporary: Optional[bool] = None, 
                      workspace: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Update an existing session.
        
        Args:
            session_id: The ID of the session to update
            name: Optional new name for the session
            is_temporary: Optional new temporary flag
            workspace: Optional new workspace path
            
        Returns:
            The updated session data, or None if not found
            
        Raises:
            sqlite3.IntegrityError: If trying to rename to a name that already exists
        """
        # First check if the session exists
        existing_session = self.find_session_by_id(session_id)
        if not existing_session:
            return None
        
        # Build update query dynamically based on provided fields
        update_fields = []
        params = []
        
        if name is not None:
            update_fields.append("session_name = ?")
            params.append(name)
        
        if is_temporary is not None:
            update_fields.append("is_temporary = ?")
            params.append(1 if is_temporary else 0)
        
        if workspace is not None:
            update_fields.append("workspace = ?")
            params.append(workspace)
        
        # Add updated_at timestamp
        update_fields.append("updated_at = ?")
        params.append(datetime.now().isoformat())
        
        # Add session_id for WHERE clause
        params.append(session_id)
        
        if update_fields:
            cursor = self._db.cursor()
            query = f"UPDATE sessions SET {', '.join(update_fields)} WHERE session_id = ?"
            cursor.execute(query, params)
            self._db.commit()
        
        return self.find_session_by_id(session_id)
    
    def delete_session(self, session_id: str) -> bool:
        """
        Delete a session by ID.
        
        Args:
            session_id: The ID of the session to delete
            
        Returns:
            True if the session was deleted, False if not found
        """
        cursor = self._db.cursor()
        cursor.execute("DELETE FROM sessions WHERE session_id = ?", (session_id,))
        self._db.commit()
        return cursor.rowcount > 0
    
    def list_sessions(self, include_temporary: bool = False) -> List[Dict[str, Any]]:
        """
        List all sessions.
        
        Args:
            include_temporary: Whether to include temporary sessions
            
        Returns:
            List of session data dictionaries
        """
        cursor = self._db.cursor()
        
        if include_temporary:
            cursor.execute("SELECT * FROM sessions ORDER BY created_at DESC")
        else:
            cursor.execute("SELECT * FROM sessions WHERE is_temporary = 0 ORDER BY created_at DESC")
        
        return [dict(row) for row in cursor.fetchall()]
    
    def get_last_created_session(self, include_temporary: bool = False) -> Optional[Dict[str, Any]]:
        """
        Get the most recently created session.
        
        Args:
            include_temporary: Whether to include temporary sessions
            
        Returns:
            The most recently created session data, or None if no sessions exist
        """
        cursor = self._db.cursor()
        
        if include_temporary:
            cursor.execute("SELECT * FROM sessions ORDER BY created_at DESC LIMIT 1")
        else:
            cursor.execute("SELECT * FROM sessions WHERE is_temporary = 0 ORDER BY created_at DESC LIMIT 1")
        
        session_data = cursor.fetchone()
        return dict(session_data) if session_data else None
    
    def set_last_active_session(self, session_id: str) -> None:
        """
        Set the last active session.
        
        Args:
            session_id: The ID of the session to set as last active
        """
        cursor = self._db.cursor()
        cursor.execute(
            """
            INSERT INTO settings (key, value) 
            VALUES ('last_active_session', ?) 
            ON CONFLICT(key) DO UPDATE SET value = ?
            """,
            (session_id, session_id)
        )
        self._db.commit()
    
    def get_last_active_session_id(self) -> Optional[str]:
        """
        Get the ID of the last active session.
        
        Returns:
            The ID of the last active session, or None if not set
        """
        cursor = self._db.cursor()
        cursor.execute("SELECT value FROM settings WHERE key = 'last_active_session'")
        result = cursor.fetchone()
        return result['value'] if result else None
