"""
Context module providing a dataclass for storing context information.
"""

from dataclasses import dataclass
import os
from typing import Optional
from typing import TYPE_CHECKING
from src.core.exceptions import FatalError

# For type checking only - not imported at runtime
if TYPE_CHECKING:
    from src.core.model import Model
    from src.core.shell import Shell
    from src.agent.agent import Agent


@dataclass
class Context:
    """
    Context dataclass for storing information needed across components.

    Attributes:
        session_id: Unique identifier for the current session
        session_name: Optional friendly name for the session
        _workspace: Optional path to the code workspace
    """

    session_id: str
    session_name: Optional[str] = None
    _workspace: Optional[str] = None
    _model: Optional["Model"] = None
    _shell: Optional["Shell"] = None
    _agent: Optional["Agent"] = None

    def select_model(self, size: str = "LG") -> "Model":
        """
        Create a model instance based on size parameter.
        Args:
            size: Either "SM" or "LG". Defaults to "LG"
        Returns:
            A new Model instance with the specified size
        """
        from src.core.model import Model

        if size not in ["SM", "LG"]:
            raise ValueError("Size must be either 'SM' or 'LG'")

        model_id = os.environ.get("MODEL_ID")  # Default/LG model
        if size == "SM":
            model_id = os.environ.get(
                "SM_MODEL_ID", model_id
            )  # Fallback to default if SM not specified

        return Model(ctx=self, model_id=model_id)

    @classmethod
    def builder(cls) -> "ContextBuilder":
        """Create a new ContextBuilder instance."""
        return ContextBuilder()

    @property
    def workspace(self) -> str:
        """Get the workspace path, defaulting to current directory if not set."""
        if self._workspace is None:
            return os.getcwd()
        return self._workspace

    @workspace.setter
    def workspace(self, value: Optional[str]):
        """Set the workspace path."""
        self._workspace = value

    @property
    def model(self) -> "Model":
        """Get the model from the context, raising an error if it's not available."""
        if self._model is None:
            raise FatalError("Model not available in context")
        return self._model

    @property
    def shell(self) -> "Shell":
        """Get the shell from the context, raising an error if it's not available."""
        if self._shell is None:
            raise FatalError("Shell not available in context")
        return self._shell

    @property
    def internal_session_dir(self) -> str:
        """Get the internal session directory path (~/.neo/<session_id>)."""
        return os.path.expanduser(f"~/.neo/{self.session_id}")

    @property
    def agent(self) -> "Agent":
        """Get the agent from the context, raising an error if it's not available."""
        if self._agent is None:
            raise FatalError("Agent not available in context")
        return self._agent


class ContextBuilder:
    """
    Builder class for constructing Context objects with all dependencies.
    Provides a fluent interface for setting context attributes.
    """

    def __init__(self):
        self._session_id = None
        self._session_name = None
        self._workspace = None
        self._model_name = None
        self._context = None

    def _copy(self) -> "ContextBuilder":
        """Create a copy of this builder with the same settings."""
        new_builder = ContextBuilder()
        new_builder._session_id = self._session_id
        new_builder._session_name = self._session_name
        new_builder._workspace = self._workspace
        new_builder._model_name = self._model_name
        return new_builder

    def session_id(self, session_id: Optional[str]) -> "ContextBuilder":
        """Set the session ID for this context."""
        new_builder = self._copy()
        new_builder._session_id = session_id
        return new_builder

    def session_name(self, session_name: str) -> "ContextBuilder":
        """Set a friendly name for this session."""
        new_builder = self._copy()
        new_builder._session_name = session_name
        return new_builder

    def workspace(self, workspace: str) -> "ContextBuilder":
        """Set the workspace path for the context."""
        new_builder = self._copy()
        new_builder._workspace = workspace
        return new_builder

    def model(self, model_name: str) -> "ContextBuilder":
        """Set the model name to be used."""
        new_builder = self._copy()
        new_builder._model_name = model_name
        return new_builder
        
    def _generate_default_session_id(self) -> str:
        """Generate a default session ID."""
        import datetime
        now = datetime.datetime.now(datetime.timezone.utc).astimezone()
        return f"session-{now.month:02d}{now.day:02d}-{now.hour:02d}{now.minute:02d}{now.second:02d}"

    def initialize(self) -> Context:
        """
        Initialize the context with the configured settings.
        
        Returns:
            Initialized Context object
        """
        # Use provided session ID or generate a default one
        session_id = self._session_id or self._generate_default_session_id()
        session_name = self._session_name
        
        # Create the context object
        ctx = Context(
            session_id=session_id,
            session_name=session_name,
            _workspace=self._workspace,
        )

        # Initialize the shell
        from src.core.shell import Shell
        ctx._shell = Shell(ctx=ctx)

        # Initialize the model
        from src.core.model import Model
        ctx._model = Model(ctx=ctx, model_id=self._model_name)

        # Initialize the agent
        from src.agent.agent import Agent
        ctx._agent = Agent(ctx=ctx)

        return ctx
