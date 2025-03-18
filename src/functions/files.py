"""
File system operation functions for the LLM agent.

This module provides functions that allow the LLM to interact with the file system:
- ReadFiles: Reading single or multiple files with wildcard support
- UpdateFile: Creating or modifying files with content replacement or diff patching
- TreeFile: Getting a tree view of files and directories with metadata
"""

import os
import logging
from typing import Dict, Any, List, Optional

from src.function import Function, Example
from src.files import read, update_with_content, apply, tree

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
                    }
                },
                "required": ["path"]
            }
        }
    
    def examples(self) -> List[Example]:
        """Returns a list of examples demonstrating usage of this function."""
        return [
            Example(
                description="Read a Python file with line numbers",
                args={"path": "src/model.py"},
                result="1 import os\n2 import logging\n3 ..."
            ),
            Example(
                description="Read a configuration file",
                args={"path": "config.json"},
                result="1 {\n2   \"debug\": true,\n3   \"port\": 8000\n4 }"
            )
        ]
    
    def invoke(self, args: Dict[str, Any]) -> str:
        """
        Reads content from a single file at the specified path.
        
        Args:
            args: Dictionary containing 'path' key.
            
        Returns:
            File contents with optional line numbers, or error message
        
        Raises:
            ValueError: If path argument is missing
        """
        if "path" not in args:
            logger.error("Path not provided to ReadFile function")
            raise ValueError("Path argument is required")
        
        path = args["path"]
        
        return read(path, include_line_numbers=True)


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
                    "diff": {
                        "type": "string",
                        "description": "The diff to apply to the existing file. Use this for making targeted changes to existing files."
                    }
                },
                "required": ["path"]
            }
        }
    
    def examples(self) -> List[Example]:
        """Returns a list of examples demonstrating usage of this function."""
        return [
            Example(
                description="Apply a simple diff to update a configuration value",
                args={
                    "path": "src/config.py",
                    "diff": "--- src/config.py\n+++ src/config.py\n@@ -1,5 +1,5 @@\n DEBUG = False\n-PORT = 8000\n+PORT = 9000\n"
                },
                result="SUCCESS (+1,-1)"
            ),
            Example(
                description="Apply a diff to add a new function",
                args={
                    "path": "src/utils.py",
                    "diff": "--- src/utils.py\n+++ src/utils.py\n@@ -45,3 +45,8 @@\n     return formatted_data\n \n # End of existing functions\n+\n+def validate_config(config):\n+    \"\"\"Validate the configuration object.\"\"\"\n+    return all(key in config for key in ['api_key', 'endpoint'])\n"
                },
                result="SUCCESS (+5,-0)"
            )
        ]
    
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
            logger.error("Path not provided to files.update function")
            raise ValueError("Path argument is required")
        
        path = args["path"]
        
        # Validate that either content or diff is provided
        if "diff" not in args:
            logger.error("Diff not provided to files.update function")
            raise ValueError("Diff not provided to files.update function")
        
        # Normalize path and ensure it's within workspace
        normalized_path = self._normalize_path(path)
        
        # Choose update mode based on provided arguments
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


class TreeFile(Function):
    """
    Returns a tree-like structure of files and directories starting from a given path.
    
    Features:
    - Provides hierarchical view of files and directories
    - Respects .gitignore files to exclude ignored files
    - Includes file metadata like size in bytes and line count
    - Sortable output for better organization
    """
    
    def __init__(self, workspace):
        """
        Initialize with the root workspace directory.
        
        Args:
            workspace: Absolute path to the workspace directory
        """
        self.workspace = workspace
    
    def name(self) -> str:
        return "files.tree"
    
    def describe(self) -> Dict[str, Any]:
        return {
            "name": self.name(),
            "description": "Get a tree view of files and directories in the workspace.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Path to the directory to list. Defaults to the root of the workspace."
                    },
                    "respect_gitignore": {
                        "type": "boolean",
                        "description": "Whether to respect .gitignore files. Default is true.",
                        "default": True
                    }
                }
            }
        }
    
    def examples(self) -> List[Example]:
        """Returns a list of examples demonstrating usage of this function."""
        return [
            Example(
                description="Get a tree view of the entire workspace",
                args={},
                result={
                    "path": "",
                    "tree": [
                        {
                            "type": "directory",
                            "name": "src",
                            "children": [
                                {
                                    "type": "file",
                                    "name": "main.py",
                                    "size": {"bytes": 1024, "lines": 48}
                                }
                            ]
                        }
                    ]
                }
            ),
            Example(
                description="Get a tree view of a specific directory without respecting .gitignore",
                args={"path": "src/models", "respect_gitignore": False},
                result={
                    "path": "src/models",
                    "tree": [
                        {
                            "type": "file",
                            "name": "model.py",
                            "size": {"bytes": 2048, "lines": 86}
                        }
                    ]
                }
            )
        ]
    
    def invoke(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """
        Returns a tree representation of files and directories.
        
        Args:
            args: Dictionary optionally containing 'path' and 'respect_gitignore' keys
            
        Returns:
            Dictionary with tree structure of files and directories
        """
        # Default to the workspace root if no path is provided
        path = args.get("path", "")
        respect_gitignore = args.get("respect_gitignore", True)
        
        # Normalize path and ensure it's within workspace
        workspace_path = self._normalize_path(path)
        
        # Get the tree structure
        try:
            tree_structure = tree(workspace_path, respect_gitignore)
            rel_path = os.path.relpath(workspace_path, self.workspace)
            return {
                "path": rel_path if rel_path != "." else "",
                "tree": tree_structure
            }
        except Exception as e:
            logger.error(f"Error generating tree for {path}: {e}")
            return {
                "error": f"Failed to generate tree: {str(e)}"
            }
    
    def _normalize_path(self, path: str) -> str:
        """
        Normalizes a path to ensure it's relative to the workspace.
        
        Args:
            path: Path provided by the LLM
            
        Returns:
            Normalized absolute path within the workspace
        """
        # Use workspace root if path is empty
        if not path:
            return self.workspace
            
        # Remove leading slash if present
        if path.startswith('/'):
            path = path[1:]
            
        # Construct the full path
        full_path = os.path.join(self.workspace, path)
        
        # Ensure the path is within the workspace for security
        # Using os.path.commonpath prevents directory traversal attacks
        if not os.path.commonpath([self.workspace, os.path.realpath(full_path)]) == self.workspace:
            logger.warning(f"Attempted to access path outside workspace: {path}")
            return self.workspace
            
        return full_path