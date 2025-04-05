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
from src.core.messages import _escape_special_chars, _unescape_special_chars

# Configure logging
logger = logging.getLogger(__name__)

def read(path: str, include_line_numbers: bool = False, range_str: Optional[str] = None, max_lines: int = 200) -> str:
    """
    Reads content from a single file at the specified path.
    Special command characters are automatically escaped with Unicode escapes.
    
    Args:
        path: Path to the file to read
        include_line_numbers: Whether to prefix each line with its line number
        range_str: Optional range specification in format "start:end" 
                   Examples: "323:" (line 323 + 100 lines), ":323" (100 lines before 323),
                   "323:423" (lines 323-423), "-100:" (last 100 lines)
        max_lines: Maximum number of lines to return (default: 200)
            
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
            
            # Split into lines for processing
            lines = content.split("\n")
            total_lines = len(lines)
            
            # Process range parameter if provided
            start_line = 0
            end_line = total_lines
            
            if range_str:
                try:
                    # Parse the range string
                    if ":" not in range_str:
                        raise ValueError("Range must contain colon ':'")
                    
                    range_parts = range_str.split(":")
                    start_str = range_parts[0]
                    end_str = range_parts[1]
                    
                    # Process start line
                    if start_str:
                        start_line = int(start_str)
                        # Handle negative indices (counting from end)
                        if start_line < 0:
                            start_line = total_lines + start_line
                        else:
                            # Convert to 0-indexed
                            start_line = start_line - 1
                    else:
                        # If no start specified with ":N", show 100 lines before end
                        end_line = int(end_str)
                        if end_line < 0:
                            end_line = total_lines + end_line
                        else:
                            # Convert to 0-indexed
                            end_line = min(end_line, total_lines)
                        start_line = max(0, end_line - 100)
                    
                    # Process end line
                    if end_str:
                        end_line = int(end_str)
                        # Handle negative indices
                        if end_line < 0:
                            end_line = total_lines + end_line
                        else:
                            # Convert to 0-indexed + 1 (to include the end line)
                            end_line = min(end_line, total_lines)
                    else:
                        # If no end specified with "N:", show N + 100 lines
                        start_line = max(0, start_line)
                        end_line = min(start_line + 100, total_lines)
                    
                except ValueError as e:
                    logger.error(f"Invalid range format: {range_str} - {str(e)}")
                    return f"Error: Invalid range format: {range_str} - {str(e)}"
            
            # Validate range boundaries
            start_line = max(0, min(start_line, total_lines - 1))
            end_line = max(start_line + 1, min(end_line, total_lines))
            
            # Apply max_lines limit if no specific range was requested
            if not range_str and (end_line - start_line) > max_lines:
                end_line = start_line + max_lines
            
            # Get the selected lines
            selected_lines = lines[start_line:end_line]
            
            # Format the result
            if include_line_numbers:
                # Add line numbers
                numbered_lines = [f"{i+1} {line}" for i, line in enumerate(selected_lines, start=start_line+1)]
                result = "\n".join(numbered_lines)
            else:
                result = "\n".join(selected_lines)
                
            logger.info(f"Successfully read file: {path} (showing {len(selected_lines)} of {total_lines} lines)")
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
    
    try:
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
        
    except FatalError as e:
        # Extract line number from error message if possible
        line_num_match = re.search(r'[Ll]ine (\d+)', str(e))
        error_line_num = None
        if line_num_match:
            try:
                error_line_num = int(line_num_match.group(1))
            except ValueError:
                pass
        
        # Prepare error message with context
        error_msg = str(e)
        
        # If we have a specific line number, include relevant context around it
        if error_line_num and error_line_num <= len(original_lines):
            # Show 10 lines before and after the error
            start_line = max(0, error_line_num - 11)  # -11 because error_line_num is 1-indexed
            end_line = min(len(original_lines), error_line_num + 10)
            
            # Create content chunk with line numbers
            context_lines = []
            for i in range(start_line, end_line):
                line_marker = ">" if i == error_line_num - 1 else " "
                context_lines.append(f"{line_marker}{i+1:4d}: {original_lines[i]}")
            
            error_context = "\n".join(context_lines)
            error_msg = f"{error_msg}\n\nRelevant file content:\n{error_context}"
        else:
            # No specific line, include the entire file if it's not too large
            if len(original_lines) <= 100:  # Only include full content for reasonably-sized files
                file_content = "\n".join([f"{i+1:4d}: {line}" for i, line in enumerate(original_lines)])
                error_msg = f"{error_msg}\n\nFile content:\n{file_content}"
            else:
                # File too large, just indicate size
                error_msg = f"{error_msg}\n\nFile is large ({len(original_lines)} lines) - showing first 50 lines:\n"
                file_preview = "\n".join([f"{i+1:4d}: {line}" for i, line in enumerate(original_lines[:50])])
                error_msg = f"{error_msg}{file_preview}\n..."
        
        raise FatalError(error_msg)
    except Exception as e:
        # For other exceptions, include full file content if not too large
        error_msg = f"Error applying patch to {path}: {str(e)}"
        
        if len(original_lines) <= 100:  # Only include full content for reasonably-sized files
            file_content = "\n".join([f"{i+1:4d}: {line}" for i, line in enumerate(original_lines)])
            error_msg = f"{error_msg}\n\nFile content:\n{file_content}"
        else:
            # File too large, just indicate size
            error_msg = f"{error_msg}\n\nFile is large ({len(original_lines)} lines) - showing first 50 lines:\n"
            file_preview = "\n".join([f"{i+1:4d}: {line}" for i, line in enumerate(original_lines[:50])])
            error_msg = f"{error_msg}{file_preview}\n..."
            
        raise FatalError(error_msg)


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