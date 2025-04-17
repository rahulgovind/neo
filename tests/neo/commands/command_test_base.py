"""
Base class for file-related command tests.

This module provides a common base class for testing file-related commands
with shared test infrastructure for setting up and tearing down a test environment.
"""

import os
import unittest
import tempfile
import shutil
import logging
from pathlib import Path
from typing import Dict, Any, Optional

from src.neo.core.messages import CommandResult
from src.neo.shell.command import Command
from src.neo.exceptions import FatalError
from src.neo.session import Session
from src.neo.shell import Shell
from src.neo.core.constants import COMMAND_END

# Configure logging
logger = logging.getLogger(__name__)


class CommandTestBase(unittest.TestCase):
    """Base class for command tests with common test infrastructure."""

    def setUp(self):
        """Set up a temporary test environment."""
        # Create a temporary directory
        self.temp_dir = tempfile.mkdtemp()

        # Create a temporary test session ID
        self.test_session_id = f"test_{self.__class__.__name__.lower()}_session"

        # Create a session with our temp directory as workspace
        self.session = (
            Session.builder()
            .session_id(self.test_session_id)
            .workspace(self.temp_dir)
            .initialize()
        )

        # Create a shell instance
        self.shell = self.session.shell

    def tearDown(self):
        """Clean up the test environment."""
        # Remove temporary directory
        shutil.rmtree(self.temp_dir)


    def execute_command(self, command_line: str) -> CommandResult:
        """Helper method to execute a command with the shell.

        Args:
            command_line: The command line string to execute

        Returns:
            The command result
        """
        logger.debug(f"Command input: {command_line}")
        parsed_cmd = self.shell.parse(command_line)

        logger.debug(f"Executing command with parameters: {parsed_cmd.parameters}")
        result = self.shell.execute(
            parsed_cmd.name, parsed_cmd.parameters, parsed_cmd.data
        )
        logger.debug(f"Command result success: {result.success}")
        logger.debug(f"Command result: {str(result.content)}")

        return result