"""
Search module to perform web searches and extract relevant information.
"""

import logging
from bs4 import BeautifulSoup
from dataclasses import dataclass
from typing import List
from src.web.browser import Browser, BrowserException
from typing import Tuple
from dataclasses import replace
from concurrent.futures import ThreadPoolExecutor, as_completed

@dataclass
class SearchResult:
    """Data class representing a search result."""

    title: str
    description: str
    link: str


# Configure logging
logger = logging.getLogger(__name__)


def perform_bing_search(
    browser: Browser, query: str, max_results: int = 5
) -> List[SearchResult]:
    """
    Use Playwright to search Bing and return the first page of results.

    Args:
        browser: Browser instance to use for search
        query: The search query to perform
        max_results: Maximum number of results to extract

    Returns:
        List of SearchResult objects containing search results
    """
    results = []

    # Navigate to Bing
    logger.info("Navigating to Bing")
    browser.goto("https://www.bing.com")

    # Enter search query
    logger.info(f"Entering search query: {query}")
    browser.fill("#sb_form_q", query)

    # Wait for results to load
    logger.info("Waiting for search results")
    browser._page.wait_for_selector(".b_algo", timeout=10000)

    # Get the HTML content
    html_content = browser.get_page_content()

    # Process HTML with BeautifulSoup
    soup = BeautifulSoup(html_content, "html.parser")

    # Find all search result items
    result_elements = soup.select(".b_algo")

    # Process each result element
    for element in result_elements:
        try:
            # Extract all results from this element (main + deep links)
            element_results = extract_search_result(element)

            # Add results until we reach max_results
            for result in element_results:
                results.append(result)
                if len(results) >= max_results:
                    break

            # If we've reached max_results, stop processing
            if len(results) >= max_results:
                break

        except Exception as e:
            logger.warning(f"Error extracting result: {e}")
            continue

    logger.info(f"Found {len(results)} search results")
    return results


def extract_search_result(element) -> List[SearchResult]:
    """
    Extract search result information from a BeautifulSoup element.

    Args:
        element: BeautifulSoup element representing a search result

    Returns:
        List of SearchResult objects containing search results
    """
    results = []

    try:
        # Get main result title and URL
        title_element = element.select_one("h2 a")
        if not title_element:
            return results

        main_title = title_element.get_text(strip=True)
        main_url = title_element.get("href")

        if not main_url or not main_url.startswith("http"):
            return results

        # Extract main snippet
        main_snippet = ""

        # Check for tabbed content
        tab_contents = element.select(".tab-content .tab-ajaxCompleted")
        if tab_contents:
            tab_titles = element.select(".tab-menu li")
            tab_snippets = []

            for i, tab in enumerate(tab_contents):
                tab_title = (
                    tab_titles[i].get_text(strip=True)
                    if i < len(tab_titles)
                    else f"Tab {i+1}"
                )
                tab_text = tab.get_text(strip=True)
                if tab_text:
                    tab_snippets.append(f"# {tab_title}\n{tab_text}")

            main_snippet = "\n\n".join(tab_snippets)

        # Check for standard snippet
        elif element.select_one(".b_caption p"):
            main_snippet = element.select_one(".b_caption p").get_text(strip=True)

        # Check for lineclamp snippet
        elif element.select_one(".b_lineclamp2"):
            main_snippet = element.select_one(".b_lineclamp2").get_text(strip=True)

        # If still no snippet, try any text content in the element
        if not main_snippet:
            main_snippet = element.get_text(strip=True)
            # Limit snippet size if it's too large
            if len(main_snippet) > 500:
                main_snippet = main_snippet[:500] + "..."

        # Add the main result
        results.append(
            SearchResult(title=main_title, link=main_url, description=main_snippet)
        )

        # Check for deep links and add them as separate results
        deep_links = element.select(".b_vlist2col.b_deep li")
        for li in deep_links:
            deep_link_title = li.select_one("h3 a")
            deep_link_text = li.select_one("p")

            if deep_link_title and deep_link_text:
                # Get the truncated title from the HTML
                title_text = deep_link_title.get_text(strip=True)
                link_url = deep_link_title.get("href")
                link_desc = deep_link_text.get_text(strip=True)

                # Try to improve truncated titles by extracting from URL path or using HTML title attribute
                if title_text.endswith("…"):
                    # First check if there's a title attribute that might have the full title
                    full_title = deep_link_title.get("title")
                    if full_title:
                        title_text = full_title
                    else:
                        # Try to extract a better title from the URL path
                        try:
                            from urllib.parse import urlparse

                            parsed_url = urlparse(link_url)
                            path = parsed_url.path

                            # Get the last part of the path which might be descriptive
                            path_parts = [p for p in path.split("/") if p]
                            if path_parts:
                                last_part = path_parts[-1]
                                # Replace hyphens and underscores with spaces
                                last_part = last_part.replace("-", " ").replace(
                                    "_", " "
                                )
                                # Some basic title casing
                                improved_title = " ".join(
                                    word.capitalize() for word in last_part.split()
                                )

                                # If the improved title is substantially better, use it
                                if len(improved_title) > len(title_text):
                                    title_text = improved_title
                        except Exception as e:
                            # Log but continue if URL parsing fails
                            logger.debug(f"Error improving title from URL: {e}")

                # Only add if we have a valid URL
                if link_url and link_url.startswith("http"):
                    results.append(
                        SearchResult(
                            title=title_text, link=link_url, description=link_desc
                        )
                    )

        return results

    except Exception as e:
        logger.warning(f"Error in extract_search_result: {e}")
        return results


def enrich_search_results(
    search_results: List[SearchResult], max_workers: int = 3
) -> List[SearchResult]:
    """
    Enrich search results by fetching more accurate titles and descriptions directly from the linked pages.

    Args:
        search_results: List of SearchResult objects to enrich
        max_workers: Maximum number of concurrent requests

    Returns:
        Enriched list of SearchResult objects
    """
    if not search_results:
        return search_results

    logger.info(f"Enriching {len(search_results)} search results")

    def enrich_single_result(
        result: SearchResult,
    ) -> SearchResult:
        """Fetch metadata for a single search result."""
        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
            }
            response = requests.get(result.link, headers=headers, timeout=5)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, "html.parser")

            # Extract page title
            title_tag = soup.find("title")
            if title_tag and title_tag.text.strip():
                result = replace(result, title=title_tag.text.strip())

            # Extract page description
            desc_tag = (
                soup.find("meta", attrs={"name": "description"})
                or soup.find("meta", attrs={"property": "og:description"})
                or soup.find("meta", attrs={"name": "twitter:description"})
            )
            if desc_tag and desc_tag.get("content"):
                result = replace(result, description=desc_tag.get("content").strip())
        except Exception as e:
            logger.debug(f"Error fetching metadata for {result.link}: {e}")

        return result

    enriched_results = []
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_result = {
            executor.submit(enrich_single_result, result): result
            for result in search_results
        }
        for future in as_completed(future_to_result):
            original_result = future_to_result[future]
            try:
                enriched_result = future.result()

                enriched_results.append(enriched_result)

            except Exception as e:
                logger.error(f"Error processing search result: {e}")
                # Keep the original result if enrichment fails
                enriched_results.append(original_result)

    # Sort enriched results to match original order
    result_order = {result.link: i for i, result in enumerate(search_results)}
    enriched_results.sort(key=lambda r: result_order.get(r.link, 9999))

    return enriched_results


def search(
    browser: Browser, query: str, max_results: int = 5
) -> List[SearchResult]:
    """
    Perform a web search and extract results directly from the HTML.

    Args:
        browser: Browser instance to use for search
        query: Search query to perform
        max_results: Maximum number of search results to process

    Returns:
        List of SearchResult objects containing search results
    """
    logger.info(f"Starting search for: '{query}'")

    # Search Bing with direct HTML extraction
    search_results = perform_bing_search(browser, query, max_results)

    # Always enrich search results
    if search_results:
        search_results = enrich_search_results(search_results)

    # Return the search results (may be empty if none found)
    return search_results


def format_results_for_display(results: List[SearchResult], query: str) -> str:
    """Format search results for display in the terminal."""
    if not results:
        return f"No results found for: {query}"

    output = []
    output.append(f"# Search Results for: {query}\n")

    for i, result in enumerate(results, 1):
        title = result.title
        url = result.link
        snippet = result.description

        output.append(f"## {i}. [{title}]({url})")
        output.append(f"{snippet}\n")

    return "\n".join(output)


def main() -> None:
    """Command-line interface for search functionality."""
    parser = argparse.ArgumentParser(description="Web Search")
    parser.add_argument("query", type=str, help="Search query")
    parser.add_argument(
        "--max-results",
        type=int,
        default=5,
        help="Maximum number of search results to retrieve (default: 5)",
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        help="Run browser in headless mode (default: False)",
    )
    parser.add_argument("--verbose", action="store_true", help="Enable verbose output")

    args = parser.parse_args()

    # Set log level based on verbosity
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    try:
        # Perform search
        print(f"Searching for '{args.query}'...")
        search_results = search(
            args.query, max_results=args.max_results, headless=args.headless
        )

        # Display results
        formatted_results = format_results_for_display(search_results, args.query)

        print("\n" + "=" * 80)
        print("SEARCH RESULTS FOR: " + args.query)
        print("=" * 80)
        print(formatted_results)
        print("=" * 80)

    except Exception as e:
        logger.error(f"Error during search: {e}")
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
