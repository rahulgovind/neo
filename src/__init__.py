"""
Neo - CLI application for interacting with LLMs to build software.

This package provides tools for using LLMs to assist with software development
through a command-line interface.
"""

import logging
import os
from dotenv import load_dotenv

# Load environment variables from .env file if present
load_dotenv()

# Configure logging
log_level = os.environ.get("LOG_LEVEL", "INFO")
log_file = os.environ.get("LOG_FILE")

# Set up logging format
log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
logging.basicConfig(
    level=getattr(logging, log_level),
    format=log_format,
    handlers=[
        logging.StreamHandler(),
        # Add file handler if LOG_FILE is specified
        *(
            [logging.FileHandler(log_file)] 
            if log_file else []
        )
    ]
)

# Set conservative default levels for noisy libraries
logging.getLogger("httpx").setLevel(logging.WARNING)

# Import version from VERSION file for use within the package
try:
    with open(os.path.join(os.path.dirname(__file__), "..", "VERSION"), "r") as f:
        __version__ = f.read().strip()
except FileNotFoundError:
    # This can happen if package is not installed in development mode
    __version__ = "unknown"