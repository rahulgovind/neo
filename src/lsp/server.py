"""
LSP server manager - Simplified Python-only implementation.

Manages lifecycle of Python language server and exposes it over TCP for client connections.
"""

import logging
import os
import select
import socket
import subprocess
import sys
import threading
import time
from contextlib import closing
from typing import Dict, List, Optional, Any, Tuple

from .installer import is_server_installed, install

# Configure logging
logger = logging.getLogger(__name__)


class LSPServer:
    """Manages Python language server and provides TCP connectivity."""
    
    # Python LSP server command
    PYTHON_SERVER_COMMAND = ["pylsp"]
    
    def __init__(self):
        """Initialize the LSP server manager."""
        self._server_process = None
        self._tcp_socket = None
        self._port = None
        self._running = False
        self._client_handlers = []
        
    def is_server_installed(self) -> bool:
        """Check if pylsp is installed."""
        try:
            return is_server_installed("python")
        except Exception as e:
            logger.error(f"Error checking if Python LSP server is installed: {e}")
            return False
    
    def install_server(self) -> bool:
        """Install Python LSP server."""
        if self.is_server_installed():
            logger.info("Python LSP server is already installed")
            return True
            
        try:
            logger.info("Installing Python LSP server...")
            return install("python")
        except Exception as e:
            logger.error(f"Error installing Python LSP server: {e}")
            return False
    
    def _start_server_process(self) -> Optional[subprocess.Popen]:
        """Start the Python LSP server process."""
        if not self.is_server_installed():
            installed = self.install_server()
            if not installed:
                logger.error("Failed to install Python LSP server")
                return None

        # Set environment variables for better logging
        env = os.environ.copy()
        env["PYTHONUNBUFFERED"] = "1"  # Ensure Python output is not buffered
        
        try:
            logger.info(f"Starting Python language server with command: {' '.join(self.PYTHON_SERVER_COMMAND)}")
            
            # Start the process with stdin/stdout pipes
            process = subprocess.Popen(
                self.PYTHON_SERVER_COMMAND,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=env,
                bufsize=-1,  # Use system default buffering
                text=False,  # Binary mode for proper JSON-RPC handling
            )
            
            # Check if the process started successfully
            if process.poll() is not None:
                exit_code = process.returncode
                stderr_data = process.stderr.read().decode('utf-8', errors='replace')
                logger.error(f"Python language server failed to start (exit code: {exit_code})")
                if stderr_data:
                    logger.error(f"Server error output: {stderr_data}")
                return None
            
            logger.info(f"Python language server started with PID {process.pid}")
            logger.info(f"Python language server process started successfully with PID {process.pid}")
            return process
            
        except Exception as e:
            logger.error(f"Failed to start Python language server: {e}")
            return None
    
    def _find_free_port(self) -> Optional[int]:
        """Find an available TCP port."""
        try:
            with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as s:
                s.bind(("127.0.0.1", 0))
                s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                return s.getsockname()[1]
        except Exception as e:
            logger.error(f"Failed to find a free port: {e}")
            return None
    
    def setup_local_server(self, language: str) -> Optional[int]:
        """Start server and expose over TCP on a random port.
        
        Args:
            language: The language identifier (must be 'python')
            
        Returns:
            The port number or None if failed
        """
        if language.lower() != "python":
            logger.error(f"Unsupported language: {language}. Only Python is supported")
            return None
            
        # Check if we already have a running server
        if self._running and self._server_process and self._server_process.poll() is None:
            logger.info(f"Reusing existing Python language server on port {self._port}")
            return self._port
            
        # Clean up any existing resources
        self.shutdown()
        
        # Start new Python language server
        process = self._start_server_process()
        if not process:
            return None
            
        # Find an available TCP port
        port = self._find_free_port()
        if not port:
            self._stop_process(process)
            return None
            
        # Start TCP server
        try:
            # Create a socket server
            tcp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            tcp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            tcp_socket.bind(("127.0.0.1", port))
            tcp_socket.listen(5)
            
            # Save server state
            self._server_process = process
            self._tcp_socket = tcp_socket
            self._port = port
            self._running = True
            
            # Start a thread to handle client connections
            server_thread = threading.Thread(
                target=self._accept_clients,
                daemon=True,
                name="lsp-server-thread"
            )
            server_thread.start()
            
            logger.info(f"LSP proxy for python listening on port {port}")
            logger.info(f"Proxy server for python ready for connections on port {port}")
            return port
            
        except Exception as e:
            logger.error(f"Failed to set up TCP server: {e}")
            self._stop_process(process)
            if tcp_socket:
                tcp_socket.close()
            return None
    
    def _accept_clients(self):
        """Accept and handle client connections."""
        if not self._tcp_socket or not self._server_process:
            logger.error("Cannot accept clients: server not properly initialized")
            return
            
        try:
            while self._running:
                # Brief timeout to allow checking if we should exit
                self._tcp_socket.settimeout(0.5)
                try:
                    client_socket, client_addr = self._tcp_socket.accept()
                    logger.info(f"Client connected to LSP proxy for python from {client_addr}")
                    
                    # Create a new thread to handle this client connection
                    handler_thread = threading.Thread(
                        target=self._handle_client,
                        args=(client_socket, client_addr),
                        daemon=True,
                        name=f"lsp-client-handler-{client_addr[1]}"
                    )
                    self._client_handlers.append(handler_thread)
                    handler_thread.start()
                    
                except socket.timeout:
                    # Expected when timeout is set, just retry
                    continue
                except Exception as e:
                    if self._running:  # Only log if we're supposed to be running
                        logger.error(f"Error accepting client connection: {e}")
                    time.sleep(0.1)  # Brief pause to avoid CPU spinning
        except Exception as e:
            logger.error(f"Client acceptor thread error: {e}")
        finally:
            logger.info("Client acceptor thread exiting")
    
    def _handle_client(self, client_socket: socket.socket, client_addr: tuple):
        """Handle communication between client and LSP server process."""
        if not self._server_process or self._server_process.poll() is not None:
            logger.error("Cannot handle client: server process not running")
            client_socket.close()
            return
            
        # Use blocking IO for more reliable data transfer
        client_socket.setblocking(True)  
        
        # Get process pipes
        server_in = self._server_process.stdin
        server_out = self._server_process.stdout
        
        # Create threads for bidirectional communication
        def client_to_server():
            try:
                while self._running and self._server_process.poll() is None:
                    try:
                        # Set a timeout to avoid blocking indefinitely
                        client_socket.settimeout(0.5)
                        data = client_socket.recv(4096)
                        
                        if not data:  # Connection closed
                            logger.debug("Client closed connection")
                            break
                            
                        # Log message details for debugging
                        logger.debug(f"Client→Server: {len(data)} bytes")
                        
                        # Forward to server process
                        if server_in and not server_in.closed:
                            server_in.write(data)
                            server_in.flush()
                        else:
                            logger.error("Server stdin closed unexpectedly")
                            break
                    except socket.timeout:
                        # This is expected when no data is available
                        continue
                    except (ConnectionError, BrokenPipeError) as e:
                        logger.error(f"Connection error in client→server: {e}")
                        break
            except Exception as e:
                logger.error(f"Error in client→server thread: {e}")
            finally:
                logger.debug("Client→server thread exiting")
        
        def server_to_client():
            try:
                # Use select to monitor server stdout
                while self._running and self._server_process.poll() is None:
                    if server_out.closed:
                        logger.error("Server stdout closed unexpectedly")
                        break
                        
                    # Use select with timeout to check for available data
                    r, _, _ = select.select([server_out], [], [], 0.5)
                    
                    if server_out in r:
                        try:
                            data = server_out.read1(4096)  # Use read1 for better efficiency
                            
                            if not data:  # EOF
                                logger.debug("Server closed stdout")
                                break
                                
                            # Log message details for debugging
                            logger.debug(f"Server→Client: {len(data)} bytes")
                            
                            # Send to client
                            try:
                                client_socket.sendall(data)
                            except (ConnectionError, BrokenPipeError) as e:
                                logger.error(f"Error sending to client: {e}")
                                break
                        except OSError as e:
                            logger.error(f"Error reading from server: {e}")
                            break
            except Exception as e:
                logger.error(f"Error in server→client thread: {e}")
            finally:
                logger.debug("Server→client thread exiting")
        
        # Start communication threads
        c2s_thread = threading.Thread(target=client_to_server, daemon=True, 
                                    name=f"client-to-server-{client_addr[1]}")
        s2c_thread = threading.Thread(target=server_to_client, daemon=True,
                                    name=f"server-to-client-{client_addr[1]}")
        
        try:
            c2s_thread.start()
            s2c_thread.start()
            
            # Monitor the process and threads
            while self._running and (c2s_thread.is_alive() or s2c_thread.is_alive()):
                # Check if server process is still alive
                if self._server_process.poll() is not None:
                    code = self._server_process.returncode
                    logger.error(f"Language server process exited with code {code}")
                    # Get stderr output if available
                    if self._server_process.stderr:
                        stderr = self._server_process.stderr.read()
                        if stderr:
                            logger.error(f"Server stderr: {stderr.decode('utf-8', errors='replace')}")
                    break
                    
                # Brief pause to avoid CPU spinning
                time.sleep(0.2)
                
        except Exception as e:
            logger.error(f"Error in client handler: {e}")
        finally:
            # Clean up
            try:
                client_socket.close()
            except:
                pass
            logger.info(f"Client handler for {client_addr} exiting")
    
    def _stop_process(self, process: Optional[subprocess.Popen]) -> None:
        """Safely stop a subprocess and clean up resources."""
        if not process:
            return
                
        try:
            # Close file descriptors first to avoid resource warnings
            if process.stdin:
                process.stdin.close()
            if process.stdout:
                process.stdout.close()
            if process.stderr:
                process.stderr.close()
                    
            # Stop the process if it's still running
            if process.poll() is None:
                process.terminate()
                    
                # Give it a moment to terminate gracefully
                for _ in range(5):
                    if process.poll() is not None:
                        break
                    time.sleep(0.1)
                    
                # Force kill if still running
                if process.poll() is None:
                    logger.warning("Process did not terminate gracefully, forcing kill")
                    process.kill()
                    try:
                        process.wait(timeout=1)
                    except subprocess.TimeoutExpired:
                        logger.error("Process failed to terminate even after kill signal")
                    
                logger.info(f"Process stopped (exit code: {process.returncode or 'unknown'})")
                    
        except Exception as e:
            logger.error(f"Error stopping process: {e}")
        
    def get_supported_languages(self) -> List[str]:
        """List all supported language identifiers."""
        return ["python"]  # Only Python is supported
    
    def shutdown(self) -> None:
        """Stop the server and release all resources."""
        logger.info("Shutting down LSP server")
        self._running = False
        
        # Store process reference before setting to None
        process = self._server_process
        self._server_process = None
        
        # Stop the server process after setting reference to None
        # This ensures other threads don't try to use it during shutdown
        if process:
            self._stop_process(process)
        
        # Close TCP socket
        if self._tcp_socket:
            try:
                self._tcp_socket.close()
            except Exception as e:
                logger.debug(f"Error closing TCP socket: {e}")
            self._tcp_socket = None
        
        # Reset state
        self._port = None
        
        logger.info("LSP server shutdown complete")


def create_lsp_server() -> LSPServer:
    """Create and return a new LSP server manager instance."""
    return LSPServer()


if __name__ == "__main__":
    # Set up logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[logging.StreamHandler()],
    )

    # Example of usage
    server = create_lsp_server()
    port = server.setup_local_server("python")
    
    if port:
        print(f"Python LSP server started on port {port}")
        print("Press Ctrl+C to exit")
        try:
            # Keep the main thread alive
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("Shutting down...")
        finally:
            server.shutdown()
    else:
        print("Failed to start Python LSP server")
