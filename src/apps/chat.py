"""
Chat module providing the interactive interface between user and Agent.

This module defines the Chat class which manages the interactive terminal session,
processes user inputs, displays Agent responses, and handles the CLI interaction flow.
It serves as the bridge between the Agent's capabilities and the user.
"""

import os
import sys
import logging
import signal
import time
from typing import Optional, Callable, Dict, Any, List

from rich.console import Console
import glob
from rich.markdown import Markdown
from prompt_toolkit.key_binding import KeyBindings
from rich.panel import Panel
from rich.prompt import Prompt
from prompt_toolkit import PromptSession
from prompt_toolkit.history import FileHistory
from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
from prompt_toolkit.completion import Completer, Completion, WordCompleter, merge_completers
from prompt_toolkit.document import Document
from prompt_toolkit.completion import WordCompleter

from src.agent import Agent
from src.core.context import Context

# Configure logging
logger = logging.getLogger(__name__)


class PathCompleter(Completer):
    """
    Custom completer for filesystem paths relative to a workspace.
    
    This completer suggests files and directories when completing paths,
    making it easier to navigate the workspace when using the /load command.
    """
    
    def __init__(self, workspace: str):
        """
        Initialize the path completer.
        
        Args:
            workspace: Base directory for path completion
        """
        self.workspace = os.path.abspath(workspace)
    
    def get_completions(self, document: Document, complete_event=None):
        """
        Yield completions for the current path.
        
        Args:
            document: The current document (input text)
            complete_event: The completion event
            
        Yields:
            Completion objects for matching paths
        """
        # Only provide completions for /load command
        text = document.text
        if not text.startswith("/load "):
            return
            
        # Extract the part of text we want to complete (after /load and space)
        path_to_complete = text[len("/load "):].strip()
        
        # Generate the absolute path to search in
        if os.path.isabs(path_to_complete):
            base_path = path_to_complete
        else:
            base_path = os.path.join(self.workspace, path_to_complete)
            
        # Get the directory to look in and the prefix to match
        if os.path.isdir(base_path):
            directory = base_path
            prefix = ''
        else:
            directory = os.path.dirname(base_path) or '.'
            prefix = os.path.basename(base_path)
            
        # Convert directory to absolute path if needed
        if not os.path.isabs(directory):
            directory = os.path.join(self.workspace, directory)
            
        # Get all matching files and directories
        try:
            names = os.listdir(directory)
            for name in sorted(names):
                if name.startswith(prefix):
                    # Get the full path
                    full_path = os.path.join(directory, name)
                    # Determine if it's a directory (add trailing slash if so)
                    display_name = name + ('/' if os.path.isdir(full_path) else '')
                    # Calculate what to insert and where to position cursor
                    yield Completion(display_name, start_position=-len(prefix))
        except Exception as e:
            # If directory doesn't exist or can't be read, don't offer completions
            logger.debug(f"Path completion error: {e}")


class Chat:
    """
    Interactive chat interface for communicating with an LLM-powered Agent.
    
    The Chat class provides:
    - A terminal-based interactive session
    - Rich text rendering of markdown responses
    - Command handling for special user inputs
    - History tracking and persistence
    - Session management (start, stop, graceful termination)
    """
    
    # Special commands that can be entered by the user
    COMMANDS = {
        "/exit": "Exit the chat session",
        "/help": "Show this help message",
        "/clear": "Clear the conversation history",
        "/debug": "Toggle debug mode",
    }
    
    def __init__(
        self,
        agent: Agent,
        workspace: str,
        history_file: Optional[str] = None,
    ):
        """
        Initialize the chat interface.
        
        Args:
            agent: The Agent instance that will process messages
            workspace: Path to the code workspace being modified
            history_file: Path to file for storing command history
        """
        self.agent = agent
        self.workspace = workspace
        self.console = Console()
        
        # Initialize session
        self.session = None
        
        # Determine history file location
        if history_file is None:
            # Use a default location in the user's home directory
            history_dir = os.path.join(os.path.expanduser("~"), ".neo")
            os.makedirs(history_dir, exist_ok=True)
            self.history_file = os.path.join(history_dir, "history")
        else:
            self.history_file = history_file
            # Ensure the directory exists
            os.makedirs(os.path.dirname(os.path.abspath(self.history_file)), exist_ok=True)
        
        # Setup custom key bindings
        kb = KeyBindings()
        
        # Add a custom Ctrl+D handler
        @kb.add('c-d')
        def _(event):
            """Exit when the user presses Ctrl+D."""
            self.running = False
            event.app.exit()
        
        # Initialize prompt session with history, auto-suggestion and key bindings
        # Use a combined completer for commands and file paths
        command_completer = WordCompleter(list(self.COMMANDS.keys()))
        path_completer = PathCompleter(workspace)
        
        # Use command completer
        completers = command_completer
        
        self.session_prompt = PromptSession(
            history=FileHistory(self.history_file),
            auto_suggest=AutoSuggestFromHistory(),
            completer=completers,
            key_bindings=kb
        )
        
        # State tracking
        self.debug_mode = False
        self.running = False
        self.interrupt_counter = 0
        self.last_interrupt_time = 0
        
        logger.info(f"Chat initialized with workspace: {workspace}")
    
    def launch(self) -> None:
        """
        Start the chat session.
        
        This method enters the main chat loop and handles:
        - Initial welcome message
        - Signal handlers for graceful termination
        - Processing of user inputs
        - Display of agent responses
        - Special command execution
        
        The method runs until explicitly terminated via command or signal.
        """
        try:
            # Setup signal handlers for graceful termination
            self._setup_signal_handlers()
            
            # No need to create a session anymore
            
            # Display welcome message
            self._print_welcome_message()
            
            # Set running state
            self.running = True
            
            # Main chat loop
            while self.running:
                try:
                    # Get user input
                    user_input = self._get_user_input()
                    
                    # Reset interrupt counter on successful input
                    self.interrupt_counter = 0
                    
                    # Check if this is a special command
                    if user_input.startswith("/"):
                        # Handle commands and check if we should continue
                        should_continue = self._handle_command(user_input)
                        if not should_continue:
                            break
                        continue
                    
                    # Skip empty inputs
                    if not user_input.strip():
                        continue
                    
                    # Process input with agent, including loaded files if present
                    logger.info("Sending user input to agent")
                    # Process user input
                    response = self.agent.process(user_input)
                    
                    # Display the response
                    self._display_response(response)
                    
                except KeyboardInterrupt:
                    # Handle Ctrl+C properly
                    current_time = time.time()
                    
                    # If user rapidly presses Ctrl+C twice within 1 second, exit
                    if current_time - self.last_interrupt_time < 1:
                        self.interrupt_counter += 1
                        if self.interrupt_counter >= 2:
                            self.console.print("\n[yellow]Double interrupt detected. Exiting...[/yellow]")
                            break
                    else:
                        self.interrupt_counter = 1
                    
                    self.last_interrupt_time = current_time
                    self.console.print("\n[yellow]Press Ctrl+C again to exit or /exit to quit.[/yellow]")
                    continue
                except EOFError:
                    # Handle Ctrl+D (EOF)
                    self.console.print("\n[yellow]EOF detected. Exiting...[/yellow]")
                    break
                except Exception as e:
                    # Handle any other exceptions within the loop
                    error_msg = f"Error processing message: {str(e)}"
                    logger.error(error_msg, exc_info=True)
                    self.console.print(f"\n[bold red]Error:[/bold red] {error_msg}")
            
            logger.info("Chat session ended")
            
        except Exception as e:
            # Handle any exceptions in the outer scope
            logger.critical(f"Critical error in chat session: {e}", exc_info=True)
            self.console.print(f"\n[bold red]Critical error:[/bold red] {str(e)}")
            
        finally:
            # Ensure we always clean up, even after errors
            self._cleanup()
    
    def _create_context_with_loaded_files(self) -> str:
        """
        Create a context string with all loaded files.
        
        Returns:
            Formatted string with all loaded file contents
        """
        context = []
        
        for file_path, content in self.loaded_files:
            # Format as specified: filename followed by numbered lines
            file_content = f'"""\n{file_path}\n'
            
            # Add numbered lines
            for i, line in enumerate(content.splitlines(), 1):
                file_content += f"{i} {line}\n"
            
            file_content += '"""'
            context.append(file_content)
        
        return "\n\n".join(context)
    
    def _load_file(self, file_path: str) -> tuple[bool, str]:
        """
        Load file contents from the workspace.
        
        Args:
            file_path: Path to the file to load
            
        Returns:
            Tuple of (success, message or content)
        """
        # Check if path is absolute or relative to workspace
        if not os.path.isabs(file_path):
            file_path = os.path.join(self.workspace, file_path)
        
        try:
            # Check if file exists
            if not os.path.isfile(file_path):
                return False, f"File not found: {file_path}"
            
            # Read file contents
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            return True, content
            
        except Exception as e:
            logger.error(f"Error loading file {file_path}: {e}")
            return False, f"Error loading file: {str(e)}"
    
    def _setup_signal_handlers(self) -> None:
        """
        Set up handlers for system signals to ensure graceful termination.
        
        This handles SIGINT (Ctrl+C) and SIGTERM so the chat session can
        clean up properly even when terminated externally.
        """
        # Using lambda to preserve self reference in the handler
        signal.signal(signal.SIGINT, lambda sig, frame: self._signal_handler(sig, frame))
        signal.signal(signal.SIGTERM, lambda sig, frame: self._signal_handler(sig, frame))
        
        logger.debug("Signal handlers configured")
    
    def _signal_handler(self, sig: int, frame: Any) -> None:
        """
        Handle system signals for immediate termination.
        
        Args:
            sig: Signal number
            frame: Current stack frame
        """
        # Get signal name for logging
        signal_name = "SIGINT" if sig == signal.SIGINT else "SIGTERM"
        logger.info(f"Received {signal_name}, initiating immediate shutdown")
        
        # Set running to false
        self.running = False
        
        # Perform cleanup operations
        try:
            self._cleanup()
        except Exception as e:
            logger.error(f"Error during cleanup on signal {signal_name}: {e}")
        
        # Print exit message to console
        try:
            self.console.print(f"\n[yellow]Received {signal_name} signal. Exiting immediately...[/yellow]")
        except:
            # Fallback if console printing fails
            print(f"\nReceived {signal_name} signal. Exiting immediately...")
        
        # Exit immediately for both SIGINT and SIGTERM
        sys.exit(0)
    
    def _print_welcome_message(self) -> None:
        """Display welcome message with optional workspace information."""
        welcome_text = "[bold green]Neo CLI[/bold green]\n" + "Interactive chat assistant.\n"
        
        # Add workspace info only if it's not the current directory
        if self.workspace and os.path.abspath(self.workspace) != os.path.abspath('.'):
            welcome_text += f"Workspace: [cyan]{self.workspace}[/cyan]\n"
        
        # Add session information
        from src.core.context import get
        try:
            ctx = get()
            welcome_text += f"Session: [magenta]{ctx.session_id}[/magenta]\n"
        except Exception as e:
            logger.warning(f"Could not retrieve session ID: {e}")
            
        welcome_text += "Type [blue]/help[/blue] for available commands.\n"
        welcome_text += "Press [blue]Ctrl+C[/blue] twice quickly or [blue]Ctrl+D[/blue] to exit."
        
        self.console.print(Panel.fit(welcome_text))
    
    def _get_user_input(self) -> str:
        """
        Get input from the user with prompt toolkit.
        
        This method provides:
        - Command history navigation (up/down arrows)
        - Auto-suggestions based on history
        - Command completion
        
        Returns:
            User input string
            
        Raises:
            KeyboardInterrupt: When user presses Ctrl+C
            EOFError: When user presses Ctrl+D
        """
        try:
            # Use a simple leading indicator for the prompt
            return self.session_prompt.prompt("🤔 > ")
        except (KeyboardInterrupt, EOFError):
            # Let these propagate to be handled by the main loop
            raise
    
    def _handle_command(self, command: str) -> bool:
        """
        Process special commands entered by the user.
        
        Args:
            command: The command string starting with /
            
        Returns:
            True if chat should continue, False if it should exit
        """
        # Extract command and args
        parts = command.strip().split()
        cmd = parts[0].lower()
        args = parts[1:] if len(parts) > 1 else []
        
        if cmd == "/exit":
            logger.info("User requested exit")
            self.console.print("[yellow]Exiting chat session...[/yellow]")
            return False
            
        elif cmd == "/help":
            self._show_help()
            
        elif cmd == "/clear":
            # Visual separation for "clearing" the screen
            self.console.print("\n" * 20)
            self._print_welcome_message()
            # Reset agent state - no need to create a new session
            # Also clear loaded files
            self.loaded_files = []
            logger.info("Conversation history and session cleared")
            
        elif cmd == "/debug":
            self.debug_mode = not self.debug_mode
            status = "enabled" if self.debug_mode else "disabled"
            self.console.print(f"[yellow]Debug mode {status}[/yellow]")
            logger.info(f"Debug mode {status}")
            

            
        else:
            self.console.print(f"[red]Unknown command: {cmd}[/red]")
            self.console.print("Type [blue]/help[/blue] for available commands.")
        
        return True
    
    def _show_help(self) -> None:
        """Display available commands and their descriptions."""
        self.console.print("\n[bold blue]Available Commands:[/bold blue]")
        
        for cmd, desc in self.COMMANDS.items():
            self.console.print(f"  [blue]{cmd}[/blue]: {desc}")
            
        self.console.print("\nOtherwise, just type your message to chat with the assistant.")
        self.console.print("\n[bold blue]Keyboard Shortcuts:[/bold blue]")
        self.console.print("  [blue]Ctrl+C[/blue] twice quickly: Exit the application")
        self.console.print("  [blue]Ctrl+D[/blue]: Exit the application")
    
    def _display_response(self, response: str) -> None:
        """
        Display the agent's response with rich formatting.
        
        Args:
            response: Text response from the agent
        """
        # In debug mode, show the raw response
        if self.debug_mode:
            self.console.print("[dim]--- Raw Response ---[/dim]")
            self.console.print(f"[dim]{response}[/dim]")
            self.console.print("[dim]--- End Raw Response ---[/dim]\n")
        
        # Display the response with markdown rendering
        try:
            # Parse the response as markdown for rich formatting
            formatted_response = Markdown(response)
            # Fix: Use a valid box parameter instead of None
            self.console.print(Panel(
                formatted_response,
                border_style="green",
                padding=(1, 2)
            ))
        except Exception as e:
            # Fallback to plain text if markdown parsing fails
            logger.warning(f"Failed to render markdown: {e}")
            self.console.print(Panel(
                response,
                border_style="yellow",
                padding=(1, 2)
            ))
    
    def _cleanup(self) -> None:
        """
        Perform cleanup operations when shutting down.
        
        This ensures resources are properly released and state is saved.
        """
        logger.debug("Performing chat cleanup")
        # Currently just ensures running is False, but provides
        # a hook for future cleanup needs (e.g., saving state)
        self.running = False


class ChatFactory:
    """
    Factory for creating Chat instances with different configurations.
    
    This provides a clean way to construct Chat objects with dependencies
    injected, while hiding the complexity of agent and model setup.
    """
    
    @staticmethod
    def create(
        agent: Agent,
        workspace: str,
        history_file: Optional[str] = None,
        **kwargs
    ) -> Chat:
        """
        Create a new Chat instance with the provided configuration.
        
        Args:
            agent: The Agent instance to use for message processing
            workspace: Path to the code workspace
            history_file: Optional path to history file
            **kwargs: Additional configuration parameters for future extensions
            
        Returns:
            Configured Chat instance ready to launch
        """
        # Create and return the chat instance
        # Additional setup can be added here as needed
        chat = Chat(
            agent=agent,
            workspace=workspace,
            history_file=history_file,
        )
        
        return chat