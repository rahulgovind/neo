"""
Context module providing a dataclass for storing context information.
"""

from dataclasses import dataclass
from typing import Optional, TYPE_CHECKING

# For type checking only - not imported at runtime
if TYPE_CHECKING:
    from src.core.model import Model
    from src.core.shell import Shell

_env = None

def initialize():
    """
    Initialize the global environment with default values.
    The actual model and shell instances will be set later.
    """
    global _env
    _env = Env(model=None, shell=None)

@dataclass
class Env:
    """
    Global state.
    """
    model: Optional['Model'] = None
    shell: Optional['Shell'] = None

def load_model():
    """Load the model from the environment, raising an error if it's not available."""
    if _env is None:
        raise RuntimeError("Environment not initialized")
    if _env.model is None:
        from src.core.exceptions import FatalError
        raise FatalError("Model not available")
    return _env.model

def load_shell():
    """Load the shell from the environment, raising an error if it's not available."""
    if _env is None:
        raise RuntimeError("Environment not initialized")
    if _env.shell is None:
        from src.core.exceptions import FatalError
        raise FatalError("Shell not available")
    return _env.shell

def set_model(model):
    """Set the model in the environment."""
    global _env
    if _env is None:
        raise RuntimeError("Environment not initialized")
    _env.model = model

def set_shell(shell):
    """Set the shell in the environment."""
    global _env
    if _env is None:
        raise RuntimeError("Environment not initialized")
    _env.shell = shell