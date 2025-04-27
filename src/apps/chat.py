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
from src.neo.core.messages import Message, TextBlock, CommandCall
from src.neo.service.session_manager import SessionInfo

# Configure logging
logger = logging.getLogger(__name__)


COMMANDS = {
    "/exit": "Exit the chat session",
    "/help": "Show this help message",
    "/new-session": "Create a new session (requires workspace)",
    "/list": "List persistent sessions",
    "/switch": "Switch to a different persistent session",
    "/info": "Show current session info",
    "/set": "Update session settings (e.g., /set workspace <path>)",
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
        # For user messages, use simpler formatting with proper text wrapping
        content = message.display_text()
        # Get console width and calculate appropriate panel width to ensure text wrapping
        console_width = console.width if console.width else 80
        max_width = console_width - 4  # Account for panel borders and padding
        console.print(Panel(
            renderable=content,
            title=f"[dim]({timestamp})[/dim]",
            border_style=border_style,
            padding=(0, 1),
            width=max_width,
        ))

        console.print("")
    else:  # Agent message
        # Get all command results to display
        command_results = message.command_results()
        
        # Check for structured output first
        structured_output = message.structured_output()

        # print(f"{command_results=} {structured_output=} {command_calls=}")
        if structured_output:
            # Calculate appropriate panel width for text wrapping
            console_width = console.width if console.width else 80
            max_width = console_width - 4  # Account for panel borders and padding
            console.print(Panel(
                renderable=Markdown(structured_output.display_text()),
                border_style="green",
                padding=(0, 1),
                width=max_width,
            ))
        # Process command results with command outputs
        elif command_results:
            for result in command_results:
                if hasattr(result, 'command_output') and result.command_output is not None:
                    cmd_output = result.command_output
                    
                    # Check the type of command output
                    if hasattr(cmd_output, 'diff'):  # FileUpdate output
                        # Display file updates in a panel
                        file_name = cmd_output.message.split()[-1] if ' ' in cmd_output.message else ''
                        action = "Created" if "Created" in cmd_output.message else "Updated"
                        console.print(f"📄 [bold green]{action}[/bold green] {file_name}")
                        
                        # Only show diff if it's not empty
                        if cmd_output.diff.strip():
                            console_width = console.width if console.width else 80
                            max_width = console_width - 4
                            
                            # Colorize the diff output
                            colorized_lines = []
                            for line in cmd_output.diff.splitlines():
                                if line.startswith("+") and not line.startswith("++"):
                                    # Green for added lines (but not the +++ header)
                                    colorized_lines.append(f"[green]{line}[/green]")
                                elif line.startswith("-") and not line.startswith("---"):
                                    # Red for removed lines (but not the --- header)
                                    colorized_lines.append(f"[red]{line}[/red]")
                                else:
                                    # No color for context lines and headers
                                    colorized_lines.append(line)
                            
                            # Join the colorized lines back together
                            colorized_diff = "\n".join(colorized_lines)
                            
                            console.print(Panel(
                                colorized_diff,
                                title="[bold]Diff[/bold]",
                                border_style="green",
                                padding=(0, 1),
                                width=max_width,
                            ))
                    
                    elif hasattr(cmd_output, 'console'):  # ShellOutput output
                        # Display shell outputs in a panel
                        console.print(f"🖥️ [bold cyan]{cmd_output.message}[/bold cyan]")
                        
                        # Only show console output if it's not empty
                        if cmd_output.console.strip():
                            console_width = console.width if console.width else 80
                            max_width = console_width - 4
                            console.print(Panel(
                                cmd_output.console,
                                title="[bold]Console Output[/bold]",
                                border_style="blue",
                                padding=(0, 1),
                                width=max_width,
                            ))
                    
                    else:  # Generic CommandOutput
                        # Use appropriate icons based on command name
                        icon = "✅"
                        if cmd_output.name == "file_path_search" or cmd_output.name == "file_text_search":
                            icon = "🔍"
                        elif cmd_output.name == "read_file":
                            icon = "📖"
                        elif cmd_output.name == "wait":
                            icon = "⏱️"
                        
                        console.print(f"{icon} [bold]{cmd_output.message}[/bold]")
                
                # If no command output is available, check if there's a command_call to display
                elif hasattr(result, 'command_call') and result.command_call is not None:
                    # Only display the command call if command_output is not set
                    console.print(result.display_text())
                # Otherwise, fall back to displaying raw result content
                elif result.content:
                    console.print(result.display_text())
        
        # If no command results or structured output, display the message text
        # but filter out any CommandCall blocks
        else:
            # Create a filtered version of the message without CommandCall blocks
            filtered_content = [block for block in message.content if not isinstance(block, CommandCall)]
            if filtered_content:
                filtered_text = "\n".join(block.display_text() for block in filtered_content)
                console.print(Markdown(filtered_text))
            # If there's no content after filtering, don't display anything

class MessageQueue:

    @dataclass
    class Item:
        session_id: str
        message: str

    def __init__(self) -> None:
        self._stop_worker = threading.Event()
        self._stopping_status = threading.Event()  # Flag to indicate stopping status
        self._message_queue: queue.Queue[MessageQueue.Item] = queue.Queue()
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

            status = "[bold green]Processing..."
            with console.status(status) as status_display:
                # Process through the service
                for message in Service.message(
                    msg=message.message, session_id=message.session_id
                ):
                    # Check if we need to update status to show stopping
                    if self._stopping_status.is_set():
                        status_display.update("[bold yellow]Stopping...")
                        self._stopping_status.clear()  # Reset after updating display
                        
                    print_message(message)
                    if self._stop_worker.is_set():
                        break

            # Reset flags after interruption if needed
            if self._stop_worker.is_set():
                logger.info("Resetting worker stop flag after interruption")
                self._stop_worker.clear()
                self._stopping_status.clear()  # Also reset stopping status

        logger.info("Message worker thread stopped")

    def add_message(self, message: str) -> None:
        # Add to processing queue
        print_message(Message(role=None, content=[TextBlock(text=message)]))
        msg = self.Item(session_id=session_id, message=message)
        self._message_queue.put(msg)

        
    def stop(self, block: bool = True) -> None:
        """
        Stop message processing and optionally block until completion.
        
        Args:
            block: If True, wait for current processing to complete.
                   If False, just set the flag and return immediately.
        """
        # Clear all messages currently in the queue
        while not self._message_queue.empty():
            try:
                self._message_queue.get_nowait()
                self._message_queue.task_done()
            except queue.Empty:
                break
                
        # Set the stop flag to interrupt current message processing
        self._stop_worker.set()
        # Set stopping status flag to update display
        self._stopping_status.set()
        
        # If we're shutting down completely (not just interrupting)
        if not block or not self._thread or not self._thread.is_alive():
            return
            
        # Block until processing stops or timeout occurs
        logger.info("Waiting for current processing to complete...")
        timeout_seconds = 2.0
        wait_start = time.time()
        
        # Wait until the flag is cleared (indicating processing is done) or timeout
        while self._stop_worker.is_set() and time.time() - wait_start < timeout_seconds:
            time.sleep(0.1)
            
        if self._stop_worker.is_set():
            logger.warning("Processing did not complete within %.1f seconds", timeout_seconds)
        else:
            logger.info("Processing interrupted successfully")
    def join(self) -> None:
        """
        Block until all items in the message queue have been processed.
        This method waits until the message queue is empty and all tasks are done.
        """
        logger.info("Waiting for message queue to be processed...")
        try:
            if self._thread and self._thread.is_alive():
                self._message_queue.join()
            logger.info("Message queue processing completed.")
        except Exception:
            logger.exception("Error while waiting for message queue to complete")

message_queue = MessageQueue()

def run_processing_loop() -> None:
    message_queue.start()
    while True:
        try:
            # Create a custom prompt application that will clean up after itself
            user_input = ""  # Initialize with empty string instead of None to handle slicing operations
            
            with patch_stdout(raw=True):
                # Create a prompt application that will erase prompt when done
                def accept_input(buff):
                    nonlocal user_input
                    user_input = buff.text
                    app.exit()
                
                # Configure session to use our custom accept handler
                session = PromptSession(
                    message=HTML("\n<ansigreen>></ansigreen> "),
                    history=prompt_session.history,
                    auto_suggest=AutoSuggestFromHistory(),
                )
                
                # Create application with erase_when_done=True
                app = session.app
                app.erase_when_done = True
                
                # Set accept handler
                session.default_buffer.accept_handler = accept_input
                
                # Run the application
                app.run()
                
                # Now we have the user input and the prompt has been erased

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
            
            # Block until the message is processed
            message_queue.join()

        except KeyboardInterrupt:
            handle_keyboard_interrupt()
        except EOFError:  # Ctrl+D during input
            raise TerminateChat("[bold red]Exiting due to Ctrl+D[/bold red]")


def handle_keyboard_interrupt() -> None:
    """
    Handle system signals for immediate termination.
    On first Ctrl+C: Clear message queue and stop current processing
    On second Ctrl+C (within 1 second): Exit the application
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
        # Stop processing on first Ctrl+C but don't block
        message_queue.stop(block=False)
        console.print("[bold yellow]Message processing interrupted.[/bold yellow]")
        console.print("[yellow]You can send a new message or press Ctrl+C again quickly to exit.[/yellow]")



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
            new_session_name = args.strip()
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
    elif cmd == "set":
        if not args or " " not in args:
            console.print("[yellow]Usage: /set <setting> <value>[/yellow]")
            console.print("[yellow]Available settings: workspace[/yellow]")
        else:
            # Split into setting name and value
            parts = args.split(" ", 1)
            setting = parts[0].lower()
            value = parts[1].strip()
            
            try:
                if setting == "workspace":
                    # Verify the workspace path exists
                    if not os.path.isdir(value):
                        console.print(f"[red]Invalid workspace path: '{value}' is not a directory[/red]")
                        return
                        
                    # Get absolute path
                    abs_path = os.path.abspath(value)
                    
                    # Update session workspace
                    updated_session = Service.update_session(session_id, workspace=abs_path)
                    
                    if not updated_session:
                        console.print(f"[red]Failed to update workspace: Session '{session_id}' not found[/red]")
                        return
                    
                    # Update session info in the application
                    _update_session(updated_session)
                    
                    console.print(f"[green]Workspace updated to: [bold]{abs_path}[/bold][/green]")
                else:
                    console.print(f"[red]Unknown setting: {setting}[/red]")
                    console.print("[yellow]Available settings: workspace[/yellow]")
            except Exception as e:
                console.print(f"[red]Error updating setting: {e}[/red]")
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
