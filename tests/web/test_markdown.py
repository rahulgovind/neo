"""
Tests for the markdown module functionality.
"""
import pytest
from unittest.mock import patch, MagicMock
from src.web.markdown import from_html, from_url


def test_from_html():
    """Test HTML to Markdown conversion."""
    # Simple HTML to test conversion
    html = "<h1>Hello World</h1><p>This is a test.</p>"
    markdown = from_html(html)
    
    # Check that the conversion worked correctly
    assert "# Hello World" in markdown
    assert "This is a test." in markdown


@patch('src.web.markdown.fetch_html')
def test_from_html_with_url(mock_fetch):
    """Test HTML to Markdown conversion when passing a URL."""
    # Mock the fetch_html function to return a simple HTML
    mock_fetch.return_value = "<h1>Hello World</h1><p>This is a test.</p>"
    
    # Test conversion with a URL
    with patch('src.web.markdown.from_url') as mock_from_url:
        mock_from_url.return_value = "# Hello World\n\nThis is a test."
        result = from_html("https://example.com")
        
        # Verify the URL handling works
        mock_from_url.assert_called_once_with("https://example.com")
        assert "# Hello World" in result


@patch('src.web.browser.Browser')
def test_from_url_with_session(mock_browser_class):
    """Test fetching a URL and converting to markdown using a session."""
    # Mock browser instance
    mock_browser = MagicMock()
    mock_browser.get_page_content.return_value = "<h1>Hello World</h1><p>This is a test.</p>"
    
    # Mock session
    mock_session = MagicMock()
    mock_session.get_browser.return_value = mock_browser
    
    # Test conversion with a URL
    with patch('src.web.markdown.from_html') as mock_from_html:
        mock_from_html.return_value = "# Hello World\n\nThis is a test."
        result = from_url("https://example.com", session=mock_session)
        
        # Verify browser interaction
        mock_session.get_browser.assert_called_once_with(headless=True)
        mock_browser.goto.assert_called_once_with("https://example.com")
        mock_browser.get_page_content.assert_called_once()
        mock_from_html.assert_called_once()
        
        # Check the result
        assert result == "# Hello World\n\nThis is a test."


@patch('src.web.markdown.fetch_html')
def test_from_url_without_session(mock_fetch):
    """Test fetching a URL and converting to markdown without a session."""
    # Mock the fetch_html function
    mock_fetch.return_value = "<h1>Hello World</h1><p>This is a test.</p>"
    
    # Test conversion with a URL
    with patch('src.web.markdown.from_html') as mock_from_html:
        mock_from_html.return_value = "# Hello World\n\nThis is a test."
        result = from_url("example.com")  # Test without http prefix
        
        # Verify URL normalization and fetch
        mock_fetch.assert_called_once_with("https://example.com")
        mock_from_html.assert_called_once()
        
        # Check the result
        assert result == "# Hello World\n\nThis is a test."
