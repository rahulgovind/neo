"""
Module for converting HTML to Markdown using a rule-based approach with html2text.
"""

import logging
import html2text
import requests
import sys
import argparse
import re
from typing import Optional, Union
import urllib.parse
from src.web.browser import Browser
from bs4 import BeautifulSoup
from bs4.element import Comment


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
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.114 Safari/537.36",
    }
    response = requests.get(url, headers=headers, timeout=30)
    response.raise_for_status()  # Raise exception for HTTP errors

    # Try to get the encoding from the HTTP headers or content
    logger.debug(f"Response encoding: {response.encoding}")

    return response.content.decode(response.apparent_encoding)


def filter_invisible_elements(html: str) -> str:
    """
    Filter out invisible elements from HTML before conversion to Markdown.
    
    Args:
        html: HTML content as a string
        
    Returns:
        Filtered HTML with invisible elements removed
    """
    logger.info("Filtering invisible elements from HTML")
    
    soup = BeautifulSoup(html, 'html.parser')
    
    # Remove elements with style="display:none" or style="visibility:hidden"
    for element in soup.find_all(style=True):
        style = element.get('style', '').lower()
        if 'display:none' in style or 'visibility:hidden' in style:
            element.decompose()
    
    # Remove hidden form elements
    for element in soup.find_all(type='hidden'):
        element.decompose()
    
    # Remove script and style tags
    for tag in soup.find_all(['script', 'style', 'noscript']):
        tag.decompose()
    
    # Remove elements with hidden class
    for element in soup.find_all(class_=True):
        classes = element.get('class', [])
        if any(c in ['hidden', 'hide', 'invisible', 'd-none'] for c in classes):
            element.decompose()
    
    # Remove comment nodes
    for comment in soup.find_all(text=lambda text: isinstance(text, Comment)):
        comment.extract()
    
    # Remove aria-hidden elements
    for element in soup.find_all(attrs={"aria-hidden": "true"}):
        element.decompose()
        
    logger.debug(f"Filtered HTML size: {len(str(soup))} chars")
    
    return str(soup)


def from_url(browser: Browser, url: str) -> str:
    """Fetch a web page and convert it to markdown using a headless browser.
    
    Args:
        browser: Browser object to use for fetching and converting
        url: URL to fetch and convert to markdown
        
    Returns:
        The page content converted to markdown
        
    Raises:
        Exception: If fetching or conversion fails
    """
    logger.info(f"Fetching and converting {url} to markdown using headless browser")
    
    # Ensure URL has scheme
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    
    browser.goto(url)
    html = browser.get_page_content()
    
    # Convert the HTML to markdown
    return from_html(html)


def from_html(html: str) -> str:
    """Convert HTML to Markdown using html2text."""

    # Handle URL input - detect if input is a URL and fetch content
    if isinstance(html, str) and html.startswith(("http://", "https://")):
        return from_url(html)
        
    logger.info(f"Converting HTML ({len(html)} chars) to Markdown using html2text")

    # Filter out invisible elements before conversion
    soup = BeautifulSoup(html, 'html.parser')
    
    # Remove elements with display:none or visibility:hidden in style attribute
    for element in soup.find_all(lambda tag: tag.has_attr('class') and 'neo-highlight' in tag['class']):
        element.decompose()
    
    filtered_html = str(soup)
    logger.debug(f"Filtered HTML size: {len(filtered_html)} chars")
    
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

    # Convert filtered HTML to Markdown
    markdown = converter.handle(filtered_html)

    # Clean up the markdown
    markdown = markdown.strip()

    logger.info(f"Converted HTML to Markdown ({len(markdown)} chars)")

    return markdown


def main() -> None:
    """Command-line interface for HTML to Markdown conversion."""
    parser = argparse.ArgumentParser(description="HTML to Markdown conversion")
    parser.add_argument("url", type=str, help="URL to fetch and convert to markdown")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose output")
    parser.add_argument("--headless", action="store_true", help="Run browser in headless mode")

    args = parser.parse_args()

    # Set log level based on verbosity
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    else:
        # Only show errors by default
        logging.getLogger().setLevel(logging.ERROR)

    try:
        # Fetch URL and convert to markdown
        markdown = from_url(Browser.init_chrome(headless=args.headless), args.url)

        # Print the markdown output to stdout
        print(markdown)

    except Exception as e:
        logger.error(f"Error converting HTML to markdown: {e}")
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()