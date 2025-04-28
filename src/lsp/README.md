# Python LSP Client

A simplified Language Server Protocol (LSP) client implementation focused on Python code navigation.

## Overview

This module provides a lightweight LSP client that connects to a Python Language Server (pylsp) and offers core code intelligence features:

- Hover information: Get documentation and type information for symbols
- Definition lookup: Find where symbols are defined
- Document synchronization: Keep the server updated about open files

## Usage

```python
from src.lsp.client import create_lsp_client

# Create a client instance connected to Python LSP server
client = create_lsp_client()

# Open a document to enable LSP features for it
file_uri = "file:///path/to/your/file.py"
client.did_open(uri=file_uri, language_id="python")

# Get hover information (type hints, docs) for a symbol
hover_info = client.text_document_hover(
    uri=file_uri,
    line=10,    # 0-based line number
    character=5 # 0-based character position
)

# Find definition of a symbol
definitions = client.text_document_definition(
    uri=file_uri,
    line=10,
    character=5
)

# Clean up when done
client.shutdown()
```

## Requirements

- Python 3.6 or higher
- `python-lsp-server` (pylsp) must be installed:
  ```
  pip install python-lsp-server
  ```

## Implementation Notes

- The client automatically handles connection to pylsp and manages its lifecycle
- Communication happens over TCP sockets with JSON-RPC
- The implementation is deliberately simplified to focus on core navigation features
- Unlike full LSP clients, this implementation does not support document editing, completion, diagnostics, or workspace-level features

## API Reference

### LSPClient

The main client class for communicating with the Python LSP server.

#### Core Methods

- `text_document_hover(uri, line, character)`: Get hover information for symbol at position
- `text_document_definition(uri, line, character)`: Find definition locations for symbol at position
- `did_open(uri, language_id, version=1)`: Notify server that a document has been opened
- `shutdown()`: Terminate the LSP session and clean up resources

### Helper Functions

- `create_lsp_client(language="python")`: Create an LSP client connected to a shared server instance
