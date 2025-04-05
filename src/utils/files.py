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
from src.core.messages import _escape_special_chars, _unescape_special_chars

# Configure logging
logger = logging.getLogger(__name__)

def read(path: str, include_line_numbers: bool = False, from_: Optional[int] = None, until: Optional[int] = None, limit: int = -1) -> str:
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
        
        with open(path, 'r', encoding='utf-8') as f:
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
                logger.error(f"Invalid line numbers: from={from_}, until={until} - {str(e)}")
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
                first_display_line = start_line + 1  # Convert to 1-indexed for user display
                omitted_lines = first_display_line - 1
                result_lines.append(f"... {omitted_lines} additional lines")
                
            # Format the result
            if include_line_numbers:
                # Add line numbers - for unlimited display, we need to start counting from 1
                # otherwise, adjust line numbers based on the starting line
                if read_entire_file:
                    numbered_lines = [f"{i+1}:{line}" for i, line in enumerate(selected_lines)]
                else:
                    numbered_lines = [f"{i+1}:{line}" for i, line in enumerate(selected_lines, start=start_line)]
                result_lines.extend(numbered_lines)
            else:
                result_lines.extend(selected_lines)
                
            # Add indicator for lines after the selection
            if end_line < total_lines:
                # Calculate exactly how many lines are omitted after the current selection
                omitted_after = total_lines - end_line
                result_lines.append(f"... {omitted_after} additional lines")
                
            result = "\n".join(result_lines)
            
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
    

def _process_delete_section(section_content: str, original_lines: list, operations: list) -> None:
    """Process a @DELETE section from the diff."""
    for line in section_content.split("\n"):
        line = line.strip()
        if not line:
            continue
            
        # Parse the line number and content
        parts = line.split(":", 1)
        if len(parts) < 2:
            raise RuntimeError(f"Invalid line format in DELETE section, missing line content: {line}")
        
        try:
            line_num = int(parts[0]) - 1  # Convert to 0-indexed
            line_content = parts[1] if len(parts) > 1 else ""
        except ValueError:
            raise RuntimeError(f"Invalid line number in DELETE section: {parts[0]}")
        
        # Validate line exists in the original content
        if line_num >= len(original_lines):
            raise RuntimeError(f"Line {line_num + 1} does not exist in the original content")
        if original_lines[line_num] != line_content:
            raise RuntimeError(
                f"Line mismatch at line {line_num + 1}:\n" +
                f"Expected: '{line_content}'\n" +
                f"Actual: '{original_lines[line_num]}'"
            )
        
        # Add delete operation
        operations.append((PatchOpType.DELETE.value, line_num, line_content))


def _process_update_section(section_content: str, original_lines: list, operations: list) -> None:
    """Process an @UPDATE section from the diff."""
    # Split into BEFORE and AFTER sections
    sections = section_content.split("AFTER")
    if len(sections) != 2 or "BEFORE" not in sections[0]:
        raise RuntimeError(f"Invalid UPDATE format, must contain 'BEFORE' and 'AFTER' sections:\n{section_content}")
    
    before_section = sections[0].replace("BEFORE", "").strip()
    after_section = sections[1].strip()
    
    # Process BEFORE section (lines to delete)
    before_lines = []
    if before_section:
        for line in before_section.split("\n"):
            line = line.strip()
            if not line:
                continue
                
            # Parse the line number and content
            parts = line.split(":", 1)
            if len(parts) < 2:
                raise RuntimeError(f"Invalid line format in BEFORE section, missing line content: {line}")
            
            try:
                line_num = int(parts[0]) - 1  # Convert to 0-indexed
                line_content = parts[1] if len(parts) > 1 else ""
            except ValueError:
                raise RuntimeError(f"Invalid line number in BEFORE section: {parts[0]}")
            
            before_lines.append((line_num, line_content))
    
    # Process AFTER section (lines to add)
    after_lines = []
    if after_section:
        for line in after_section.split("\n"):
            line = line.strip()
            if not line:
                continue
                
            # Parse the line number and content
            parts = line.split(":", 1)
            if len(parts) < 2:
                raise RuntimeError(f"Invalid line format in AFTER section, missing line content: {line}")
            
            try:
                line_num = int(parts[0]) - 1  # Convert to 0-indexed
                line_content = parts[1] if len(parts) > 1 else ""
            except ValueError:
                raise RuntimeError(f"Invalid line number in AFTER section: {parts[0]}")
            
            after_lines.append((line_num, line_content))
    
    # Validate BEFORE lines exist in the original content
    for line_num, line_content in before_lines:
        if line_num >= len(original_lines):
            raise RuntimeError(f"Line {line_num + 1} does not exist in the original content")
        if original_lines[line_num] != line_content:
            raise RuntimeError(
                f"Line mismatch at line {line_num + 1}:\n" +
                f"Expected: '{line_content}'\n" +
                f"Actual: '{original_lines[line_num]}'"
            )
        
        # Add delete operation
        operations.append((PatchOpType.DELETE.value, line_num, line_content))
    
    # Add the AFTER lines
    for i, (line_num, line_content) in enumerate(after_lines):
        operations.append((PatchOpType.ADD.value, line_num, line_content))


def _process_insert_section(section_content: str, operations: list) -> None:
    """Process an @INSERT section from the diff."""
    for line in section_content.split("\n"):
        line = line.strip()
        if not line:
            continue
            
        # Parse the line number and content
        parts = line.split(":", 1)
        if len(parts) < 2:
            raise RuntimeError(f"Invalid line format in INSERT section, missing line content: {line}")
        
        try:
            line_num = int(parts[0]) - 1  # Convert to 0-indexed
            line_content = parts[1] if len(parts) > 1 else ""
        except ValueError:
            raise RuntimeError(f"Invalid line number in INSERT section: {parts[0]}")
        
        # Add insert operation
        operations.append((PatchOpType.ADD.value, line_num, line_content))


def patch(path: str, diff_text: str) -> str:
    """
    Apply a diff to update file content using the structured format.
    
    The diff format uses sections marked with:
    - @DELETE - For lines to be deleted
    - @UPDATE - For lines to be updated, with BEFORE and AFTER subsections
    - @INSERT - For lines to be inserted
    
    For example:
    @DELETE
    2:xyz
    3:basdf

    @UPDATE
    BEFORE
    5:asdf
    6:asdf
    AFTER
    5:asfdwe
    6:asdgqwe
    7:werlkjlb

    @INSERT
    10:asldkfjalkj
    11:aslkdj
    
    Args:
        path: File to update
        diff_text: Diff to apply in the specified format
        
    Returns:
        Updated content after applying the diff
        
    Raises:
        RuntimeError: If the diff cannot be applied for any reason
    """
    try:
        # Read the original file content
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()
    except FileNotFoundError:
        # The file doesn't exist, so the patch can't be applied
        raise RuntimeError(f"File {path} not found")
    except Exception as e:
        raise RuntimeError(f"Error reading file {path}: {str(e)}")
    
    # Split into lines for processing
    original_lines = content.split("\n")
    # If the file ends with a newline, the split will create an empty element at the end
    # Remove it to simplify processing
    if original_lines and original_lines[-1] == "":
        original_lines.pop()
    
    try:
        # Parse the diff sections
        operations = []
        
        # Split the diff text into sections by finding section markers
        sections = []
        current_section = ""
        current_type = None
        
        for line in diff_text.splitlines():
            if line.startswith("@DELETE"):
                if current_type:
                    sections.append((current_type, current_section))
                current_type = "DELETE"
                current_section = ""
            elif line.startswith("@UPDATE"):
                if current_type:
                    sections.append((current_type, current_section))
                current_type = "UPDATE"
                current_section = ""
            elif line.startswith("@INSERT"):
                if current_type:
                    sections.append((current_type, current_section))
                current_type = "INSERT"
                current_section = ""
            else:
                current_section += line + "\n"
        
        if current_type and current_section:
            sections.append((current_type, current_section))
        
        # Process each section based on its type
        for section_type, section_content in sections:
            section_content = section_content.strip()
            if not section_content:
                continue
                
            if section_type == "DELETE":
                _process_delete_section(section_content, original_lines, operations)
            elif section_type == "UPDATE":
                _process_update_section(section_content, original_lines, operations)
            elif section_type == "INSERT":
                _process_insert_section(section_content, operations)
            else:
                raise RuntimeError(f"Unknown section type: {section_type}")
        
        # Sort operations by line number in reverse order
        # This ensures we modify from bottom to top to avoid line number shifting
        # For INSERT operations at the same position, maintain their order from the diff
        # DELETE always comes before INSERT at the same position
        def op_sort_key(operation):
            op, line_num, _ = operation
            # Sort by negative line number for reverse order (bottom to top)
            # Secondary sort: DELETE operations (0) before INSERT operations (1)
            return (-line_num, 0 if op == PatchOpType.DELETE.value else 1)
            
        operations.sort(key=op_sort_key)
        
        # Apply the operations to create the updated content
        updated_lines = original_lines.copy()
        for op, line_num, line_content in operations:
            if op == PatchOpType.DELETE.value:
                # Remove the line at the specified position
                if 0 <= line_num < len(updated_lines):
                    updated_lines.pop(line_num)
            elif op == PatchOpType.ADD.value:
                # Insert a new line at the specified position
                # Note: this handles both insertion and append correctly
                if 0 <= line_num <= len(updated_lines):
                    updated_lines.insert(line_num, line_content)
                else:
                    # If position is beyond end of file, just append
                    updated_lines.append(line_content)
        
        # Combine the updated lines into the result
        # Add a trailing newline to match standard text file format
        updated_content = "\n".join(updated_lines) + "\n"
        return updated_content
    except Exception as e:
        # Prepare the error message
        error_msg = f"Error applying patch to {path}: {str(e)}"
        raise RuntimeError(error_msg)
        
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
        
        # Include the diff in the error message
        error_msg = f"{error_msg}\n\nDiff that failed to apply:\n{diff_text}"
        raise RuntimeError(error_msg)
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
            
        # Include the diff in the error message
        error_msg = f"{error_msg}\n\nDiff that failed to apply:\n{diff_text}"
        raise RuntimeError(error_msg)


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