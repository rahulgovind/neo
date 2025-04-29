"""
Tests for the web_markdown command.
"""
import pytest
import os
from unittest.mock import patch, MagicMock, mock_open
import argparse
import tempfile

from src.neo.commands.web_markdown import WebMarkdownCommand, WebMarkdownArguments, WebMarkdownResult
from src.neo.commands.base import CommandResult


def test_web_markdown_arguments():
    """Test that WebMarkdownArguments can be created correctly."""
    args = WebMarkdownArguments(
        url="https://example.com"
    )
    
    assert args.url == "https://example.com"


def test_web_markdown_result():
    """Test that WebMarkdownResult formats the output correctly."""
    result = WebMarkdownResult(
        name="web_markdown",
        markdown="# Test Markdown\n\nThis is a test",
        url="https://example.com",
        output_file="/path/to/output.md"
    )
    
    # Check the message is correctly generated
    assert "Fetched https://example.com" in result.message


def test_web_markdown_result_with_long_content():
    """Test that WebMarkdownResult handles long content correctly."""
    # Create a markdown string with many lines
    lines = [f"Line {i}" for i in range(1, 600)]
    long_markdown = "\n".join(lines)
    
    # Test with long content
    result = WebMarkdownResult(
        name="web_markdown",
        markdown=long_markdown,
        url="https://example.com",
        output_file="/path/to/output.md"
    )
    
    # Check the message is correctly generated
    assert "Fetched https://example.com" in result.message


@patch('src.web.markdown.from_url')
def test_execute_command_success(mock_from_url):
    """Test successful execution of the WebMarkdownCommand."""
    # Mock the from_url function
    mock_from_url.return_value = "# Test Markdown\n\nThis is a test"
    
    # Create a mock session with internal_session_dir
    mock_session = MagicMock()
    mock_session.internal_session_dir = "/path/to/session"
    mock_session.get_browser.return_value = MagicMock()  # Mock browser object
    
    # Create the command
    command = WebMarkdownCommand()
    
    # Mock os.makedirs and file open operations
    with patch('os.makedirs') as mock_makedirs, \
         patch('builtins.open', mock_open()) as mock_file, \
         patch('os.path.join', return_value="/path/to/session/web_markdown/example_com_timestamp.md"):
        
        # Execute the command
        result = command.execute(mock_session, "https://example.com")
        
        # Verify the command was successful
        assert result.success is True
        assert "Successfully converted" in result.content
        assert "saved to" in result.content
        assert isinstance(result.command_output, WebMarkdownResult)
        
        # Verify that file operations were attempted
        assert mock_makedirs.called
    
    # Verify mock_from_url was called as expected
    mock_from_url.assert_called_once_with(url="https://example.com", session=mock_session)


@patch('src.web.markdown.from_url')
def test_execute_command_with_auto_file_saving(mock_from_url):
    """Test WebMarkdownCommand with automatic file saving to session directory."""
    # Mock the from_url function
    mock_from_url.return_value = "# Test Markdown\n\nThis is a test"
    
    # Create a mock session with internal_session_dir
    mock_session = MagicMock()
    mock_session.internal_session_dir = "/path/to/session"
    mock_session.get_browser.return_value = MagicMock()  # Mock browser object
    
    # Create the command
    command = WebMarkdownCommand()
    
    # Mock os.makedirs and file open operations
    with patch('os.makedirs') as mock_makedirs, \
         patch('builtins.open', mock_open()) as mock_file, \
         patch('os.path.join', return_value="/path/to/session/web_markdown/example_com_timestamp.md") as mock_join:
        
        # Execute the command
        result = command.execute(mock_session, "https://example.com")
    
    # Verify the command was successful
    assert isinstance(result, CommandResult)
    assert result.success is True
    
    # Verify the directory was created
    assert mock_makedirs.called
    
    # Verify mock_from_url was called as expected
    mock_from_url.assert_called_once_with(url="https://example.com", session=mock_session)
    
    # Verify the output contains the correct message in content field
    assert "saved to" in result.content


@patch('src.web.markdown.from_url')
def test_execute_command_error(mock_from_url):
    """Test error handling in the WebMarkdownCommand."""
    # Configure mock to raise an exception
    mock_from_url.side_effect = Exception("Conversion error")
    
    # Create a mock session
    mock_session = MagicMock()
    mock_session.internal_session_dir = "/path/to/session"
    
    # Create the command
    command = WebMarkdownCommand()
    
    # Execute the command
    result = command.execute(mock_session, "https://example.com")
    
    # Verify the command returned an error
    assert isinstance(result, CommandResult)
    assert result.success is False
    assert "Error converting webpage to markdown" in result.content
    assert "Conversion error" in result.content
    assert result.error is not None


def test_parse_statement():
    """Test parsing command statement."""
    command = WebMarkdownCommand()
    
    # Parse a statement
    args = command._parse_statement("https://example.com")
    
    # Check the parsed arguments
    assert isinstance(args, WebMarkdownArguments)
    assert args.url == "https://example.com"
    
    # Test with quoted URL
    args = command._parse_statement('"https://example.com/with space"')
    assert args.url == "https://example.com/with space"
