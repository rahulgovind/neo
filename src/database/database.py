"""
Database module for storing application state in SQLite.
"""

import os
import sqlite3
import json
import logging
from typing import List, Dict, Any, Optional, Tuple, Union
from pathlib import Path
import pickle

# Configure logging
logger = logging.getLogger(__name__)

class Database:
    """SQLite database for storing application state"""
    
    def __init__(self, db_path: Optional[str] = None):
        """Initialize the database"""
        if db_path is None:
            # Use ~/.neo/state.db as default
            home_dir = str(Path.home())
            neo_dir = os.path.join(home_dir, ".neo")
            self.db_path = os.path.join(neo_dir, "state.db")
        else:
            self.db_path = db_path
        
        self._init_db()
        
    def _init_db(self) -> None:
        """Initialize the database schema if it doesn't exist"""
        try:
            # Ensure the directory exists
            os.makedirs(os.path.dirname(os.path.abspath(self.db_path)), exist_ok=True)
            
            # Connect to DB and create tables if they don't exist
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Create sessions table
                cursor.execute('''
                CREATE TABLE IF NOT EXISTS sessions (
                    session_id TEXT PRIMARY KEY,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    description TEXT
                )
                ''')
                
                # Create messages table
                cursor.execute('''
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    role TEXT NOT NULL,
                    message TEXT NOT NULL,
                    FOREIGN KEY (session_id) REFERENCES sessions(session_id) ON DELETE CASCADE
                )
                ''')
                
                # Create memory table
                cursor.execute('''
                CREATE TABLE IF NOT EXISTS memory (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    data BLOB,
                    FOREIGN KEY (session_id) REFERENCES sessions(session_id) ON DELETE CASCADE
                )
                ''')
                
                conn.commit()
                logger.info("Database initialized successfully")
                
        except Exception as e:
            logger.error(f"Error initializing database: {e}")
            raise
    
    # Session management
    
    def create_session(self, session_id: str, description: Optional[str] = None) -> None:
        """Create a new session"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "INSERT OR IGNORE INTO sessions (session_id, description) VALUES (?, ?)",
                    (session_id, description)
                )
                conn.commit()
                
            logger.info(f"Created session {session_id}")
            
        except Exception as e:
            logger.error(f"Error creating session: {e}")
            raise
    
    def update_session(self, session_id: str, description: Optional[str] = None) -> None:
        """Update a session's description and updated_at timestamp"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                if description is not None:
                    cursor.execute(
                        "UPDATE sessions SET description = ?, updated_at = CURRENT_TIMESTAMP WHERE session_id = ?",
                        (description, session_id)
                    )
                else:
                    cursor.execute(
                        "UPDATE sessions SET updated_at = CURRENT_TIMESTAMP WHERE session_id = ?",
                        (session_id,)
                    )
                    
                conn.commit()
                
            logger.debug(f"Updated session {session_id}")
            
        except Exception as e:
            logger.error(f"Error updating session: {e}")
            raise
    
    def get_sessions(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get a list of recent sessions, ordered by updated_at"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT session_id, created_at, updated_at, description FROM sessions ORDER BY updated_at DESC LIMIT ?",
                    (limit,)
                )
                
                sessions = []
                for row in cursor.fetchall():
                    sessions.append({
                        "session_id": row["session_id"],
                        "created_at": row["created_at"],
                        "updated_at": row["updated_at"],
                        "description": row["description"]
                    })
                
            logger.debug(f"Retrieved {len(sessions)} recent sessions")
            return sessions
            
        except Exception as e:
            logger.error(f"Error getting sessions: {e}")
            raise
            
    def get_latest_session(self) -> Optional[Dict[str, Any]]:
        """Get the most recent session, ordered by updated_at
        
        Returns:
            The latest session as a dictionary, or None if no sessions exist
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT session_id, created_at, updated_at, description FROM sessions ORDER BY updated_at DESC LIMIT 1"
                )
                
                row = cursor.fetchone()
                if row is None:
                    return None
                    
                return {
                    "session_id": row["session_id"],
                    "created_at": row["created_at"],
                    "updated_at": row["updated_at"],
                    "description": row["description"]
                }
                
        except Exception as e:
            logger.error(f"Error getting latest session: {e}")
            return None
    
    def delete_session(self, session_id: str) -> None:
        """Delete a session and all related data"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                # Delete session (related data will be deleted via CASCADE)
                cursor.execute("DELETE FROM sessions WHERE session_id = ?", (session_id,))
                conn.commit()
                
            logger.info(f"Deleted session {session_id}")
            
        except Exception as e:
            logger.error(f"Error deleting session: {e}")
            raise
    
    # Message management
    
    def add_message(self, session_id: str, role: str, message: str) -> int:
        """Add a message to the database"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "INSERT INTO messages (session_id, role, message) VALUES (?, ?, ?)",
                    (session_id, role, message)
                )
                message_id = cursor.lastrowid
                conn.commit()
                
                # Update session activity
                self.update_session(session_id)
                
            logger.debug(f"Added {role} message to session {session_id}")
            return message_id
            
        except Exception as e:
            logger.error(f"Error adding message: {e}")
            raise
    
    def get_session_messages(self, session_id: str, limit: int = 100) -> List[Dict[str, Any]]:
        """Get messages for a specific session, ordered by timestamp"""
        try:
            logger.debug(f"DB: Getting messages for session {session_id} with limit {limit}")
            # First check if the session exists
            with sqlite3.connect(self.db_path) as conn:
                logger.debug(f"DB: Connected to database at {self.db_path}")
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                
                # Check if session exists
                logger.debug(f"DB: Checking if session {session_id} exists")
                cursor.execute("SELECT 1 FROM sessions WHERE session_id = ?", (session_id,))
                session_exists = cursor.fetchone()
                
                if session_exists is None:
                    logger.warning(f"DB: Attempted to get messages for non-existent session: {session_id}")
                    return []
                    
                logger.debug(f"DB: Session {session_id} exists, retrieving messages")
                
                # Get messages
                cursor.execute(
                    "SELECT id, session_id, timestamp, role, message FROM messages WHERE session_id = ? ORDER BY timestamp ASC LIMIT ?",
                    (session_id, limit)
                )
                
                rows = cursor.fetchall()
                logger.debug(f"DB: Raw query returned {len(rows)} messages")
                
                messages = []
                for row in rows:
                    messages.append({
                        "id": row["id"],
                        "session_id": row["session_id"],
                        "timestamp": row["timestamp"],
                        "role": row["role"],
                        "message": row["message"]
                    })
                
            if messages:
                logger.debug(f"DB: First message sample: {messages[0]}")
            logger.debug(f"DB: Retrieved {len(messages)} messages for session {session_id}")
            return messages
            
        except Exception as e:
            logger.error(f"DB: Error getting session messages: {e}")
            import traceback
            logger.error(f"DB: Traceback: {traceback.format_exc()}")
            # Return empty list instead of raising exception
            return []
    
    # Memory management
    
    def store_memory(self, session_id: str, data: Any) -> int:
        """Store memory data for a session"""
        try:
            # Serialize the data using pickle
            serialized_data = pickle.dumps(data)
            
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Check if memory already exists for this session
                cursor.execute("SELECT id FROM memory WHERE session_id = ?", (session_id,))
                existing = cursor.fetchone()
                
                if existing:
                    # Update existing memory
                    cursor.execute(
                        "UPDATE memory SET data = ?, updated_at = CURRENT_TIMESTAMP WHERE session_id = ?",
                        (serialized_data, session_id)
                    )
                    memory_id = existing[0]
                else:
                    # Create new memory
                    cursor.execute(
                        "INSERT INTO memory (session_id, data) VALUES (?, ?)",
                        (session_id, serialized_data)
                    )
                    memory_id = cursor.lastrowid
                
                conn.commit()
                
                # Update session activity
                self.update_session(session_id)
            
            logger.debug(f"Stored memory for session {session_id}")
            return memory_id
            
        except Exception as e:
            logger.error(f"Error storing memory: {e}")
            raise
    
    def get_memory(self, session_id: str) -> Optional[Any]:
        """Retrieve memory data for a session"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT data FROM memory WHERE session_id = ?",
                    (session_id,)
                )
                
                row = cursor.fetchone()
                if row and row[0]:
                    # Deserialize the data
                    return pickle.loads(row[0])
                
            logger.debug(f"No memory found for session {session_id}")
            return None
            
        except Exception as e:
            logger.error(f"Error retrieving memory: {e}")
            raise
    
    def delete_memory(self, session_id: str) -> None:
        """Delete memory for a session"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM memory WHERE session_id = ?", (session_id,))
                conn.commit()
                
            logger.info(f"Deleted memory for session {session_id}")
            
        except Exception as e:
            logger.error(f"Error deleting memory: {e}")
            raise
