"""
Terminal process management utilities.

This module provides the Terminal class for managing individual terminal processes,
handling command execution, and monitoring process output.
"""

import logging
import os
import re
import subprocess
import select
import signal
import time
import threading
import shlex
from collections import deque
from dataclasses import dataclass, field
from typing import Deque, Optional

from textwrap import dedent

# Configure logging
logger = logging.getLogger(__name__)


class TerminalError(Exception):
    """Base exception for terminal-related errors."""

    pass


class TerminalExecutionError(TerminalError):
    """Raised when terminal command execution fails."""

    pass


class TerminalTerminationError(TerminalError):
    """Raised when terminal termination fails."""

    pass


class TerminalAlreadyTerminated(TerminalError):
    """Raised when terminal is already terminated."""

    pass


@dataclass
class ActiveCommandStatus:
    """Internal status of an active command with output buffer."""

    exit_code: Optional[int] = None
    output_buffer: Deque[str] = field(default_factory=lambda: deque(maxlen=50))
    is_truncated: bool = False
    log_file: Optional[str] = None


@dataclass
class CommandStatus:
    """Status and output of a shell command."""

    output: str
    exit_code: Optional[int] = None
    output_file: Optional[str] = None
    is_truncated: bool = False

    @property
    def success(self) -> bool:
        """Whether the command completed successfully."""
        return self.exit_code == 0

    @property
    def running(self) -> bool:
        """Whether the command is still running."""
        return self.exit_code is None


class Terminal:
    """Persistent shell process manager for command execution and monitoring."""

    def __init__(self, shell_id: str, exec_dir: str, session):
        # Core identity and settings
        self.id = shell_id
        self.exec_dir = exec_dir
        self.session = session
        self.terminated = False
        self.process = None
        self.log_file = None
        self.log_file_monitor_handle = None

        # Command state tracking with thread safety
        self._command_status_lock = threading.RLock()
        self._command_status = None

        # Background monitoring
        self._command_monitor_thread = None

        self._create_shell_process()
        self._start_command_monitor_thread()

    def _create_shell_process(self) -> None:
        """Initialize the shell process with logging and monitoring."""
        # Set up log file in the execution directory
        log_dir = os.path.join(self.exec_dir, ".neo", "shell")
        os.makedirs(log_dir, exist_ok=True)
        self.log_file = os.path.join(log_dir, f"terminal_{self.id}.log")

        logger.info(f"Terminal {self.id} log file initialized at {self.log_file}")

        # Set up execution environment
        env = os.environ.copy()
        env["TERM"] = "xterm-256color"  # Ensure we get color output
        env["PS1"] = "$ "  # Set a very basic prompt to avoid interference
        env["BASH_SILENCE_DEPRECATION_WARNING"] = "1"  # Silence macOS bash warnings

        # Start the shell process
        logger.info(f"Starting shell process for terminal {self.id} in {self.exec_dir}")
        # Open the log file for writing
        log_fd = open(self.log_file, "w", buffering=1)
        log_fd.flush()
        self.process = subprocess.Popen(
            ["bash"],
            stdin=subprocess.PIPE,
            stdout=log_fd,
            stderr=subprocess.STDOUT,
            shell=True,
            cwd=self.exec_dir,
            env=env,
        )

        # Initialize with a cd to the exec_dir to ensure we're in the right place
        cd_cmd = f"cd {shlex.quote(self.exec_dir)}\n"
        self.process.stdin.write(cd_cmd.encode())
        self.process.stdin.flush()

        # Verify process started successfully
        if self.process.poll() is not None:
            raise TerminalExecutionError(
                f"Terminal process failed immediately with exit code: {self.process.returncode}"
            )

        logger.info(f"Shell process started for terminal {self.id}")

    def _start_command_monitor_thread(self) -> None:
        """Start a background thread to monitor terminal output and process command status."""
        self._command_monitor_thread = threading.Thread(
            target=self._monitor_worker, daemon=True
        )
        self._command_monitor_thread.start()

    def _monitor_worker(self):
        logger.info(f"Command monitor thread for terminal {self.id} started")
        try:
            self.log_file_monitor_handle = open(self.log_file, "r", buffering=1)
            log_fd = self.log_file_monitor_handle
            while True:
                line = log_fd.readline()
                if not line:
                    time.sleep(0.1)
                    continue
                self._process_log_update(line)
        except Exception as e:
            logger.error(
                f"Error in command monitor thread for terminal {self.id}", exc_info=True
            )
        finally:
            if self.log_file_monitor_handle:
                self.log_file_monitor_handle.close()
                self.log_file_monitor_handle = None

    def _process_log_update(self, line: str) -> None:
        """Process a line from the log file and handle command completion if detected."""
        exit_code = None
        end_marker = f"__CMD_END_{self.id}"
        logger.info(f"Processing log update: {line}")
        end_marker_idx = line.find(end_marker)
        new_line = line
        if end_marker_idx != -1:
            try:
                # The marker is in format __CMD_END_id_exitcode
                exit_code = int(line.split("_")[-1].strip())
                if end_marker_idx > 0:
                    new_line = line[:end_marker_idx]
                else:
                    new_line = None
            except (ValueError, IndexError) as e:
                logger.error(f"Failed to parse exit code from '{line}': {e}")
                exit_code = 1
        

        with self._command_status_lock:
            if not self._command_status:
                return
            if new_line:
                output_buffer = self._command_status.output_buffer
                # Add to output buffer
                if len(output_buffer) == output_buffer.maxlen:
                    self._command_status.is_truncated = True
                output_buffer.append(new_line)
            if exit_code is not None:
                self._command_status.exit_code = exit_code
                logger.info(
                    f"Command in terminal {self.id} completed with exit code {exit_code}"
                )

    def _get_command_status(self) -> Optional[CommandStatus]:
        """Return current command status with output buffer contents."""
        with self._command_status_lock:
            if not self._command_status:
                return None
            return CommandStatus(
                output="".join(list(self._command_status.output_buffer)),
                exit_code=self._command_status.exit_code,
                output_file=self.log_file,
                is_truncated=self._command_status.is_truncated,
            )

    def _submit_command(self, command: str) -> None:
        """Submit a command for execution and initialize its status tracking."""
        # Initialize command state with a new status object
        with self._command_status_lock:
            self._command_status = ActiveCommandStatus(log_file=self.log_file)

        # Create the command script with end marker
        end_marker = f"__CMD_END_{self.id}"
        script = f"""{command}; printf '{end_marker}_%d\n' $?;\n"""

        # Log and execute
        logger.info(f"Executing command in terminal {self.id}: {command}")
        self.process.stdin.write(script.encode())
        self.process.stdin.flush()

    def _validate_shell_not_terminated(self) -> None:
        if self.terminated:
            raise TerminalAlreadyTerminated("Terminal has been terminated")

    def _validate_command_submitted(self) -> None:
        if not self._command_status:
            raise TerminalExecutionError(
                "No command has been submitted yet to the terminal"
            )

    def _validate_command_running(self) -> None:
        self._validate_command_submitted()
        if not self._get_command_status().running:
            raise TerminalExecutionError("Command is not running")

    def status(self, timeout: float = 5.0) -> CommandStatus:
        """Get current command status, optionally waiting for completion."""
        self._validate_command_submitted()

        start_time = time.time()
        current_status = self._get_command_status()
        while time.time() - start_time < timeout and current_status.running:
            time.sleep(0.1)
            current_status = self._get_command_status()

        return current_status

    def execute_command(self, command: str, timeout: float = 2.0) -> CommandStatus:
        """Run a command and wait for completion if timeout > 0."""
        self._validate_shell_not_terminated()
        if not command.strip():
            raise TerminalExecutionError("Cannot execute empty command")

        command_status = self._get_command_status()
        if command_status and command_status.running:
            raise TerminalExecutionError("Another command is already running")

        self._submit_command(command)
        return self.status(timeout)

    def write_input(self, content: str, press_enter: bool = True) -> bool:
        """Write input to the terminal, optionally adding a newline."""
        self._validate_shell_not_terminated()
        self._validate_command_running()

        # Add a newline if requested
        if press_enter and not content.endswith("\n"):
            content += "\n"

        # Write to process stdin
        self.process.stdin.write(content.encode())
        self.process.stdin.flush()

        return True

    def terminate(self) -> None:
        """Terminate the terminal process and clean up resources."""
        # Already terminated, nothing to do
        if self.terminated:
            return

        # Kill shell process
        self.process.kill()

        # Kill command monitor thread.
        if self.log_file_monitor_handle:
            # Closing file handle will interrupt the monitor
            self.log_file_monitor_handle.close()
            self.log_file_monitor_handle = None
        self._command_monitor_thread.join(1.0)

        with self._command_status_lock:
            if (
                self._command_status is not None
                and self._command_status.exit_code is None
            ):
                self._command_status.exit_code = 1

        self.terminated = True

        with open(self.log_file, "r") as f:
            print(f"zzz - log file contents:\n{f.read()}\n")
