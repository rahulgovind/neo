"""
Terminal management utilities for creating and tracking multiple terminal instances.

This module provides the TerminalManager class which manages multiple Terminal instances
and handles their lifecycle (creation, lookup, termination).
"""

import logging
import os
from typing import ClassVar, Dict, Optional, Type

from src.neo.session import Session
from src.utils.terminal import (CommandStatus, Terminal,
                                TerminalAlreadyTerminated,
                                TerminalExecutionError)

# Define missing exception class
class TerminalNotFoundError(Exception):
    """Raised when a requested terminal ID doesn't exist."""
    pass

# Configure logging
logger = logging.getLogger(__name__)


class TerminalManager:
    """Manages the lifecycle of multiple Terminal instances."""

    # Store Terminal instances by ID
    _terminals: ClassVar[Dict[str, Terminal]] = {}

    @classmethod
    def _create_terminal(cls, session: Session, terminal_id: str) -> Terminal:
        if terminal_id in cls._terminals:
            cls.terminate(terminal_id)

        terminal = Terminal(terminal_id, session.workspace, session)
        cls._terminals[terminal_id] = terminal
        logger.info(f"Terminal {terminal_id} created successfully")
        return terminal

    @classmethod
    def _get_terminal(cls, terminal_id: str) -> Terminal:
        """Get terminal by ID or raise TerminalNotFoundError."""
        terminal = cls._terminals.get(terminal_id)
        if not terminal:
            raise TerminalNotFoundError(f"No terminal found with ID '{terminal_id}'")
        return terminal

    @classmethod
    def cleanup(cls) -> None:
        """Terminate all terminal instances."""
        terminal_ids = list(cls._terminals.keys())
        for terminal_id in terminal_ids:
            cls.terminate(terminal_id)

    @classmethod
    def execute_command(
        cls,
        session: Session,
        terminal_id: str = None, 
        command: str = None,
        timeout: float = 2.0,
    ) -> CommandStatus:
        """Execute a command, creating a terminal if needed."""

        if not terminal_id:
            terminal_id = "default"
            
        terminal = cls._terminals.get(terminal_id)
        if terminal:
            try:
                return terminal.execute_command(command, timeout)
            except TerminalAlreadyTerminated:
                terminal = None

        terminal = cls._create_terminal(session, terminal_id)
        cls._terminals[terminal_id] = terminal
        return terminal.execute_command(command, timeout)

    @classmethod
    def terminate(cls, terminal_id: str) -> None:
        """Terminate a terminal process by ID."""
        terminal = cls._get_terminal(terminal_id)
        terminal.terminate()
        
    @classmethod
    def view_output(cls, terminal_id: str, timeout: float = 0.0) -> Optional[CommandStatus]:
        """View the current output of a terminal command.
        
        Args:
            terminal_id: The ID of the terminal to view output from
            timeout: How long to wait for command to complete (0.0 = don't wait)
            
        Returns:
            CommandStatus containing output and status, or None if terminal not found
        """
        terminal = cls._get_terminal(terminal_id)
        return terminal.status(timeout)
            
    @classmethod
    def write_to_terminal(cls, terminal_id: str, content: str, press_enter: bool = True) -> None:
        terminal = cls._get_terminal(terminal_id)
        terminal.write_input(content, press_enter)
