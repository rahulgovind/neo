"""
Display module for formatting and displaying messages in the terminal.

This module provides functions to display formatted messages, command results,
and other UI elements in a consistent way across the application.
"""

import logging
from datetime import datetime
from typing import List, Any

from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown


from src.neo.core.messages import Message, CommandCall

# Configure logging
logger = logging.getLogger(__name__)

# Initialize console with soft-wrapping and highlighting
console = Console(soft_wrap=True, highlight=True)


def print_message(message: Message) -> None:
    """Display a message with appropriate formatting based on its role and content."""
    timestamp = datetime.now().strftime("%H:%M:%S")
    
    if message.role == "user":  # User message
        _print_user_message(message, timestamp)
    else:  # Agent message
        _print_agent_message(message)


def _print_user_message(message: Message, timestamp: str) -> None:
    """Display a user message with appropriate formatting."""
    content = message.display_text()
    # Use expand=True instead of fixed width to handle terminal width automatically
    
    console.print(
        Panel(
            renderable=content,
            title=f"[dim]({timestamp})[/dim]",
            border_style="blue",
            padding=(0, 1),
            expand=True,
        ),
        soft_wrap=False,
    )


def _print_agent_message(message: Message) -> None:
    """Display an agent message with appropriate formatting based on its content."""
    # Get all command results to display
    command_results = message.command_results()
    
    # Check for structured output first
    structured_output = message.structured_output()
    
    if structured_output:
        _print_structured_output(structured_output)
    # Process command results with command outputs
    elif command_results:
        _print_command_results(command_results)
    # If no command results or structured output, display the message text
    else:
        _print_regular_message_content(message)
    
    console.print("")


def _print_structured_output(structured_output: Any) -> None:
    """Display structured output in a panel."""
    console_width = console.width if console.width else 80
    max_width = console_width - 4  # Account for panel borders and padding
    
    console.print(
        Panel(
            renderable=Markdown(structured_output.value),
            border_style="green",
            padding=(0, 1),
            width=max_width,
        ),
        soft_wrap=False,
    )


def _print_command_results(command_results: List[Any]) -> None:
    """Display command results with appropriate formatting."""
    for result in command_results:
        if hasattr(result, "command_output") and result.command_output is not None:
            cmd_output = result.command_output
            
            # Check the type of command output
            if hasattr(cmd_output, "diff"):  # FileUpdate output
                _print_file_update(cmd_output)
            elif hasattr(cmd_output, "console"):  # ShellOutput output
                _print_shell_output(cmd_output)
            else:  # Generic CommandOutput
                _print_generic_command_output(cmd_output)
                
        # If no command output is available, check if there's a command_call to display
        elif hasattr(result, "command_call") and result.command_call is not None:
            # Only display the command call if command_output is not set
            console.print(result.display_text())
        # Otherwise, fall back to displaying raw result content
        elif result.content:
            console.print(result.display_text())


def _print_file_update(cmd_output: Any) -> None:
    """Display file update output with diff."""
    file_name = cmd_output.message.split()[-1] if " " in cmd_output.message else ""
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
        
        console.print(
            Panel(
                colorized_diff,
                title="[bold]Diff[/bold]",
                border_style="green",
                padding=(0, 1),
                width=max_width,
            )
        )


def _print_shell_output(cmd_output: Any) -> None:
    """Display shell command output."""
    console.print(f"🖥️ [bold cyan]{cmd_output.message}[/bold cyan]")
    
    # Only show console output if it's not empty
    if cmd_output.console.strip():
        console_width = console.width if console.width else 80
        max_width = console_width - 4
        console.print(
            Panel(
                cmd_output.console,
                title="[bold]Console Output[/bold]",
                border_style="blue",
                padding=(0, 1),
                width=max_width,
            )
        )


def _get_command_icon(cmd_name: str) -> str:
    """Get an appropriate icon based on command name."""
    icons = {
        "file_path_search": "🔍",
        "file_text_search": "🔍",
        "read_file": "📖",
        "wait": "⏱️",
        "web_search": "🌐",
        "web_markdown": "🌐",
    }
    return icons.get(cmd_name, "\u2705")


def _print_generic_command_output(cmd_output: Any) -> None:
    """Display generic command output with appropriate icon."""
    icon = _get_command_icon(cmd_output.name)
    console.print(f"{icon} [bold]{cmd_output.message}[/bold]")


def _print_regular_message_content(message: Message) -> None:
    """Display regular message content excluding CommandCall blocks."""
    # Create a filtered version of the message without CommandCall blocks
    filtered_content = [
        block for block in message.content if not isinstance(block, CommandCall)
    ]
    if filtered_content:
        filtered_text = "\n".join(
            block.display_text() for block in filtered_content
        )
        console.print(
            Markdown(
                filtered_text,
                justify="left",
            ),
            soft_wrap=False,
        )
    # If there's no content after filtering, don't display anything