"""
Agent memory management module.
"""

import logging
from typing import List, Dict, Any, Optional
from textwrap import dedent

from src.database import Database

logger = logging.getLogger(__name__)

class AgentMemory:
    """Memory management for Agent that persists conversation history"""
    
    def __init__(self, session_id: str, db: Optional[Database] = None):
        """Initialize memory manager for a specific session"""
        self._session_id = session_id
        self._db = db or Database()
        
    def get_memory(self) -> List[Dict[str, str]]:
        """Retrieve agent memory for the current session"""
        try:
            # Get memory data from database
            memory_data = self._db.get_memory(self._session_id)
            
            # If no memory exists yet, return empty list
            if memory_data is None:
                logger.debug(f"No existing memory found for session {self._session_id}")
                return []
                
            return memory_data
            
        except Exception as e:
            logger.error(f"Error retrieving agent memory: {e}")
            # Return empty list if there's an error
            return []
            
    def update_memory(self, user_message: str, assistant_response: str) -> None:
        """
        Update memory with the latest exchange
        
        This method adds a new message pair to the memory and persists it to the database
        """
        try:
            # Skip update if user message is empty
            if not user_message.strip():
                logger.debug("Skipping memory update due to empty user message")
                return
                
            # Get existing memory
            memory = self.get_memory()
            
            # Add new message pair
            memory.append({
                "user": user_message.strip(),
                "assistant": assistant_response
            })
            
            # Store updated memory in database
            self._db.store_memory(self._session_id, memory)
            
            logger.debug(f"Memory updated for session {self._session_id}, now contains {len(memory)} exchanges")
            
        except Exception as e:
            logger.error(f"Error updating agent memory: {e}")
            
    def clear_memory(self) -> None:
        """Clear all memory for the current session"""
        try:
            self._db.delete_memory(self._session_id)
            logger.info(f"Memory cleared for session {self._session_id}")
            
        except Exception as e:
            logger.error(f"Error clearing agent memory: {e}")
            
    def get_recent_exchanges(self, limit: int = 5) -> List[Dict[str, str]]:
        """Get the most recent exchanges, limited to the specified number"""
        memory = self.get_memory()
        return memory[-limit:] if memory else []
