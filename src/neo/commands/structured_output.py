"""
NeoFind command implementation.

This module provides the NeoFindCommand class for finding files based on name and type.
"""

"""
Implements the 'find' command for searching files within the workspace."""

import os
import re
import json
import logging
import subprocess
import textwrap
import jsonschema
from typing import Dict, Any, Optional, List

from src.neo.commands.base import Command, CommandTemplate, CommandParameter
from src.neo.session import Session
from src.neo.core.messages import CommandResult, StructuredOutput

# Configure logging
logger = logging.getLogger(__name__)


class StructuredOutputCommand(Command):
    """
    Command used to output structured data.
    """
    
    @property
    def name(self) -> str:
        """Return the command name."""
        return "output"
    
    def description(self) -> str:
        """Returns a short description of the command."""
        return "Command used to output structured data."
    
    def help(self) -> str:
        """Returns detailed help for the command."""
        return textwrap.dedent(
            """\
            Use the `output` command to output structured data when requested.

            Usage: ▶output [--destination <destination>]｜<data>■
            """
        )
        
    def validate(self, session, statement: str, data: Optional[str] = None) -> None:
        """Validate the output command."""
        if not data:
            raise ValueError("Output command requires data to process after the pipe symbol.")
        
    def execute(self, session, statement: str, data: Optional[str] = None) -> CommandResult:
        # Command is never expected to be directly called on the shell.
        return StructuredOutput(
            content="Successfully processed output.",
            destination="default",
            value=data
        )
