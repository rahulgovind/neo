"""
Tests for the search module functionality.
"""
import pytest
from unittest.mock import patch, MagicMock
from src.web.search import search, SearchResult, enrich_search_results


def test_search_result_class():
    """Test SearchResult dataclass functionality."""
    result = SearchResult(
        title="Test Title",
        description="Test Description",
        link="https://example.com"
    )
    
    assert result.title == "Test Title"
    assert result.description == "Test Description"
    assert result.link == "https://example.com"


@patch('src.web.search.perform_bing_search')
def test_search_basic(mock_perform_search):
    """Test that search function works correctly."""
    # Create mock search results
    mock_results = [
        SearchResult(title="Result 1", description="Description 1", link="https://example1.com"),
        SearchResult(title="Result 2", description="Description 2", link="https://example2.com")
    ]
    
    # Configure mock to return results
    mock_perform_search.return_value = mock_results
    
    # Test with mocked enrichment
    with patch('src.web.search.enrich_search_results', return_value=mock_results):
        results = search("test query", max_results=2)
        
        # Verify search was performed correctly
        mock_perform_search.assert_called_once_with("test query", 2, headless=True)
        
        # Verify results
        assert len(results) == 2
        assert results[0].title == "Result 1"
        assert results[1].link == "https://example2.com"


@patch('src.web.search.perform_bing_search')
def test_search_empty_results(mock_perform_search):
    """Test search function when no results are found."""
    # Configure mock to return empty results
    mock_perform_search.return_value = []
    
    # Test search with empty results
    results = search("query with no results")
    
    # Verify empty results handling
    assert results == []


@patch('src.web.search.requests.get')
def test_enrich_search_results(mock_get):
    """Test enrichment of search results."""
    # Create mock response for requests with metadata in HTML
    mock_response = MagicMock()
    mock_response.text = """
    <html>
        <head>
            <meta name="description" content="Enhanced description">
            <title>Enhanced Title</title>
        </head>
        <body><p>Additional content</p></body>
    </html>"""
    mock_get.return_value = mock_response
    
    # Create test results to enrich
    original_results = [
        SearchResult(title="Result 1", description="Description 1", link="https://example1.com"),
        SearchResult(title="Result 2", description="Description 2", link="https://example2.com")
    ]
    
    # Use patch for BeautifulSoup to simulate metadata extraction
    with patch('src.web.search.BeautifulSoup') as mock_bs:
        # Set up the mock soup to return our metadata
        mock_soup = MagicMock()
        mock_bs.return_value = mock_soup
        
        # Mock the find method to return metadata tags
        meta_tag = MagicMock()
        meta_tag.get.return_value = "Enhanced description"
        mock_soup.find.return_value = meta_tag
        
        # Test enrichment
        enriched = enrich_search_results(original_results)
        
        # Verify enrichment
        assert len(enriched) == 2
        assert mock_get.call_count == 2  # Should be called for each result
        
        # URLs should be preserved
        assert enriched[0].link == "https://example1.com"
        assert enriched[1].link == "https://example2.com"
