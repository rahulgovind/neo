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
import asyncio
from typing import Optional, Any, Dict

from rich.console import Console
from rich.markdown import Markdown
from prompt_toolkit.key_binding import KeyBindings
from rich.panel import Panel
from prompt_toolkit import PromptSession
from prompt_toolkit.history import FileHistory
from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
from prompt_toolkit.completion import WordCompleter

from src.neo.service.service import Service
from src.neo.core.messages import Message

# Configure logging
logger = logging.getLogger(__name__)


class Chat:
    """Manages an interactive chat session in the terminal."""

    COMMANDS = {
        "/exit": "Exit the chat session",
        "/help": "Show this help message",
        "/debug": "Toggle debug mode",
        "/new-session": "Create a new session (requires workspace)",
        "/list-sessions": "List persistent sessions",
        "/switch-session": "Switch to a different persistent session",
        "/info": "Show current session info",
    }

    def __init__(self, workspace: str):
        """Initializes the interactive chat session (synchronous part). Takes only workspace."""
        self._console = Console()
        self._workspace: str = (
            workspace  # Workspace is now mandatory for initialization
        )
        # Session ID and name are now set during async initialization
        self._session_id: Optional[str] = None
        self._session_name: Optional[str] = None
        self._message_stream_task: Optional[asyncio.Task] = None
        self._is_exiting: bool = False
        self._running = False
        self.debug_mode = False
        self.interrupt_counter = 0
        self.last_interrupt_time = time.time()

        # Command mapping
        self._commands = {
            "/exit": "Exit the chat session",
            "/help": "Show this help message",
            "/debug": "Toggle debug mode",
            "/new-session": "Create a new session (requires workspace)",
            "/list-sessions": "List persistent sessions",
            "/switch-session": "Switch to a different persistent session",
            "/info": "Show current session info",
        }

        logger.info(
            f"Chat initialized for workspace {workspace}. Call launch() to create session and start."
        )

    def _initialize(self) -> None:
        """Initialization steps, including creating the temporary session."""
        logger.info(
            f"Starting initialization for chat in workspace {self._workspace}..."
        )

        # 1. Get the last active session or create a new default one
        try:
            logger.info("Looking for last active session...")
            session_obj = Service.get_last_active_session()
            
            if session_obj:
                # Use the last active session
                self._session_id = session_obj.session_id
                self._session_name = session_obj.session_name
                logger.info(f"Using last active session: {self._session_name} (ID: {self._session_id})")
            else:
                # Create a new default session named 'session-1'
                logger.info(f"No active session found. Creating default session for workspace: {self._workspace}")
                session_obj = Service.create_session(
                    session_name="session-1",
                    workspace=self._workspace
                )
                self._session_id = session_obj.session_id
                self._session_name = session_obj.session_name
                logger.info(f"Created default session: {self._session_name} (ID: {self._session_id})")
        except Exception as e:
            logger.error(
                f"Fatal: Failed to create temporary session: {e}", exc_info=True
            )
            print(f"\nError: Could not create a chat session. Aborting.")
            # Set exiting flag or raise to prevent launch from continuing?
            self._is_exiting = True  # Prevent launch loop
            return  # Stop initialization

        # 2. Get session state (might be minimal for temporary, but good practice)
        try:
            session_info = Service.get_session(self._session_id)
            if session_info and session_info.session_name:
                # If info exists and has a name (e.g., if temporary becomes persistent later?)
                self._session_name = session_info.session_name
                # Ensure workspace consistency
                if self._workspace != session_info.workspace:
                    logger.warning(
                        f"Session workspace '{session_info.workspace}' differs from initial '{self._workspace}'. Using initial."
                    )
                    # Stick with the workspace the Chat was initialized with
            else:
                logger.info(
                    f"Using default name '{self._session_name}' for session {self._session_id}."
                )
        except Exception as e:
            logger.error(
                f"Error getting session info for {self._session_id}: {e}",
                exc_info=True,
            )
            # Keep the placeholder name

        # 3. Setup history file
        history_dir = os.path.join(os.path.expanduser("~"), ".neo")
        os.makedirs(history_dir, exist_ok=True)
        history_file = os.path.join(history_dir, "neo_chat_history.txt")
        try:
            if not os.path.exists(history_file):
                with open(history_file, "w") as f:
                    f.write("")
        except Exception as e:
            logger.error(f"Error ensuring history file exists {history_file}: {e}")

        # 4. Initialize prompt_toolkit session
        try:
            self._history = FileHistory(history_file)
            # Setup key bindings
            kb = KeyBindings()

            @kb.add("c-d")
            def _(event):
                """Handle Ctrl+D for exit."""
                if not event.cli.current_buffer.text:  # Only exit if buffer is empty
                    logger.info("Ctrl+D detected on empty line. Exiting.")
                    # Find the running Chat instance and signal exit?
                    # This is tricky. Better to rely on EOFError from prompt.
                    event.app.exit(result=EOFError)
                else:
                    # If buffer is not empty, just delete char under cursor or do nothing
                    pass

            self._prompt_session = PromptSession(
                history=self._history,
                auto_suggest=AutoSuggestFromHistory(),
                completer=WordCompleter(list(self._commands.keys()), ignore_case=True),
                complete_while_typing=True,
                key_bindings=kb,  # Add key bindings
            )
        except Exception as e:
            logger.error(
                f"Failed to initialize prompt session with history {history_file}: {e}",
                exc_info=True,
            )
            # Fallback without history or keybindings?
            self._prompt_session = PromptSession(
                completer=WordCompleter(list(self._commands.keys()), ignore_case=True),
                complete_while_typing=True,
            )
            print("Warning: Failed to load command history.")

        self._update_prompt()
        logger.info(
            f"Chat asynchronous initialization complete for session {self._session_id}."
        )

    def _update_prompt(self) -> None:
        """Updates the prompt text to reflect the current session name."""
        if not self._prompt_session:
            logger.warning(
                "Attempted to update prompt before prompt_session was initialized."
            )
            return

        # Use the session name if available, otherwise use the session ID
        session_identifier = (
            self._session_name if self._session_name else self._session_id[:8] + "..."
        )
        self._prompt_session.message = f"[{session_identifier}] 🤔 > "

    def launch(self) -> None:
        """Creates the session and starts the interactive chat loop."""
        # Perform initialization (which now includes session creation)
        self._initialize()

        # Check if initialization failed (e.g., session creation)
        if self._is_exiting or not self._session_id or not self._prompt_session:
            logger.error("Initialization failed or aborted. Cannot launch chat.")
            return

        # Register signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._handle_interrupt)
        signal.signal(signal.SIGTERM, self._handle_interrupt)

        # Display welcome message
        self._print_welcome_message()
        
        # Set running flag
        self._running = True

        # Main chat loop
        while self._running:
            user_input = None
            try:
                # Get user input directly
                user_input = self._get_user_input()

                # Reset interrupt counter on successful input
                self.interrupt_counter = 0

                if (
                    user_input is None
                ):  # Can happen if prompt is cancelled (e.g., Ctrl+D)
                    if not self._running:  # Check if exit was signalled
                        break
                    else:
                        continue  # Prompt cancelled, but not exiting, try again

                # Check if this is a special command
                if user_input.startswith("/"):
                    # Handle commands and check if we should continue
                    should_continue = self._handle_command(user_input)
                    if not should_continue:
                        self._running = False  # Signal loop to stop
                        break
                    continue

                # Skip empty inputs
                if not user_input.strip():
                    continue

                # Send message to the service
                logger.info(f"Sending user input to session {self._session_id}")
                for message in Service.message(msg=user_input, session_id=self._session_id):
                    # Print each message from the service
                    self._console.print(message)

            except KeyboardInterrupt:
                # Handle Ctrl+C during input
                current_time = time.time()
                if current_time - self.last_interrupt_time < 1:
                    self.interrupt_counter += 1
                else:
                    self.interrupt_counter = 1
                self.last_interrupt_time = current_time

                if self.interrupt_counter >= 2:
                    self._console.print(
                        "[bold red]Exiting due to repeated Ctrl+C[/bold red]"
                    )
                    self._running = False
                    break
                else:
                    self._console.print(
                        "[yellow]Press Ctrl+C again quickly or Ctrl+D to exit.[/yellow]"
                    )

            except EOFError:  # Ctrl+D during input
                self._console.print("[yellow]Exiting due to Ctrl+D.[/yellow]")
                self._running = False
                break

            except Exception as e:
                logger.error(f"Error in chat loop: {e}", exc_info=True)
                self._console.print(f"[red]An unexpected error occurred: {e}[/red]")
                # Decide if the error is fatal
                # self._running = False
                # break

        # Cleanup: Stop the message stream task
        self._stop_message_stream()
        logger.info("Interactive chat session ended.")

    def _setup_signal_handlers(self) -> None:
        """
        Set up handlers for system signals to ensure graceful termination.
        """
        loop = asyncio.get_event_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(
                sig, lambda s=sig: asyncio.create_task(self._signal_handler(s))
            )

    def _handle_interrupt(self, sig, frame) -> None:
        """
        Handle system signals for immediate termination.
        """
        self._running = False
        # Attempt to cancel the background task gracefully
        self._stop_message_stream()
        # Exit the program
        sys.exit(0)

    def _print_welcome_message(self) -> None:
        """Display welcome message with optional workspace information."""
        self._console.print("[bold green]Welcome to Neo Interactive Chat![/bold green]")
        self._console.print(
            f"Session: [cyan]{self._session_name}[/cyan] (ID: {self._session_id[:8]}...)"
        )
        if self._workspace:
            self._console.print(f"Workspace: [blue]{self._workspace}[/blue]")
        else:
            self._console.print(f"Workspace: [yellow]Not set[/yellow]")
        self._console.print(
            "Type [blue]/help[/blue] for commands, [blue]/exit[/blue] or [blue]Ctrl+D[/blue] to quit."
        )
        self._console.print("---")

    def _get_user_input(self) -> Optional[str]:  # Made sync again, will run in thread
        """
        Get input from the user with prompt toolkit.
        """
        try:
            # Use a simple leading indicator for the prompt
            prompt_text = f"[{self._session_name[:10]}] 🤔 > "
            return self._prompt_session.prompt(prompt_text)
        except EOFError:
            # Raised on Ctrl+D, signal exit intent
            self._running = False
            return None  # Signal cancellation
        except KeyboardInterrupt:
            # Raised on Ctrl+C, signal interrupt
            raise  # Let the main loop handle KeyboardInterrupt

    def _handle_command(self, command: str) -> bool:
        """
        Process special commands entered by the user.
        """
        # Extract command and args
        parts = command.strip().split()
        cmd = parts[0].lower()
        args = parts[1:]

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
            if not self._workspace:
                self._console.print(
                    "[red]Cannot create new session: Workspace not set.[/red]"
                )
                return True
            session_name = args[0] if args else None
            try:
                new_session = Service.create_session(
                    session_name=session_name, workspace=self._workspace
                )
                self._console.print(
                    f"[green]Created and switched to new session: [bold]{new_session.session_name}[/bold] (ID: {new_session.session_id[:8]}...)[/green]"
                )
                self.switch_session(
                    new_session.session_id
                )  # Switch internal state
            except Exception as e:
                self._console.print(f"[red]Error creating session: {e}[/red]")
        elif cmd == "/list-sessions":
            sessions = Service.list_sessions()
            if sessions:
                self._console.print(
                    "[bold green]Available Sessions (ID: Name):[/bold green]"
                )
                for session_id, name in sessions.items():
                    self._console.print(f"  [cyan]{session_id[:8]}...[/cyan]: {name}")
            else:
                self._console.print("[yellow]No persistent sessions found.[/yellow]")
        elif cmd == "/switch-session":
            if not args:
                self._console.print("[red]Missing session ID or name[/red]")
                return True
            target = args[0]
            # Try finding by ID first, then by name
            session_id_to_switch = None
            all_sessions = Service.list_sessions()
            if target in all_sessions:
                session_id_to_switch = target
            else:
                # Try finding by name (case-sensitive for now)
                found = False
                for sid, sname in all_sessions.items():
                    if sname == target:
                        session_id_to_switch = sid
                        found = True
                        break
                if not found:
                    # Last resort: maybe it's a partial ID?
                    for sid in all_sessions.keys():
                        if sid.startswith(target):
                            session_id_to_switch = sid
                            break  # Take the first partial match

            if session_id_to_switch:
                if session_id_to_switch == self._session_id:
                    self._console.print("[yellow]Already in this session.[/yellow]")
                else:
                    self.switch_session(session_id_to_switch)
            else:
                self._console.print(f"[red]Session '{target}' not found.[/red]")
        elif cmd == "/info":
            self._console.print(f"Current Session: [cyan]{self._session_name}[/cyan]")
            self._console.print(f"Session ID: [cyan]{self._session_id}[/cyan]")
            self._console.print(
                f"Workspace: [blue]{self._workspace or '[Not Set]'}[/blue]"
            )
        else:
            self._console.print(f"[red]Unknown command: {cmd}[/red]")
            self._console.print("Type [blue]/help[/blue] for available commands.")

        return True

    def _show_help(self) -> None:
        """Display available commands and their descriptions."""
        self._console.print("\n[bold blue]Available Commands:[/bold blue]")

        for cmd, desc in self._commands.items():
            self._console.print(f"  [blue]{cmd}[/blue]: {desc}")

        self._console.print(
            "\nOtherwise, just type your message to chat with the assistant."
        )
        self._console.print("\n[bold blue]Keyboard Shortcuts:[/bold blue]")
        self._console.print("  [blue]Ctrl+C[/blue] twice quickly: Exit the application")
        self._console.print("  [blue]Ctrl+D[/blue]: Exit the application")

    def switch_session(self, new_session_id: str) -> None:
        """
        Switch to an existing session.

        Args:
            new_session_id: ID of the session to switch to
        """
        # Basic check if ID is the same
        if new_session_id == self._session_id:
            self._console.print("[yellow]Already in this session.[/yellow]")
            return

        # Attempt to load the new session info to confirm it exists and get its details
        try:
            new_session_info = Service.get_session(new_session_id)
            if not new_session_info:
                raise FileNotFoundError("Session not found")
            new_session_name = new_session_info.session_name
            new_workspace = new_session_info.workspace
        except Exception as e:
            self._console.print(
                f"[red]Failed to load session '{new_session_id[:8]}...': {e}[/red]"
            )
            return

        logger.info(f"Switching from session {self._session_id} to {new_session_id}")

        # Stop the current message stream
        self._stop_message_stream()

        # Update internal state
        self._session_id = new_session_id
        self._session_name = new_session_name
        self._workspace = new_workspace  # Update workspace too

        # Start the message stream for the new session
        self._start_message_stream()

        self._console.print(
            f"[green]Switched to session: [bold]{self._session_name}[/bold] (ID: {self._session_id[:8]}...)[/green]"
        )
        # Optionally clear the screen or add a separator
        self._console.print("---")

    # --- Async Task Management for Streaming ---

    def _start_message_stream(self) -> None:
        """Placeholder for starting message stream - not needed in synchronous implementation."""
        logger.info(f"Message streaming is handled synchronously for session {self._session_id}")

    def _stop_message_stream(self) -> None:
        """Placeholder for stopping message stream - not needed in synchronous implementation."""
        logger.info(f"No background message stream to stop for session {self._session_id}")

    async def _stream_and_display_messages(self):
        """The core task that streams messages and displays them."""
        try:
            logger.debug(f"Message stream loop started for {self._session_id}.")
            async for message in Service.stream_messages(self._session_id):
                self._display_response(message)
        except asyncio.CancelledError:
            # Expected on shutdown or session switch
            logger.info(f"Message stream for {self._session_id} cancelled.")
            raise  # Re-raise to allow _stop_message_stream to catch it
        except ValueError as ve:
            logger.error(f"Value error in stream (e.g., session not found?): {ve}")
            self._console.print(
                f"[bold red]Error streaming messages: {ve}. Session might be invalid.[/bold red]"
            )
            self._running = False  # Stop the main loop if session is bad
        except Exception as e:
            logger.error(
                f"Unexpected error in message stream for {self._session_id}: {e}",
                exc_info=True,
            )
            self._console.print(
                f"[bold red]An error occurred while streaming messages: {e}[/bold red]"
            )
            # Depending on the error, you might want to stop the main loop
            # self._running = False
        finally:
            logger.debug(f"Message stream loop finished for {self._session_id}.")
