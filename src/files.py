"""
Core file system operations.

This module provides the core logic for file operations:
- read: Read file contents with optional line numbering
- update_with_content: Replace a file's contents completely
- patch: Apply a diff to a file using the system's patch CLI tool
"""

import os
import logging
import fnmatch
import subprocess
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

def ensure_directory_exists(file_path: str) -> None:
    """Creates parent directories for a file if they don't exist."""
    directory = os.path.dirname(file_path)
    if directory and not os.path.exists(directory):
        try:
            os.makedirs(directory, exist_ok=True)
            logger.info(f"Created directory: {directory}")
        except Exception as e:
            logger.error(f"Failed to create directory {directory}: {e}")
            raise

def count_lines(content: str) -> int:
    """Counts the number of lines in a string."""
    # Handle empty strings and strings without newlines
    if not content:
        return 0
    return content.count('\n') + (0 if content.endswith('\n') else 1)

def update_with_content(file_path: str, content: str) -> Tuple[bool, int, int]:
    """
    Updates a file by completely replacing its content.
    
    Args:
        file_path: Full path to the file
        content: New content for the file
        
    Returns:
        Tuple of (success, lines_added, lines_deleted)
        
    Raises:
        Various exceptions related to file operations
    """
    # Count lines in the existing file if it exists
    old_lines = 0
    file_existed = os.path.exists(file_path)
    
    if file_existed:
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                old_content = f.read()
                old_lines = count_lines(old_content)
        except Exception as e:
            logger.warning(f"Couldn't read existing file for line count: {e}")
            # Continue with update even if we couldn't get the line count
    
    # Create directory structure if needed
    ensure_directory_exists(file_path)
    
    # Write the new content
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)
    
    # Count lines in the new content
    new_lines = count_lines(content)
    
    # Calculate changes
    lines_added = max(new_lines - old_lines, 0)
    lines_deleted = max(old_lines - new_lines, 0)
    
    action = "Updated" if file_existed else "Created"
    logger.info(f"{action} file: {file_path} (+{lines_added},-{lines_deleted})")
    
    return True, lines_added, lines_deleted

def patch(file_path: str, diff_text: str) -> Tuple[bool, int, int]:
    """
    Updates a file by applying a diff/patch using the system's 'patch' command.
    
    Args:
        file_path: Full path to the file
        diff_text: Unified diff to apply
        
    Returns:
        Tuple of (success, lines_added, lines_deleted)
        
    Raises:
        FileNotFoundError: If the file doesn't exist
        Various other exceptions related to file operations
    """
    if not os.path.exists(file_path):
        logger.warning(f"Cannot apply patch: File does not exist: {file_path}")
        raise FileNotFoundError(f"Cannot apply patch: File does not exist: {file_path}")
    
    logger.info(f"Applying patch to file: {file_path}")
    
    # Read the current file content to count original lines
    with open(file_path, 'r', encoding='utf-8') as f:
        current_content = f.read()
        old_lines = count_lines(current_content)
    
    # Create a temporary file for the patch
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.patch') as temp_file:
        temp_patch_path = temp_file.name
        temp_file.write(diff_text)
    
    try:
        # Apply the patch using the system patch command
        # -u for unified diff format, --forward forces patch to apply even if the patch seems reversed
        # -N for treating non-existent files as empty, -r rejects file to put rejected hunks in
        result = subprocess.run(
            ['patch', '-u', '--forward', '-N', file_path, '-i', temp_patch_path],
            capture_output=True, 
            text=True
        )
        
        # Check if patch applied successfully
        if result.returncode != 0:
            logger.error(f"Patch failed: {result.stderr}")
            raise Exception(f"Patch failed: {result.stderr}")
        
        # Read the new file content to calculate line changes
        with open(file_path, 'r', encoding='utf-8') as f:
            new_content = f.read()
            new_lines = count_lines(new_content)
        
        # Calculate changes
        lines_added = max(new_lines - old_lines, 0)
        lines_deleted = max(old_lines - new_lines, 0)
        
        logger.info(f"Applied patch to file: {file_path} (+{lines_added},-{lines_deleted})")
        
        # Parse the patch output to get more accurate added/deleted line counts
        for line in result.stdout.splitlines():
            if line.startswith("patching file"):
                continue
            logger.debug(f"Patch output: {line}")
        
        return True, lines_added, lines_deleted
    
    except Exception as e:
        logger.error(f"Error applying patch to file {file_path}: {e}")
        raise
    finally:
        # Remove the temporary patch file
        try:
            os.unlink(temp_patch_path)
        except Exception as e:
            logger.warning(f"Failed to remove temporary patch file: {e}")

def tree(path: str, respect_gitignore: bool = True) -> List[Dict[str, Any]]:
    """
    Creates a tree representation of the file system starting at the given path.
    
    Args:
        path: Path to the directory to create a tree from
        respect_gitignore: Whether to respect .gitignore patterns
        
    Returns:
        List of dictionaries representing the file system tree
        Each dictionary has the format:
        {
            "type": "file" or "directory",
            "name": name of the file or directory,
            "children": list of child dictionaries (for directories),
            "size": {"bytes": size in bytes, "lines": number of lines} (for files)
        }
    """
    logger.info(f"Creating tree for path: {path}")
    
    if not os.path.exists(path):
        logger.warning(f"Path does not exist: {path}")
        return []
    
    # Get gitignore patterns if needed
    gitignore_patterns = []
    if respect_gitignore:
        gitignore_patterns = _get_gitignore_patterns(path)
    
    # If path is a file, return a single node
    if os.path.isfile(path):
        return [_create_file_node(path, os.path.basename(path))]
    
    # If path is a directory, create a tree
    return _create_directory_tree(path, gitignore_patterns)


def _get_gitignore_patterns(start_path: str) -> List[str]:
    """
    Collects all gitignore patterns from .gitignore files in the path hierarchy.
    
    Args:
        start_path: Path to start looking for .gitignore files
        
    Returns:
        List of gitignore patterns
    """
    patterns = []
    
    # Check for .gitignore in the current directory
    gitignore_path = os.path.join(start_path, ".gitignore")
    if os.path.isfile(gitignore_path):
        try:
            with open(gitignore_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    # Skip empty lines and comments
                    if line and not line.startswith("#"):
                        patterns.append(line)
            logger.debug(f"Found .gitignore with {len(patterns)} patterns")
        except Exception as e:
            logger.warning(f"Error reading .gitignore: {e}")
    
    return patterns


def _should_ignore(path: str, rel_path: str, gitignore_patterns: List[str]) -> bool:
    """
    Checks if a path should be ignored based on gitignore patterns.
    
    Args:
        path: Absolute path to check
        rel_path: Path relative to the root directory
        gitignore_patterns: List of gitignore patterns
        
    Returns:
        True if the path should be ignored, False otherwise
    """
    # Always ignore .git directory
    if ".git" in rel_path.split(os.sep):
        return True
        
    # Check each pattern
    for pattern in gitignore_patterns:
        # Handle negation (patterns that start with !)
        if pattern.startswith("!"):
            if fnmatch.fnmatch(rel_path, pattern[1:]):
                return False
        # Handle directory-only patterns (patterns that end with /)
        elif pattern.endswith("/") and os.path.isdir(path):
            if fnmatch.fnmatch(rel_path, pattern[:-1] + "*"):
                return True
        # Handle regular patterns
        elif fnmatch.fnmatch(rel_path, pattern) or fnmatch.fnmatch(os.path.basename(path), pattern):
            return True
    
    return False


def _create_file_node(path: str, name: str) -> Dict[str, Any]:
    """
    Creates a node representing a file.
    
    Args:
        path: Path to the file
        name: Name of the file
        
    Returns:
        Dictionary representing the file
    """
    size_bytes = os.path.getsize(path)
    try:
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
            lines = count_lines(content)
    except (UnicodeDecodeError, PermissionError):
        # If we can't read the file as text, assume it's binary
        lines = None
    
    return {
        "type": "file",
        "name": name,
        "size": {"bytes": size_bytes, "lines": lines}
    }


def _create_directory_tree(path: str, gitignore_patterns: List[str]) -> List[Dict[str, Any]]:
    """
    Creates a tree representation of a directory.
    
    Args:
        path: Path to the directory
        gitignore_patterns: List of gitignore patterns to respect
        
    Returns:
        List of dictionaries representing the directory contents
    """
    result = []
    root_path = path
    
    try:
        for item in sorted(os.listdir(path)):
            item_path = os.path.join(path, item)
            rel_path = os.path.relpath(item_path, root_path)
            
            # Check if this item should be ignored
            if _should_ignore(item_path, rel_path, gitignore_patterns):
                continue
                
            if os.path.isdir(item_path):
                children = _create_directory_tree(item_path, gitignore_patterns)
                result.append({
                    "type": "directory",
                    "name": item,
                    "children": children
                })
            else:
                result.append(_create_file_node(item_path, item))
    except PermissionError:
        logger.warning(f"Permission denied for {path}")
    except Exception as e:
        logger.error(f"Error creating directory tree for {path}: {e}")
    
    return result