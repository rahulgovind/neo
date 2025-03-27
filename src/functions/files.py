"""
File system operation functions for the LLM agent.

This module provides functions that allow the LLM to interact with the file system:
- ReadFiles: Reading single or multiple files with wildcard support
- PatchFile: Modifying files with a custom diff format
- OverwriteFile: Creating or completely replacing files
- TreeFile: Getting a tree view of files and directories with metadata
"""

import os
import logging
from typing import Dict, Any, List, Optional, Tuple
from textwrap import dedent

from src.function import Function, Example

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
        
        # Import read function here to avoid circular imports
        from src.files import read
        return read(path, include_line_numbers=True)


class OverwriteFile(Function):
    """
    Creates new files or completely overwrites existing files in the workspace directory.
    
    Features:
    - Creates new files or completely replaces content of existing files
    - Creates parent directories automatically if they don't exist
    - Returns line addition/deletion statistics
    """
    
    def __init__(self, workspace):
        """
        Initialize with the root workspace directory.
        
        Args:
            workspace: Absolute path to the workspace directory
        """
        self.workspace = workspace
    
    def name(self) -> str:
        return "files.overwrite"
    
    def describe(self) -> Dict[str, Any]:
        return {
            "name": self.name(),
            "description": "Create a new file or completely overwrite an existing file in the workspace. Use this function when you need to create a new file or when you want to replace all of a file's content. Do NOT use this function for making small targeted changes to existing files; use files.patch for that purpose.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Path to the file to create or overwrite."
                    },
                    "content": {
                        "type": "string",
                        "description": "The complete content to write to the file, replacing any existing content."
                    }
                },
                "required": ["path", "content"]
            }
        }
    
    def examples(self) -> List[Example]:
        """Returns a list of examples demonstrating usage of this function."""
        return [
            Example(
                description="Create a new Python file (appropriate use case because the file doesn't exist yet)",
                args={
                    "path": "src/utils.py",
                    "content": dedent("""\
                    def format_date(date):
                        \"\"\"Format a date object as a string.\"\"\"
                        return date.strftime('%Y-%m-%d')
                    """)
                },
                result="SUCCESS (+3,-0)"
            ),
            Example(
                description="Overwrite an existing configuration file (appropriate when the entire file needs to be replaced)",
                args={
                    "path": "config.json",
                    "content": dedent("""\
                    {
                      "debug": false,
                      "port": 9000,
                      "api_key": "YOUR_API_KEY"
                    }""")
                },
                result="SUCCESS (+4,-2)"
            ),
            Example(
                description="Inappropriate use case: Don't use overwrite for minor changes to a large file",
                args={
                    "path": "src/large_module.py",
                    "content": "# This would require copying the entire file content with just a small change"
                },
                result="SUCCESS (+300,-298) - This is inefficient; use files.patch instead for targeted changes"
            )
        ]
    
    def invoke(self, args: Dict[str, Any]) -> str:
        """
        Creates or completely overwrites a file in the workspace.
        
        Args:
            args: Dictionary containing 'path' and 'content' keys
            
        Returns:
            Status message with line addition/deletion counts
            
        Raises:
            ValueError: If path or content are missing
        """
        if "path" not in args:
            logger.error("Path not provided to files.overwrite function")
            raise ValueError("Path argument is required")
        
        if "content" not in args:
            logger.error("Content not provided to files.overwrite function")
            raise ValueError("Content argument is required")
        
        path = args["path"]
        content = args["content"]
        
        try:
            # Import overwrite function here to avoid circular imports
            from src.files import overwrite
            success, lines_added, lines_deleted = overwrite(self.workspace, path, content)
            return f"SUCCESS (+{lines_added},-{lines_deleted})"
            
        except PermissionError:
            logger.error(f"Permission denied writing to file: {path}")
            return f"Error: Permission denied writing to file: {path}"
        except Exception as e:
            logger.error(f"Error writing to file {path}: {e}")
            return f"Error writing to file {path}: {str(e)}"


class PatchFile(Function):
    """
    Updates existing files in the workspace using a custom patch format.
    
    Features:
    - Supports targeted updates to existing files using a custom patch format
    - Each change hunk specifies the original line number and operations
    - Operations include insert (+), delete (-), update (-/+), and context (space)
    - Maintains original file line numbers across multiple change hunks
    """
    
    def __init__(self, workspace):
        """
        Initialize with the root workspace directory.
        
        Args:
            workspace: Absolute path to the workspace directory
        """
        self.workspace = workspace
    
    def name(self) -> str:
        return "files.patch"
    
    def describe(self) -> Dict[str, Any]:
        return {
            "name": self.name(),
            "description": dedent(
                """\
                Update an existing file using a custom patch format. This function is designed for making targeted changes to existing files.
                DO NOT use this function to create new files (use files.overwrite instead).
                The custom patch format works as follows:
                - Each change hunk starts with @ LINE_NUMBER where LINE_NUMBER
                - LINE_NUMBER is the line number in the original file that the first line in the change (either additiona, deletion or contextual) corresponds to
                - Lines starting with a space are context lines that should match existing content
                - Lines starting with + are insertions
                - Lines starting with - are deletions
                - Preserve the original whitespace in contextual and deleted lines. Add whitespace as necessary in new lines to match surrounding context.
                - Updates are represented as a - line followed by a + line
                - If multiple consecutive lines are being updated, all deletions must come before all insertions
                - Always use line numbers from the ORIGINAL file, not accounting for previous hunks
                - Include ~2 lines of context before and after changes when possible
                - If two chunks are <= 4 lines apart, combine them into a single chunk
                - DO NOT add additional empty lines to separate chunks
                - When appending to the end of a file, use the last line number + 1"""),
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Path to the file to update."
                    },
                    "content": {
                        "type": "string",
                        "description": "The patch in custom format to apply to the file."
                    }
                },
                "required": ["path", "content"]
            }
        }
    
    def examples(self) -> List[Example]:
        """Returns a list of examples demonstrating usage of this function."""
        return [
            Example(
                description=dedent("""\
                Update a function in a Python file (simple line change with context)

                Original content:
                ...
                4 # Configuration settings
                5 DEBUG = False
                6 PORT = 8000
                7 LOG_LEVEL = 'INFO'
                8 TIMEOUT = 30
                ...

                Updated content:
                ...
                4 # Configuration settings
                5 DEBUG = False
                6 PORT = 9000
                7 LOG_LEVEL = 'INFO'
                8 TIMEOUT = 30
                ..."""),
                args={
                    "path": "src/config.py",
                    "content": dedent("""\
                    @ 5
                     DEBUG = False
                    -PORT = 8000
                    +PORT = 9000
                     LOG_LEVEL = 'INFO'""")
                },
                result="SUCCESS (+1,-1)"
            ),
            Example(
                description=dedent("""\
                Add a new function to an existing file (shows adding content with context and preserving whitespace)

                Original content:
                ...
                44             # Format the data and return
                45             return formatted_data
                46         
                47         # End of existing functions
                ...

                Updated content:
                ...
                44             # Format the data and return
                45             return formatted_data
                46         
                47         # End of existing functions
                48         
                49         def validate_config(config):
                50             \"\"\"Validate the configuration object.\"\"\"
                51             return all(key in config for key in ['api_key', 'endpoint'])
                ..."""),
                args={
                    "path": "src/utils.py",
                    "content": dedent("""\
                    @ 45
                             return formatted_data
                             
                             # End of existing functions
                    +        
                    +        def validate_config(config):
                    +            \"\"\"Validate the configuration object.\"\"\"
                    +            return all(key in config for key in ['api_key', 'endpoint'])""")
                },
                result="SUCCESS (+5,-0)"
            ),
            Example(
                description=dedent("""\
                Multiple non-adjacent changes (demonstrates using original line numbers for each chunk)
                Also note that there is no empty line between chunks.

                Original content:
                ...
                9 # Standard imports
                10 import os
                11 import logging
                12 from datetime import datetime
                ...
                41 
                42 def process_file(filename):
                43     \"\"\"Process a single file.\"\"\"
                44     with open(filename, 'r') as f:
                45         data = f.read()
                ...

                Updated content:
                ...
                9 # Standard imports
                10 import os
                11 import logging
                12 import json
                13 from datetime import datetime
                ...
                42 def process_file(filename):
                43     \"\"\"Process a single file.\"\"\"
                44     with open(filename, 'r', encoding='utf-8') as f:
                45         data = f.read()
                ..."""),
                args={
                    "path": "src/main.py",
                    "content": dedent("""\
                    @ 10
                     import os
                     import logging
                    +import json
                     from datetime import datetime
                    @ 42
                     def process_file(filename):
                         \"\"\"Process a single file.\"\"\"
                    -    with open(filename, 'r') as f:
                    +    with open(filename, 'r', encoding='utf-8') as f:
                         data = f.read()""")
                },
                result="SUCCESS (+2,-1)"
            ),
            Example(
                description=dedent("""\
                Multi-line update (showing deletions before insertions)

                Original content:
                ...
                24 
                25 def transform_data(data):
                26     \"\"\"Transform the input data.\"\"\"
                27     # Old implementation with low performance
                28     result = {}
                29     for key, value in data.items():
                30         result[key] = value.upper()
                31     return result
                ...

                Updated content:
                ...
                24 
                25 def transform_data(data):
                26     \"\"\"Transform the input data.\"\"\"
                27     # New implementation with better performance
                28     result = {
                29         key: value.upper() 
                30         for key, value in data.items()
                31     }
                32     return result
                ..."""),
                args={
                    "path": "src/process.py",
                    "content": dedent("""\
                    @ 25
                     def transform_data(data):
                         \"\"\"Transform the input data.\"\"\"
                    -    # Old implementation with low performance
                    -    result = {}
                    -    for key, value in data.items():
                    -        result[key] = value.upper()
                    +    # New implementation with better performance
                    +    result = {
                    +        key: value.upper() 
                    +        for key, value in data.items()
                    +    }
                         return result""")
                },
                result="SUCCESS (+5,-4)"
            ),
            Example(
                description=dedent("""\
                Adding content to the end of a file (note the line number is last line + 1)

                Original content:
                ...
                76 def last_helper_function():
                77     return "last helper"
                78 # Existing last line of code

                Updated content:
                ...
                76 def last_helper_function():
                77     return "last helper"
                78 # Existing last line of code
                79 
                80 def new_helper_function():
                81     \"\"\"A new helper function added to the end of the file.\"\"\"
                82     return True"""),
                args={
                    "path": "src/helpers.py",
                    "content": dedent("""\
                    @ 78
                     # Existing last line of code
                    +
                    +def new_helper_function():
                    +    \"\"\"A new helper function added to the end of the file.\"\"\"
                    +    return True""")
                },
                result="SUCCESS (+4,-0)"
            ),
            Example(
                description="INCORRECT EXAMPLE: Do not use for creating new files",
                args={
                    "path": "src/new_file.py",
                    "content": dedent("""\
                    @ 1
                    +#!/usr/bin/env python
                    +
                    +def main():
                    +    print('Hello world')
                    +
                    +if __name__ == '__main__':
                    +    main()""")
                },
                result="Error: Cannot apply patch - File does not exist: src/new_file.py. Use files.overwrite for new files."
            )
        ]
    
    def invoke(self, args: Dict[str, Any]) -> str:
        """
        Updates a file using the custom patch format.
        
        Args:
            args: Dictionary containing 'path' and 'content' keys
            
        Returns:
            Status message with line addition/deletion counts
            
        Raises:
            ValueError: If path or content are missing
        """
        if "path" not in args:
            logger.error("Path not provided to files.patch function")
            raise ValueError("Path argument is required")
        
        if "content" not in args:
            logger.error("Content not provided to files.patch function")
            raise ValueError("Content argument is required")
        
        path = args["path"]
        content = args["content"]
        
        try:
            # Import patch function here to avoid circular imports
            from src.files import patch
            success, lines_added, lines_deleted = patch(self.workspace, path, content)
            return f"SUCCESS (+{lines_added},-{lines_deleted})"
        except FileNotFoundError:
            logger.error(f"Cannot apply patch: File does not exist: {path}")
            return f"Error: Cannot apply patch - File does not exist: {path}. Use files.overwrite for new files."
        except Exception as e:
            logger.error(f"Error applying patch to file {path}: {e}")
            return f"Error applying patch to file {path}: {str(e)}"


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
            "description": "Get a tree view of files and directories in the workspace, showing the hierarchical structure with metadata like file sizes and line counts.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Path to the directory to list. Defaults to the root of the workspace."
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
                description="Get a tree view of a specific directory",
                args={"path": "src/models"},
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
            args: Dictionary optionally containing 'path' key
            
        Returns:
            Dictionary with tree structure of files and directories
        """
        # Default to the workspace root if no path is provided
        path = args.get("path", "")
        
        # Always respect gitignore files
        respect_gitignore = True
        
        # Get the tree structure
        try:
            # Import tree function here to avoid circular imports
            from src.files import tree
            tree_structure = tree(self.workspace, path, respect_gitignore)
            
            # When path is empty, we're at the workspace root
            if not path:
                return {
                    "path": "",
                    "tree": tree_structure
                }
            
            # For specific paths, include the relative path in the result
            return {
                "path": path,
                "tree": tree_structure
            }
        except Exception as e:
            logger.error(f"Error generating tree for {path}: {e}")
            return {
                "error": f"Failed to generate tree: {str(e)}"
            }