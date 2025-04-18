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
import threading
import queue
from typing import Optional, Any, Dict, List, Iterator, Union
from datetime import datetime

from attr import dataclass
from rich import align
from rich.align import Align
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.markdown import Markdown
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit import PromptSession
from prompt_toolkit.history import FileHistory
from prompt_toolkit.patch_stdout import patch_stdout
from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
from prompt_toolkit.completion import WordCompleter
from prompt_toolkit.formatted_text import HTML
from rich.control import Control
from src import NEO_HOME
from src.neo.service.service import Service
from src.neo.core.messages import Message, TextBlock
from src.neo.service.session_manager import SessionInfo
from rich.table import Table

# Configure logging
logger = logging.getLogger(__name__)


COMMANDS = {
    "/exit": "Exit the chat session",
    "/help": "Show this help message",
    "/new-session": "Create a new session (requires workspace)",
    "/list": "List persistent sessions",
    "/switch": "Switch to a different persistent session",
    "/info": "Show current session info",
}

# Initialize console with soft-wrapping and highlighting
console = Console(soft_wrap=True, highlight=True)

# History is stored in NEO_HOME/cli_chat_history
history_file = os.path.join(NEO_HOME, "cli_chat_history")

prompt_session = PromptSession(
    message=HTML("\n<ansigreen>></ansigreen> "),
    history=FileHistory(history_file),
    auto_suggest=AutoSuggestFromHistory(),
)

session_id = None
session_name = None
workspace = None

# Track interrupt state
interrupt_counter = 0
last_interrupt_time = 0

message_layout = None

def _update_session(session_info: SessionInfo) -> None:
    global session_name, session_id, workspace
    session_name = session_info.session_name
    session_id = session_info.session_id
    workspace = session_info.workspace

def print_message(message: Message) -> None:
    """Display a message with appropriate formatting based on its role and content."""
    timestamp = datetime.now().strftime("%H:%M:%S")
    
    # Determine style based on message role
    if message.role is None:  # User message
        border_style = "blue"
        # For user messages, use simpler formatting
        content = message.display_text()
        console.print(Panel(
            renderable=content,
            title=f"[dim]({timestamp})[/dim]",
            border_style=border_style,
            padding=(0, 1),
        ))
        console.print("")
    else:  # Agent message
        # For agent messages (Neo), display without a panel border
        # For agent messages, use Markdown for rich formatting
        # Print Neo's messages without a panel
        console.print(Markdown(message.display_text()))

class MessageQueue:

    @dataclass
    class Item:
        session_id: str
        message: str

    def __init__(self) -> None:
        self._stop_worker = threading.Event()
        self._message_queue: queue.Queue[Item] = queue.Queue()
        self._thread = threading.Thread(
            target=self._process, daemon=True, name="MessageWorker"
        )

    def start(self) -> None:
        self._thread.start()
        logger.info(f"Started message worker thread")

    def _process(self) -> None:
        """Worker thread to process and display messages from the queue."""
        logger.info("Message worker thread started")

        while not self._stop_worker.is_set():
            # Get a message from the queue with a timeout
            # This allows the thread to check the stop flag periodically
            try:
                message = self._message_queue.get(timeout=0.1)
            except queue.Empty:
                continue

            self._message_queue.task_done()
            # Process the message and display results
            logger.info(
                f"Worker processing message: {message.message[:30]}..."
                if len(message.message) > 30
                else message.message
            )

            with console.status("[bold green]Processing..."):
                # Process through the service
                for message in Service.message(
                    msg=message.message, session_id=message.session_id
                ):
                    print_message(message)
                    if self._stop_worker.is_set():
                        break

        logger.info("Message worker thread stopped")

    def add_message(self, message: str) -> None:
        # Add to processing queue
        print_message(Message(role=None, content=[TextBlock(text=message)]))
        msg = self.Item(session_id=session_id, message=message)
        self._message_queue.put(msg)

    def stop(self) -> None:
        """Stop the message worker thread if running."""
        if self._thread and self._thread.is_alive():
            logger.info("Stopping message worker thread...")
            self._stop_worker.set()
            self._thread.join(timeout=2.0)
            if self._thread.is_alive():
                logger.warning("Message worker thread did not stop gracefully")
            else:
                logger.info("Message worker thread stopped successfully")

message_queue = MessageQueue()

def run_processing_loop() -> None:
    message_queue.start()
    while True:
        try:
            # Use patch_stdout to ensure proper prompt handling (only in the UI thread)
            with patch_stdout(raw=True):
                user_input = prompt_session.prompt()
            print("\033[A                             \033[A")

            # Reset interrupt counter on successful input
            global interrupt_counter
            interrupt_counter = 0

            # Check if this is a special command
            if user_input.startswith("/"):
                handle_command(user_input)
                continue

            # Skip empty inputs
            if not user_input.strip():
                continue

            # Add message to queue for processing by worker thread
            message_queue.add_message(user_input)
            logger.info(
                f"Added message to queue: {user_input[:30]}..."
                if len(user_input) > 30
                else user_input
            )

        except KeyboardInterrupt:
            handle_keyboard_interrupt()
        except EOFError:  # Ctrl+D during input
            raise TerminateChat("[bold red]Exiting due to Ctrl+D[/bold red]")


def handle_keyboard_interrupt() -> None:
    """
    Handle system signals for immediate termination.
    """
    global interrupt_counter, last_interrupt_time
    current_time = time.time()
    if current_time - last_interrupt_time < 1:
        interrupt_counter += 1
    else:
        interrupt_counter = 1
    last_interrupt_time = current_time

    if interrupt_counter >= 2:
        raise TerminateChat("[bold red]Exiting due to repeated Ctrl+C[/bold red]")
    else:
        console.print("[yellow]Press Ctrl+C again quickly or Ctrl+D to exit.[/yellow]")



def handle_command(command: str) -> None:
    # Strip the leading slash and split into command and args
    parts = command[1:].split(maxsplit=1)
    cmd = parts[0].lower() if parts else ""
    args = parts[1] if len(parts) > 1 else ""

    if cmd == "exit":
        raise TerminateChat("[bold red]Exiting chat...[/bold red]")
    elif cmd == "help":
        console.print("[bold]Available Commands:[/bold]")
        for cmd, desc in COMMANDS.items():
            console.print(f"  [blue]{cmd}[/blue] - {desc}")
    elif cmd == "info":
        console.print(
            f"[bold]Session:[/bold] {session_name} ([italic]{session_id}[/italic])"
        )
        console.print(f"[bold]Workspace:[/bold] {workspace}")

    elif cmd == "list":
        # List all persistent sessions
        try:
            sessions = Service.list_sessions()
            if not sessions:
                console.print("[yellow]No persistent sessions found.[/yellow]")
            else:
                console.print("[bold]Available Sessions:[/bold]")
                for idx, session in enumerate(sessions, 1):
                    is_current = session.session_id == session_id
                    current_marker = "[green]*[/green] " if is_current else "  "
                    console.print(
                        f"{current_marker}{idx}. [cyan]{session.session_name}[/cyan] "
                        f"([italic]{session.session_id[:8]}...[/italic]) "
                        f"- Workspace: {session.workspace or 'None'}"
                    )
        except Exception as e:
            console.print(f"[red]Error listing sessions: {e}[/red]")

    elif cmd == "switch":
        if not args:
            console.print("[yellow]Usage: /switch <session_id>[/yellow]")
            console.print("Use [blue]/list[/blue] to see available sessions.")
        else:
            logger.info(f"Attempting to switch to session {new_session_name}")
            if new_session_name == session_name:
                console.print("[yellow]Already in this session.[/yellow]")
                return

            try:
                new_session_info = Service.get_session(new_session_name)
                if not new_session_info:
                    console.print(f"[red]Session '{new_session_name}' not found[/red]")
                    return
            except Exception as e:
                console.print(
                    f"[red]Failed to load session '{new_session_name[:8]}...': {e}[/red]"
                )
                return

            _update_session(new_session_info)

            console.print(
                f"[green]Switched to session: [bold]{session_name}[/bold] (ID: {session_id[:8]}...)[/green]"
            )
            console.print("---")
    elif cmd == "new-session":
        if not args:
            console.print("[yellow]Usage: /new-session <session_name>[/yellow]")
        else:
            try:
                new_session_name = args.strip() if args.strip() else None
                new_session = Service.create_session(new_session_name, workspace)
                console.print(
                    f"[green]Created new session: [bold]{new_session.session_name}[/bold] (ID: {new_session.session_id})[/green]"
                )
                _update_session(new_session)
            except Exception as e:
                console.print(f"[red]Failed to create session: {e}[/red]")
    else:
        console.print(f"[red]Unknown command: {cmd}[/red]")
        console.print("Use [blue]/help[/blue] to see available commands.")


class TerminateChat(Exception):
    """Exception to signal the chat loop should terminate."""

    def __init__(self, message: str) -> None:
        self.message = message


def launch() -> None:
    """Creates the session and starts the interactive chat loop."""

    is_new_session = False
    session_info = Service.get_last_active_session()
    workspace = os.getcwd()

    if not session_info:
        session_info = Service.create_session(workspace=workspace)
        is_new_session = True

    _update_session(session_info)
    
    # Display welcome message with optional workspace information
    console.print(f"Session: [cyan]{session_name}[/cyan] (ID: {session_id})")
    
    if workspace:
        console.print(f"Workspace: [blue]{workspace}[/blue]")
    else:
        console.print(f"Workspace: [yellow]Not set[/yellow]")
        
    console.print(
        "Type [blue]/help[/blue] for commands, [blue]/exit[/blue] or [blue]Ctrl+D[/blue] to quit."
    )

    # Main chat loop (UI thread)
    try:
        run_processing_loop()
    except TerminateChat as e:
        console.print(e.message)
    except Exception as e:
        logger.exception("Unexpected error in chat loop")
        console.print(f"[red]An unexpected error occurred: {e}[/red]")

    logger.info("Interactive chat session ended.")
