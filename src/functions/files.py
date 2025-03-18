"""
File system operation functions for the LLM agent.

This module provides functions that allow the LLM to interact with the file system:
- ReadFiles: Reading single or multiple files with wildcard support
- UpdateFile: Creating or modifying files with content replacement or diff patching
"""

import os
import logging
from typing import Dict, Any

from src.function import Function
from src.files import read, update_with_content, apply

# Configure logging
logger = logging.getLogger(__name__)


class ReadFile(Function):
    """
    Reads content from a single file.
    
    Features:
    - Adds line numbers to make referencing specific lines easier
    - Handles common file reading errors gracefully
    """
    def __init__(self, **kwargs) -> None:
        pass

    def name(self) -> str:
        return "files.read"
    
    def describe(self) -> Dict[str, Any]:
        return {
            "name": self.name(),
            "description": "Read a file from the file system.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Path to the file to read."
                    },
                    "include_line_numbers": {
                        "type": "boolean",
                        "description": "Whether to include line numbers in the output.",
                        "default": False
                    }
                },
                "required": ["path"]
            }
        }
    
    def invoke(self, args: Dict[str, Any]) -> str:
        """
        Reads content from a single file at the specified path.
        
        Args:
            args: Dictionary containing 'path' key and optional 'include_line_numbers' key
            
        Returns:
            File contents with optional line numbers, or error message
        
        Raises:
            ValueError: If path argument is missing
        """
        if "path" not in args:
            logger.error("Path not provided to ReadFile function")
            raise ValueError("Path argument is required")
        
        path = args["path"]
        include_line_numbers = args.get("include_line_numbers", False)
        
        return read(path, include_line_numbers)


class UpdateFile(Function):
    """
    Creates or updates files in the workspace directory.
    
    Features:
    - Can create new files or update existing ones
    - Supports two modes: full content replacement or diff-based updates
    - Creates parent directories automatically if they don't exist
    """
    
    def __init__(self, workspace):
        """
        Initialize with the root workspace directory.
        
        Args:
            workspace: Absolute path to the workspace directory
        """
        self.workspace = workspace
    
    def name(self) -> str:
        return "files.update"
    
    def describe(self) -> Dict[str, Any]:
        return {
            "name": self.name(),
            "description": "Create or update a file in the workspace.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Path to the file to create or update."
                    },
                    "content": {
                        "type": "string",
                        "description": "The complete new content for the file. Use this for creating new files or completely replacing existing ones."
                    },
                    "diff": {
                        "type": "string",
                        "description": "The diff to apply to the existing file. Use this for making targeted changes to existing files."
                    }
                },
                "required": ["path"]
            }
        }
    
    def invoke(self, args: Dict[str, Any]) -> str:
        """
        Creates or updates a file in the workspace.
        
        The function supports two update modes:
        1. Full content replacement using the 'content' argument
        2. Targeted updates using the 'diff' argument
        
        At least one of 'content' or 'diff' must be provided.
        
        Args:
            args: Dictionary containing 'path' and either 'content' or 'diff'
            
        Returns:
            Status message with line addition/deletion counts
            
        Raises:
            ValueError: If path is missing or neither content nor diff is provided
        """
        if "path" not in args:
            logger.error("Path not provided to UpdateFile function")
            raise ValueError("Path argument is required")
        
        path = args["path"]
        
        # Validate that either content or diff is provided
        if "content" not in args and "diff" not in args:
            logger.error("Neither content nor diff provided to UpdateFile function")
            raise ValueError("Either content or diff argument must be provided")
        
        # Normalize path and ensure it's within workspace
        normalized_path = self._normalize_path(path)
        
        # Choose update mode based on provided arguments
        if "content" in args:
            return self._update_with_content(normalized_path, args["content"])
        else:
            return self._update_with_diff(normalized_path, args["diff"])
    
    def _normalize_path(self, path: str) -> str:
        """
        Normalizes a path to ensure it's relative to the workspace.
        
        Args:
            path: Path provided by the LLM
            
        Returns:
            Normalized absolute path within the workspace
        """
        # Remove leading slash if present
        if path.startswith('/'):
            path = path[1:]
            
        # Construct the full path
        full_path = os.path.join(self.workspace, path)
        
        # Ensure the path is within the workspace for security
        # Using os.path.commonpath prevents directory traversal attacks
        if not os.path.commonpath([self.workspace, os.path.realpath(full_path)]) == self.workspace:
            logger.warning(f"Attempted to write to path outside workspace: {path}")
            return os.path.join(self.workspace, os.path.basename(path))
            
        return full_path
    
    def _update_with_content(self, file_path: str, content: str) -> str:
        """
        Updates a file by completely replacing its content.
        
        Args:
            file_path: Full path to the file
            content: New content for the file
            
        Returns:
            Status message with line counts
        """
        try:
            success, lines_added, lines_deleted = update_with_content(file_path, content)
            return f"SUCCESS (+{lines_added},-{lines_deleted})"
            
        except PermissionError:
            rel_path = os.path.relpath(file_path, self.workspace)
            logger.error(f"Permission denied writing to file: {rel_path}")
            return f"Error: Permission denied writing to file: {rel_path}"
        except Exception as e:
            rel_path = os.path.relpath(file_path, self.workspace)
            logger.error(f"Error writing to file {rel_path}: {e}")
            return f"Error writing to file {rel_path}: {str(e)}"
    
    def _update_with_diff(self, file_path: str, diff_text: str) -> str:
        """
        Updates a file by applying a diff/patch.
        
        Args:
            file_path: Full path to the file
            diff_text: Unified diff to apply
            
        Returns:
            Status message with line counts
        """
        try:
            success, lines_added, lines_deleted = apply(file_path, diff_text)
            return f"SUCCESS (+{lines_added},-{lines_deleted})"
            
        except FileNotFoundError as e:
            rel_path = os.path.relpath(file_path, self.workspace)
            return f"Cannot apply diff: File does not exist: {rel_path}"
        except Exception as e:
            rel_path = os.path.relpath(file_path, self.workspace)
            logger.error(f"Error applying diff to file {rel_path}: {e}")
            return f"Error applying diff to file {rel_path}: {str(e)}"