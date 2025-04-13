
class Chat:
    """
    Interactive chat interface for communicating with an LLM-powered Agent.

    The Chat class provides:
    - A terminal-based interactive session
    - Rich text rendering of markdown responses
    - Command handling for special user inputs
    - History tracking and persistence
    - Session management (start, stop, graceful termination)
    """

    def _create_session(self, 
        workspace: Optional[str] = None, 
        session_name: Optional[str] = None,
        is_temporary: bool = False
    ) -> None:
        """
        Initialize the session.
        
        Args:
            workspace: Path to the workspace
            session_name: Optional name of the session to use or create
            is_temporary: Whether the session is temporary
        """
        # Process workspace path if provided
        if workspace:
            # Expand user directory (e.g., ~/) and environment variables
            workspace = os.path.expanduser(workspace)
            workspace = os.path.expandvars(workspace)

            # Convert to absolute path if it's not already
            if not os.path.isabs(workspace):
                workspace = os.path.abspath(workspace)

            # Validate workspace directory
            if not os.path.isdir(workspace):
                raise ValueError(f"Workspace directory does not exist: {workspace}")
                
            # Update the instance workspace
            self.workspace = workspace
            
        is_new_session = False
        
        if session_name:
            # If a session name is provided, try to get that session
            ctx = SessionManager.get_session(session_name)
            
            if ctx:
                # Session exists, check if workspace matches
                if ctx.workspace != workspace:
                    raise ValueError(f"Session '{session_name}' exists but has a different workspace. "
                                     f"Existing: {ctx.workspace}, Requested: {workspace}")
            else:
                # Session doesn't exist, create a new one with the specified name
                ctx = SessionManager.create_session(name=session_name, workspace=workspace)
                is_new_session = True
        else:
            if is_temporary:
                # Create a temporary session
                ctx = SessionManager.create_temporary_session(workspace=workspace)
                is_new_session = True
            else:
                # No session name provided, use the last active session or create a new one
                ctx = SessionManager.get_last_active_session()
                
                # If no active session exists or the workspace is different, create a new one
                if ctx is None or ctx.workspace != workspace:
                    ctx = SessionManager.create_session(workspace=workspace)
                    is_new_session = True

        logger.info(f"{'Created new' if is_new_session else 'Using existing'} session: {ctx.session_id}")
        self._ctx = ctx
    
    def _list_sessions(self) -> None:
        """
        List all existing sessions.
        """
        sessions = SessionManager.list_sessions()
        if sessions:
            self._console.print("[green]Existing sessions:[/green]")
            for session in sessions:
                self._console.print(f"  [bold]{session}[/bold]")
        else:
            self._console.print("[yellow]No sessions found[/yellow]")

    def _create_new_session(self, session_name: Optional[str] = None) -> Context:
        """
        Create a new session and update the context.
        
        Args:
            session_name: Optional name for the session
            
        Returns:
            The created Context object
        """
        try:
            # Create a new session
            ctx = SessionManager.create_session(name=session_name, workspace=self.workspace)
            
            # If this is called from the CLI, we want to update the current context
            self.ctx = ctx
            
            # If console is initialized, show success message
            if hasattr(self, '_console') and self._console:
                self._console.print(f"[green]Created new session: {self.ctx.session_name}[/green]")
                self._console.print(f"[dim]Session ID: {self.ctx.session_id}[/dim]")
                
            logger.info(f"Created new session: {ctx.session_name} ({ctx.session_id})")
            return ctx
        except Exception as e:
            if hasattr(self, '_console') and self._console:
                self._console.print(f"[red]Failed to create new session: {str(e)}[/red]")
            logger.error(f"Failed to create new session: {e}", exc_info=True)
            raise

    def _message(self, content: str) -> None:
        """
        Process content in headless mode without interactive UI and print the response.
        
        Args:
            content: The message content to process
        """
        logger.info(f"Processing content in headless mode: {content[:50]}...")
        
        # Process the content through the agent
        try:
            response = self.ctx.agent.process_message(content)
            # Display the response
            self._display_response(response)
        except Exception as e:
            logger.error(f"Error processing content: {e}", exc_info=True)
            self._console.print(f"[red]Error: {str(e)}[/red]")

    @classmethod
    def message(cls, message: str, session_id: str) -> None:
        """
        Process a single message with optional session name.
        
        This is a convenience method for CLI usage that handles session creation and message processing.
        
        Args:
            message: The message content to process
            session_name: Optional session name to use
        """
        logger.info("Processing message in headless mode")
        logger.info(f"Using workspace: {os.getcwd()}")
        
        # Create a chat instance with the specified parameters
        chat = cls(session_name=session_name, session_id=session_id)
        
        # Process the message
        chat._message(message)
        
    @classmethod
    def create_session(cls, workspace: str, session_name: Optional[str] = None) -> Context:
        """
        Create a new session for CLI usage.
        
        This is a convenience method for CLI usage that handles session creation and returns the context.
        
        Args:
            workspace: Workspace path
            session_name: Optional name for the session
            
        Returns:
            The created Context object
        """
        logger.info(f"Creating new session with name: {session_name}")
        
        # Create a chat instance with the specified workspace
        chat = cls(workspace=workspace)
        
        # Create a new session
        return chat.create_session(session_name)
        
    @classmethod
    def launch(cls, workspace: str, history_file: Optional[str] = None, session_name: Optional[str] = None) -> None:
        """
        Launch an interactive chat session for CLI usage.
        
        This is a convenience method for CLI usage that handles creating and launching a chat session.
        
        Args:
            workspace: Path to the code workspace being modified
            history_file: Optional path to file for storing command history
            session_name: Optional name of the session to use or create
        """
        logger.info("Launching interactive chat session")
        
        # Create a chat instance with the specified parameters
        chat = cls(workspace=workspace, history_file=history_file, session_name=session_name)
        
        # Launch the chat session
        chat.start_interactive()