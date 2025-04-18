"""
Database module for storing application state in SQLite.
"""

import logging
import os
import pickle
import sqlite3
import traceback
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from src import NEO_HOME

# Load environment variables
# load_dotenv()  # This line is commented out because load_dotenv is not imported

# Configure logging
logger = logging.getLogger(__name__)


class Database:
    """SQLite database for storing application state"""

    def __init__(self, db_path: Optional[str] = None):
        if db_path is None:
            self.db_path = os.path.join(NEO_HOME, "state.db")
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
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS sessions (
                        session_id TEXT PRIMARY KEY,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        description TEXT
                    )
                """
                )

                # Create messages table
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS messages (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        session_id TEXT NOT NULL,
                        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        role TEXT NOT NULL,
                        message TEXT NOT NULL,
                        FOREIGN KEY (session_id)
                            REFERENCES sessions(session_id) ON DELETE CASCADE
                    )
                """
                )

                # Create memory table
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS memory (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        session_id TEXT NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        data BLOB,
                        FOREIGN KEY (session_id)
                            REFERENCES sessions(session_id) ON DELETE CASCADE
                    )
                """
                )

                conn.commit()
                logger.info("Database initialized successfully")
        except sqlite3.Error as e:
            logger.error("Error initializing database: %s", e)
            raise

    # Session management
    def create_session(
        self, session_id: str, description: Optional[str] = None
    ) -> None:
        """Create a new session"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "INSERT INTO sessions (session_id, description) VALUES (?, ?)",
                    (session_id, description),
                )
                conn.commit()

            logger.info("Created session %s", session_id)

        except sqlite3.Error as e:
            logger.error("Error creating session %s: %s", session_id, e)
            raise

    def update_session(
        self,
        session_id: str,
        description: Optional[str] = None,
        update_timestamp: bool = True,
    ) -> None:
        """Update session description or timestamp"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                fields_to_update = []
                params = []

                if description is not None:
                    fields_to_update.append("description = ?")
                    params.append(description)

                if update_timestamp:
                    fields_to_update.append("updated_at = ?")
                    # Use current timestamp for update
                    params.append(datetime.now())

                if not fields_to_update:
                    logger.debug(
                        "No fields provided to update for session %s", session_id
                    )
                    return

                sql = f"UPDATE sessions SET {', '.join(fields_to_update)} WHERE session_id = ?"
                params.append(session_id)

                cursor.execute(sql, tuple(params))

                conn.commit()

            logger.debug("Updated session %s", session_id)

        except sqlite3.Error as e:
            logger.error("Error updating session %s: %s", session_id, e)
            raise

    def get_sessions(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent sessions"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                # Order by updated_at to get most recently interacted with sessions
                cursor.execute(
                    "SELECT * FROM sessions ORDER BY updated_at DESC LIMIT ?", (limit,)
                )
                rows = cursor.fetchall()
                sessions = []
                for row in rows:
                    sessions.append(
                        {
                            "session_id": row["session_id"],
                            "created_at": row["created_at"],
                            "updated_at": row["updated_at"],
                            "description": row["description"],
                        }
                    )

            logger.debug("Retrieved %d recent sessions", len(sessions))
            return sessions

        except sqlite3.Error as e:
            logger.error("Error getting sessions: %s", e)
            raise

    def get_latest_session(self) -> Optional[Dict[str, Any]]:
        """Get the most recently updated session"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                # Get the session with the latest updated_at timestamp
                cursor.execute(
                    "SELECT * FROM sessions ORDER BY updated_at DESC LIMIT 1"
                )
                row = cursor.fetchone()

                if row:
                    return {
                        "session_id": row["session_id"],
                        "created_at": row["created_at"],
                        "updated_at": row["updated_at"],
                        "description": row["description"],
                    }
                return None  # No sessions found

        except sqlite3.Error as e:
            logger.error("Error getting latest session: %s", e)
            return None

    def delete_session(self, session_id: str) -> None:
        """Delete a session and associated data (messages, memory)"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                # Deletion cascades due to FOREIGN KEY constraints
                cursor.execute(
                    "DELETE FROM sessions WHERE session_id = ?", (session_id,)
                )
                conn.commit()

            logger.info("Deleted session %s", session_id)

        except sqlite3.Error as e:
            logger.error("Error deleting session %s: %s", session_id, e)
            raise

    # Message management
    def add_message(self, session_id: str, role: str, message: str) -> Optional[int]:
        """Add a message to a session"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "INSERT INTO messages (session_id, role, message) VALUES (?, ?, ?)",
                    (session_id, role, message),
                )
                message_id = cursor.lastrowid
                conn.commit()

                # Update session activity
                self.update_session(session_id)

            logger.debug("Added %s message to session %s", role, session_id)
            return message_id

        except sqlite3.Error as e:
            logger.error("Error adding message: %s", e)
            raise

    def get_session_messages(
        self, session_id: str, limit: int = 50
    ) -> List[Dict[str, Any]]:
        """Get messages for a specific session, ordered by timestamp"""
        try:
            logger.debug(
                "DB: Getting messages for session %s with limit %d", session_id, limit
            )
            # First check if the session exists
            with sqlite3.connect(self.db_path) as conn:
                logger.debug("DB: Connected to database at %s", self.db_path)
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()

                logger.debug("DB: Checking if session %s exists", session_id)
                cursor.execute(
                    "SELECT 1 FROM sessions WHERE session_id = ?", (session_id,)
                )
                session_exists = cursor.fetchone()

                if session_exists is None:
                    logger.warning(
                        "DB: Attempted to get messages for non-existent session: %s",
                        session_id,
                    )
                    return []

                logger.debug("DB: Session %s exists, retrieving messages", session_id)

                # Get messages, ordered by timestamp ASC (oldest first)
                cursor.execute(
                    "SELECT * FROM messages WHERE session_id = ? ORDER BY timestamp ASC LIMIT ?",
                    (session_id, limit),
                )

                rows = cursor.fetchall()
                logger.debug("DB: Raw query returned %d messages", len(rows))

                messages = []
                for row in rows:
                    messages.append(
                        {
                            "id": row["id"],
                            "session_id": row["session_id"],
                            "timestamp": row["timestamp"],
                            "role": row["role"],
                            "message": row["message"],
                        }
                    )

            if messages:
                logger.debug("DB: First message sample: %s", messages[0])
            logger.debug(
                "DB: Retrieved %d messages for session %s", len(messages), session_id
            )
            return messages

        except sqlite3.Error as e:
            logger.error("DB: Error getting session messages: %s", e)
            logger.error("DB: Traceback: %s", traceback.format_exc())
            # Return empty list instead of raising exception
            return []

    # Memory management (simple key-value store per session for now)
    def store_memory(self, session_id: str, data: Any) -> Optional[int]:
        """Store arbitrary data (memory) for a session"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                # Serialize the data using pickle
                serialized_data = pickle.dumps(data)
                # Use INSERT OR REPLACE to update if exists
                cursor.execute(
                    "INSERT OR REPLACE INTO memory (session_id, data) VALUES (?, ?)",
                    (session_id, serialized_data),
                )
                memory_id = cursor.lastrowid
                conn.commit()

                # Update session activity
                self.update_session(session_id)

            logger.debug("Stored memory for session %s", session_id)
            return memory_id

        except sqlite3.Error as e:
            logger.error("Error storing memory: %s", e)
            raise
        except pickle.PicklingError as e:
            logger.error("Error pickling memory data for session %s: %s", session_id, e)
            raise  # Re-raise as a specific error or handle differently

    def get_memory(self, session_id: str) -> Optional[Any]:
        """Retrieve stored memory for a session"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                # Retrieve the latest memory entry for the session
                cursor.execute(
                    "SELECT data FROM memory WHERE session_id = ? ORDER BY updated_at DESC LIMIT 1",
                    (session_id,),
                )
                row = cursor.fetchone()
                if row and row[0]:
                    # Deserialize the data
                    return pickle.loads(row[0])

            logger.debug("No memory found for session %s", session_id)
            return None

        except sqlite3.Error as e:
            logger.error("Error retrieving memory: %s", e)
            raise
        except pickle.UnpicklingError as e:
            logger.error(
                "Error unpickling memory data for session %s: %s", session_id, e
            )
            # Decide how to handle corrupted data - return None, raise error, etc.
            return None

    def delete_memory(self, session_id: str) -> None:
        """Delete all memory associated with a session"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM memory WHERE session_id = ?", (session_id,))
                conn.commit()

            logger.info("Deleted memory for session %s", session_id)

        except sqlite3.Error as e:
            logger.error("Error deleting memory: %s", e)
            raise
