#!/usr/bin/env python3
"""
Data models for LSP responses.

This module contains dataclasses representing structured results from LSP operations
such as hover, definition, and references.
"""

from dataclasses import dataclass
from typing import Dict, List, Optional, Any


@dataclass
class LspPosition:
    """Position in a document expressed as zero-based line and character offset."""
    line: int
    character: int


@dataclass
class LspRange:
    """Range in a document expressed as start and end positions."""
    start: LspPosition
    end: LspPosition


@dataclass
class LspLocation:
    """Location in a document expressed as a URI and a range."""
    uri: str
    range: LspRange


@dataclass
class LspHoverContent:
    """Content of a hover message."""
    value: str
    kind: Optional[str] = None


@dataclass
class LspHoverResult:
    """Result of a hover request."""
    contents: Optional[LspHoverContent] = None
    range: Optional[LspRange] = None


@dataclass
class LspDefinitionResult:
    """Result of a definition request."""
    locations: List[LspLocation]


@dataclass
class LspReferencesResult:
    """Result of a references request."""
    locations: List[LspLocation]
