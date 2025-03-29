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
import random
import datetime
from typing import Dict, Any, Optional, List

from src.core.model import Model
from src.core.context import Context
from src.agent import Agent
from src.core.shell import Shell
from src.core import env
from src.apps.chat import Chat, ChatFactory

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
    
    # Default system instructions for the agent
    DEFAULT_INSTRUCTIONS = """
    You are Neo, an AI assistant that can help with a wide range of tasks.
    
    You can assist users by:
    1. Understanding their requirements and questions
    2. Providing relevant information and explanations
    3. Engaging in thoughtful conversation
    
    - You SHOULD explain your reasoning clearly and offer context for your suggestions. Do this prior to making any command calls.
    - You MUST not write anything after a command call.
    - YOU SHOULD make incremental, focused changes when modifying files rather than rewriting everything.
    
    Be helpful, accurate, and respectful in your interactions.
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
            
            # Create the agent
            agent = cls._setup_components(args)
            
            # Create and launch the chat
            chat = ChatFactory.create(
                agent=agent,
                workspace=args.workspace,
                history_file=args.history_file,
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
        
        logger.debug(f"Logging configured with verbosity level {verbosity}")
    
    @classmethod
    def _setup_components(cls, args: argparse.Namespace) -> tuple:
        """
        Set up the core application components.
        
        This method initializes:
        1. The Model for LLM communication
        2. Function registry with available functions
        3. Agent with instructions and functions
        
        Args:
            args: Parsed command-line arguments
            
        Returns:
            Tuple of (model, agent)
            
        Raises:
            ValueError: If required environment variables are missing
            Exception: If component initialization fails
        """
        try:
            # Initialize the environment
            logger.debug("Initializing environment")
            env.initialize()
            
            # Generate a session ID in the format YYYYMMDD_HHMMSS_XXXX
            now = datetime.datetime.now()
            date_part = now.strftime("%Y%m%d")
            time_part = now.strftime("%H%M%S")
            random_part = f"{random.randint(1000, 9999)}"
            session_id = f"{date_part}_{time_part}_{random_part}"
            
            # Initialize the context before other components
            logger.debug(f"Initializing context with session_id={session_id} and workspace={args.workspace}")
            from src.core.context import new_context
            # Use the context manager pattern
            with new_context(session_id=session_id, workspace=args.workspace) as ctx:
                # Initialize the shell
                logger.debug("Initializing Shell")
                shell = Shell()
                
                # Initialize the model
                logger.debug("Initializing Model")
                model = Model()
                
                # Set the model and shell in the environment
                env.set_model(model)
                env.set_shell(shell)
            
            # Get system instructions - using default instructions
            instructions = cls.DEFAULT_INSTRUCTIONS
            
            # Create the agent
            logger.debug("Initializing Agent")
            agent = Agent(
                instructions=instructions,
            )
            
            logger.info("Agent initialized successfully")
            return agent
            
        except Exception as e:
            logger.error(f"Error setting up components: {e}")
            # Re-raise with additional context to help with debugging
            raise Exception(f"Failed to initialize application components: {str(e)}") from e
    



def main() -> None:
    """
    Main entry point for the application.
    
    This function simply delegates to the CLI class to start the application.
    It's kept separate to facilitate testing and to provide a clean entry point.
    """
    CLI.start()


if __name__ == "__main__":
    main()