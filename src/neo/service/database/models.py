"""
Data models for database entities.

Provides dataclass models that map to database tables.
"""

from dataclasses import dataclass
from typing import Optional
from datetime import datetime


@dataclass
class SessionState:
    """
    Session state model representing a session in the database.
    
    Maps to the 'sessions' table in the database.
    """
    session_id: str
    session_name: str
    is_temporary: bool = False
    workspace: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    @classmethod
    def from_dict(cls, data: dict) -> "SessionState":
        """
        Create a SessionState from a dictionary.
        
        Args:
            data: Dictionary containing session data
            
        Returns:
            SessionState object
        """
        # Convert SQLite integer to boolean
        is_temporary = bool(data.get("is_temporary", 0))
        
        # Parse datetime strings to datetime objects if present
        created_at = None
        if data.get("created_at"):
            try:
                created_at = datetime.fromisoformat(data["created_at"])
            except (ValueError, TypeError):
                pass
        
        updated_at = None
        if data.get("updated_at"):
            try:
                updated_at = datetime.fromisoformat(data["updated_at"])
            except (ValueError, TypeError):
                pass
        
        return cls(
            session_id=data["session_id"],
            session_name=data["session_name"],
            is_temporary=is_temporary,
            workspace=data.get("workspace"),
            created_at=created_at,
            updated_at=updated_at
        )
    
    def to_dict(self) -> dict:
        """
        Convert SessionState to a dictionary.
        
        Returns:
            Dictionary representation of the session state
        """
        result = {
            "session_id": self.session_id,
            "session_name": self.session_name,
            "is_temporary": 1 if self.is_temporary else 0,
            "workspace": self.workspace
        }
        
        if self.created_at:
            result["created_at"] = self.created_at.isoformat()
            
        if self.updated_at:
            result["updated_at"] = self.updated_at.isoformat()
            
        return result
