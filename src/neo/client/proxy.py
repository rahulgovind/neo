"""
Proxy module provides abstraction over different LLM API providers.
Each proxy implements the same interface but connects to a different backend.
"""

import os
import logging
from typing import List, Dict, Any, Optional
from abc import ABC, abstractmethod

from src.neo.core.messages import Message

# Configure logging
logger = logging.getLogger(__name__)


class Proxy(ABC):
    """
    Abstract base class defining the interface for all LLM API proxies.
    Each implementation provides connection to a specific LLM provider.
    """

    @abstractmethod
    def process(
        self,
        messages: List[Message],
        model: Optional[str] = None,
        stop: List[str] = None,
        session_id: Optional[str] = None,
    ) -> Message:
        """
        Process a conversation with the LLM and return the response.

        Args:
            messages: List of messages representing the conversation history
            model: Optional model identifier to override the default model
            stop: Optional list of stop sequences
            session_id: Optional session identifier for tracking

        Returns:
            Message: LLM's response as a Message object

        Raises:
            Exception: Any error during processing is logged and re-raised
        """
        pass

    @staticmethod
    def get_proxy() -> 'Proxy':
        """
        Factory method to get the appropriate proxy implementation.
        
        Returns:
            Proxy: An instance of a concrete Proxy implementation based on environment settings
        """
        from src.neo.client.open_router_proxy import OpenRouterProxy
        
        proxy_type = os.environ.get("PROXY", "OPEN_ROUTER")
        
        if proxy_type == "OPEN_ROUTER":
            return OpenRouterProxy()
        else:
            logger.warning(f"Unknown proxy type: {proxy_type}, defaulting to OpenRouter")
            return OpenRouterProxy()
