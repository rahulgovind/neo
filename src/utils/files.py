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
from src.core.constants import COMMAND_START, COMMAND_END, STDIN_SEPARATOR, ERROR_PREFIX, SUCCESS_PREFIX
from src.core.exceptions import FatalError

# Configure logging
logger = logging.getLogger(__name__)

def _escape_special_chars(content: str) -> str:
    """
    Replace special command characters with their escaped Unicode variants.
    Also properly escapes already-escaped unicode sequences.
    
    Args:
        content: The content to process
        
    Returns:
        Content with special characters replaced
    """
    if content is None:
        return ""
    
    # First, handle already-escaped sequences by doubling the backslashes
    # This matches \u25b6, \u25a0, etc. and replaces with \\u25b6, \\u25a0, etc.
    result = re.sub(
        r'\\u(25b6|25a0|ff5c|274c|2705)', 
        r'\\\\u\1',  # \1 is the backreference to the captured group
        content
    )
    
    # Then replace actual special characters with their escaped forms
    # Create a dictionary mapping special characters to their escape sequences
    char_to_escape = {
        COMMAND_START: '\\u25b6',    # ▶ -> \u25b6
        COMMAND_END: '\\u25a0',      # ■ -> \u25a0
        STDIN_SEPARATOR: '\\uff5c',  # ｜ -> \uff5c
        ERROR_PREFIX: '\\u274c',     # ❌ -> \u274c
        SUCCESS_PREFIX: '\\u2705',   # ✅ -> \u2705
    }
    
    # Build the pattern of all special characters to match
    pattern = '[' + re.escape(''.join(char_to_escape.keys())) + ']'
    
    # Define a replacement function that looks up the correct escape sequence
    def replace_special_char(match):
        return char_to_escape[match.group(0)]
    
    # Apply the substitution for special characters
    result = re.sub(pattern, replace_special_char, result)
    
    return result


def _unescape_special_chars(content: str) -> str:
    """
    Reverse the escaping process, converting Unicode escapes back to special characters.
    Handles both single-escaped and double-escaped sequences correctly.
    
    Args:
        content: The content to process
        
    Returns:
        Content with Unicode escapes converted back to special characters
    """
    if content is None:
        return ""
    
    # We need to detect if we're working with:
    # 1. A literal double-escaped sequence like "\\u25b6" (which should become "\u25b6")
    # 2. A single-escaped sequence like "\u25b6" (which should become the actual character)
    
    # Create a dictionary for the escape sequence to special character mapping
    escape_to_char = {
        '\\u25b6': COMMAND_START,     # \u25b6 -> ▶
        '\\u25a0': COMMAND_END,       # \u25a0 -> ■
        '\\uff5c': STDIN_SEPARATOR,   # \uff5c -> ｜
        '\\u274c': ERROR_PREFIX,      # \u274c -> ❌
        '\\u2705': SUCCESS_PREFIX,    # \u2705 -> ✅
    }
    
    # Define a replacement function for our regex
    def replacer(match):
        # Get the full match
        full_match = match.group(0)
        prefix = match.group(1)  # Will be either '\\' or '\'
        code = match.group(2)    # Will be one of our unicode values
        
        # If this is a double-escaped sequence (\\u...)
        if prefix == '\\\\': 
            # Return a single-escaped sequence (\u...)
            return f'\\u{code}'
        
        # Otherwise it's a single-escaped sequence (\u...) 
        # Return the corresponding special character
        return escape_to_char.get(f'\\u{code}')
    
    # Use a pattern that captures both the prefix and the code to distinguish
    # between double-escaped (\\u...) and single-escaped (\u...)
    pattern = r'(\\\\|\\)u(25b6|25a0|ff5c|274c|2705)'
    
    # Apply the substitution
    result = re.sub(pattern, replacer, content)
    
    return result


def read(path: str, include_line_numbers: bool = False) -> str:
    """
    Reads content from a single file at the specified path.
    Special command characters are automatically escaped with Unicode escapes.
    
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
                lines = content.split("\n")  # keepends=True to preserve newlines
                numbered_lines = [f"{i+1} {line}" for i, line in enumerate(lines)]
                result = "\n".join(numbered_lines)
                    
                logger.info(f"Successfully read file: {path} ({len(lines)} lines)")
                return result
            else:
                logger.info(f"Successfully read file: {path} ({len(content.split("\n"))} lines)")
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
    
    The diff format uses a chunk-based structure:
    - Lines starting with '@' indicate the start of a chunk with a line number
    - Format: @<line_number> [optional description]
    - Within each chunk:
      - Lines with '- ' indicate lines to delete
      - Lines with '+ ' indicate lines to add
      - Lines with '  ' indicate context (unchanged) lines
    
    Args:
        path: File to update
        diff_text: Diff to apply
        
    Returns:
        Updated content after applying the diff
        
    Raises:
        FatalError: If the diff cannot be applied for any reason
    """
    try:
        # Read the original file content
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()
    except FileNotFoundError:
        # The file doesn't exist, so the patch can't be applied
        raise FatalError(f"File {path} not found")
    except Exception as e:
        raise FatalError(f"Error reading file {path}: {str(e)}")
    
    # Split into lines for processing
    original_lines = content.split("\n")
    
    # Remove empty lines from the diff
    diff_lines = [
        line for line in diff_text.split("\n")
        if line.strip() != ""
    ]
    
    # Process the diff lines
    operations = []
    
    # Parse the chunk-based format
    chunk_pattern = re.compile(r'^@(\d+)\s*(.*)$')
    current_line_num = 0
    
    i = 0
    while i < len(diff_lines):
        line = diff_lines[i]
        
        # Check if this is a chunk header
        chunk_match = chunk_pattern.match(line)
        if chunk_match:
            # Get the starting line number for this chunk (1-indexed in the diff)
            current_line_num = int(chunk_match.group(1)) - 1  # Convert to 0-indexed
            i += 1  # Move to the next line
            
            # Process lines in this chunk
            while i < len(diff_lines) and not diff_lines[i].startswith('@'):
                chunk_line = diff_lines[i]
                
                if chunk_line.startswith('- '):
                    # Delete line
                    if current_line_num >= len(original_lines):
                        raise FatalError(f"Line {current_line_num + 1} does not exist in the original content")
                    # Verify that the line to delete matches what's in the diff
                    line_content = chunk_line[2:]
                    if original_lines[current_line_num] != line_content:
                        raise FatalError(
                            f"Line mismatch at line {current_line_num + 1}:\n" +
                            f"Expected: '{line_content}'\n" +
                            f"Actual: '{original_lines[current_line_num]}'"
                        )
                    operations.append((PatchOpType.DELETE.value, current_line_num, original_lines[current_line_num]))
                    current_line_num += 1
                elif chunk_line.startswith('+ '):
                    # Add line
                    operations.append((PatchOpType.ADD.value, current_line_num, chunk_line[2:]))
                elif chunk_line.startswith('  '):
                    # Unchanged line
                    if current_line_num >= len(original_lines):
                        raise FatalError(f"Line {current_line_num + 1} does not exist in the original content")
                    # Verify that the unchanged line matches what's in the diff
                    line_content = chunk_line[2:]
                    if original_lines[current_line_num] != line_content:
                        raise FatalError(
                            f"Line mismatch at line {current_line_num + 1}:\n" +
                            f"Expected: '{line_content}'\n" +
                            f"Actual: '{original_lines[current_line_num]}'"
                        )
                    operations.append((PatchOpType.UNCHANGED.value, current_line_num, original_lines[current_line_num]))
                    current_line_num += 1
                else:
                    # Invalid line in chunk
                    raise FatalError(f"Invalid line format in chunk: {chunk_line}")
                
                i += 1
        else:
            # If it's not a chunk header, raise an error
            raise FatalError(f"Invalid diff format: Line must start with @ to indicate a chunk: {line}")
    
    # Sort operations by line number, with deletions before additions
    # This is important to handle overlapping line changes correctly
    def op_sort_key(operation):
        op, line_num, _ = operation
        # Sort by line number first
        # Then by operation type: deletions before additions
        return (line_num, 0 if op == PatchOpType.DELETE.value else 
                       1 if op == PatchOpType.UNCHANGED.value else 2)
        
    operations.sort(key=op_sort_key)
    
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
    
    # Add trailing newline if the original had one or if there are lines in the result
    if result_str and not result_str.endswith('\n'):
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
