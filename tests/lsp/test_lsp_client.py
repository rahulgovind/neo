#!/usr/bin/env python3
"""Test script for LSP client functionality.

This script creates and tests an LSP client connection to a language server.
"""

import logging
import os
import sys
import time
import threading
from pathlib import Path

# Configure logging to see what's happening
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()]
)

# Add the project root to Python path
project_root = Path(__file__).parent
sys.path.append(str(project_root))

# Import LSP client
from src.lsp.client import create_lsp_client
from src.lsp.server import LSPServer

def test_python_client():
    """Test the Python language client."""
    print("\n\nTesting PYTHON LSP client:\n" + "-" * 40)
    client = create_lsp_client("python")
    
    # Give it some time to establish the connection
    time.sleep(2)
    
    # Find a Python file to test with
    test_file = None
    for path in project_root.glob("**/*.py"):
        if "__pycache__" not in str(path) and path.is_file():
            test_file = str(path)
            break
    
    assert test_file is not None, "Could not find a Python file to test with"
    print(f"Testing with file: {test_file}")
    
    # Convert path to URI (file:///)
    if sys.platform == "win32":
        uri = "file:///" + test_file.replace("\\", "/")
    else:
        uri = "file://" + test_file
    
    # Store the URI for later use
    print("Using document URI for LSP operations...")
    
    # Get hover information for a position in the file
    try:
        print("Getting hover information...")
        # Try to get hover info for line 10, character 5
        hover_info = client.text_document_hover(uri, 10, 5)
        print(f"Hover info type: {type(hover_info)}")
        if hover_info and hover_info.contents:
            print(f"Hover information received with {len(hover_info.contents.value)} characters")
        else:
            print("No hover information available at this position")
    except Exception as e:
        print(f"Error getting hover information: {e}")
        raise
    
    # Try to find definitions
    try:
        print("Finding definitions...")
        definitions = client.text_document_definition(uri, 10, 5)
        print(f"Definitions type: {type(definitions)}")
        if definitions and definitions.locations:
            print(f"Found {len(definitions.locations)} definitions")
            for definition in definitions.locations:
                print(f"  - {definition.uri} at line {definition.range.start.line}, col {definition.range.start.character}")
        else:
            print("No definitions found at this position")
    except Exception as e:
        print(f"Error finding definitions: {e}")
        raise
    
    # Verify client is still connected
    assert client._socket is not None, "Client should still have an active socket connection"

def test_shutdown():
    """Test LSP client shutdown functionality."""
    print("Testing Python LSP client shutdown\n")
    
    # Create a client to test shutdown
    client = create_lsp_client("python")
    
    # Clean up resources properly before exiting
    try:
        client.shutdown()
        print("LSP client shut down properly")
    except Exception as e:
        print(f"Error shutting down client: {e}")
        raise

# Allow running as a script too
if __name__ == "__main__":
    test_python_client()
    test_shutdown()
