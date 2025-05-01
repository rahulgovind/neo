"""
Browser module for fetching HTML content using Playwright.
"""
from playwright.sync_api import sync_playwright, Page, BrowserContext
import os
import time
import logging
import base64
from typing import List, Dict, Optional, Union
from dataclasses import dataclass
from contextlib import contextmanager
from pathlib import Path

# Configure logging
logger = logging.getLogger(__name__)

PAGE_LOAD_TIMEOUT = 30  # seconds
ELEMENT_WAIT_TIMEOUT = 10000  # milliseconds

@dataclass
class Action:
    """Represents an interactive element on the page."""
    id: int
    metadata: Dict[str, str]

    def __str__(self) -> str:
        return f"Action(id={self.id}, metadata={self.metadata})"

class BrowserException(Exception):
    """Custom exception for browser-related errors."""
    pass

_playwright = None

class Browser:
    def __init__(self, context: BrowserContext):
        """
        Initialize Browser with a Playwright context.
        
        Args:
            context: Playwright browser context
        """
        self._context = context
        self._page = context.pages[0]
        self._initialize_page()

    def _initialize_page(self) -> None:
        """Set up page event handlers and initialize highlight counter."""
        self._page.evaluate("window.__highlightCounter = 1;")
        self._page.on("domcontentloaded", self._highlight_interactive_elements)
        self._page.on("load", self._highlight_interactive_elements)

    @contextmanager
    def _navigation_context(self, timeout: int = PAGE_LOAD_TIMEOUT):
        """
        Context manager for handling page navigation and stability checks.
        
        Args:
            timeout: Maximum time to wait for navigation in seconds
        """
        try:
            with self._page.expect_navigation(wait_until='networkidle', timeout=timeout * 1000):
                yield
        except Exception as e:
            raise BrowserException(f"Navigation failed: {str(e)}")

    def screenshot(self) -> bytes:
        """Returns a jpeg-encoded screenshot of the current page."""
        try:
            screenshot_bytes = self._page.screenshot(type='jpeg', full_page=True)
            return screenshot_bytes
        except Exception as e:
            raise BrowserException(f"Screenshot failed: {str(e)}")

    def list_actions(self) -> List[Action]:
        """Returns a list of interactive elements on the page."""
        js_actions = self._page.evaluate("""() => {
            const actions = [];
            const highlighted = document.querySelectorAll('[data-highlight]');
            
            for (const el of highlighted) {
                const id = parseInt(el.getAttribute('data-highlight'));
                if (!id) continue;
                
                const metadata = {
                    element_type: el.tagName.toLowerCase(),
                    text: el.innerText?.trim() || '',
                    class: el.className || '',
                    element_id: el.id || '',
                    href: el.href || '',
                    type: el.type || '',
                    name: el.name || '',
                    value: el.value || '',
                    placeholder: el.placeholder || '',
                    aria_label: el.getAttribute('aria-label') || '',
                    role: el.getAttribute('role') || '',
                    alt: el.tagName.toLowerCase() === 'img' ? (el.alt || '') : ''
                };
                
                // Clean metadata by removing empty values
                Object.keys(metadata).forEach(key => 
                    !metadata[key] && delete metadata[key]
                );
                
                actions.push({ id, metadata });
            }
            return actions;
        }""")
        
        return [Action(id=a['id'], metadata=a['metadata']) for a in js_actions]

    def _is_page_stable(self) -> bool:
        """Check if page has finished loading and is stable."""
        pending = self._get_pending_requests()
        if pending:
            return False
        initial_actions = self.list_actions()
        time.sleep(0.5)
        return str(initial_actions) == str(self.list_actions())

    def goto(self, url: str) -> None:
        """
        Navigate to URL and wait for page stability.
        
        Args:
            url: Target URL
            
        Raises:
            BrowserException: If navigation fails or timeout occurs
        """
        logger.info(f"Navigating to {url}")
        try:
            self._page.goto(url, wait_until='domcontentloaded')
            timeout = time.time() + PAGE_LOAD_TIMEOUT
            
            while not self._is_page_stable():
                if time.time() > timeout:
                    logger.warning("Page load timeout reached")
                    break
                time.sleep(0.1)
                
        except Exception as e:
            raise BrowserException(f"Navigation failed: {str(e)}")

    def get_current_url(self) -> str:
        """Return current page URL."""
        return self._page.url

    def get_page_content(self) -> str:
        """Return current page HTML content."""
        try:
            return self._page.content()
        except Exception as e:
            raise BrowserException(f"Failed to get page content: {str(e)}")

    def fill(self, selector: str, text: str) -> None:
        """
        Fill form field and submit with Enter key.
        
        Args:
            selector: Element selector
            text: Text to input
            
        Raises:
            BrowserException: If element not found or action fails
        """
        try:
            logger.info(f"Filling selector {selector} with text")
            self._page.wait_for_selector(selector, state='visible', 
                                       timeout=ELEMENT_WAIT_TIMEOUT)
            self._page.fill(selector, text)
            
            with self._navigation_context():
                self._page.keyboard.press('Enter')
            self._highlight_interactive_elements()
            
        except Exception as e:
            raise BrowserException(f"Fill action failed: {str(e)}")

    def click(self, selector: str) -> None:
        """
        Click element and wait for navigation.
        
        Args:
            selector: Element selector
            
        Raises:
            BrowserException: If element not found or click fails
        """
        try:
            logger.info(f"Clicking selector: {selector}")
            self._page.wait_for_selector(selector, state='visible', 
                                       timeout=ELEMENT_WAIT_TIMEOUT)
            
            with self._navigation_context():
                self._page.click(selector)
                
        except Exception as e:
            raise BrowserException(f"Click action failed: {str(e)}")

    @staticmethod
    def init_chrome(session=None, headless=False) -> 'Browser':
        """
        Initialize Chrome browser instance.
        
        Args:
            session: The session object containing the internal directory path
            headless: Whether to run the browser in headless mode (default: False)
            
        Returns:
            Browser: New browser instance
            
        Raises:
            BrowserException: If browser initialization fails
        """
        try:
            logger.info(f"Initializing Chrome browser (headless: {headless})")
            global _playwright
            if _playwright is None:
                _playwright = sync_playwright().start()
            
            # Get user data directory
            user_data_dir = None
            if session:
                user_data_dir = Path(session.internal_session_dir) / "chrome_data"
            else:
                # For testing/standalone usage
                user_data_dir_env = os.environ.get("USER_DATA_DIR")
                if user_data_dir_env:
                    user_data_dir = Path(user_data_dir_env) / "chrome_data"
            
            if user_data_dir:
                logger.info(f"Using user data directory: {user_data_dir}")
                context = _playwright.chromium.launch_persistent_context(
                    user_data_dir=str(user_data_dir),
                    headless=headless
                )
            else:
                logger.info("No user data directory specified, using temporary profile")
                browser = _playwright.chromium.launch(headless=headless)
                context = browser.new_context(
                    user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36"
                )
            
            # Create a page if none exists
            if len(context.pages) == 0:
                context.new_page()
            
            return Browser(context)
        except Exception as e:
            raise BrowserException(f"Browser initialization failed: {str(e)}")

    def _get_pending_requests(self) -> List[str]:
        """Get list of pending network requests."""
        return self._page.evaluate("""() => {
            return [
                ...(window.__pendingFetch || []),
                ...Array.from(document.querySelectorAll('*'))
                    .filter(el => el._xhr && !el._xhr.completed)
                    .map(el => el._xhr.url),
                ...performance.getEntriesByType('resource')
                    .filter(r => !r.responseEnd)
                    .map(r => r.name)
            ];
        }""")

    def _highlight_interactive_elements(self) -> None:
        """Highlight interactive elements with unique identifiers."""
        logger.info("Highlighting interactive elements")
        js_highlight = """
            // Initialize counter
            if (!window.__highlightCounter) window.__highlightCounter = 1;
            
            const getHighlightColor = (el) => {
                const tag = el.tagName.toLowerCase();
                const role = el.getAttribute('role');
                
                // Input elements
                if (tag === 'textarea' || 
                    (tag === 'input' && !['button', 'submit', 'reset'].includes(el.type)) ||
                    tag === 'select') {
                    return 'red';
                }
                
                // Clickable elements
                if (tag === 'button' ||
                    (tag === 'input' && ['button', 'submit', 'reset'].includes(el.type)) ||
                    role === 'button' ||
                    (tag === 'a' && !el.href.startsWith('#')) ||
                    (el.onclick !== null)) {
                    return 'blue';
                }
                
                return 'red'; // Default color for other interactive elements
            };

            const highlightElement = (el) => {
                if (el.hasAttribute('data-highlight') ||
                    window.getComputedStyle(el).display === 'none' || 
                    window.getComputedStyle(el).visibility === 'hidden') return;
                
                const id = window.__highlightCounter++;
                const color = getHighlightColor(el);
                el.style.outline = `2px solid ${color}`;
                el.setAttribute('data-highlight', id);
                
                const label = document.createElement('div');
                label.textContent = id;
                label.className = "neo-highlight"
                label.style.cssText = `
                    position: fixed;
                    background: ${color};
                    color: white;
                    padding: 2px 5px;
                    border-radius: 3px;
                    font-size: 12px;
                    z-index: 2147483647;
                    pointer-events: none;
                `;
                document.body.appendChild(label);
                
                const updatePosition = () => {
                    const rect = el.getBoundingClientRect();
                    const labelHeight = 24; // Height of label including padding
                    const minTopOffset = 5; // Minimum distance from top of viewport
                    const viewportHeight = window.innerHeight;
                    
                    // Calculate initial position
                    let left = rect.left;
                    let top = rect.top - labelHeight - 5; // 5px gap between element and label
                    
                    // Handle horizontal positioning
                    const labelWidth = label.offsetWidth || 50; // Fallback width if not yet in DOM
                    if (left + labelWidth > window.innerWidth) {
                        left = window.innerWidth - labelWidth - 5;
                    }
                    if (left < 0) {
                        left = 5;
                    }
                    
                    // Handle vertical positioning
                    if (top < minTopOffset) {
                        // If there's not enough space above, try putting it below
                        top = rect.bottom + 5;
                        
                        // If it still doesn't fit below, put it at minimum top offset
                        if (top + labelHeight > viewportHeight) {
                            top = minTopOffset;
                        }
                    }
                    
                    label.style.left = `${Math.max(0, left)}px`;
                    label.style.top = `${Math.max(minTopOffset, top)}px`;
                };
                
                updatePosition();
                document.addEventListener('scroll', updatePosition);
                window.addEventListener('resize', updatePosition);
            };

            const selector = `
                a, button, input, textarea, select,
                [role="button"], [role="link"],
                [onclick], [tabindex]:not([tabindex="-1"]),
                label[for]
            `;
            
            document.querySelectorAll(selector).forEach(highlightElement);

            new MutationObserver((mutations) => {
                mutations.forEach(mutation => {
                    mutation.addedNodes.forEach(node => {
                        if (node.nodeType === 1) {
                            if (node.matches(selector)) highlightElement(node);
                            node.querySelectorAll(selector).forEach(highlightElement);
                        }
                    });
                });
            }).observe(document.body, {childList: true, subtree: true});
        """
        self._page.evaluate(js_highlight)
        logger.info("Interactive elements highlighted")

    def __del__(self):
        """Clean up resources on object destruction."""
        try:
            if hasattr(self, '_context') and self._context:
                self._context.close()
        except Exception as e:
            logger.error(f"Error closing browser context: {e}")


def fetch_html_with_browser(url: str, session=None) -> str:
    """
    Fetch HTML content from a URL using the Browser.
    
    Args:
        url: The URL to fetch HTML from
        session: Optional session object to use for browser data
        
    Returns:
        str: The HTML content of the page
        
    Raises:
        BrowserException: If fetching fails
    """
    browser = None
    try:
        browser = Browser.init_chrome(session)
        browser.goto(url)
        html_content = browser.get_page_content()
        logger.info(f"Successfully fetched HTML content from {url} ({len(html_content)} bytes)")
        return html_content
    except Exception as e:
        raise BrowserException(f"Failed to fetch HTML from {url}: {str(e)}")
    finally:
        if browser:
            del browser
