"""
Session module for managing chat sessions with unique identifiers.
"""

import datetime
import logging
import random
import time
from typing import Optional, TYPE_CHECKING

# Use TYPE_CHECKING to avoid circular imports
if TYPE_CHECKING:
    from src.agent import Agent

# Configure logging
logger = logging.getLogger(__name__)


class Session:
    """
    Session class representing a unique chat session with an agent.
    
    Each session has a unique identifier and maintains its own state.
    Sessions are created and managed by the ChatFactory.
    """
    
    def __init__(self, agent: 'Agent', session_id: Optional[str] = None):
        """
        Initialize a new session with an optional custom session ID.
        
        Args:
            agent: The Agent instance that will process messages
            session_id: Optional custom session ID (will be generated if None)
        """
        self.agent = agent
        # Generate session ID if not provided
        self.session_id = session_id if session_id else self._generate_session_id()
        logger.info(f"New session created with ID: {self.session_id}")
    
    def _generate_session_id(self) -> str:
        """
        Generate a unique session ID in the format yyyymmdd_hhmmss_<rand>.
        
        Returns:
            Formatted session ID string
        """
        timestamp = datetime.datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        # Generate random 4-digit number
        rand = random.randint(1000, 9999)
        return f"{timestamp}_{rand}"
    
    def process(self, user_message: str) -> str:
        """
        Process a user message through the agent.
        
        Args:
            user_message: The user's input message
            
        Returns:
            The agent's response as a string
        """
        return self.agent.process(user_message)
    
    def get_session_id(self) -> str:
        """Get the current session ID."""
        return self.session_id