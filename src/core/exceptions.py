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
