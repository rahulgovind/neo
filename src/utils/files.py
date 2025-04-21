"""
Core file system operations.

This module provides the core logic for file operations:
- read: Read file contents with optional line numbering
- overwrite: Replace a file's contents completely
"""


import os
import logging
from typing import List, Tuple, Optional
from dataclasses import dataclass




@dataclass
class FileContent:
    """Structured representation of file content with metadata."""
    content: str  # The raw content without line numbers
    lines: List[str]  # List of individual lines
    line_count: int  # Total number of lines in the file
    displayed_range: Tuple[int, int]  # The range of lines displayed (0-indexed)
    
    def format(self, include_line_numbers: bool = True) -> str:
        """
        Format the content with or without line numbers.
        
        Args:
            include_line_numbers: Whether to include line numbers in the output
            
        Returns:
            Formatted string representation of the file content
        """
        result_lines = []
        
        # Add indicator for lines before the selection if truncated at start
        start_line = self.displayed_range[0]
        if start_line > 0:
            lines_before = start_line
            result_lines.append(f"... {lines_before} additional lines")
        
        # Add lines either with or without line numbers
        if include_line_numbers:
            # Add lines with line numbers
            for i, line in enumerate(self.lines, start=start_line + 1):  # Convert to 1-indexed
                result_lines.append(f"{i}:{line}")
        else:
            # Add lines without line numbers
            result_lines.extend(self.lines)
        
        # Add indicator for lines after the selection if truncated at end
        end_line = self.displayed_range[1]
        if end_line < self.line_count:
            lines_after = self.line_count - end_line
            result_lines.append(f"... {lines_after} additional lines")
            
        return "\n".join(result_lines)
    
    # Add backward compatible methods
    def format_with_line_numbers(self) -> str:
        """Format the content with line numbers (deprecated, use format(True))."""
        return self.format(include_line_numbers=True)
    
    def format_without_line_numbers(self) -> str:
        """Format the content without line numbers (deprecated, use format(False))."""
        return self.format(include_line_numbers=False)
    
    def __str__(self) -> str:
        """String representation with line numbers by default."""
        return self.format(include_line_numbers=True)



from src.utils.linters import lint_code, get_supported_file_types


# Configure logging
logger = logging.getLogger(__name__)


def read(
    path: str,
    from_: Optional[int] = None,
    until: Optional[int] = None,
    limit: int = -1,
) -> FileContent:
    """
    Reads content from a single file at the specified path.
    Special command characters are automatically escaped with Unicode escapes.

    Args:
        path: Path to the file to read
        from_: Optional start line number (1-indexed, or negative to count from end)
        until: Optional end line number (1-indexed, or negative to count from end)
        limit: Maximum number of lines to return (default: 200). Use -1 for unlimited.


    Returns:
        FileContent object containing the file contents and metadata

    Raises:
        FileNotFoundError: If the file does not exist
        IsADirectoryError: If the path is a directory, not a file
        PermissionError: If the user lacks permission to read the file
        UnicodeDecodeError: If the file cannot be decoded as text
        ValueError: If the line range parameters are invalid
        IOError: For other file-related errors
    """
    logger.info("Reading file '%s'", path)

    if not os.path.exists(path):
        logger.warning("File not found: %s", path)
        raise FileNotFoundError(f"File not found: {path}")

    if not os.path.isfile(path):
        logger.warning("Path is not a file: %s", path)
        raise IsADirectoryError(f"Path is not a file: {path}")


    with open(path, "r", encoding="utf-8") as f:
        # Read the file content directly to preserve the exact format including final newline
        content = f.read()

        # Split into lines for processing
        lines = content.split("\n")
        total_lines = len(lines)

        # Set default start and end lines
        start_line = 0
        end_line = total_lines
        read_entire_file = limit == -1

        # Process from_ parameter if provided
        if from_ is not None:
            # Handle negative indices (counting from end)
            if from_ < 0:
                start_line = max(0, total_lines + from_)
            else:
                # Convert to 0-indexed
                start_line = max(0, from_ - 1)

        # Process until parameter if provided
        if until is not None:
            # Handle negative indices
            if until < 0:
                end_line = max(start_line + 1, total_lines + until + 1)
            else:
                # Convert to 0-indexed + 1 (to include the end line)
                end_line = min(total_lines, until)
        elif from_ is not None and until is None:
            # If only from_ is specified, read from that line to a reasonable number of lines after
            # (unless limit is -1, in which case read to the end)
            if not read_entire_file:
                end_line = min(start_line + 200, total_lines)

        # If only until is specified, show a reasonable number of lines before it
        if until is not None and from_ is None:
            start_line = max(0, end_line - 200)

        # Validate range boundaries
        start_line = max(0, min(start_line, total_lines - 1))
        end_line = max(start_line + 1, min(end_line, total_lines))

        # Apply line limit unless reading entire file (limit=-1)
        if not read_entire_file and limit > 0 and (end_line - start_line) > limit:
            end_line = start_line + limit

        # Get the selected lines
        selected_lines = lines[start_line:end_line]

        # Create the FileContent object
        file_content = FileContent(
            content=content,
            lines=selected_lines,
            line_count=total_lines,
            displayed_range=(start_line, end_line)
        )

        logger.info(
            "Successfully read file: %s (showing %d of %d lines)",
            path, len(selected_lines), total_lines
        )

        return file_content




def overwrite(  # pylint: disable=unused-argument
    workspace: str, path: str, content: str, enable_lint: bool = True  # Kept for API compatibility, lint is always checked
) -> Tuple[bool, int, int]:



    """
    Creates a new file or completely overwrites an existing file's content.

    Args:
        workspace: Root workspace directory path
        path: Path to the file, relative to workspace
        content: New content for the file
        enable_lint: Whether to fail on linting errors (default: True)

    Returns:
        Tuple of (success, lines_added, lines_deleted)

    Raises:
        Various exceptions related to file operations
        RuntimeError: If linting fails and strict=True
    """
    # Normalize the path
    file_path = _normalize_path(workspace, path)

    # Count lines in the existing file if it exists
    old_lines = 0
    file_existed = os.path.exists(file_path)

    if file_existed:
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                old_content = f.read()
                old_lines = _count_lines(old_content)
        except (IOError, OSError, UnicodeDecodeError) as e:
            # Handle specific file-related exceptions
            logger.warning("Couldn't read existing file for line count: %s", e)
            # Continue with update even if we couldn't get the line count


    # Create directory structure if needed
    _ensure_directory_exists(file_path)

    # Check for linting issues if applicable
    lint_warnings = None
    _, file_ext = os.path.splitext(path.lower())

    # Get supported file extensions for linting
    supported_extensions = get_supported_file_types()

    if file_ext in supported_extensions:
        # We have a linter for this file type
        logger.info("Linting file with extension %s: %s", file_ext, path)

        is_valid, lint_output = lint_code(content, path)
        if not is_valid and lint_output:
            lint_warnings = lint_output

    # Write the new content
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(content)

    # Count lines in updated content
    new_lines = _count_lines(content)
    lines_added = new_lines
    lines_deleted = old_lines

    if file_existed:
        # If file already existed, report difference
        logger.info("Updated file: %s (+%d,-%d)", path, new_lines, old_lines)
    else:
        # If file is new
        logger.info("Created file: %s (+%d lines)", path, new_lines)


    # If we have lint warnings, handle based on strict mode
    if lint_warnings:
        # Build a more informative error message
        error_msg = [
            "File updated successfully, but linting failed for {}:".format(path),
            "",
            "Linting errors:",
            "{}".format(lint_warnings),
            "",
            "Note: The file has been written despite linting errors.",
            "Please fix the issues and update the file again."
        ]
        
        # Always raise an error for lint failures
        raise RuntimeError("\n".join(error_msg))


    return True, lines_added, lines_deleted




def _count_lines(content: str) -> int:
    """Count the number of lines in the content."""
    if not content:
        return 0
    # Count the number of newlines, and add 1 if the content doesn't end with a newline
    return content.count("\n") + (0 if content.endswith("\n") else 1)


def _normalize_path(workspace: str, path: str) -> str:
    """Normalize a path relative to the workspace."""
    # If path is absolute, use it directly (after normalization)
    if os.path.isabs(path):
        return os.path.normpath(path)

    # Otherwise, join with workspace
    return os.path.normpath(os.path.join(workspace, path))


def _ensure_directory_exists(file_path: str) -> None:
    """
    Ensure the directory for a file exists, creating it if necessary.

    Args:
        file_path: Path to the file
    """
    directory = os.path.dirname(file_path)
    if directory and not os.path.exists(directory):
        os.makedirs(directory, exist_ok=True)
        logger.info("Created directory: %s", directory)

