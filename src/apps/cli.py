"""
Command Line Interface module for Neo application.

This module provides the main entry point for the Neo CLI application,
handling command-line arguments, configuring components, and launching the chat.
It ties together all the other modules to create a cohesive application.
"""

import os
import sys
import logging
import argparse
from typing import Dict, Any, Optional, List

from src.core.model import Model
from src.core.context import Context, ContextBuilder
from src.agent.agent import Agent
from src.core.shell import Shell
from src.apps.chat import Chat

# Configure logging
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
        2. Sets up the application components
        3. Launches the interactive chat
        
        It's the main entry point for the application.
        """
        try:
            # Parse command-line arguments
            args = cls._parse_args()
            
            # Configure logging
            cls._setup_logging(args.verbose)
            
            # Log startup information
            logger.info(f"Starting Neo CLI with workspace: {args.workspace}")
            
            # Create and launch the chat
            chat = Chat(
                workspace=args.workspace,
                history_file=args.history_file
            )
            
            # Launch the chat session
            chat.launch()
            
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
            formatter_class=argparse.ArgumentDefaultsHelpFormatter
        )
        
        # Positional argument for workspace
        parser.add_argument(
            "workspace",
            nargs="?",  # Makes it optional
            help="Path to a code workspace directory"
        )
        
        parser.add_argument(
            "--history-file",
            type=str,
            help="Path to file for storing command history"
        )
        
        parser.add_argument(
            "--verbose", "-v",
            action="count",
            default=0,
            help="Increase verbosity (can be used multiple times)"
        )
        
        args = parser.parse_args()
        
        # Process workspace path if provided
        if args.workspace:
            # Expand user directory (e.g., ~/) and environment variables
            workspace_path = os.path.expanduser(args.workspace)
            workspace_path = os.path.expandvars(workspace_path)
            
            # Convert to absolute path if it's not already
            if not os.path.isabs(workspace_path):
                workspace_path = os.path.abspath(workspace_path)
            
            # Validate workspace directory
            if not os.path.isdir(workspace_path):
                raise ValueError(f"Workspace directory does not exist: {workspace_path}")
            
            args.workspace = workspace_path
        else:
            # Default to current directory if no workspace specified
            args.workspace = os.path.abspath('.')
        
        return args
    
    @staticmethod
    def _setup_logging(verbosity: int) -> None:
        """
        Configure logging based on verbosity level.
        
        Args:
            verbosity: Level of verbosity (0=INFO, 1=DEBUG, 2+=DEBUG with more details)
        """
        # Set root logger level based on verbosity
        if verbosity == 0:
            log_level = logging.INFO
        else:
            log_level = logging.DEBUG
        
        # Configure root logger
        logging.basicConfig(
            level=log_level,
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
        
        # For very verbose mode, enable debug logging for all modules
        if verbosity >= 2:
            logging.getLogger().setLevel(logging.DEBUG)
        else:
            # Set conservative default levels for noisy libraries
            logging.getLogger("openai").setLevel(logging.WARNING)
            logging.getLogger("httpx").setLevel(logging.WARNING)
        
        logger.debug(f"Logging configured with verbosity level {verbosity}")


def main() -> None:
    """
    Main entry point for the application.
    
    This function simply delegates to the CLI class to start the application.
    It's kept separate to facilitate testing and to provide a clean entry point.
    """
    CLI.start()


if __name__ == "__main__":
    main()