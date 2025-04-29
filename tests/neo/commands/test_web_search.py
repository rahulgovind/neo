"""
Tests for the web_search command.
"""
import pytest
from unittest.mock import patch, MagicMock
import argparse

from src.neo.commands.web_search import WebSearchCommand, WebSearchArguments, WebSearchResult
from src.neo.commands.base import CommandResult
from src.web.search import SearchResult


def test_web_search_arguments():
    """Test that WebSearchArguments can be created correctly."""
    args = WebSearchArguments(
        query="test query"
    )
    
    assert args.query == "test query"


def test_web_search_result():
    """Test that WebSearchResult formats the output correctly."""
    # Create sample search results
    search_results = [
        SearchResult(title="Result 1", description="Description 1", link="https://example1.com"),
        SearchResult(title="Result 2", description="Description 2", link="https://example2.com")
    ]
    
    # Create the command result
    result = WebSearchResult(
        name="web_search",
        results=search_results, 
        query="test query"
    )
    
    # Check message formatting
    assert "Searched web for 'test query'" in result.message


def test_web_search_no_results():
    """Test WebSearchResult when there are no results."""
    # Create an empty result
    result = WebSearchResult(
        name="web_search",
        results=[], 
        query="no results query"
    )
    
    # Check message formatting
    assert "Searched web for 'no results query'" in result.message


@patch('src.web.search.search')
def test_execute_command_success(mock_search):
    """Test successful execution of the WebSearchCommand."""
    # Create sample search results
    search_results = [
        SearchResult(title="Result 1", description="Description 1", link="https://example1.com"),
        SearchResult(title="Result 2", description="Description 2", link="https://example2.com")
    ]
    
    # Configure mock
    mock_search.return_value = search_results
    
    # Create the command and mock session
    command = WebSearchCommand()
    mock_session = MagicMock()
    
    # Execute the command
    result = command.execute(mock_session, "test query")
    
    # Verify the command was successful
    assert isinstance(result, CommandResult)
    assert result.success is True
    assert "Search completed successfully" in result.content
    assert isinstance(result.command_output, WebSearchResult)
    
    # Check that the search function was called with correct arguments
    mock_search.assert_called_once_with(query="test query", max_results=5, headless=True)
    
    # Verify the output contains the results
    assert len(result.command_output.results) == 2
    assert result.command_output.results[0].title == "Result 1"


@patch('src.web.search.search')
def test_execute_command_error(mock_search):
    """Test error handling in the WebSearchCommand."""
    # Configure mock to raise an exception
    mock_search.side_effect = Exception("Search error")
    
    # Create the command and mock session
    command = WebSearchCommand()
    mock_session = MagicMock()
    
    # Execute the command
    result = command.execute(mock_session, "test query")
    
    # Verify the command returned an error
    assert isinstance(result, CommandResult)
    assert result.success is False
    assert "Error performing web search" in result.content
    assert "Search error" in result.content
    assert result.error is not None


def test_parse_statement():
    """Test parsing command statement."""
    command = WebSearchCommand()
    
    # Parse a statement
    args = command._parse_statement("test query")
    
    # Check the parsed arguments
    assert isinstance(args, WebSearchArguments)
    assert args.query == "test query"
    
    # Test with quoted query
    args = command._parse_statement('"test query with spaces"')
    assert args.query == "test query with spaces"
