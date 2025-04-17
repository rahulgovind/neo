"""Implements the 'bash' command for executing shell commands."""

import os
import logging
import subprocess
import textwrap
import signal
import select
from typing import Dict, Any, Optional, List

from src.neo.shell.command import Command, CommandTemplate
from src.neo.core.messages import CommandResult
from src.neo.session import Session

# Configure logging
logger = logging.getLogger(__name__)


class BashCommand(Command):
    """
    Command for executing shell commands using a persistent shell.

    Features:
    - Maintains a persistent shell across command invocations
    - Runs standard shell commands
    - Captures and returns command output
    - Uses the workspace from the Session as the working directory
    """

    # Class variable to store the persistent shell process
    _shell_process = None
    _process_id = None

    def template(self) -> CommandTemplate:
        """
        Returns the command template with parameter definitions and documentation.
        """
        return CommandTemplate(
            name="bash",
            description=textwrap.dedent(
                """
                Execute a shell command.
                
                The bash command executes the shell command specified in the data section after the pipe symbol.
                The command is executed in the current workspace directory.
                
                NOTE: This command should only be used when more specialized commands cannot be used.
                Always prefer using dedicated commands like read_file, write_file, grep, or find when possible.
            """
            ),
            examples=textwrap.dedent(
                """
                ▶bash｜ls -la■
                ✅total 24
                drwxr-xr-x  5 user  staff  160 Apr  4 10:00 .
                drwxr-xr-x  8 user  staff  256 Apr  4 09:58 ..
                -rw-r--r--  1 user  staff   78 Apr  4 10:00 file1.txt
                -rw-r--r--  1 user  staff  102 Apr  4 10:00 file2.py■
                
                ▶bash｜cat file1.txt■
                ✅This is the content of file1.txt■
                
                ▶bash｜echo "Hello, world!"■
                ✅Hello, world!■
            """
            ),
            requires_data=True,
            parameters=[],
        )

    def process(
        self, session, args: Dict[str, Any], data: Optional[str] = None
    ) -> CommandResult:
        """
        Process the command with the parsed arguments and data.

        Args:
            session: Application session
            args: Dictionary of parameter names to their values
            data: The shell command to execute as a string

        Returns:
            CommandResult with output from the shell command and summary
        """
        # Get the workspace from the session
        workspace = session.workspace

        # Get the command from the data parameter
        command = data.strip() if data else ""
        if not command:
            logger.error("Empty command provided to bash command")
            raise RuntimeError("Command cannot be empty")

        logger.info(f"Executing shell command: {command}")

        result_prefix = ""

        try:
            # Check if we need to start a new shell process
            if (
                BashCommand._shell_process is None
                or BashCommand._shell_process.poll() is not None
            ):
                # If process terminated normally, add a message
                if (
                    BashCommand._shell_process is not None
                    and BashCommand._shell_process.poll() == 0
                ):
                    result_prefix = f"* Shell {BashCommand._process_id} terminated *\n"

                # Start a new persistent shell process
                BashCommand._shell_process = subprocess.Popen(
                    "/bin/bash",
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    cwd=workspace,
                    bufsize=1,
                    universal_newlines=True,
                )
                BashCommand._process_id = BashCommand._shell_process.pid
                result_prefix += f"* Started shell {BashCommand._process_id} *\n"
                logger.info(
                    f"Started new shell process with PID: {BashCommand._process_id}"
                )
            else:
                result_prefix = (
                    f"* Continuing execution on shell {BashCommand._process_id} *\n"
                )
                logger.info(
                    f"Reusing existing shell with PID: {BashCommand._process_id}"
                )

            # If the command is 'exit', handle it specially
            if command.strip() == "exit":
                # The shell will be terminating, so capture this before it happens
                result = result_prefix + "* Shell terminating *"
                # Clean up references to the terminated process
                BashCommand._process_id = None
                BashCommand._shell_process = None
                summary = "Shell terminated"
                return CommandResult(content=result, success=True, summary=summary)

            # Send the command to the shell process
            command_with_newline = command + "\n"
            BashCommand._shell_process.stdin.write(command_with_newline)
            BashCommand._shell_process.stdin.flush()
            
            # Add a command to capture the exit code immediately
            BashCommand._shell_process.stdin.write("EXIT_CODE=$?\n")
            BashCommand._shell_process.stdin.flush()
            
            # Add a unique marker to detect end of output
            end_marker = f"__END_OF_COMMAND_{id(command)}__"
            BashCommand._shell_process.stdin.write(f"echo {end_marker}\n")
            BashCommand._shell_process.stdin.flush()

            # Collect output until we see the end marker
            output_lines = []
            error_lines = []

            # Check if the process is still alive
            if BashCommand._shell_process.poll() is not None:
                returncode = BashCommand._shell_process.poll()
                stderr = BashCommand._shell_process.stderr.read()
                error_msg = (
                    stderr.strip() if stderr else f"Shell exited with code {returncode}"
                )
                logger.error(f"Shell process terminated unexpectedly: {error_msg}")
                raise RuntimeError(f"Shell process terminated: {error_msg}")

            # Read output until we find the end marker
            while True:
                line = BashCommand._shell_process.stdout.readline().rstrip("\n")
                if end_marker in line:
                    # Remove the marker if it's part of the line
                    if line != end_marker:
                        clean_line = line.replace(end_marker, "")
                        if clean_line:
                            output_lines.append(clean_line)
                    break
                output_lines.append(line)

                # Check if process has terminated while we're reading
                if BashCommand._shell_process.poll() is not None:
                    break

            # Get the exit code we saved earlier
            try:
                BashCommand._shell_process.stdin.write("echo $EXIT_CODE\n")
                BashCommand._shell_process.stdin.flush()
                exit_code_line = BashCommand._shell_process.stdout.readline().strip()
            except BrokenPipeError:
                # If the pipe is broken, the shell has likely terminated
                logger.info("Shell process terminated while checking exit status")
                BashCommand._process_id = None
                BashCommand._shell_process = None
                result = result_prefix + "\n".join(output_lines)
                summary = "Shell terminated while executing command"
                return CommandResult(content=result, success=True, summary=summary)

            try:
                exit_code = int(exit_code_line)
            except ValueError:
                logger.warning(f"Could not parse exit code: {exit_code_line}")
                exit_code = 0  # Assume success if we can't parse the exit code

            # Read any error output
            while (
                BashCommand._shell_process.stderr.readable()
                and select.select([BashCommand._shell_process.stderr], [], [], 0)[0]
            ):
                error_line = BashCommand._shell_process.stderr.readline().rstrip("\n")
                if error_line:
                    error_lines.append(error_line)

            # Log command execution details
            logger.debug(f"Bash command exit code: {exit_code}")
            logger.debug(f"Bash command stdout: {' '.join(output_lines[:5])}...")
            logger.debug(f"Bash command stderr: {' '.join(error_lines[:5])}...")

            # If there's an error, include the stderr in the output
            if exit_code != 0:
                error_msg = (
                    "\n".join(error_lines)
                    if error_lines
                    else f"Command exited with code {exit_code}"
                )
                logger.error(f"Bash command failed: {error_msg}")
                # Return a failure result instead of raising an exception
                error_output = f"Command failed with exit code {exit_code}: {error_msg}"
                return CommandResult(content=error_output, success=False)

            # Return the stdout from the command without the prefix for tests
            # The tests expect just the raw output without the shell prefix
            result = "\n".join(output_lines)
            
            summary = (
                f"Command executed: {command[:30]}{'...' if len(command) > 30 else ''}"
            )
            return CommandResult(content=result, success=True, summary=summary)

        except BrokenPipeError as e:
            logger.info(f"Shell process terminated: {str(e)}")
            # If this is due to exiting the shell, don't treat as an error
            if command.strip() == "exit":
                BashCommand._process_id = None
                BashCommand._shell_process = None
                return result_prefix + "* Shell terminated *"
            # For other commands, clean up and report the error
            BashCommand._process_id = None
            BashCommand._shell_process = None
            return CommandResult(success=False, content="Shell terminated unexpectedly")

        except Exception as e:
            logger.error(f"Error executing bash command: {str(e)}")

            # Clean up the shell process if there was a serious error
            if (
                BashCommand._shell_process is not None
                and BashCommand._shell_process.poll() is None
            ):
                try:
                    BashCommand._shell_process.terminate()
                    BashCommand._process_id = None
                    BashCommand._shell_process = None
                except:
                    pass

            # Return a failure result instead of raising an exception
            return CommandResult(content=f"Error executing command: {str(e)}", success=False, error=e)
