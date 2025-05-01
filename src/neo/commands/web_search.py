"""
Web search command for executing web searches from the command line.

This command allows users to search the web and get relevant results
directly in the terminal.
"""

import argparse
import logging
import shlex
from dataclasses import dataclass
from typing import List, Optional
from textwrap import dedent

from src.neo.commands.base import Command, CommandResult, CommandOutput
from src.web.search import search as web_search, SearchResult

# Configure logging
logger = logging.getLogger(__name__)


@dataclass
class WebSearchArguments:
    """Structured arguments for web_search command."""
    query: str


@dataclass
class WebSearchResult(CommandOutput):
    """Structure for web search result output."""
    name: str = "web_search"
    message: str = ""
    results: List[SearchResult] = None
    query: str = ""
    
    def __post_init__(self):
        if not self.message and self.query:
            self.message = f"Searched web for '{self.query}'"


class WebSearchCommand(Command):
    """Command to perform web searches."""
    
    command_name = "web_search"
    help_text = "Search the web for information"
    
    @property
    def name(self) -> str:
        return self.command_name
    
    def description(self) -> str:
        return self.help_text
    
    def validate(self, session, statement, data=None) -> None:
        # Validation could be implemented if needed
        pass
    
    def _parse_statement(self, statement: str, data: Optional[str] = None) -> WebSearchArguments:
        """Parse the command statement using argparse."""
        # Validate that data parameter is not set
        if data:
            raise ValueError("The web_search command does not accept data input")
        
        # If statement is just the query itself without any flags, return it directly
        # This handles cases when the statement is passed directly from tests
        if not statement.startswith("-") and " -" not in statement:
            # Handle quoted statement by removing surrounding quotes if present
            clean_statement = statement.strip()
            if (clean_statement.startswith('"') and clean_statement.endswith('"')) or \
               (clean_statement.startswith("'") and clean_statement.endswith("'")):
                clean_statement = clean_statement[1:-1]
            return WebSearchArguments(query=clean_statement)
        
        # Create parser for web_search command
        parser = argparse.ArgumentParser(prog="web_search", exit_on_error=False)
        
        # Add arguments
        parser.add_argument("query", help="Search query")
        
        # Split statement into parts using shlex for proper handling of quoted arguments
        try:
            args = shlex.split(statement)
            
            # Parse arguments
            parsed_args = parser.parse_args(args)
            return WebSearchArguments(query=parsed_args.query)
        except Exception as e:
            # If there's an error parsing, assume the entire statement is the query
            clean_statement = statement.strip()
            if (clean_statement.startswith('"') and clean_statement.endswith('"')) or \
               (clean_statement.startswith("'") and clean_statement.endswith("'")):
                clean_statement = clean_statement[1:-1]
            return WebSearchArguments(query=clean_statement)
        
    def execute(self, session, statement: str, data: Optional[str] = None) -> CommandResult:
        """Execute the web search command."""
        try:
            # Parse the command statement
            args = self._parse_statement(statement, data)
            
            logger.info(f"Performing web search for: {args.query}")
            
            # Perform the search with standard parameters
            # Import here to support patching in tests
            from src.web.search import search
            results = search(session.get_browser(headless=True), query=args.query, max_results=5)
            
            if len(results) == 0:
                content = "No results found"
            else:
                content = "\n".join([f"{i+1}. Title: {result.title}\nLink: {result.link}\nDescription: {result.description}" for i, result in enumerate(results)])
            
            # Return the search results
            return CommandResult(
                success=True,
                content=content,
                command_output=WebSearchResult(
                    results=results,
                    query=args.query
                )
            )
            
        except Exception as e:
            logger.error(f"Error performing web search: {e}")
            return CommandResult(
                success=False,
                content=f"Error performing web search: {str(e)}",
                error=e
            )
    
    def help(self) -> str:
        return dedent(
            """
            Use the `web_search` command to search the web for information.
            
            Usage: web_search QUERY
            
            - QUERY: The search query to send to the search engine. Wrap in quotes
              for queries that involve multiple words.
            
            Example:
            web_search "python programming tutorials"
            Search results for: python programming tutorials
            1. Python Tutorial - W3Schools
               URL: https://www.w3schools.com/python/
               Learn Python with free tutorials and examples.
            
            2. Python Programming Tutorials
               URL: https://www.programiz.com/python-programming
               Step by step Python tutorials for beginners.

            Use the `web_markdown` command to get additional information for each URL.
            """
        )
