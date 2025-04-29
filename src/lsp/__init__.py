"""
Language Server Protocol (LSP) implementation.

Provides client and server components for language navigation features
like go-to-definition, find references, and hover information.
"""

from src.lsp.client import LSPClient, create_lsp_client
from src.lsp.server import LSPServer, create_lsp_server

__all__ = [
    'LSPClient',
    'LSPServer',
    'create_lsp_client',
    'create_lsp_server',
]
