"""
Core file system operations.

This module provides the core logic for file operations:
- read: Read file contents with optional line numbering
- overwrite: Replace a file's contents completely
- patch: Apply a diff to update a file
"""

import os
import re
import sys
import logging
import textwrap
from contextlib import contextmanager
from typing import Dict, Any, List, Tuple, Optional
from dataclasses import dataclass
from enum import Enum
from src.core.constants import (
    COMMAND_START,
    COMMAND_END,
    STDIN_SEPARATOR,
    ERROR_PREFIX,
    SUCCESS_PREFIX,
)
from src.core.messages import _escape_special_chars, _unescape_special_chars
from src.utils.linters import lint_code, get_supported_file_types, LintError

# Configure logging
logger = logging.getLogger(__name__)


def read(
    path: str,
    include_line_numbers: bool = False,
    from_: Optional[int] = None,
    until: Optional[int] = None,
    limit: int = -1,
) -> str:
    """
    Reads content from a single file at the specified path.
    Special command characters are automatically escaped with Unicode escapes.

    Args:
        path: Path to the file to read
        include_line_numbers: Whether to prefix each line with its line number
        from_: Optional start line number (1-indexed, or negative to count from end)
        until: Optional end line number (1-indexed, or negative to count from end)
        limit: Maximum number of lines to return (default: 200). Use -1 for unlimited.

    Returns:
        File contents, optionally with line numbers, or error message
    """
    logger.info(f"Reading file '{path}'")

    try:
        if not os.path.exists(path):
            logger.warning(f"File not found: {path}")
            return f"File not found: {path}"

        if not os.path.isfile(path):
            logger.warning(f"Path is not a file: {path}")
            return f"Path is not a file: {path}"

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

            try:
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
                        end_line = min(start_line + 100, total_lines)

                # If only until is specified, show a reasonable number of lines before it
                if until is not None and from_ is None:
                    start_line = max(0, end_line - 100)

            except ValueError as e:
                logger.error(
                    f"Invalid line numbers: from={from_}, until={until} - {str(e)}"
                )
                return f"Error: Invalid line numbers: from={from_}, until={until} - {str(e)}"

            # Validate range boundaries
            start_line = max(0, min(start_line, total_lines - 1))
            end_line = max(start_line + 1, min(end_line, total_lines))

            # Apply line limit unless reading entire file (limit=-1)
            if not read_entire_file and limit > 0 and (end_line - start_line) > limit:
                end_line = start_line + limit

            # Get the selected lines
            selected_lines = lines[start_line:end_line]

            # Prepare result with truncation indicators
            result_lines = []

            # Add indicator for lines before the selection
            if start_line > 0:
                # For 1-indexed display, we need to account for the different indexing
                # If we're starting at index 19 (0-indexed), that means lines 1-20 are omitted
                # So the number to display is the 1-indexed line number of the first displayed line, minus 1
                first_display_line = (
                    start_line + 1
                )  # Convert to 1-indexed for user display
                omitted_lines = first_display_line - 1
                result_lines.append(f"... {omitted_lines} additional lines")

            # Format the result
            if include_line_numbers:
                # Add line numbers - for unlimited display, we need to start counting from 1
                # otherwise, adjust line numbers based on the starting line
                if read_entire_file:
                    numbered_lines = [
                        f"{i+1}:{line}" for i, line in enumerate(selected_lines)
                    ]
                else:
                    numbered_lines = [
                        f"{i+1}:{line}"
                        for i, line in enumerate(selected_lines, start=start_line)
                    ]
                result_lines.extend(numbered_lines)
            else:
                result_lines.extend(selected_lines)

            # Add indicator for lines after the selection
            if end_line < total_lines:
                # Calculate exactly how many lines are omitted after the current selection
                omitted_after = total_lines - end_line
                result_lines.append(f"... {omitted_after} additional lines")

            result = "\n".join(result_lines)

            logger.info(
                f"Successfully read file: {path} (showing {len(selected_lines)} of {total_lines} lines)"
            )
            return result

    except UnicodeDecodeError:
        logger.error(f"File is not text or has unknown encoding: {path}")
        return f"Error: File is not text or has unknown encoding: {path}"
    except PermissionError:
        logger.error(f"Permission denied reading file: {path}")
        return f"Error: Permission denied reading file: {path}"
    except Exception as e:
        logger.error(f"Error reading file {path}: {str(e)}")
        return f"Error reading file {path}: {str(e)}"


def overwrite(workspace: str, path: str, content: str, enable_lint: bool = True) -> Tuple[bool, int, int]:
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
        except Exception as e:
            logger.warning(f"Couldn't read existing file for line count: {e}")
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
        logger.info(f"Linting file with extension {file_ext}: {path}")
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
        logger.info(f"Updated file: {path} (+{new_lines},-{old_lines})")
    else:
        # If file is new
        logger.info(f"Created file: {path} (+{new_lines} lines)")

    # If we have lint warnings, handle based on strict mode
    if lint_warnings:
        # Build a more informative error message
        error_msg = [
            f"File updated successfully, but linting failed for {path}:",
            "",
            f"Linting errors:",
            f"{lint_warnings}",
            "",
            "Note: The file has been written despite linting errors."
        ]
        
        if strict:
            error_msg.append("Please fix the issues and update the file again.")
            raise RuntimeError("\n".join(error_msg))
        else:
            # Just log the warning but don't raise an exception
            logger.warning("\n".join(error_msg))

    return True, lines_added, lines_deleted


def patch(file_path: str, diff_text: str) -> str:
    """
    Apply a diff to update a file.

    Args:
        file_path: Path to the file that needs to be updated
        diff_text: The diff containing @DELETE, @INSERT, and/or @UPDATE directives

    Returns:
        Updated file content as a string

    Raises:
        RuntimeError: If the diff could not be applied
    """
    logger.info(f"Applying diff to file: {file_path}")

    # Read the current content of the file
    if not os.path.exists(file_path):
        raise RuntimeError(f"File not found: {file_path}")

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            lines = f.read().split("\n")
    except Exception as e:
        raise RuntimeError(f"Error reading file: {e}")

    # Parse the diff
    current_op = None
    current_section = None
    pending_updates = []

    # Sections for the current UPDATE operation
    before_lines = []
    after_lines = []

    # Helper function to process a line with line_number:content format
    def parse_line_entry(line):
        match = re.match(r"^(\d+):(.*)$", line)
        if not match:
            raise RuntimeError(
                f"Invalid line format in diff: '{line}'. Expected format: LINE_NUMBER:CONTENT"
            )
        line_num = int(match.group(1)) - 1  # Convert to 0-indexed
        content = match.group(2)
        return line_num, content

    # Process each line of the diff
    for line in diff_text.strip().split("\n"):
        line = line.strip()

        # Skip empty lines and comment lines
        if not line or line.startswith("#"):
            continue

        # Check for operation directives
        if line == "@DELETE":
            # Finalize any in-progress UPDATE operations
            if current_op == "@UPDATE" and before_lines and after_lines:
                pending_updates.append(("@UPDATE", before_lines, after_lines))
                before_lines = []
                after_lines = []

            current_op = "@DELETE"
            current_section = None
            continue

        if line == "@INSERT":
            # Finalize any in-progress UPDATE operations
            if current_op == "@UPDATE" and before_lines and after_lines:
                pending_updates.append(("@UPDATE", before_lines, after_lines))
                before_lines = []
                after_lines = []

            current_op = "@INSERT"
            current_section = None
            continue

        if line == "@UPDATE":
            # Finalize any in-progress UPDATE operations
            if current_op == "@UPDATE" and before_lines and after_lines:
                pending_updates.append(("@UPDATE", before_lines, after_lines))
                before_lines = []
                after_lines = []

            current_op = "@UPDATE"
            current_section = None
            continue

        # Process UPDATE sections
        if current_op == "@UPDATE":
            if line == "BEFORE":
                current_section = "BEFORE"
                continue
            elif line == "AFTER":
                current_section = "AFTER"
                continue

            # Process content in BEFORE/AFTER sections
            if current_section == "BEFORE":
                try:
                    line_num, content = parse_line_entry(line)
                    before_lines.append((line_num, content))
                except RuntimeError as e:
                    raise RuntimeError(f"Error in BEFORE section: {e}")
            elif current_section == "AFTER":
                try:
                    line_num, content = parse_line_entry(line)
                    after_lines.append((line_num, content))
                except RuntimeError as e:
                    raise RuntimeError(f"Error in AFTER section: {e}")
            else:
                raise RuntimeError(f"Missing BEFORE/AFTER section in @UPDATE operation")

        # Process DELETE and INSERT operations
        elif current_op == "@DELETE":
            try:
                line_num, content = parse_line_entry(line)
                pending_updates.append(("@DELETE", [(line_num, content)], None))
            except RuntimeError as e:
                raise RuntimeError(f"Error in DELETE operation: {e}")

        elif current_op == "@INSERT":
            try:
                line_num, content = parse_line_entry(line)
                pending_updates.append(("@INSERT", [(line_num, content)], None))
            except RuntimeError as e:
                raise RuntimeError(f"Error in INSERT operation: {e}")

        else:
            raise RuntimeError(
                f"Unexpected line in diff: '{line}'. Must be preceded by @DELETE, @UPDATE, or @INSERT"
            )

    # Finalize the last UPDATE operation if there is one
    if current_op == "@UPDATE" and before_lines and after_lines:
        pending_updates.append(("@UPDATE", before_lines, after_lines))
        before_lines = []
        after_lines = []

    # Validate that we have a non-empty list of updates
    if not pending_updates:
        raise RuntimeError("No valid diff operations found")

    # Apply the updates
    # We need to apply them in the correct order (those affecting earlier lines first)
    # Sort by the first line number in each operation
    pending_updates.sort(key=lambda x: x[1][0][0] if x[1] else 0)

    # Keep track of line number adjustments as we apply updates
    line_offset = 0

    for op, before, after in pending_updates:
        if op == "@DELETE":
            # Delete a line
            line_num = before[0][0] + line_offset
            expected_content = before[0][1]

            # Check if line number is valid
            if line_num < 0 or line_num >= len(lines):
                raise RuntimeError(
                    f"Line number {line_num + 1} out of range (file has {len(lines)} lines)"
                )

            # Verify the line content matches what's expected
            if lines[line_num] != expected_content:
                raise RuntimeError(
                    f"Content mismatch for line {line_num + 1}:\n"
                    f"Expected: '{expected_content}'\n"
                    f"Actual: '{lines[line_num]}'"
                )

            # Delete the line
            lines.pop(line_num)
            line_offset -= 1  # Adjust offset for subsequent operations

        elif op == "@INSERT":
            # Insert a line
            line_num = before[0][0] + line_offset
            content = before[0][1]

            # Check if line number is valid (can insert at end of file)
            if line_num < 0 or line_num > len(lines):
                raise RuntimeError(
                    f"Insert position {line_num + 1} out of range (file has {len(lines)} lines)"
                )

            # Insert the line
            lines.insert(line_num, content)
            line_offset += 1  # Adjust offset for subsequent operations

        elif op == "@UPDATE":
            # Update a section
            # First, verify the BEFORE section matches
            start_line = before[0][0] + line_offset

            # Check if the starting line is valid
            if start_line < 0 or start_line >= len(lines):
                raise RuntimeError(
                    f"Update start line {start_line + 1} out of range (file has {len(lines)} lines)"
                )

            # Check each BEFORE line matches the file
            for i, (line_num, expected_content) in enumerate(before):
                adjusted_line_num = line_num + line_offset

                # Check if line number is valid
                if adjusted_line_num < 0 or adjusted_line_num >= len(lines):
                    raise RuntimeError(
                        f"Line number {adjusted_line_num + 1} out of range (file has {len(lines)} lines)"
                    )

                # Verify the line content matches what's expected
                if lines[adjusted_line_num] != expected_content:
                    raise RuntimeError(
                        f"Content mismatch for line {adjusted_line_num + 1}:\n"
                        f"Expected: '{expected_content}'\n"
                        f"Actual: '{lines[adjusted_line_num]}'"
                    )

            # Replace the BEFORE lines with AFTER lines
            # First, calculate how many lines to remove
            before_count = len(before)
            after_count = len(after)

            # Remove the BEFORE lines
            for _ in range(before_count):
                lines.pop(start_line)

            # Insert the AFTER lines
            for i, (line_num, content) in enumerate(after):
                lines.insert(start_line + i, content)

            # Adjust line offset for subsequent operations
            line_offset += after_count - before_count

    # Return the updated content
    return "\n".join(lines)


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
        logger.info(f"Created directory: {directory}")
