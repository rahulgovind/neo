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

from src.model import Model
from src.function import FunctionRegistry
from src.agent import Agent
from src.chat import Chat, ChatFactory

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
    
    - You SHOULD explain your reasoning clearly and offer context for your suggestions. Do this prior to making any function calls.
    - You MUST not write anything after a function call.
    - YOU SHOULD make incremental, focused changes when modifying files rather than rewriting everything.
    
    Be helpful, accurate, and respectful in your interactions.
    """
    
    # Default package for function discovery
    FUNCTIONS_PACKAGE = "src.functions"
    
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
            
            # Create the model, function registry, and agent
            model, agent = cls._setup_components(args)
            
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
        
        # Optional flag for workspace (for backward compatibility)
        parser.add_argument(
            "--workspace", "-w",
            dest="workspace_flag",
            type=str,
            help="Path to a code workspace directory (alternative to positional argument)"
        )
        
        parser.add_argument(
            "--instructions",
            type=str,
            help="Path to a file containing custom system instructions"
        )
        
        parser.add_argument(
            "--history-file",
            type=str,
            help="Path to file for storing command history"
        )
        
        parser.add_argument(
            "--functions-package",
            type=str,
            default="src.functions",
            help="Package name to discover function implementations"
        )
        
        parser.add_argument(
            "--verbose", "-v",
            action="count",
            default=0,
            help="Increase verbosity (can be used multiple times)"
        )
        
        args = parser.parse_args()
        
        # Determine workspace path (prioritize flag over positional for backwards compatibility)
        workspace_path = args.workspace_flag if args.workspace_flag else args.workspace
        
        # Process workspace path if provided
        if workspace_path:
            # Expand user directory (e.g., ~/) and environment variables
            workspace_path = os.path.expanduser(workspace_path)
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
            # Initialize the model
            logger.debug("Initializing Model")
            model = Model()
            
            # Create function registry and add functions
            logger.debug("Setting up function registry")
            registry = FunctionRegistry()
            
            # Dynamically discover and load functions from the functions package
            functions_package = args.functions_package or cls.FUNCTIONS_PACKAGE
            try:
                logger.info(f"Discovering functions from package: {functions_package}")
                # Pass workspace to function constructors if available
                kwargs = {"workspace": args.workspace} if args.workspace else {}
                registry.discover_and_load_functions(functions_package, **kwargs)
            except ImportError as e:
                # Log but don't fail if the functions package doesn't exist yet
                logger.warning(f"Functions package '{functions_package}' not found: {e}")
            except Exception as e:
                logger.error(f"Error loading functions from package '{functions_package}': {e}")
                # Don't re-raise here to allow the application to start with core functions
            
            # Log the total number of registered functions
            logger.info(f"Total registered functions: {len(registry.functions)}")
            
            # Get system instructions
            instructions = cls._load_instructions(args.instructions)
            
            # Create the agent
            logger.debug("Initializing Agent")
            agent = Agent(
                model=model,
                function_registry=registry,
                instructions=instructions,
            )
            
            logger.info("All components initialized successfully")
            return model, agent
            
        except Exception as e:
            logger.error(f"Error setting up components: {e}")
            # Re-raise with additional context to help with debugging
            raise Exception(f"Failed to initialize application components: {str(e)}") from e
    
    @classmethod
    def _load_instructions(cls, instructions_file: Optional[str]) -> str:
        """
        Load system instructions from a file or use defaults.
        
        Args:
            instructions_file: Path to file containing custom instructions, or None
            
        Returns:
            String containing the system instructions
        """
        if instructions_file and os.path.isfile(instructions_file):
            try:
                logger.info(f"Loading custom instructions from {instructions_file}")
                with open(instructions_file, 'r', encoding='utf-8') as f:
                    return f.read()
            except Exception as e:
                logger.error(f"Failed to load instructions file: {e}")
                logger.info("Falling back to default instructions")
                return cls.DEFAULT_INSTRUCTIONS
        else:
            logger.debug("Using default instructions")
            return cls.DEFAULT_INSTRUCTIONS


def main() -> None:
    """
    Main entry point for the application.
    
    This function simply delegates to the CLI class to start the application.
    It's kept separate to facilitate testing and to provide a clean entry point.
    """
    CLI.start()


if __name__ == "__main__":
    main()