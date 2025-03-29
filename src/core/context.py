"""
Context module providing thread-local storage for context information with context manager support.
"""

import threading
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Optional, Iterator

from src.core.exceptions import ContextNotSetError

# Thread-local storage for context
_thread_local = threading.local()

@dataclass
class Context:
    """
    Context dataclass for storing information needed across components.
    
    Attributes:
        session_id: Unique identifier for the current session
        workspace: Optional path to the code workspace
    """
    session_id: str
    workspace: Optional[str] = None

@contextmanager
def new_context(session_id: str, workspace: Optional[str] = None) -> Iterator[Context]:
    """
    Context manager to temporarily set a new context and restore the previous one.
    
    Args:
        session_id: Unique identifier for the current session
        workspace: Optional path to the code workspace
        
    Yields:
        The created Context object
        
    Example:
        with new_context(session_id="abc123", workspace="/path/to/workspace"):
            # Code that runs with the new context
        # Context is reset to previous value after the block
    """
    # Save the previous context if it exists
    previous_context = getattr(_thread_local, 'context', None)
    
    # Set the new context
    context = Context(session_id=session_id, workspace=workspace)
    _thread_local.context = context
    
    try:
        # Yield control back to the caller
        yield context
    finally:
        # Restore the previous context
        if previous_context is not None:
            _thread_local.context = previous_context
        else:
            # If there was no previous context, delete the attribute
            if hasattr(_thread_local, 'context'):
                delattr(_thread_local, 'context')

# with_context function has been removed as it should not be used.
# Use the new_context context manager pattern instead:

def get() -> Context:
    """
    Get the current thread's context.
    
    Returns:
        The current Context object
        
    Raises:
        ContextNotSetError: If the context has not been set
    """
    context = getattr(_thread_local, 'context', None)
    if context is None:
        raise ContextNotSetError("Context has not been set. Use 'with new_context(...):' first.")
    return context
