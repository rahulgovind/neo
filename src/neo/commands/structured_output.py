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
import argparse
import shlex
import json
from dataclasses import dataclass
from typing import Optional, Any, Union

from src.neo.commands.base import Command, CommandTemplate, CommandParameter
from src.neo.session import Session
from src.neo.core.messages import CommandResult, StructuredOutput

# Configure logging
logger = logging.getLogger(__name__)


@dataclass
class StructuredOutputArgs:
    """Structured arguments for output command."""
    destination: str = "default"
    output_type: str = "raw"


class StructuredOutputCommand(Command):
    """
    Command used to output structured data.
    
    Features:
    - Supports different output types (raw, markdown, int)
    - Optional destination parameter
    - Converts data to appropriate type based on selected output_type
    """
    
    @property
    def name(self) -> str:
        """Return the command name."""
        return "output"
    
    def _parse_statement(self, statement: str, data: Optional[str] = None) -> StructuredOutputArgs:
        """Parse the command statement using argparse."""
        # Create parser for output command
        parser = argparse.ArgumentParser(prog="output", exit_on_error=False)
        
        # Add arguments
        parser.add_argument("-d", "--destination", default="default", 
                          help="Destination for the structured output (default: default)")
        parser.add_argument("-t", "--type", dest="output_type", default="raw", 
                          choices=["raw", "markdown", "int"],
                          help="Type of the output data (raw, markdown, or int)")
        
        # If statement is empty, return default arguments
        if not statement.strip():
            return StructuredOutputArgs()
            
        # Split statement into parts using shlex for proper handling of quoted arguments
        args = shlex.split(statement)
        
        # Parse arguments
        parsed_args = parser.parse_args(args)
        return StructuredOutputArgs(
            destination=parsed_args.destination,
            output_type=parsed_args.output_type
        )
    
    def description(self) -> str:
        """Returns a short description of the command."""
        return "Command used to output structured data."
    
    def help(self) -> str:
        """Returns detailed help for the command."""
        return textwrap.dedent(
            """\
            Use the `output` command to output structured data when requested.

            Usage: ▶output [--destination <destination>] [--type <type>]｜<data>■
            
            Parameters:
            - destination (-d, --destination): Destination for the output (default: default)
            - type (-t, --type): Type of the output data (options: raw, markdown, int) (default: raw)

            Examples: 
            USER: What is 10+10? Return it as structured output.
            ▶output -t int｜20■
            
            USER: Generate markdown for a simple table.
            ▶output -t markdown｜| Name | Value |\n|------|-------|\n| Key | Value |■
            
            USER: Return JSON data for processing.
            ▶output｜{"name": "John", "age": 30}■
            """
        )
        
    def validate(self, session, statement: str, data: Optional[str] = None) -> None:
        """Validate the output command."""
        if not data:
            raise ValueError("Output command requires data to process after the pipe symbol.")
        
        # Parse the arguments to validate them
        args = self._parse_statement(statement, data)
        
        # Validate the output type
        if args.output_type not in ["raw", "markdown", "int"]:
            raise ValueError(f"Invalid output type: {args.output_type}. Must be 'raw', 'markdown', or 'int'.")
            
        # If output_type is int, validate the data can be converted to int
        if args.output_type == "int":
            try:
                int(data)
            except ValueError:
                raise ValueError(f"Cannot convert '{data}' to integer.")
    
    def execute(self, session, statement: str, data: Optional[str] = None) -> CommandResult:
        """Execute the output command."""
        # Parse the arguments
        args = self._parse_statement(statement, data)
        
        # Process the value based on output_type
        value = data
        
        if args.output_type == "int":
            try:
                value = int(data)
            except ValueError as e:
                return CommandResult(
                    success=False,
                    content=f"Error converting to integer: {str(e)}"
                )
        
        # Return structured output with the processed value
        return StructuredOutput(
            content="Successfully processed output.",
            destination=args.destination,
            value=value
        )
