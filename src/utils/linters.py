"""
Linting utilities for checking code quality.

This module provides functionality to check code quality using various linters.
Currently supports:
- Python code linting with pylint

Implementation uses a registry pattern to make it easy to add new linters
for additional file types in the future.

To add a new linter:
1. Create a new class that inherits from LinterBase
2. Implement the lint() method
3. Register it with @register_linter('.extension')
"""

import logging
import os
import re
import subprocess
import tempfile
from typing import Dict, List, Tuple, Optional, Type, Callable

# Configure logging
logger = logging.getLogger(__name__)


class LintError(Exception):
    """Exception raised for linting errors."""

    def __init__(self, message, lint_output=None):
        self.message = message
        self.lint_output = lint_output
        super().__init__(self.message)


# Registry to store all linter classes
LINTER_REGISTRY = {}


def register_linter(file_extension: str) -> Callable:
    """
    Decorator to register a linter class for a specific file extension.

    Args:
        file_extension: The file extension this linter supports (e.g., '.py')

    Returns:
        Decorator function
    """

    def decorator(linter_class):
        LINTER_REGISTRY[file_extension] = linter_class
        return linter_class

    return decorator


class LinterBase:
    """Base class for all linters."""

    def __init__(self):
        self.name = "Base Linter"

    def lint(self, content: str, filename: str) -> Tuple[bool, Optional[str]]:
        """
        Lint the provided content.

        Args:
            content: The code content to lint
            filename: The name of the file (used for determining file type)

        Returns:
            Tuple of (is_valid, error_message)
            is_valid: True if linting passed, False otherwise
            error_message: None if linting passed, otherwise a string with error details
        """
        raise NotImplementedError("Subclasses must implement this method")


@register_linter(".py")
class PythonLinter(LinterBase):
    """Linter for Python code using pylint."""

    def __init__(self):
        super().__init__()
        self.name = "Python Linter (pylint)"

    def supports_file(self, filename: str) -> bool:
        """Check if the file is a Python file."""
        return filename.lower().endswith(".py")

    def lint(self, content: str, filename: str) -> Tuple[bool, Optional[str]]:
        """
        Lint Python code using the 'pylint' tool.

        Args:
            content: Python code to lint
            filename: Name of the file (for reporting purposes)

        Returns:
            Tuple of (is_valid, error_message)
        """
        logger.info(f"Linting Python file: {filename}")

        # Create a temporary file for linting
        with tempfile.NamedTemporaryFile(suffix=".py", delete=False) as temp_file:
            temp_filename = temp_file.name
            temp_file.write(content.encode("utf-8"))

        try:
            # Run pylint on the temporary file
            # Disable R (Refactor) and C (Convention) checks
            cmd = ["pylint", "--disable=R,C,W", "--output-format=text", temp_filename]
            result = subprocess.run(cmd, capture_output=True, text=True)

            # Check if linting failed
            if result.returncode != 0:
                # Clean up the output to make it more readable
                error_output = self._format_lint_output(result.stdout)
                return False, error_output

            return True, None

        except subprocess.SubprocessError as e:
            logger.error(f"Error running pylint: {str(e)}")
            return False, f"Failed to run pylint: {str(e)}"
        finally:
            # Clean up the temporary file
            if os.path.exists(temp_filename):
                os.unlink(temp_filename)

    def _format_lint_output(self, output: str) -> str:
        """Format pylint output to be more readable."""
        # Extract just the important parts of the pylint output
        lines = output.splitlines()
        filtered_lines = []

        for line in lines:
            # Skip module score and some headers
            if "rated at" in line or "----" in line or not line.strip():
                continue
            filtered_lines.append(line)

        return "\n".join(filtered_lines)


@register_linter(".js")
class JavaScriptLinter(LinterBase):
    """Linter for JavaScript code.

    Note: This is a placeholder implementation. To make it functional,
    you would need to add actual JS linting functionality using a tool
    like ESLint and update requirements.txt accordingly.
    """

    def __init__(self):
        super().__init__()
        self.name = "JavaScript Linter"

    def lint(self, content: str, filename: str) -> Tuple[bool, Optional[str]]:
        """
        Placeholder for JavaScript linting.

        In a real implementation, this would run ESLint or another JavaScript linter.

        Args:
            content: JavaScript code to lint
            filename: Name of the file

        Returns:
            Tuple of (is_valid, error_message)
        """
        logger.info(f"JavaScript linting not fully implemented for: {filename}")
        # This is where you would add actual JavaScript linting logic
        # For demonstration purposes, we'll just return a success
        return True, None


def get_linter_for_file(filename: str) -> Optional[LinterBase]:
    """
    Get the appropriate linter for the given file based on its extension.

    Args:
        filename: The name of the file to get a linter for

    Returns:
        A linter instance or None if no linter supports the file type
    """
    _, ext = os.path.splitext(filename.lower())

    if ext in LINTER_REGISTRY:
        return LINTER_REGISTRY[ext]()

    return None


def lint_code(content: str, filename: str) -> Tuple[bool, Optional[str]]:
    """
    Lint the provided code content.

    Args:
        content: The code content to lint
        filename: The name of the file (used for determining the linter)

    Returns:
        Tuple of (is_valid, error_message)
        is_valid: True if linting passed, False otherwise
        error_message: None if linting passed, otherwise a string with error details
    """
    linter = get_linter_for_file(filename)

    if linter:
        logger.info(f"Using {linter.name} for {filename}")
        return linter.lint(content, filename)

    # No linter found for this file type
    logger.info(f"No linter available for {filename}")
    return True, None


# List of supported file types for documentation purposes
def get_supported_file_types() -> List[str]:
    """
    Get a list of all file extensions supported by registered linters.

    Returns:
        List of supported file extensions (e.g., ['.py', '.js'])
    """
    return list(LINTER_REGISTRY.keys())
