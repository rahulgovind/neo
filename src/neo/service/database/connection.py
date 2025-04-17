"""
Database connection management for Neo application.

Provides connection management for SQLite database using singleton pattern.
"""

import os
import sqlite3
import logging
from typing import Optional

logger = logging.getLogger(__name__)

class DatabaseConnection:
    """Singleton class for managing database connections."""
    
    _instance: Optional["DatabaseConnection"] = None
    _connection: Optional[sqlite3.Connection] = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(DatabaseConnection, cls).__new__(cls)
            cls._instance._initialize_connection()
        return cls._instance
    
    def _initialize_connection(self) -> None:
        """Initialize the database connection and create tables if they don't exist."""
        neo_dir = os.path.expanduser("~/.neo")
        os.makedirs(neo_dir, exist_ok=True)
        
        database_path = os.path.join(neo_dir, "neo.db")
        self._connection = sqlite3.connect(database_path)
        self._connection.row_factory = sqlite3.Row
        
        # Enable foreign keys constraint enforcement
        self._connection.execute("PRAGMA foreign_keys = ON")
        
        # Create tables if they don't exist
        self._create_tables()
        logger.info(f"Database connection initialized at {database_path}")
    
    def _create_tables(self) -> None:
        """Create database tables if they don't exist."""
        cursor = self._connection.cursor()
        
        # Sessions table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS sessions (
            session_id TEXT PRIMARY KEY,
            session_name TEXT NOT NULL UNIQUE,
            is_temporary BOOLEAN NOT NULL DEFAULT 0,
            workspace TEXT,
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        ''')
        
        # Last active session
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )
        ''')
        
        self._connection.commit()
    
    def get_connection(self) -> sqlite3.Connection:
        """Get the SQLite connection object."""
        if self._connection is None:
            self._initialize_connection()
        return self._connection
    
    def close(self) -> None:
        """Close the database connection."""
        if self._connection:
            self._connection.close()
            self._connection = None
            logger.info("Database connection closed")
    
    def __del__(self) -> None:
        """Close connection on object destruction."""
        self.close()
