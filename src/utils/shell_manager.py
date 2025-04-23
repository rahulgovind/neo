"""
Core shell utilities for interacting with shell processes.

This module provides utilities for:
- Starting and managing shell processes
- Executing commands in a shell
- Handling input/output of shell processes
- Terminating shell processes
"""

import os
import logging
import subprocess
import select
import signal
import time
import errno
from typing import Dict, Optional, Tuple, List, Any
from dataclasses import dataclass

# Configure logging
logger = logging.getLogger(__name__)


class ShellError(Exception):
    """Base exception for shell-related errors."""
    pass

class ShellNotFoundError(ShellError):
    """Raised when a requested shell ID doesn't exist."""
    pass

class ShellExecutionError(ShellError):
    """Raised when shell command execution fails."""
    pass

class ShellTerminationError(ShellError):
    """Raised when shell termination fails."""
    pass

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

class Shell:
    """Manages a single shell process with monitoring and command execution."""
    
    def __init__(self, shell_id: str, exec_dir: str, session):
        # Core properties
        self.id: str = shell_id
        self.exec_dir: str = exec_dir
        self.session = session  # Session object for logging context
        
        # Process state
        self.process: Optional[subprocess.Popen] = None
        self.log_file: Optional[str] = None
        self.active: bool = False
        self.running_command: bool = False
        self.last_exit_code: Optional[int] = None
        self.current_command: str = ''
        
        # Monitoring threads
        self._render_monitor_thread = None
        self._process_monitor_thread = None
        self._stop_threads: bool = False
        
        # Initialize the shell process
        self._create_shell_process()
        
    def _create_shell_process(self) -> None:
        """Initialize the shell process with proper logging and monitoring."""
        log_fd = None
        try:
            # Setup the execution environment
            cwd = self._setup_working_directory()
            log_fd = self._setup_log_file(cwd)
            env = self._prepare_environment()
            
            # Start the actual shell process
            self.process = self._start_shell_process(cwd, log_fd, env)
            self.active = True
            
            # Setup shell environment and start monitoring
            self._setup_shell_environment(log_fd)
            self._start_monitoring_threads()
            
            logger.info(f"Shell {self.id} created successfully in {cwd}")
            
        except FileNotFoundError as e:
            logger.error(f"Directory or binary not found: {e}")
            raise ShellExecutionError(f"Directory or shell binary not found: {e}") from e
        except (PermissionError, OSError) as e:
            logger.error(f"Failed to access file or directory: {e}")
            raise ShellExecutionError(f"File or directory access error: {e}") from e
        except subprocess.SubprocessError as e:
            logger.error(f"Failed to start shell process: {e}")
            raise ShellExecutionError(f"Shell process creation failed: {e}") from e
        except Exception as e:
            logger.error(f"Unexpected error creating shell: {e}")
            raise ShellExecutionError(f"Shell creation failed: {e}") from e
        finally:
            # Ensure log file descriptor is closed if opened
            if log_fd is not None:
                try:
                    log_fd.close()
                except Exception:
                    pass
    
    def _setup_working_directory(self) -> str:
        """Ensure working directory exists or fall back to a valid one."""
        cwd = self.exec_dir
        if not os.path.isdir(cwd):
            # Fall back to current directory if specified one doesn't exist
            cwd = os.getcwd()
            logger.warning(f"Directory {self.exec_dir} not found, using {cwd}")
            self.exec_dir = cwd
        return cwd
        
    def _setup_log_file(self, cwd: str) -> Any:  # Returns file descriptor
        """Create and initialize the log file."""
        # Create log directory in session directory
        log_dir = os.path.join(self.session.internal_session_dir, "shell", self.id)
        os.makedirs(log_dir, exist_ok=True)
        
        # Set up log file path
        self.log_file = os.path.join(log_dir, "output.log")
        
        # Initialize log file with header information
        with open(self.log_file, 'w') as f:
            f.write(f"# Shell session started at {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"# Working directory: {cwd}\n")
            f.write(f"# Shell ID: {self.id}\n")
        
        # Return file descriptor for process output redirection
        return open(self.log_file, 'a', buffering=1)  # Line-buffered mode
    
    def _prepare_environment(self) -> Dict[str, str]:
        """Prepare environment variables for the shell process."""
        env = os.environ.copy()
        env["PS1"] = ""  # Empty prompt to avoid cluttering output
        env["HISTFILE"] = "/dev/null"  # Disable command history
        env["TERM"] = "xterm-256color"  # Enable color support
        return env
        
    def _start_shell_process(self, cwd: str, log_fd: Any, env: Dict[str, str]) -> subprocess.Popen:
        """Start the actual shell process with the prepared configuration."""
        process = subprocess.Popen(
            '/bin/bash',
            stdin=subprocess.PIPE,
            stdout=log_fd,
            stderr=log_fd,
            cwd=cwd,
            env=env,
            universal_newlines=False,  # Binary mode for stdin
            bufsize=1,  # Line buffered
            shell=False  # Don't wrap in another shell
        )
        
        # Verify process started successfully
        if process.poll() is not None:
            raise ShellExecutionError(
                f"Shell process failed immediately with exit code: {process.returncode}"
            )
            
        return process
        
    def _start_monitoring_threads(self) -> None:
        """Start the monitoring threads for this shell."""
        self._start_render_monitor_thread()
        self._start_process_monitor_thread()
            
    def _setup_shell_environment(self, log_fd):
        """Setup the shell environment with initial configuration."""
        # Essential shell configurations
        setup_commands = [
            "export PS1=''",              # Empty prompt
            "export HISTFILE=/dev/null",  # Disable command history
            "shopt -s expand_aliases",    # Enable aliases
            "set -o pipefail",           # Better error handling for pipelines
            "PAGER=cat",                 # Don't use pagers
            "stty -echo"                 # Disable terminal echo
        ]
        
        # Write setup commands to shell
        setup_script = '\n'.join(setup_commands) + '\n'
        self.process.stdin.write(setup_script.encode('utf-8'))
        self.process.stdin.flush()
        
        # Flush all setup commands
        self.process.stdin.flush()
    
    def _start_render_monitor_thread(self):
        """Start a background thread to monitor the log file for command markers."""
        import threading
        
        def render_monitor_thread():
            """Monitor the log file for command start and completion markers."""
            try:
                # Keep track of the last read position
                file_position = 0
                
                while not self._stop_threads and self.active:
                    # Only check for markers if a command is running
                    if self.running_command:
                        try:
                            with open(self.log_file, 'r') as log:
                                # Seek to last read position
                                log.seek(file_position)
                                
                                # Read new content
                                new_content = log.read()
                                
                                # Update file position for next read
                                file_position = log.tell()
                                
                                # Check for command completion marker if new content
                                if new_content and self.running_command:
                                    self._check_for_completion_marker(new_content)
                        except Exception as e:
                            logger.error(f"Error reading log file: {str(e)}")
                    
                    # Short sleep to avoid busy-waiting
                    time.sleep(0.05)
            
            except Exception as e:
                logger.error(f"Error in render monitor thread: {str(e)}")
            finally:
                logger.info(f"Render monitor thread for shell {self.id} exiting")
        
        # Start the thread
        self._render_monitor_thread = threading.Thread(target=render_monitor_thread, daemon=True)
        self._render_monitor_thread.start()
    
    def _start_process_monitor_thread(self):
        """Start a background thread to monitor the shell process status."""
        import threading
        
        def process_monitor_thread():
            """Monitor the shell process and update status when it terminates."""
            try:
                while not self._stop_threads and self.active:
                    # Check if process has terminated
                    if self.process and self.process.poll() is not None:
                        # Process has terminated
                        exit_code = self.process.returncode
                        logger.info(f"Shell process {self.id} terminated with exit code {exit_code}")
                        
                        # Update shell status
                        self.active = False
                        
                        # If a command was running, mark it as failed
                        if self.running_command:
                            self.running_command = False
                            self.last_exit_code = exit_code
                            
                            # Log termination to the log file
                            try:
                                with open(self.log_file, 'a') as log:
                                    log.write(f"\n[Shell process terminated with exit code {exit_code}]\n")
                            except:
                                pass
                        
                        break
                    
                    # Check periodically
                    time.sleep(0.1)
            
            except Exception as e:
                logger.error(f"Error in process monitor thread: {str(e)}")
            finally:
                logger.info(f"Process monitor thread for shell {self.id} exiting")
        
        # Start the thread
        self._process_monitor_thread = threading.Thread(target=process_monitor_thread, daemon=True)
        self._process_monitor_thread.start()
        
    def wait_on_command(self, timeout: float = 2.0) -> bool:
        """
        Wait for the current command to complete or timeout.
        
        Args:
            timeout: Maximum time to wait in seconds
            
        Returns:
            True if command completed, False if it timed out
        """
        if not self.running_command:
            return True  # No command running, so we're done
        
        start_time = time.time()
        while time.time() - start_time < timeout and self.running_command:
            # The render monitor thread will detect command completion
            time.sleep(0.05)
        
        # Return True if command completed, False if it timed out
        return not self.running_command
    
    def _check_for_completion_marker(self, text: str):
        """Check if the text contains a command completion marker."""
        # Check for command end marker with format __CMD_END_{shell_id}_{timestamp}_{exit_code}
        end_marker_pattern = f"__CMD_END_{self.id}_"
        
        if end_marker_pattern in text:
            # Extract the exit code from the marker line
            lines = text.splitlines()
            for line in lines:
                if end_marker_pattern in line:
                    try:
                        # Format is: __CMD_END_{shell_id}_{timestamp}_{exit_code}
                        parts = line.strip().split('_')
                        # Extract exit code from the last part
                        if len(parts) >= 5:
                            self.last_exit_code = int(parts[-1])
                            self.running_command = False
                            logger.info(f"Command completed with exit code {self.last_exit_code}")
                            break
                    except (ValueError, IndexError) as e:
                        logger.warning(f"Could not parse exit code from marker: {line}, error: {str(e)}")
                        # Default to success if we can't parse the exit code
                        self.last_exit_code = 0
                        self.running_command = False
    
    def execute_command(self, command: str, timeout: float = 2.0, max_output_lines: int = 100) -> CommandStatus:
        """Run a command in the shell with output tracking."""
        # Validate shell and command state
        self._validate_shell_state()
        self._validate_command_state()
        
        # Create command markers to track execution
        markers = self._create_command_markers()
        
        # Set command state
        self.running_command = True
        self.current_command = command
        
        try:
            # Send and wait for command
            self._send_command_to_shell(command, markers)
            command_completed = self._wait_for_command_completion(timeout)
            
            # Return the command output
            return self._get_command_result(markers, max_output_lines, not command_completed)
            
        except BrokenPipeError as e:
            logger.error(f"Shell process pipe closed: {e}")
            self._handle_command_failure("Shell process has terminated")
            return CommandStatus(output="Shell process has terminated", exit_code=1)
        except OSError as e:
            logger.error(f"OS error while executing command: {e}")
            self._handle_command_failure(f"OS error: {e}")
            return CommandStatus(output=f"OS error: {e}", exit_code=1)
        except Exception as e:
            logger.error(f"Unexpected error executing command: {e}")
            self._handle_command_failure(str(e))
            return CommandStatus(output=f"Error: {e}", exit_code=1)
    
    def _validate_shell_state(self) -> None:
        """Ensure shell is in a valid state for command execution."""
        if not self.active or not self.process or self.process.poll() is not None:
            raise ShellExecutionError("Shell is not active")
    
    def _validate_command_state(self) -> None:
        """Ensure no other command is currently running."""
        if self.running_command:
            raise ShellExecutionError("Another command is already running")
    
    def _create_command_markers(self) -> Dict[str, str]:
        """Create unique markers for tracking command start/end."""
        cmd_timestamp = int(time.time())
        start_marker = f"__CMD_START_{self.id}_{cmd_timestamp}"
        end_marker = f"__CMD_END_{self.id}_{cmd_timestamp}"
        return {"start": start_marker, "end": end_marker}
    
    def _send_command_to_shell(self, command: str, markers: Dict[str, str]) -> None:
        """Send the command to the shell process with tracking markers."""
        # Create the command script with markers
        script = f"""
printf '{markers["start"]}\n' >> "{self.log_file}"
({command}; printf '{markers["end"]}_%d\n' $?) >> "{self.log_file}" 2>&1
"""
        
        # Log and execute
        logger.info(f"Executing command in shell {self.id}: {command}")
        self.process.stdin.write(script.encode('utf-8'))
        self.process.stdin.flush()
    
    def _wait_for_command_completion(self, timeout: float) -> bool:
        """Wait for command to complete with timeout."""
        completed = self.wait_on_command(timeout)
        
        if not completed:
            logger.info(f"Command didn't complete within {timeout} seconds")
            self.running_command = False
            # Don't set exit code for command that's still running
            # Just mark it as not completed
        
        return completed
    
    def _get_command_result(self, markers: Dict[str, str], max_lines: int, timed_out: bool) -> CommandStatus:
        """Extract command output and create result."""
        return self._get_command_output(markers["start"], markers["end"], max_lines, timed_out)
    
    def _handle_command_failure(self, error_msg: str) -> None:
        """Handle command execution failure."""
        self.running_command = False
        self.last_exit_code = 1  # Generic error code
    
    def get_recent_output(self, max_output_lines: int) -> CommandStatus:
        """Get recent log output without using command markers.
        Used by the view command to get latest shell content.
        
        Args:
            max_output_lines: Maximum lines to include in the output
            
        Returns:
            CommandStatus with recent output
        """
        all_output = ""
        is_truncated = False
        
        try:
            # Read the log file to extract recent output
            with open(self.log_file, 'r') as f:
                lines = f.readlines()
                
                is_truncated = len(lines) > max_output_lines
                if is_truncated:
                    # Get the most recent lines
                    output_lines = lines[-max_output_lines:]
                    all_output = "".join(output_lines).strip()
                else:
                    all_output = "".join(lines).strip()
                
        except Exception as e:
            logger.error(f"Error reading shell output file: {str(e)}")
            all_output = f"Error reading output: {str(e)}"
        
        return CommandStatus(
            output=all_output,
            exit_code=self.last_exit_code,
            output_file=self.log_file if os.path.exists(self.log_file) else None,
            is_truncated=is_truncated
        )
        
    def _get_command_output(self, start_marker: str, end_marker: str, max_output_lines: int, timed_out: bool) -> CommandStatus:
        """Extract command output using markers."""
        all_output = ""
        is_truncated = False
        
        try:
            with open(self.log_file, 'r') as f:
                lines = f.readlines()
                
                # Find marker positions
                start_idx = -1
                end_idx = -1
                
                for i, line in enumerate(lines):
                    if start_marker in line:
                        start_idx = i
                    if end_marker in line and i > start_idx:
                        end_idx = i
                        break
                
                if start_idx == -1:
                    # Missing start marker indicates command execution failure
                    logger.error(f"Start marker not found in log file")
                    raise ShellExecutionError("Command execution failed - no start marker found")
                
                # Extract output between markers
                if end_idx != -1:
                    # Complete command execution
                    output_lines = lines[start_idx + 1:end_idx]
                else:
                    # Still running or timed out
                    output_lines = lines[start_idx + 1:]
                
                # Handle truncation if needed
                is_truncated = len(output_lines) > max_output_lines
                if is_truncated:
                    output_lines = output_lines[:max_output_lines]
                
                all_output = "".join(output_lines).strip()
        except FileNotFoundError:
            logger.error("Log file not found")
            all_output = "Log file not found or deleted"
        except IOError as e:
            logger.error(f"IO error reading log file: {e}")
            all_output = f"Error reading output: {e}"
        except Exception as e:
            logger.error(f"Unexpected error extracting command output: {e}")
            all_output = f"Error getting command output: {e}"
        
        return CommandStatus(
            output=all_output,
            exit_code=self.last_exit_code,
            output_file=self.log_file,
            is_truncated=is_truncated
        )
    
    def write_input(self, content: str, press_enter: bool = True) -> bool:
        """Write input to the shell.
        
        Args:
            content: Text content to write
            press_enter: Whether to automatically add a newline
            
        Returns:
            True if successful, False otherwise
        """
        if not self.active or not self.process or self.process.poll() is not None:
            return False
        
        try:
            # Log the input to the log file
            with open(self.log_file, 'a') as log:
                log.write(f"\n[INPUT]: {content}\n")
            
            # Write to stdin
            if press_enter:
                content += '\n'  # Add a newline to simulate pressing Enter
                
            self.process.stdin.write(content.encode('utf-8'))
            self.process.stdin.flush()
            
            return True
            
        except Exception as e:
            logger.error(f"Error writing to shell: {str(e)}")
            return False
    
    def get_recent_output(self, max_output_lines: int) -> CommandStatus:
        """Get recent output from the log file."""
        all_output = ""
        is_truncated = False
        
        try:
            with open(self.log_file, 'r') as f:
                lines = f.readlines()
                
                # Handle truncation if needed
                is_truncated = len(lines) > max_output_lines
                if is_truncated:
                    lines = lines[-max_output_lines:]
                
                all_output = "".join(lines).strip()
                
        except FileNotFoundError:
            logger.error("Log file not found")
            all_output = "Log file not found"
        except IOError as e:
            logger.error(f"IO error reading log file: {e}")
            all_output = f"Cannot read shell output: {e}"
        
        return CommandStatus(
            output=all_output,
            exit_code=self.last_exit_code,
            output_file=self.log_file,
            is_truncated=is_truncated
        )
    
    def terminate(self) -> bool:
        """Terminate the shell process and clean up resources.
        
        Returns:
            True if successful, False otherwise
        """
        if not self.active:
            return True  # Already terminated
        
        try:
            # Signal all threads to stop
            self._stop_threads = True
            
            # If a command is running, mark it as failed
            if self.running_command:
                self.running_command = False
                self.last_exit_code = -1  # Special exit code for termination during command
            
            # Log termination to the log file
            try:
                with open(self.log_file, 'a') as log:
                    log.write(f"\n[Shell {self.id} terminated at {time.strftime('%Y-%m-%d %H:%M:%S')}]\n")
            except Exception as e:
                logger.error(f"Error writing to log file during termination: {str(e)}")
            
            # Terminate the process
            if self.process:
                try:
                    # Try SIGTERM first
                    if self.process.poll() is None:
                        self.process.terminate()
                        
                    # Give it a moment to shut down
                    for _ in range(10):
                        if self.process.poll() is not None:
                            break
                        time.sleep(0.1)
                        
                    # Force kill if still running
                    if self.process.poll() is None:
                        self.process.kill()
                        self.process.wait(timeout=1)
                        
                except Exception as e:
                    logger.error(f"Error terminating process: {str(e)}")
            
            # Wait for threads to finish
            threads = []
            if self._render_monitor_thread and self._render_monitor_thread.is_alive():
                threads.append(self._render_monitor_thread)
            if self._process_monitor_thread and self._process_monitor_thread.is_alive():
                threads.append(self._process_monitor_thread)
                
            # Join all threads with timeout
            for thread in threads:
                thread.join(timeout=1.0)
            
            # Clean up resources
            self.process = None
            self._render_monitor_thread = None
            self._process_monitor_thread = None
            
            # Mark shell as inactive
            self.active = False
            logger.info(f"Shell {self.id} terminated successfully")
            return True
            
        except Exception as e:
            logger.error(f"Error terminating shell: {str(e)}")
            return False
    
class ShellManager:
    """Shell process lifecycle manager."""
    
    # Store Shell instances by ID
    _shells: Dict[str, Shell] = {}
    
    @classmethod
    def get_shell(cls, shell_id: str) -> Optional[Shell]:
        """Get shell by ID."""
        return cls._shells.get(shell_id)
    
    @classmethod
    def create_shell(cls, shell_id: str, exec_dir: str, session) -> Shell:
        """Create a new shell process."""
        # Replace existing shell if needed
        cls._ensure_shell_terminated(shell_id)
        
        try:
            # Create and register the new shell
            shell = Shell(shell_id, exec_dir, session)
            cls._shells[shell_id] = shell
            return shell
        except ShellExecutionError as e:
            logger.error(f"Failed to create shell {shell_id}: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error creating shell {shell_id}: {e}")
            raise ShellExecutionError(f"Shell creation failed: {e}") from e
            
    @classmethod
    def _ensure_shell_terminated(cls, shell_id: str) -> None:
        """Ensure any existing shell with the given ID is terminated."""
        if shell_id in cls._shells:
            cls.terminate_shell(shell_id)
            
    @classmethod
    def cleanup(cls):
        """Clean up all shell instances during session teardown."""
        cls.terminate_all()
    
    @classmethod
    def execute_command(
        cls, 
        shell_id: str, 
        command: str, 
        exec_dir: str,
        timeout: float = 2.0,
        session=None,
        max_output_lines: int = 100
    ) -> CommandStatus:
        """Execute a command in the specified shell."""
        # Handle empty commands gracefully
        if not command.strip():
            return CommandStatus(output="", exit_code=0)
            
        try:
            # Get or create shell with specified parameters
            shell = cls._get_or_create_shell(shell_id, exec_dir, session)
            
            # Execute the command in the shell
            return shell.execute_command(command, timeout, max_output_lines)
            
        except ShellNotFoundError as e:
            logger.error(f"Shell not found: {e}")
            return CommandStatus(output=str(e), exit_code=1)
        except ShellExecutionError as e:
            logger.error(f"Command execution error: {e}")
            return CommandStatus(output=str(e), exit_code=1)
    
    @classmethod
    def _get_or_create_shell(cls, shell_id: str, exec_dir: str, session) -> Shell:
        """Get existing shell or create a new one, handling directory changes."""
        # Get existing shell
        shell = cls.get_shell(shell_id)
        
        if not shell:
            # Create new shell if doesn't exist
            if session is None:
                raise ShellExecutionError("Session is required when creating a new shell")
            return cls.create_shell(shell_id, exec_dir, session)
        
        # Check if exec_dir changed and we need a new shell
        if shell.exec_dir != exec_dir:
            if session is None:
                raise ShellExecutionError("Session is required when creating a new shell")
            cls.terminate_shell(shell_id)
            return cls.create_shell(shell_id, exec_dir, session)
            
        return shell
        
    @classmethod
    def view_output(cls, shell_id: str, max_lines: int = 50) -> CommandStatus:
        """Get the latest output from a shell."""
        try:
            shell = cls._get_shell_or_raise(shell_id)
            return shell.get_recent_output(max_lines)
        except ShellNotFoundError as e:
            logger.error(f"Cannot view output: {e}")
            return CommandStatus(output=f"Shell not found: {shell_id}", exit_code=1)
        except Exception as e:
            logger.error(f"Error viewing shell output: {e}")
            return CommandStatus(output=f"Error: {e}", exit_code=1)
        
    @classmethod
    def _get_shell_or_raise(cls, shell_id: str) -> Shell:
        """Get a shell by ID or raise ShellNotFoundError."""
        shell = cls.get_shell(shell_id)
        if not shell:
            raise ShellNotFoundError(f"No shell found with ID '{shell_id}'")
        return shell
    
    @classmethod
    def write_to_shell(cls, shell_id: str, content: str, press_enter: bool = True) -> bool:
        """Write input to a shell process."""
        try:
            shell = cls._get_shell_or_raise(shell_id)
            return shell.write_input(content, press_enter)
        except ShellNotFoundError as e:
            logger.error(f"Cannot write to shell: {e}")
            return False
        except Exception as e:
            logger.error(f"Error writing to shell: {e}")
            return False
            
    @classmethod
    def terminate_shell(cls, shell_id: str) -> bool:
        """Terminate a shell process and clean up resources."""
        shell = cls.get_shell(shell_id)
        if not shell:
            return True  # Already terminated
        
        try:
            # Attempt to terminate the shell
            success = shell.terminate()
            
            # Always remove from collection, even if termination failed
            cls._shells.pop(shell_id, None)
            
            if not success:
                logger.warning(f"Shell {shell_id} reported unsuccessful termination")
                
            return success
        except Exception as e:
            logger.error(f"Error terminating shell {shell_id}: {e}")
            # Still remove from collection to avoid stuck references
            cls._shells.pop(shell_id, None)
            return False
    
    @classmethod
    def terminate_all(cls) -> bool:
        """Terminate all active shell processes."""
        if not cls._shells:
            return True  # No shells to terminate
            
        logger.info(f"Terminating {len(cls._shells)} active shells")
        success = True
        
        # Get IDs first to avoid modifying while iterating
        for shell_id in list(cls._shells.keys()):
            if not cls.terminate_shell(shell_id):
                success = False
                
        return success

    # Keep old method name for backward compatibility
    terminate_process = terminate_shell
