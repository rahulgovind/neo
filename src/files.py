"""
Core file system operations.

This module provides the core logic for file operations:
- normalize_path: Normalize and validate file paths against a workspace root
- read: Read file contents with optional line numbering
- overwrite: Replace a file's contents completely
- patch: Apply a custom format patch to a file
- tree: Generate a tree structure of files and directories
"""

import os
import logging
import fnmatch
import tempfile
from typing import Tuple, List, Dict, Any, Optional
from dataclasses import dataclass

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
            lines = f.readlines()
            if include_line_numbers:
                # Add line numbers for easier reference
                numbered_lines = [f"{i+1} {line}" for i, line in enumerate(lines)]
                logger.info(f"Successfully read file: {path} ({len(lines)} lines)")
                return "".join(numbered_lines)
            else:
                logger.info(f"Successfully read file: {path} ({len(lines)} lines)")
                return "".join(lines)
                
    except UnicodeDecodeError:
        logger.error(f"File is not text or has unknown encoding: {path}")
        return f"Error: File is not text or has unknown encoding: {path}"
    except PermissionError:
        logger.error(f"Permission denied reading file: {path}")
        return f"Error: Permission denied reading file: {path}"
    except Exception as e:
        logger.error(f"Error reading file {path}: {str(e)}")
        return f"Error reading file {path}: {str(e)}"

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

def _normalize_path(workspace: str, path: str) -> str:
    """
    Normalizes a path to ensure it's relative to the workspace.
    
    Args:
        workspace: Root workspace directory path
        path: Path provided by the user or LLM
        
    Returns:
        Normalized absolute path within the workspace
        
    Notes:
        - Removes leading slash if present
        - Ensures the path is within the workspace for security
        - Prevents directory traversal attacks
    """
    # Remove leading slash if present
    if path.startswith('/'):
        path = path[1:]
        
    # Construct the full path
    full_path = os.path.join(workspace, path)
    
    # Ensure the path is within the workspace for security
    # Using os.path.commonpath prevents directory traversal attacks
    if not os.path.commonpath([workspace, os.path.realpath(full_path)]) == workspace:
        logger.warning(f"Attempted to access path outside workspace: {path}")
        return os.path.join(workspace, os.path.basename(path))
        
    return full_path
    
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

def patch(workspace: str, path: str, patch_text: str) -> Tuple[bool, int, int]:
    """
    Updates a file by applying a custom format patch.
    
    The custom patch format is structured as follows:
    * Each change hunk starts with @ LINE_NUMBER where LINE_NUMBER is the 
      corresponding line in the original source code.
    * Inserts are added as "+" lines
    * Deletes are added as "-" lines
    * Updates are added as "-" line followed by "+" line
    * Contextual lines are prefixed with a space
    
    Args:
        workspace: Root workspace directory path
        path: Path to the file, relative to workspace
        patch_text: Custom patch format to apply
        
    Returns:
        Tuple of (success, lines_added, lines_deleted)
        
    Raises:
        FileNotFoundError: If the file doesn't exist
        ValueError: If the patch format is invalid
        Various other exceptions related to file operations
    """
    # Normalize the path
    file_path = _normalize_path(workspace, path)
    
    if not os.path.exists(file_path):
        logger.warning(f"Cannot apply patch: File does not exist: {file_path}")
        raise FileNotFoundError(f"Cannot apply patch: File does not exist: {file_path}")
    
    logger.info(f"Applying custom patch to file: {file_path}")
    
    # Read the current file content
    with open(file_path, 'r', encoding='utf-8') as f:
        original_lines = f.read().splitlines()
    
    # Parse the patch text into chunks
    chunks = []
    current_chunk = None
    
    for line in patch_text.splitlines():
        line = line.rstrip('\r\n')
        
        # Skip empty lines between chunks
        if not line and not current_chunk:
            continue
            
        # Start of a new chunk
        if line.startswith('@ '):
            if current_chunk:
                chunks.append(current_chunk)
            
            try:
                line_num_str = line[2:].strip()
                line_num = int(line_num_str)
                current_chunk = {'line': line_num, 'ops': []}
            except ValueError as e:
                raise ValueError(f"Expected a chunk header like @ <line_number>. The current value following '@ ' is '{line[2:]}' which is not a valid number.")
        # Operations within a chunk
        elif current_chunk is not None:
            current_chunk['ops'].append(line)
    
    # Add the last chunk if it exists
    if current_chunk:
        chunks.append(current_chunk)
    
    # Sort chunks by line number
    chunks.sort(key=lambda x: x['line'])
    
    # Apply the patches to create new content incrementally
    new_lines = []
    lines_added = 0
    lines_deleted = 0
    offset = 0  # Track the current line being processed in the original file
    
    for chunk in chunks:
        chunk_line = chunk['line'] - 1  # Convert to 0-based indexing
        
        # Check for overlapping chunks
        if offset > chunk_line:
            raise ValueError(f"Chunk overlap detected. Chunk starting at line {chunk_line + 1} overlaps with previous content.")
        
        # Copy lines between the current offset and this chunk's starting line
        new_lines.extend(original_lines[offset:chunk_line])
        
        # Process operations in this chunk
        current_line = chunk_line
        
        for op in chunk['ops']:
            op_type = op[0]
            content = op[1:]
            
            if op_type == '+':  # Insert line
                new_lines.append(content)
                lines_added += 1
            elif op_type == '-':  # Delete line
                if current_line >= len(original_lines):
                    raise ValueError(f"Attempted to delete non-existent line {current_line + 1}.")
                # Skip this line in the output (delete)
                current_line += 1
                lines_deleted += 1
            else:
                if current_line >= len(original_lines):
                    raise ValueError(f"Context line at position {current_line + 1} is beyond the end of the file.")
                if original_lines[current_line].strip() != content.strip():
                    raise ValueError(f"Context line mismatch at line {current_line + 1}. Expected '{original_lines[current_line]}', got '{content}'.")
                new_lines.append(original_lines[current_line])
                current_line += 1
        
        # Update offset to the current line for the next chunk
        offset = current_line
    
    # Copy any remaining lines from the original file
    new_lines.extend(original_lines[offset:])
    
    # Write the new content back to the file
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(new_lines))
        # Add final newline if original had one or if we have content
        if new_lines and (len(original_lines) == 0 or original_lines[-1] != ''):
            f.write('\n')
    
    logger.info(f"Applied custom patch to file: {file_path} (+{lines_added},-{lines_deleted})")
    return True, lines_added, lines_deleted