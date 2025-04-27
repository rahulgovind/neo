"""
Module for converting HTML to Markdown using a rule-based approach with html2text.
"""
import logging
import html2text
import requests
import sys
import argparse
from typing import Optional

# Configure logging
logger = logging.getLogger(__name__)

def fetch_html(url: str) -> str:
    """
    Fetch HTML content from a URL using requests.
    
    Args:
        url: URL to fetch HTML from
        
    Returns:
        HTML content as a string
        
    Raises:
        Exception: If fetching fails
    """
    logger.info(f"Fetching HTML from {url}")
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.114 Safari/537.36',
    }
    response = requests.get(url, headers=headers, timeout=30)
    response.raise_for_status()  # Raise exception for HTTP errors
        
    # Try to get the encoding from the HTTP headers or content
    logger.debug(f"Response encoding: {response.encoding}")
    
    return response.content.decode(response.apparent_encoding)


def from_html(html: str) -> str:
    """Convert HTML to Markdown using html2text."""
    
    # Handle URL input - detect if input is a URL and fetch content
    if html.startswith(('http://', 'https://')):
        try:
            url = html
            html = fetch_html(url)
            logger.info(f"Successfully fetched {len(html)} bytes from {url}")
        except Exception as e:
            logger.error(f"Error fetching URL content: {e}")
            raise
    
    logger.info(f"Converting HTML ({len(html)} chars) to Markdown using html2text")
    
    # Configure the HTML to Markdown converter
    converter = html2text.HTML2Text()
    
    # Configure converter settings
    converter.ignore_links = False
    converter.ignore_images = False
    converter.ignore_tables = False
    converter.body_width = 0  # No wrapping
    converter.unicode_snob = True  # Use Unicode characters instead of ASCII approximations
    converter.inline_links = True  # Use inline links
    converter.wrap_links = False  # Don't wrap links
    converter.protect_links = True  # Don't escape URLs
    converter.mark_code = True  # Use markdown code formatting
    
    # Convert HTML to Markdown
    markdown = converter.handle(html)
    
    # Clean up the markdown
    markdown = markdown.strip()
    
    logger.info(f"Converted HTML to Markdown ({len(markdown)} chars)")
    
    return markdown


def main() -> None:
    """Command-line interface for HTML to Markdown conversion."""
    parser = argparse.ArgumentParser(description='HTML to Markdown conversion')
    parser.add_argument('url', type=str, help='URL to fetch and convert to markdown')
    parser.add_argument('--verbose', action='store_true', help='Enable verbose output')
    
    args = parser.parse_args()
    
    # Set log level based on verbosity
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    else:
        # Only show errors by default
        logging.getLogger().setLevel(logging.ERROR)
    
    try:
        # Fetch URL and convert to markdown
        markdown = from_html(args.url)
        
        # Print the markdown output to stdout
        print(markdown)
        
    except Exception as e:
        logger.error(f"Error converting HTML to markdown: {e}")
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
