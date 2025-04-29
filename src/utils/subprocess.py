"""
Subprocess utility functions for executing shell commands.
"""

import subprocess
import logging
from typing import List, Dict, Any, Optional, Tuple

# Configure logging
logger = logging.getLogger(__name__)

def run_shell_command(
    cmd: List[str], 
    cwd: Optional[str] = None,
    check: bool = False,
    capture_output: bool = True,
    text: bool = True,
    env: Optional[Dict[str, str]] = None
) -> subprocess.CompletedProcess:
    """
    Run a shell command and handle logging consistently.
    
    Args:
        cmd: List of command line arguments
        cwd: Current working directory for the command
        check: If True, raise an exception if the command fails
        capture_output: If True, capture stdout and stderr
        text: If True, decode stdout and stderr as text
        env: Environment variables to set for the command
        
    Returns:
        CompletedProcess instance with return code, stdout, and stderr
    """
    cmd_str = ' '.join(cmd)
    logger.debug(f"Executing command: {cmd_str}")
    
    try:
        process = subprocess.run(
            cmd,
            capture_output=capture_output,
            text=text,
            check=check,
            cwd=cwd,
            env=env
        )
        
        logger.debug(f"Command return code: {process.returncode}")
        
        if process.stdout and capture_output:
            log_output = process.stdout[:200] + "..." if len(process.stdout) > 200 else process.stdout
            logger.debug(f"Command stdout: {log_output}")
            
        if process.stderr and capture_output:
            log_error = process.stderr[:200] + "..." if len(process.stderr) > 200 else process.stderr
            logger.debug(f"Command stderr: {log_error}")
            
        return process
    except subprocess.CalledProcessError as e:
        logger.error(f"Command failed with return code {e.returncode}: {e.stderr}")
        raise
    except Exception as e:
        logger.error(f"Error executing command: {str(e)}")
        raise
