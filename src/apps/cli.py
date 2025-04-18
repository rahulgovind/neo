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
import asyncio
from typing import Dict, Any, Optional, List
import traceback

# Logging is configured in src/__init__.py when imported
from src.neo.session import Session
from src.neo.agent.agent import Agent
from src.neo.shell.shell import Shell
from src.neo.service.service import Service

# Import launch function directly from chat module
from src.apps.chat import launch

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
        2. Delegates to the appropriate Service class methods based on the subcommand

        It's the main entry point for the application.
        """
        try:
            # Parse command-line arguments
            args = cls._parse_args()

            # Execute the appropriate subcommand
            if args.subcommand == "chat":
                workspace = args.workspace or os.getcwd()
                logger.info(
                    f"Starting interactive chat for workspace: {workspace}"
                )
                # Use the launch function directly from the chat module
                try:
                    # Session creation is handled within launch function
                    launch()
                except Exception as e:
                    logger.error(f"Error in chat launch: {e}", exc_info=True)
                    print(f"\nEncountered an error: {e}")

            elif args.subcommand == "create-session":
                # Create a new session using Service's async method
                logger.info(
                    f"Using workspace: {args.workspace} to create session '{args.session}'"
                )
                session = Service.create_session(
                    session_name=args.session, workspace=args.workspace
                )
                print(
                    f"Session '{session.session_name}' created successfully "
                    + f"(Session ID: {session.session_id})"
                )
                print(f"Workspace: {session.workspace}")
            elif args.subcommand == "message":
                # Process a single message using the Service class method
                session_id = None
                
                if args.session:
                    logger.info(f"Processing message for session '{args.session}'")
                    # If session is specified then try to find it by listing sessions and matching the name
                    all_sessions = Service.list_sessions()
                    
                    for session in all_sessions:
                        if session.session_name == args.session:
                            session_id = session.session_id
                            break
                    
                    if not session_id:
                        print(f"Error: Session '{args.session}' not found.")
                        logger.error(f"Session '{args.session}' not found for message command.")
                        sys.exit(1)

                # Use the Service.message method with the session_id
                for message in Service.message(msg=args.message, session_id=session_id):
                    print(message)
            elif args.subcommand == "list-sessions":
                logger.info("Listing persistent sessions.")
                sessions = Service.list_sessions()
                for session in sessions:
                    print(
                        f"Session ID: {session.session_id}, Name: {session.session_name}, Workspace: {session.workspace}"
                    )

        except KeyboardInterrupt:
            # Handle Ctrl+C in the main thread
            logger.info("Application interrupted by user")
            print("\nExiting Neo CLI...")
            sys.exit(0)

        except NotImplementedError as nie:
            print(f"\nError: {nie}")
            sys.exit(1)

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
        subparsers = parser.add_subparsers(
            dest="subcommand", help="Subcommand to run", required=True
        )

        # 1. Chat subcommand - interactive chat session
        chat_parser = subparsers.add_parser(
            "chat", help="Start an interactive chat session"
        )
        chat_parser.add_argument("--workspace", "-w", default=os.getcwd(), help="Path to a code workspace directory (optional, defaults to current directory)")
        chat_parser.add_argument(
            "--history-file",
            type=str,
            help="Path to file for storing command history (Not currently used by InteractiveChat)",
        )

        # 2. Create-session subcommand - create a new session
        create_session_parser = subparsers.add_parser(
            "create-session", help="Create a new persistent session"
        )
        create_session_parser.add_argument(
            "--session", "-s", type=str, help="Name of the session to create"
        )
        create_session_parser.add_argument(
            "workspace", help="Path to a code workspace directory"
        )

        # 3. Message subcommand - process a single message
        message_parser = subparsers.add_parser(
            "message", help="Send a single message to a session (headless)"
        )
        message_parser.add_argument("message", help="Message content to process")
        message_parser.add_argument(
            "--session",
            "-s",
            type=str,
            required=False,
            help="Name of the session to use (optional, will create a temporary session if not provided)",
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
