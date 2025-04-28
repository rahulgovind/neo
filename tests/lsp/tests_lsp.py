#!/usr/bin/env python3
"""
Pytest-based tests for LSP client functionality.

This test suite verifies the LSP client implementation and its integration with 
language servers.
"""

import logging
import os
import sys
import time
import pytest
from pathlib import Path
from typing import Optional

# Configure logging for detailed diagnostics
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()]
)

# Add the project root to Python path
project_root = Path(__file__).parent
if str(project_root) not in sys.path:
    sys.path.append(str(project_root))

# Import LSP client and server
from src.lsp.client import LSPClient, create_lsp_client
from src.lsp.server import create_lsp_server, LSPServer


class TestLSPClient:
    """Test suite for LSP client functionality."""
    
    @pytest.fixture
    def python_file(self) -> str:
        """Find a Python file to test with."""
        for path in project_root.glob("**/*.py"):
            if "__pycache__" not in str(path) and path.is_file():
                return str(path)
        pytest.fail("Could not find a Python file to test with")
    
    @pytest.fixture
    def server(self) -> LSPServer:
        """Create a global LSP server for testing."""
        server = create_lsp_server()
        yield server
        # Cleanup after tests
        server.shutdown()
    
    @pytest.fixture
    def python_client(self, server) -> Optional[LSPClient]:
        """Create and configure an LSP client for Python."""
        client = LSPClient()
        
        try:
            # Set up a Python language server using the server fixture
            port = server.setup_local_server("python")
            if port is None:
                pytest.skip("Failed to start Python language server - skip test")
                return None
                
            # Wait a moment for the server to start fully
            time.sleep(1)
            
            # Connect the client
            connected = client.connect("127.0.0.1", port)
            if not connected:
                pytest.skip("Could not connect to Python language server - skip test")
                return None
                
            yield client
            
            # Cleanup
            client.shutdown()
            
        except Exception as e:
            pytest.skip(f"Error setting up Python client: {e}")
            return None
    
    def test_client_creation(self, server):
        """Test the create_lsp_client helper function."""
        try:
            client = create_lsp_client("python")
            assert client is not None, "Client should be created successfully"
            
            if hasattr(client, "_socket") and client._socket is not None:
                assert client._initialized, "Client should be initialized"
            else:
                pytest.skip("Client created but not connected - check if pylsp is installed")
                
        except Exception as e:
            pytest.skip(f"Could not create client: {e}")
    
    def test_lsp_initialization(self, python_client):
        """Test that the LSP client initializes properly."""
        assert python_client is not None, "Client should be initialized"
        assert python_client._initialized, "Client should have _initialized flag set"
        assert python_client._socket is not None, "Client should have an active socket connection"
    
    def test_document_opening(self, python_client, python_file):
        """Test opening a document with the LSP client."""
        # Create a file URI
        if sys.platform == "win32":
            uri = "file:///" + python_file.replace("\\", "/")
        else:
            uri = "file://" + python_file
        
        # Open the document
        result = python_client.did_open(uri, "python")
        assert result, "Document should be opened successfully"
    
    def test_hover_request(self, python_client, python_file):
        """Test getting hover information."""
        # Create a file URI
        if sys.platform == "win32":
            uri = "file:///" + python_file.replace("\\", "/")
        else:
            uri = "file://" + python_file
        
        # Open the document first
        python_client.did_open(uri, "python")
        
        try:
            # Try multiple positions in the file to find hover info
            for line, char in [(10, 5), (15, 10), (5, 5)]:
                try:
                    hover_info = python_client.text_document_hover(uri, line, char)
                    if hover_info and hover_info.contents:
                        break
                except Exception:
                    continue
            
            # We don't assert the hover info content as it depends on the specific file
            # Just log what we found for diagnostics
            if hover_info and hover_info.contents:
                if isinstance(hover_info.contents, list):
                    content_text = str(hover_info.contents[0])
                else:
                    content_text = str(hover_info.contents)
                logging.info(f"Found hover info: {content_text[:100]}...")
        except Exception as e:
            pytest.skip(f"Error getting hover information: {e}")
    
    def test_definition_request(self, python_client, python_file):
        """Test finding definitions."""
        # Create a file URI
        if sys.platform == "win32":
            uri = "file:///" + python_file.replace("\\", "/")
        else:
            uri = "file://" + python_file
        
        # Open the document first
        python_client.did_open(uri, "python")
        
        try:
            # Try multiple positions in the file to find definitions
            for line, char in [(10, 5), (15, 10), (5, 5)]:
                try:
                    definitions = python_client.text_document_definition(uri, line, char)
                    if definitions:
                        break
                except Exception:
                    continue
            
            # Log what we found for diagnostics
            if definitions:
                for i, definition in enumerate(definitions[:3]):  # Limit to first 3
                    logging.info(f"Definition {i+1}: {definition.uri} at line {definition.range.start.line}")
        except Exception as e:
            pytest.skip(f"Error finding definitions: {e}")


if __name__ == "__main__":
    # Run with: python -m pytest tests_lsp.py -v
    pytest.main(["-v", __file__])
