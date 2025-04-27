#!/usr/bin/env python3
"""
Manual test script for HTML to Markdown conversion.

This script fetches HTML content from specified URLs, optionally trims it,
and converts it to Markdown format.

Usage:
    python -m tests.neo.web.check_html_to_markdown [--urls URL1 URL2...] [--trim-only] [--verbose]

Example:
    python -m tests.neo.web.check_html_to_markdown --urls https://example.com https://python.org --trim-only
"""
import argparse
import logging
import os
import sys
import time
import urllib.request
from pathlib import Path
from typing import List, Optional, Tuple
from urllib.error import URLError

# Set IS_TESTING to True to enable console logging
os.environ["IS_TESTING"] = "1"

# Import from project modules
from src.web.markdown import from_html, fetch_html

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Default URLs to test if none provided
DEFAULT_URLS = [
    "https://docs.databricks.com/aws/en/dlt/cdc",
    "https://en.wikipedia.org/wiki/Markdown",
    "https://www.python.org/"
]

# Output directories
TMP_DIR = Path("/tmp/html_to_markdown")


def setup_directories() -> None:
    """Create necessary directories for output files."""
    TMP_DIR.mkdir(exist_ok=True)
    logger.info(f"Output directory: {TMP_DIR}")


def fetch_html(url: str) -> Tuple[str, str]:
    """
    Fetch HTML content from the specified URL.
    
    Args:
        url: The URL to fetch
        
    Returns:
        Tuple of (html_content, filename)
    """
    logger.info(f"Fetching HTML from {url}")
    try:
        # Add a user agent to avoid being blocked
        headers = {
            "User-Agent": "Mozilla/5.0 (compatible; HTMLToMarkdownTest/1.0)"
        }
        request = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(request, timeout=10) as response:
            html = response.read().decode('utf-8', errors='replace')
            
        # Create a filename from the URL
        hostname = urllib.parse.urlparse(url).netloc
        safe_hostname = hostname.replace('.', '_')
        timestamp = int(time.time())
        filename = f"{safe_hostname}_{timestamp}"
        
        return html, filename
    except URLError as e:
        logger.error(f"Failed to fetch {url}: {e}")
        return "", ""
    except Exception as e:
        logger.exception(f"Unexpected error fetching {url}: {e}")
        return "", ""


def process_url(url: str, trim_only: bool = False, verbose: bool = False) -> None:
    """
    Process a single URL: fetch HTML, trim it, and convert to markdown.
    
    Args:
        url: URL to process
        trim_only: If True, only fetch and trim HTML without markdown conversion
        verbose: If True, print more detailed information
        timeout: Timeout in seconds for LLM API calls
    """
    html, filename = fetch_html(url)
    if not html or not filename:
        logger.error(f"Skipping {url} due to fetch error")
        return
    
    # Save raw HTML
    raw_html_path = TMP_DIR / f"{filename}_raw.html"
    with open(raw_html_path, 'w', encoding='utf-8') as f:
        f.write(html)
    logger.info(f"Saved raw HTML ({len(html)} chars) to {raw_html_path}")
    
    # No trimming step, just save the original HTML
    # Save the HTML to file
    saved_path = TMP_DIR / f"{filename}_saved.html"
    with open(saved_path, 'w', encoding='utf-8') as f:
        f.write(html)
    logger.info(f"Saved HTML ({len(html)} chars) to {saved_path}")
    
    # Convert to markdown if not trim_only
    if not trim_only:
        try:
            logger.info(f"Starting direct conversion to markdown...")
            
            # Convert HTML to Markdown
            markdown = from_html(html)
            
            # Save markdown
            markdown_path = TMP_DIR / f"{filename}.md"
            with open(markdown_path, 'w', encoding='utf-8') as f:
                f.write(markdown)
            logger.info(f"Saved markdown ({len(markdown)} chars) to {markdown_path}")
            
        except Exception as e:
            logger.exception(f"Error converting HTML to markdown: {e}")


def main() -> None:
    """Main function to parse arguments and process URLs."""
    parser = argparse.ArgumentParser(description='HTML to Markdown conversion test')
    parser.add_argument('--urls', nargs='+', help='URLs to fetch and convert')
    parser.add_argument('--trim-only', action='store_true', 
                        help='Only fetch and trim HTML, skip markdown conversion')
    parser.add_argument('--verbose', action='store_true', 
                        help='Enable verbose output')
    
    args = parser.parse_args()
    
    # Use provided URLs or default list
    urls = args.urls if args.urls else DEFAULT_URLS
    
    # Create output directories
    setup_directories()
    
    # Process each URL
    for url in urls:
        process_url(url, trim_only=args.trim_only, verbose=args.verbose)
        
    # Print final instructions
    print("\nProcessing complete! To examine the output files:")
    print(f"1. Raw HTML files: ls -la {TMP_DIR}/*_raw.html")
    print(f"2. Trimmed HTML files: ls -la {TMP_DIR}/*_trimmed.html")
    if not args.trim_only:
        print(f"3. Markdown files: ls -la {TMP_DIR}/*.md")
    print("\nTo view file contents:")
    print("  Raw HTML: head -n 20 /tmp/html_to_markdown/*_raw.html")
    print("  Trimmed HTML: head -n 20 /tmp/html_to_markdown/*_trimmed.html")
    if not args.trim_only:
        print("  Markdown: head -n 20 /tmp/html_to_markdown/*.md")


if __name__ == "__main__":
    main()
