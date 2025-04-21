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

from src.neo.shell.command import Command, CommandTemplate, CommandParameter
from src.neo.session import Session
from src.neo.core.messages import CommandResult, StructuredOutput

# Configure logging
logger = logging.getLogger(__name__)


class StructuredOutputCommand(Command):
    """
    Command used to output structured data.
    """

    def template(self) -> CommandTemplate:
        """
        Returns the command template with parameter definitions and documentation.
        """
        return CommandTemplate(
            name="output",
            description=textwrap.dedent(
                """Command used to output structured data."""
            ),
            examples=textwrap.dedent(
                """
                Command call when structured output was requested for 1+1 as int type
                ▶output｜2■
                ✅Successfully processed output.■
                
                Command call when user requested python code to print abc as raw type
                ▶output｜print("abc")■
                ✅Successfully processed output.■
                
                Command call when user requested to return a result with schema
                {
                    "type": "object", 
                    "properties": {
                        "x": {"type": "integer"}, 
                        "y": {"type": "string"}, 
                        "z": {"type": "array", "items": {"type": "number"}}
                    }
                }
                ▶output ｜{"x": 1, "y": "test", "z": [1.0, 2.0]}■
                ✅Successfully processed output.■

                Output to the "checkpoint" destination
                ▶output -d checkpoint ｜{"x": 1, "y": "test", "z": [1.0, 2.0]}■
                ✅Successfully processed output.■
                """
            ),
            # Empty list of parameters as this command is not meant to be called directly
            parameters=[
                CommandParameter(
                    name="destination",
                    description="Output destination",
                    required=False,
                    default="default",
                    is_flag=True,
                    short_flag="d",
                    long_flag="destination",
                )
            ],
            requires_data=True,
        )

    def process(
        self, session: Session, args: Dict[str, Any], data: Optional[str] = None
    ) -> CommandResult:
        # Command is never expected to be directly called on the shell.
        return StructuredOutput(
            content="Successfully processed output.",
            destination=args.get("destination", "default"),
            value=data
        )