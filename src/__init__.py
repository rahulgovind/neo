"""
Neo - CLI application for interacting with LLMs to build software.

This package provides tools for using LLMs to assist with software development
through a command-line interface.
"""

import logging
import logging.handlers
import os
import sys
from dotenv import load_dotenv

# Configure logger for this module
logger = logging.getLogger(__name__)

# Load environment variables from .env file if present
load_dotenv()

if "pytest" not in sys.modules:
    NEO_HOME = os.environ.get("NEO_HOME", os.path.expanduser("~/.neo"))
else:
    NEO_HOME = "/tmp/.neo"

def setup_logging() -> None:
    """
    Configure centralized logging for the entire application.
    
    This function sets up:
    - File logging for all messages in {NEO_HOME}/logs/stdout.log
    - File logging for warnings and above in {NEO_HOME}/logs/stderr.log
    - Console logging only if LOG_TO_CONSOLE=1 is set (disabled by default)
    - Conservative logging levels for noisy third-party libraries
    """
    # Get log level from environment or use INFO as default
    log_level_name = os.environ.get("LOG_LEVEL", "INFO")
    log_level = getattr(logging, log_level_name)
    
    # Create log directory if it doesn't exist
    log_dir = os.path.join(NEO_HOME, "logs")
    os.makedirs(log_dir, exist_ok=True)
    
    # Define log file paths
    stdout_log_file = os.path.join(log_dir, "stdout.log")
    stderr_log_file = os.path.join(log_dir, "stderr.log")
    
    # Create a formatter for all handlers
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    
    # Configure root logger and remove any existing handlers
    root_logger = logging.getLogger()
    # Remove all existing handlers to prevent duplication
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    root_logger.setLevel(log_level)
    
    # Create stdout log file handler
    stdout_handler = logging.handlers.RotatingFileHandler(
        stdout_log_file,
        maxBytes=10485760,  # 10MB
        backupCount=3,  # Keep 3 backup files
    )
    stdout_handler.setFormatter(formatter)
    stdout_handler.setLevel(log_level)
    
    # Create stderr log file handler for warnings and above
    stderr_handler = logging.handlers.RotatingFileHandler(
        stderr_log_file,
        maxBytes=10485760,  # 10MB
        backupCount=3,  # Keep 3 backup files
    )
    stderr_handler.setFormatter(formatter)
    stderr_handler.setLevel(logging.WARNING)
    
    # Add handlers to root logger
    root_logger.addHandler(stdout_handler)
    root_logger.addHandler(stderr_handler)
    
    # Only add console handler if LOG_TO_CONSOLE is set to 1
    if os.environ.get("LOG_TO_CONSOLE", "0") == "1":
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        console_handler.setLevel(log_level)
        root_logger.addHandler(console_handler)
        logger.debug("Console logging enabled")
    
    # Set conservative default levels for noisy libraries
    logging.getLogger("openai").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    
    # Log the configuration was successful
    logger.debug("Logging configured successfully")
    logger.debug(f"Standard output logs will be saved to {stdout_log_file}")
    logger.debug(f"Standard error logs will be saved to {stderr_log_file}")
    logger.debug(f"Console logging is {'enabled' if os.environ.get('LOG_TO_CONSOLE', '0') == '1' else 'disabled'}")

setup_logging()