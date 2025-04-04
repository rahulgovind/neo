"""
Core file system operations.

This module provides the core logic for file operations:
- read: Read file contents with optional line numbering
- overwrite: Replace a file's contents completely
- patch: Apply a diff to update a file
"""

import os
import logging
import re
from typing import Dict, Any, List, Tuple, Optional
from dataclasses import dataclass
import textwrap
from enum import Enum
from src.core.exceptions import FatalError

# Configure logging
logger = logging.getLogger(__name__)

def read(path: str, include_line_numbers: bool = False) -> str:
    """
    Reads content from a single file at the specified path.
    
    Args:
        path: Path to the file to read
        include_line_numbers: Whether to prefix each line with its line number
            
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
        
        with open(path, 'r', encoding='utf-8') as f:
            # Read the file content directly to preserve the exact format including final newline
            content = f.read()
            
            if include_line_numbers:
                # Split into lines and add line numbers
                lines = content.splitlines(True)  # keepends=True to preserve newlines
                numbered_lines = [f"{i+1} {line}" for i, line in enumerate(lines)]
                result = "".join(numbered_lines)
                
                # Ensure we preserve the final newline if it exists in the original file
                if content and content[-1] == '\n' and (not result or result[-1] != '\n'):
                    result += '\n'
                    
                logger.info(f"Successfully read file: {path} ({len(lines)} lines)")
                return result
            else:
                logger.info(f"Successfully read file: {path} ({len(content.splitlines())} lines)")
                return content
                
    except UnicodeDecodeError:
        logger.error(f"File is not text or has unknown encoding: {path}")
        return f"Error: File is not text or has unknown encoding: {path}"
    except PermissionError:
        logger.error(f"Permission denied reading file: {path}")
        return f"Error: Permission denied reading file: {path}"
    except Exception as e:
        logger.error(f"Error reading file {path}: {str(e)}")
        return f"Error reading file {path}: {str(e)}"


def overwrite(workspace: str, path: str, content: str) -> Tuple[bool, int, int]:
    """
    Creates a new file or completely overwrites an existing file's content.
    
    Args:
        workspace: Root workspace directory path
        path: Path to the file, relative to workspace
        content: New content for the file
        
    Returns:
        Tuple of (success, lines_added, lines_deleted)
        
    Raises:
        Various exceptions related to file operations
    """
    # Normalize the path
    file_path = _normalize_path(workspace, path)
    
    # Count lines in the existing file if it exists
    old_lines = 0
    file_existed = os.path.exists(file_path)
    
    if file_existed:
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                old_content = f.read()
                old_lines = _count_lines(old_content)
        except Exception as e:
            logger.warning(f"Couldn't read existing file for line count: {e}")
            # Continue with update even if we couldn't get the line count
    
    # Create directory structure if needed
    _ensure_directory_exists(file_path)
    
    # Write the new content
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)
    
    # Count lines in the new content
    new_lines = _count_lines(content)
    
    # Calculate changes
    lines_added = max(new_lines - old_lines, 0)
    lines_deleted = max(old_lines - new_lines, 0)
    
    action = "Updated" if file_existed else "Created"
    logger.info(f"{action} file: {file_path} (+{lines_added},-{lines_deleted})")
    
    return True, lines_added, lines_deleted

def _ensure_directory_exists(file_path: str) -> None:
    """Creates parent directories for a file if they don't exist."""
    directory = os.path.dirname(file_path)
    if directory and not os.path.exists(directory):
        try:
            os.makedirs(directory, exist_ok=True)
            logger.info(f"Created directory: {directory}")
        except Exception as e:
            logger.error(f"Failed to create directory {directory}: {e}")
            raise

def _count_lines(content: str) -> int:
    """Counts the number of lines in a string."""
    # Handle empty strings and strings without newlines
    if not content:
        return 0
    return content.count('\n') + (0 if content.endswith('\n') else 1)

class PatchOpType(Enum):
    DELETE = '-'
    ADD = '+'
    UNCHANGED = ' '
    

def patch(path: str, diff_text: str) -> str:
    """
    Apply a diff to update file content.
    
    The diff format is:
    - Lines starting with '-' indicate lines to delete from the original content
    - Lines starting with '+' indicate lines to add
    - Lines starting with ' ' indicate unmodified lines that should match for validation
    
    The line number follows the prefix and precedes the line content.
    For example: '-3 existing line' means delete line 3.
    
    Args:
        path: Path to the file to update
        diff_text: Diff text in the specified format
        
    Returns:
        Updated content after applying the diff
        
    Raises:
        FatalError: If the diff cannot be applied for any reason
    """
    # Read the original file content
    try:
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()
    except FileNotFoundError:
        raise FatalError(f"File not found: {path}")
    except PermissionError:
        raise FatalError(f"Permission denied reading file: {path}")
    except Exception as e:
        raise FatalError(f"Error reading file {path}: {str(e)}")
    
    # Check if the original content has a trailing newline
    has_trailing_newline = content.endswith('\n')
    
    # Split into lines for processing
    original_lines = content.split("\n")
    if has_trailing_newline and original_lines and original_lines[-1] == "":
        # Remove the empty string at the end that comes from splitting a string with trailing newline
        original_lines.pop()
    
    # Parse the diff
    diff_pattern = re.compile(r'^([\-+]| |)(\d+) (.*?)$')
    diff_lines = diff_text.split("\n")
    # Remove empty lines in the diff
    if diff_lines and diff_lines[-1] == "":
        diff_lines.pop()
    
    # Process the diff lines
    operations = []
    for line in diff_lines:
        # Skip completely empty lines
        if not line:
            continue
            
        match = diff_pattern.match(line)
        if not match:
            raise FatalError(f"Invalid diff line format: {line}")
            
        op, line_num_str, line_content = match.groups()
        # Convert empty string to space for unchanged lines
        if op == "":
            op = " "
            
        try:
            line_num = int(line_num_str)
            if line_num < 1:
                raise FatalError(f"Invalid line number {line_num} (must be >= 1)")
            # Convert to 0-based indexing
            line_num -= 1
            
            operations.append((op, line_num, line_content))
        except ValueError:
            raise FatalError(f"Invalid line number in diff: {line_num_str}")
    
    # Sort operations by line number
    # For the same line number, sort by operation type: delete first, then unchanged, then add
    def op_sort_key(operation):
        op, line_num, _ = operation
        op_priority = {
            PatchOpType.DELETE.value: 0,  # Process deletions first
            PatchOpType.UNCHANGED.value: 1,  # Then unchanged lines
            PatchOpType.ADD.value: 2,  # Then additions
        }[op]
        return (line_num, op_priority)
        
    operations.sort(key=op_sort_key)
    
    # Verify operations are valid for deletion and unmodified lines
    for op, line_num, line_content in operations:
        # Verify that all unmodified lines match and deleted lines exist
        if op in [PatchOpType.DELETE.value, PatchOpType.UNCHANGED.value]:
            if original_lines[line_num] != line_content:
                raise FatalError(
                    f"Line mismatch at line {line_num + 1}:\n" +
                    f"Expected: '{line_content}'\n" +
                    f"Actual: '{original_lines[line_num]}'"
                )
    
    # Process changes by iterating over operations
    result = []
    next_original_line_number = 0
    
    # Process each operation in order
    for op, line_num, line_content in operations:
        # For delete and unmodified operations, ensure the line exists
        if op in [PatchOpType.DELETE.value, PatchOpType.UNCHANGED.value] and line_num >= len(original_lines):
            raise FatalError(f"Line {line_num + 1} does not exist in the original content")
            
        # If there are lines to copy before this operation, copy them
        if line_num > next_original_line_number and next_original_line_number < len(original_lines):
            # Copy all lines up to but not including the current line
            for i in range(next_original_line_number, line_num):
                result.append(original_lines[i])
            next_original_line_number = line_num
        
        # Process the current operation
        if op == PatchOpType.DELETE.value:
            # Skip deleted line and move to next line
            next_original_line_number += 1
        elif op == PatchOpType.ADD.value:
            # Add the new line
            result.append(line_content)
            # Don't increment next_original_line_number for additions
        elif op == PatchOpType.UNCHANGED.value:
            # Add the unchanged line and move to next line
            result.append(line_content)
            next_original_line_number += 1
    
    # Add any remaining lines from the original content
    if next_original_line_number < len(original_lines):
        for i in range(next_original_line_number, len(original_lines)):
            result.append(original_lines[i])
    
    # Convert the result to a string
    result_str = '\n'.join(result)
    
    # Special case for empty file - test_patch_empty_file
    # When patching an empty file, don't add a trailing newline
    if not content and result_str:
        return result_str.rstrip('\n')
        
    # Normal case - add trailing newline only if the original had one
    if content and has_trailing_newline and result_str:
        result_str += '\n'
    
    return result_str


def _normalize_path(workspace: str, path: str) -> str:
    """
    Normalizes a path to ensure it's relative to the workspace.
    
    Args:
        workspace: Root workspace directory path
        path: Path provided by the user or LLM
        
    Returns:
        Normalized absolute path within the workspace
        
    Notes:
        - Handles both absolute and relative paths
        - Ensures the path is within the workspace for security
        - Prevents directory traversal attacks
    """
    # Handle absolute paths
    if os.path.isabs(path):
        # For absolute paths, use the path directly if it's within the workspace
        # otherwise use the basename
        if path.startswith(workspace):
            return path
        else:
            logger.info(f"Converting absolute path to workspace-relative: {path}")
            # Just use the basename to avoid path issues
            return os.path.join(workspace, os.path.basename(path))
    
    # Handle directory traversal attempts
    if '..' in os.path.normpath(path).split(os.sep):
        logger.warning(f"Attempted directory traversal attack: {path}")
        return os.path.join(workspace, os.path.basename(path))
    
    # Standard case: relative path within the workspace
    return os.path.join(workspace, path)
