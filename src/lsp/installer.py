"""
LSP server installation utilities.

Checks and reports on Python LSP server installation status.
"""

import logging
import subprocess
from typing import List

# Configure logging
logger = logging.getLogger(__name__)

def run_command(command: List[str]) -> bool:
    """Run a command and return its success status."""
    try:
        logger.info(f"Running: {' '.join(command)} > /dev/null 2>&1")
        subprocess.run(
            command,
            stdout=subprocess.DEVNULL, 
            stderr=subprocess.DEVNULL,
            check=True
        )
        return True
    except subprocess.CalledProcessError:
        return False
    except Exception as e:
        logger.error(f"Error executing command '{command}': {e}")
        return False

def is_server_installed(language: str) -> bool:
    """Check if a language server is installed.

    Raises:
        ValueError: If language other than 'python' is requested
    """
    if language.lower() != "python":
        raise ValueError(f"Unsupported language: {language}. Only Python is supported.")
    
    # Check for pylsp command
    return run_command(["pylsp", "--help"])

def install(language: str) -> bool:
    """Check and report Python LSP server installation status.

    Does not actually install anything, just confirms if already installed.

    Raises:
        ValueError: If language other than 'python' is requested
    """
    if language.lower() != "python":
        raise ValueError(f"Unsupported language: {language}. Only Python is supported.")
    
    if is_server_installed(language):
        logger.info("Python language server is already installed")
        return True
    
    logger.warning("Python language server (pylsp) is not installed.")
    logger.info("Please install it via pip: pip install python-lsp-server")
    return False
