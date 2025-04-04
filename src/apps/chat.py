"""
Chat module providing the interactive interface between user and Agent.

This module defines the Chat class which manages the interactive terminal session,
processes user inputs, displays Agent responses, and handles the CLI interaction flow.
It serves as the bridge between the Agent's capabilities and the user.
"""

import os
import logging
import signal
import time
import sys
from typing import Optional, Any, Tuple

from rich.console import Console
from rich.markdown import Markdown
from prompt_toolkit.key_binding import KeyBindings
from rich.panel import Panel
from prompt_toolkit import PromptSession
from prompt_toolkit.history import FileHistory
from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
from prompt_toolkit.completion import WordCompleter

from src.core.context import Context

# Configure logging
logger = logging.getLogger(__name__)


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
        "/debug": "Toggle debug mode",
        "/new-session": "Create a new session",
    }
    
    def __init__(
        self,
        workspace: str,
        history_file: Optional[str] = None,
    ):
        """
        Initialize the chat interface.
        
        Args:
            workspace: Path to the code workspace being modified
            history_file: Path to file for storing command history
        """
        self.workspace = workspace
        
        # Setup active session tracking
        self.active_session_file = os.path.join(os.path.expanduser("~"), ".neo", "active_session_id")
        
        # Determine if we should use an existing session or create a new one
        session_id, is_new_session = self._get_or_create_session_id()
        
        # Create and initialize the context
        if session_id:
            self._ctx = Context.builder().session_id(session_id).workspace(workspace).initialize()
        else:
            self._ctx = Context.builder().workspace(workspace).initialize()
            
        # Save the current session as active
        self._save_active_session(self._ctx.session_id)
        
        # Get the agent from the context
        self._console = Console()
        
        # Show session status on initialization
        session_status = "Using existing" if not is_new_session else "Created new"
        logger.info(f"{session_status} session: {self._ctx.session_id}")
        
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
        # Use command completer for command auto-completion
        completer = WordCompleter(list(self.COMMANDS.keys()))
        
        self.session_prompt = PromptSession(
            history=FileHistory(self.history_file),
            auto_suggest=AutoSuggestFromHistory(),
            completer=completer,
            key_bindings=kb
        )
        
        # State tracking
        self.debug_mode = False
        self.interrupt_counter = 0
        self.last_interrupt_time = 0
        
        logger.info(f"Chat initialized with workspace: {workspace}")
    
    def _get_or_create_session_id(self) -> Tuple[Optional[str], bool]:
        """
        Get the active session ID if it exists, or return None to create a new one.
        
        Returns:
            Tuple containing (session_id, is_new_session)
            - session_id will be None if no valid active session exists
            - is_new_session will be True if a new session needs to be created
        """
        try:
            # Check if there's an active session file
            if os.path.exists(self.active_session_file):
                with open(self.active_session_file, 'r') as f:
                    session_id = f.read().strip()
                
                if session_id:
                    # Check if the session directory exists
                    session_dir = os.path.expanduser(f"~/.neo/{session_id}")
                    if os.path.exists(session_dir):
                        logger.info(f"Found existing session: {session_id}")
                        return session_id, False
        
        except Exception as e:
            logger.warning(f"Error reading active session file: {e}")
        
        # If we get here, we need a new session
        return None, True
    
    def _save_active_session(self, session_id: str) -> None:
        """Save the current session ID as the active session."""
        try:
            # Ensure directory exists
            os.makedirs(os.path.dirname(self.active_session_file), exist_ok=True)
            
            # Write the session ID to the active session file
            with open(self.active_session_file, 'w') as f:
                f.write(session_id)
                
            logger.info(f"Saved {session_id} as active session")
        except Exception as e:
            logger.error(f"Error saving active session: {e}")
            
    def _create_new_session(self) -> str:
        """
        Create a new session and update the context.
        
        Returns:
            The new session ID or None if failed
        """
        try:
            # Create a new context with a new session ID
            self._ctx = Context.builder().workspace(self.workspace).initialize()
            
            # Save the new session as active
            self._save_active_session(self._ctx.session_id)
            
            logger.info(f"Created new session: {self._ctx.session_id}")
            return self._ctx.session_id
        except Exception as e:
            logger.error(f"Error creating new session: {e}")
            return None
    
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
            
            # Display welcome message
            self._print_welcome_message()
            
            # Main chat loop
            while True:
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
                    response = self._ctx.agent.process(user_input)
                    
                    # Display the response
                    self._display_response(response)
                    
                except KeyboardInterrupt:
                    # Handle Ctrl+C properly
                    current_time = time.time()
                    
                    # If user rapidly presses Ctrl+C twice within 1 second, exit
                    if current_time - self.last_interrupt_time < 1:
                        self.interrupt_counter += 1
                        if self.interrupt_counter >= 2:
                            self._console.print("\n[yellow]Double interrupt detected. Exiting...[/yellow]")
                            break
                    else:
                        self.interrupt_counter = 1
                    
                    self.last_interrupt_time = current_time
                    self._console.print("\n[yellow]Press Ctrl+C again to exit or /exit to quit.[/yellow]")
                    continue
                except EOFError:
                    # Handle Ctrl+D (EOF)
                    self._console.print("\n[yellow]EOF detected. Exiting...[/yellow]")
                    break
                except Exception as e:
                    # Handle any other exceptions within the loop
                    error_msg = f"Error processing message: {str(e)}"
                    logger.error(error_msg, exc_info=True)
                    self._console.print(f"\n[bold red]Error:[/bold red] {error_msg}")
            
            logger.info("Chat session ended")
            
        except Exception as e:
            # Handle any exceptions in the outer scope
            logger.critical(f"Critical error in chat session: {e}", exc_info=True)
            self._console.print(f"\n[bold red]Critical error:[/bold red] {str(e)}")
            
        finally:
            # Log end of session
            logger.info("Chat session ended")

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
        
        # Print exit message to console
        try:
            self._console.print(f"\n[yellow]Received {signal_name} signal. Exiting immediately...[/yellow]")
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
        try:
            welcome_text += f"Session: [magenta]{self._ctx.session_id}[/magenta]\n"
        except Exception as e:
            logger.warning(f"Could not retrieve session ID: {e}")
            
        welcome_text += "Type [blue]/help[/blue] for available commands.\n"
        welcome_text += "Press [blue]Ctrl+C[/blue] twice quickly or [blue]Ctrl+D[/blue] to exit."
        
        self._console.print(Panel.fit(welcome_text))
    
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
        
        if cmd == "/exit":
            logger.info("User requested exit")
            self._console.print("[yellow]Exiting chat session...[/yellow]")
            return False
        
        if cmd == "/help":
            self._show_help()
        elif cmd == "/debug":
            self.debug_mode = not self.debug_mode
            status = "enabled" if self.debug_mode else "disabled"
            self._console.print(f"[yellow]Debug mode {status}[/yellow]")
            logger.info(f"Debug mode {status}")
        elif cmd == "/new-session":
            old_session_id = self._ctx.session_id
            new_session_id = self._create_new_session()
            if new_session_id:
                self._console.print(f"[green]🔄 Created new session: [bold]{self._ctx.session_id}[/bold][/green]")
                self._console.print(f"[dim]Previous session was: {old_session_id}[/dim]")
            else:
                self._console.print(f"[red]Failed to create new session[/red]")
        else:
            self._console.print(f"[red]Unknown command: {cmd}[/red]")
            self._console.print("Type [blue]/help[/blue] for available commands.")
        
        return True
    
    def _show_help(self) -> None:
        """Display available commands and their descriptions."""
        self._console.print("\n[bold blue]Available Commands:[/bold blue]")
        
        for cmd, desc in self.COMMANDS.items():
            self._console.print(f"  [blue]{cmd}[/blue]: {desc}")
            
        self._console.print("\nOtherwise, just type your message to chat with the assistant.")
        self._console.print("\n[bold blue]Keyboard Shortcuts:[/bold blue]")
        self._console.print("  [blue]Ctrl+C[/blue] twice quickly: Exit the application")
        self._console.print("  [blue]Ctrl+D[/blue]: Exit the application")
    
    def _display_response(self, response: str) -> None:
        """
        Display the agent's response with rich formatting.
        
        Args:
            response: Text response from the agent
        """
        # In debug mode, show the raw response
        if self.debug_mode:
            self._console.print("[dim]--- Raw Response ---[/dim]")
            self._console.print(f"[dim]{response}[/dim]")
            self._console.print("[dim]--- End Raw Response ---[/dim]\n")
        
        # Display the response with markdown rendering
        try:
            # Parse the response as markdown for rich formatting
            formatted_response = Markdown(response)
            # Fix: Use a valid box parameter instead of None
            self._console.print(Panel(
                formatted_response,
                border_style="green",
                padding=(1, 2)
            ))
        except Exception as e:
            # Fallback to plain text if markdown parsing fails
            logger.warning(f"Failed to render markdown: {e}")
            self._console.print(Panel(
                response,
                border_style="yellow",
                padding=(1, 2)
            ))