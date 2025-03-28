"""
Core exceptions module.

This module defines custom exceptions used throughout the Neo application.
"""

class FatalError(Exception):
    """
    A fatal error that should not be caught and converted to a CommandResult.
    
    These errors represent unrecoverable conditions or programming errors that
    should be propagated up the call stack rather than being handled as a
    normal command failure.
    """
    pass


class ContextNotSetError(FatalError):
    """
    Exception raised when attempting to access context that hasn't been set.
    
    This is a fatal error because commands should always have a valid context
    to operate in. If the context is not set, it indicates a programming error
    or system misconfiguration.
    """
    pass
