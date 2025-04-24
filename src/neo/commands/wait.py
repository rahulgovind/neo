"""Implements the 'wait' command that sleeps for a specified duration."""

import argparse
import logging
import shlex
import time
from dataclasses import dataclass
from textwrap import dedent
from typing import Optional

from src.neo.commands.base import Command
from src.neo.core.messages import CommandResult
from src.neo.session import Session

# Configure logging
logger = logging.getLogger(__name__)


@dataclass
class WaitArgs:
    """Structured arguments for the wait command."""
    duration: int = 5


class WaitCommand(Command):
    """Command for waiting/sleeping for a specified duration."""

    @property
    def name(self) -> str:
        return "wait"

    def description(self) -> str:
        return "Wait for a specified number of seconds."

    def help(self) -> str:
        return dedent(
            """\
            Use the `wait` command to sleep for a specified number of seconds.
            
            Usage: ▶wait [--duration SECONDS]■
            
            - duration: Number of seconds to sleep for. Defaults to 5 seconds.
            
            Example:
            ▶wait --duration 10■
            ✅Waited for 10 seconds■
            """
        )

    def _parse_statement(
        self, statement: str, data: Optional[str] = None
    ) -> WaitArgs:
        parser = argparse.ArgumentParser(prog="wait", add_help=False)
        parser.add_argument(
            "--duration",
            type=int,
            default=5,
            help="Number of seconds to sleep for (default: 5)",
        )

        # Parse statement if present, otherwise use defaults
        arg_list = shlex.split(statement) if statement else []
        parsed_args = parser.parse_args(arg_list)

        return WaitArgs(
            duration=parsed_args.duration,
        )

    def validate(self, session, statement: str, data: Optional[str] = None) -> None:
        # Parse and validate arguments
        args = self._parse_statement(statement, data)
        
        # Check if duration is a positive number
        if args.duration < 0:
            logger.error(f"Invalid duration provided: {args.duration}")
            raise ValueError("Error: Duration must be a non-negative number")

    def execute(
        self, session, statement: str, data: Optional[str] = None
    ) -> CommandResult:
        # First run validation
        self.validate(session, statement, data)

        # Parse arguments
        args = self._parse_statement(statement, data)
        duration = args.duration

        # Sleep for the specified duration using session clock
        session.clock.sleep(duration)

        return CommandResult(
            content=f"Waited for {duration} seconds",
            success=True
        )
