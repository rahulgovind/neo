"""
Launcher module for the Neo web server.
Provides commands to start, stop, and restart the web server.
"""

import os
import sys
import signal
import argparse
import subprocess
import time
from pathlib import Path
from typing import Optional

# Default port for the web server
DEFAULT_PORT = 8888


def _get_pid_file_path() -> Path:
    """Get the path to the PID file for the web server."""
    pid_dir = Path(os.path.expanduser("~")) / ".neo" / "web"
    pid_dir.mkdir(parents=True, exist_ok=True)
    return pid_dir / "server.pid"


def _get_log_file_path() -> Path:
    """Get the path to the log file for the web server."""
    log_dir = Path(os.path.expanduser("~")) / ".neo" / "web"
    log_dir.mkdir(parents=True, exist_ok=True)
    return log_dir / "server.log"


def _read_pid() -> Optional[int]:
    """Read the PID from the PID file if it exists."""
    pid_file = _get_pid_file_path()
    if pid_file.exists():
        try:
            with open(pid_file, "r") as f:
                pid = int(f.read().strip())
            return pid
        except (ValueError, IOError):
            return None
    return None


def _write_pid(pid: int) -> None:
    """Write the PID to the PID file."""
    pid_file = _get_pid_file_path()
    with open(pid_file, "w") as f:
        f.write(str(pid))


def _remove_pid_file() -> None:
    """Remove the PID file."""
    pid_file = _get_pid_file_path()
    if pid_file.exists():
        pid_file.unlink()


def _is_process_running(pid: int) -> bool:
    """Check if a process with the given PID is running."""
    try:
        # Sending signal 0 to a pid will raise an exception if the process
        # doesn't exist or permissions deny sending the signal
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def start_server(args: argparse.Namespace) -> None:
    """Start the web server if not already running."""
    # Check if server is already running
    pid = _read_pid()
    if pid is not None and _is_process_running(pid):
        if args.force_restart:
            print(f"Server is already running with PID {pid}, stopping it first...")
            stop_server(args)
        else:
            print(f"Server is already running with PID {pid}")
            return

    # Start the server
    host = args.host
    port = args.port
    debug = args.debug
    workspace = args.workspace
    log_file_path = _get_log_file_path()

    # Create log directory if it doesn't exist
    log_dir = os.path.dirname(str(log_file_path))
    os.makedirs(log_dir, exist_ok=True)

    # Start server in a new process with logs redirected to file
    with open(log_file_path, "w") as log_file:
        server_process = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "src.apps.web.app",
                "--host",
                host,
                "--port",
                str(port),
                *(["--debug"] if debug else []),
                *(["--workspace", workspace] if workspace else []),
            ],
            stdout=log_file,
            stderr=log_file,
            start_new_session=True,  # Start in a new session to detach from parent
        )

    # Wait a short time to see if the process starts successfully
    time.sleep(1)

    # Check if the process is still running
    if _is_process_running(server_process.pid):
        # Write the PID to the PID file
        _write_pid(server_process.pid)
        print(f"Server started on http://{host}:{port}")
        print(f"PID: {server_process.pid}")
        print(f"Logs being written to: {log_file_path}")
    else:
        print("Failed to start server. Check the logs for details.")
        print(f"Log file: {log_file_path}")


def stop_server(args: argparse.Namespace) -> None:
    """Stop the web server if running."""
    pid = _read_pid()
    if pid is None:
        print("Server is not running or PID file not found")
        return

    # Check if the process is actually running
    if not _is_process_running(pid):
        print("Server is not running but PID file exists, cleaning up")
        _remove_pid_file()
        return

    # Try to gracefully terminate the process
    try:
        os.kill(pid, signal.SIGTERM)
        # Wait for the process to terminate
        for _ in range(5):  # Wait up to 5 seconds
            if not _is_process_running(pid):
                break
            time.sleep(1)
        else:
            # Force kill if it didn't terminate gracefully
            print("Server didn't terminate gracefully, force killing")
            os.kill(pid, signal.SIGKILL)
    except OSError as e:
        print(f"Error stopping server: {e}")

    # Clean up PID file
    _remove_pid_file()
    print("Server stopped")


def main() -> None:
    """Main entry point for the web server launcher."""
    parser = argparse.ArgumentParser(description="Neo Web Server Launcher")
    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # Start command
    start_parser = subparsers.add_parser("start", help="Start the web server")
    start_parser.add_argument(
        "--host", default="127.0.0.1", help="Host to run the server on"
    )
    start_parser.add_argument(
        "--port", type=int, default=DEFAULT_PORT, help="Port to run the server on"
    )
    start_parser.add_argument("--debug", action="store_true", help="Run in debug mode")
    start_parser.add_argument("--workspace", help="Path to workspace")
    start_parser.add_argument(
        "--force-restart",
        action="store_true",
        help="Force restart if server is already running",
    )

    # Stop command
    stop_parser = subparsers.add_parser("stop", help="Stop the web server")

    # Parse arguments
    args = parser.parse_args()

    # Execute the appropriate command
    if args.command == "start":
        start_server(args)
    elif args.command == "stop":
        stop_server(args)
    else:
        # Default to showing help if no command specified
        parser.print_help()


if __name__ == "__main__":
    main()
