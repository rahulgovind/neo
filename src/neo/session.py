"""
Session module providing a dataclass for storing session information.
"""

from dataclasses import dataclass
import logging
import os
from typing import Optional, TYPE_CHECKING
from src.neo.exceptions import FatalError
from src import NEO_HOME

# For type checking only - not imported at runtime
if TYPE_CHECKING:
    from src.neo.shell import Shell
    from src.neo.agent import Agent


@dataclass
class Session:
    """
    Session dataclass for storing information needed across components.

    Attributes:
        session_id: Unique identifier for the current session
        session_name: Optional friendly name for the session
        _workspace: Optional path to the code workspace
    """

    session_id: str
    session_name: Optional[str] = None
    _workspace: Optional[str] = None
    _shell: Optional["Shell"] = None
    _agent: Optional["Agent"] = None
    _client: Optional["Client"] = None

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

        return Model(session=self, model_id=model_id)

    @classmethod
    def builder(cls) -> "SessionBuilder":
        """Create a new SessionBuilder instance."""
        return SessionBuilder()

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
        """Get the model from the session, raising an error if it's not available."""
        if self._model is None:
            raise FatalError("Model not available in session")
        return self._model

    @property
    def shell(self) -> "Shell":
        """Get the shell from the session, raising an error if it's not available."""
        if self._shell is None:
            raise FatalError("Shell not available in session")
        return self._shell

    @property
    def internal_session_dir(self) -> str:
        """Get the internal session directory path (<NEO_HOME>/<session_id>)."""
        return os.path.expanduser(f"{NEO_HOME}/{self.session_id}")

    @property
    def agent(self) -> "Agent":
        """Get the agent from the session, raising an error if it's not available."""
        if self._agent is None:
            raise FatalError("Agent not available in session")
        return self._agent

    @property
    def client(self) -> "Client":
        """Get the client from the session, raising an error if it's not available."""
        if self._client is None:
            raise FatalError("Client not available in session")
        return self._client


class SessionBuilder:
    """
    Builder class for constructing Session objects with all dependencies.
    Provides a fluent interface for setting session attributes.
    """

    def __init__(self):
        self._session_id = None
        self._session_name = None
        self._workspace = None
        self._model_name = None
        self._session = None

    def _copy(self) -> "SessionBuilder":
        """Create a copy of this builder with the same settings."""
        new_builder = SessionBuilder()
        new_builder._session_id = self._session_id
        new_builder._session_name = self._session_name
        new_builder._workspace = self._workspace
        new_builder._model_name = self._model_name
        return new_builder

    def session_id(self, session_id: Optional[str]) -> "SessionBuilder":
        """Set the session ID for this session."""
        new_builder = self._copy()
        new_builder._session_id = session_id
        return new_builder

    def session_name(self, session_name: str) -> "SessionBuilder":
        """Set a friendly name for this session."""
        new_builder = self._copy()
        new_builder._session_name = session_name
        return new_builder

    def workspace(self, workspace: str) -> "SessionBuilder":
        """Set the workspace path for the session."""
        new_builder = self._copy()
        new_builder._workspace = workspace
        return new_builder

    def model(self, model_name: str) -> "SessionBuilder":
        """Set the model name to be used."""
        new_builder = self._copy()
        new_builder._model_name = model_name
        return new_builder

    def _generate_default_session_id(self) -> str:
        """Generate a default session ID."""
        import datetime

        now = datetime.datetime.now(datetime.timezone.utc).astimezone()
        return f"session-{now.month:02d}{now.day:02d}-{now.hour:02d}{now.minute:02d}{now.second:02d}"

    def initialize(self) -> Session:
        """
        Initialize the session with the configured settings.

        Returns:
            Initialized Session object
        """
        # Use provided session ID or generate a default one
        session_id = self._session_id or self._generate_default_session_id()
        session_name = self._session_name

        # Create the session object
        session = Session(
            session_id=session_id,
            session_name=session_name,
            _workspace=self._workspace,
        )

        # Initialize the shell
        from src.neo.shell import Shell

        session._shell = Shell(session=session)

        # Initialize the client
        from src.neo.client.client import Client

        session._client = Client(shell=session._shell)

        # Initialize the agent
        from src.neo.agent import Agent

        session._agent = Agent(session=session, ephemeral=False)

        logger = logging.getLogger(__name__)
        logger.info(f"Session {session.session_id} initialized.")

        return session
