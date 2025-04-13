"""
Command Line Interface module for Neo application.

This module provides the main entry point for the Neo CLI application,
handling command-line arguments, configuring components, and launching the chat.
It ties together all the other modules to create a cohesive application.
"""

import os
import sys
import argparse
import logging
from typing import Dict, Any, Optional, List

# Logging is configured in src/__init__.py when imported
from src.core.model import Model
from src.core.context import Context, ContextBuilder
from src.agent.agent import Agent
from src.core.shell import Shell
from src.apps.chat import Chat

# Configure logger for this module
logger = logging.getLogger(__name__)


class CLI:
    """
    Encapsulates the CLI application logic.

    This class is responsible for:
    - Parsing command-line arguments
    - Setting up the application environment
    - Initializing the model, functions, and agent
    - Launching the interactive chat
    """

    @classmethod
    def start(cls) -> None:
        """
        Start the CLI application.

        This method:
        1. Parses command-line arguments
        2. Delegates to the appropriate Chat class methods based on the subcommand

        It's the main entry point for the application.
        """
        try:
            # Parse command-line arguments
            args = cls._parse_args()

            # Execute the appropriate subcommand
            if args.subcommand == 'chat':
                # Start interactive chat session using Chat's class method
                logger.info(f"Using workspace: {args.workspace}")
                Chat.start_interactive(
                    workspace=args.workspace,
                    history_file=args.history_file,
                    session_name=None  # Chat subcommand doesn't take a session parameter
                )
            elif args.subcommand == 'create-session':
                # Create a new session using Chat's class method
                logger.info(f"Using workspace: {args.workspace}")
                session = Chat.create_new_session(workspace=args.workspace, session_name=args.session)
                print(f"Session '{session.session_name}' created successfully")
                print(f"Session ID: {session.session_id}")
                print(f"Workspace: {args.workspace}")
            elif args.subcommand == 'message':
                # Process a single message using the Chat class method
                # For message, we need to create a temporary workspace
                Chat.message(message=args.message, workspace=os.getcwd(), session=args.session)

        except KeyboardInterrupt:
            # Handle Ctrl+C in the main thread
            logger.info("Application interrupted by user")
            print("\nExiting Neo CLI...")
            sys.exit(0)

        except Exception as e:
            # Log any unhandled exceptions
            logger.critical(f"Unhandled exception: {e}", exc_info=True)
            print(f"\nError: {str(e)}")
            sys.exit(1)

    @staticmethod
    def _parse_args() -> argparse.Namespace:
        """
        Parse command-line arguments.

        Returns:
            Parsed argument namespace
        """
        parser = argparse.ArgumentParser(
            description="Neo - AI assistant for code tasks",
            formatter_class=argparse.ArgumentDefaultsHelpFormatter,
        )

        # Create subparsers for different commands
        subparsers = parser.add_subparsers(dest="subcommand", help="Subcommand to run", required=True)

        # 1. Chat subcommand - interactive chat session
        chat_parser = subparsers.add_parser(
            "chat", help="Start an interactive chat session"
        )
        chat_parser.add_argument(
            "workspace", help="Path to a code workspace directory"
        )
        chat_parser.add_argument(
            "--history-file", type=str, help="Path to file for storing command history"
        )

        # 2. Create-session subcommand - create a new session
        create_session_parser = subparsers.add_parser(
            "create-session", help="Create a new session"
        )
        create_session_parser.add_argument(
            "--session", "-s", type=str, help="Name of the session to create"
        )
        create_session_parser.add_argument(
            "workspace", help="Path to a code workspace directory"
        )

        # 3. Message subcommand - process a single message
        message_parser = subparsers.add_parser(
            "message", help="Process a single message in headless mode"
        )
        message_parser.add_argument(
            "message", help="Message content to process"
        )
        message_parser.add_argument(
            "--session", "-s", type=str, help="Name of the session to use"
        )

        return parser.parse_args()
        





def main() -> None:
    """
    Main entry point for the application.

    This function simply delegates to the CLI class to start the application.
    It's kept separate to facilitate testing and to provide a clean entry point.
    """
    CLI.start()


if __name__ == "__main__":
    main()
