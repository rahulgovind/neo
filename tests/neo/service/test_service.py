import unittest
import os
import shutil
from tempfile import mkdtemp
import uuid

from src.neo.core.messages import Message
from src.neo.service.service import Service






class TestService(unittest.TestCase):
    """Test suite for the Service class functionality using real components."""

    def setUp(self):
        """Set up test fixtures before each test method."""
        # Create a unique test ID using method name for complete isolation
        test_method = self._testMethodName  # This is the actual test method being run
        self.test_id = f"{test_method}_{uuid.uuid4().hex[:8]}"
        
        # Create a temporary directory for the test with a unique name
        self.test_dir = mkdtemp(prefix=f"neo_test_{self.test_id}_")
        
        # Set environment variables to ensure we use a completely isolated database
        self.original_neo_home = os.environ.get("NEO_HOME")
        self.test_neo_home = os.path.join(self.test_dir, f".neo_{self.test_id}")
        os.environ["NEO_HOME"] = self.test_neo_home
        os.makedirs(self.test_neo_home, exist_ok=True)
        
        # Create the database from scratch
        self._initialize_test_database()
        
        # Create a test workspace
        self.test_workspace = os.path.join(self.test_dir, "workspace")
        os.makedirs(self.test_workspace, exist_ok=True)
        
        # Keep track of created sessions for cleanup
        self.created_session_ids = []
        
        print(f"Set up test environment: {self.test_neo_home} for {test_method}")
        
    def _initialize_test_database(self):
        """Initialize a clean database for each test."""
        # Import needed for database initialization
        from src.neo.service.database.connection import DatabaseConnection
        
        # Get the database connection to initialize the schema
        db_conn = DatabaseConnection().get_connection()
        cursor = db_conn.cursor()
        
        # Create needed tables if they don't exist
        cursor.executescript('''
            -- Sessions table for storing session metadata
            CREATE TABLE IF NOT EXISTS sessions (
                session_id TEXT PRIMARY KEY,
                session_name TEXT UNIQUE NOT NULL,
                is_temporary INTEGER NOT NULL DEFAULT 0,
                workspace TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            
            -- Settings table for global settings
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
        ''')
        db_conn.commit()


    def tearDown(self):
        """Clean up after each test method."""
        # No need to explicitly delete sessions as they will be removed 
        # when the database file is cleaned up with the temporary directory
        
        # Clear created session IDs list
        self.created_session_ids = []
        
        # Restore original environment variables
        if self.original_neo_home:
            os.environ["NEO_HOME"] = self.original_neo_home
        else:
            os.environ.pop("NEO_HOME", None)
        
        # Remove the temporary directory with ignore_errors to avoid test failures
        # during cleanup
        shutil.rmtree(self.test_dir, ignore_errors=True)
    
    def test_create_and_get_session(self):
        """Test creating a session and then retrieving it."""
        # Create a session with a unique name
        session_name = f"test-session-{uuid.uuid4()}"
        session_info = Service.create_session(session_name, self.test_workspace)
        
        # Record the session ID for assertion
        self.created_session_ids.append(session_info.session_id)
        
        # Verify session was created with the right attributes
        self.assertEqual(session_info.session_name, session_name)
        self.assertEqual(session_info.workspace, self.test_workspace)
        
        # Get the session by ID
        retrieved_session = Service.get_session(session_info.session_id)
        
        # Verify retrieved session matches
        self.assertIsNotNone(retrieved_session)
        self.assertEqual(retrieved_session.session_id, session_info.session_id)
        self.assertEqual(retrieved_session.session_name, session_info.session_name)
    
    def test_create_session_with_generated_name(self):
        """Test creating a session with an auto-generated name."""
        # Create a session with an auto-generated name
        session_info = Service.create_session(workspace=self.test_workspace)
        self.created_session_ids.append(session_info.session_id)
        
        # Verify it has a valid generated name
        self.assertTrue(session_info.session_name.startswith("session-"))
        self.assertEqual(session_info.workspace, self.test_workspace)
        
        # Create another auto-named session and verify it has incremented number
        session_info2 = Service.create_session(workspace=self.test_workspace)
        self.created_session_ids.append(session_info2.session_id)
        
        # Extract numbers from session names
        num1 = int(session_info.session_name.split("-")[1])
        num2 = int(session_info2.session_name.split("-")[1])
        
        # Verify the second session has a higher number
        self.assertTrue(num2 > num1)
    
    def test_create_session_name_conflict(self):
        """Test creating a session with a name that already exists."""
        # Create first session
        session_name = f"conflict-test-{uuid.uuid4()}"
        session_info = Service.create_session(session_name, self.test_workspace)
        self.created_session_ids.append(session_info.session_id)
        
        # Attempt to create another with the same name
        with self.assertRaises(ValueError) as context:
            Service.create_session(session_name, self.test_workspace)
        
        self.assertIn("already exists", str(context.exception))
    
    def test_list_sessions(self):
        """Test listing all sessions."""
        # Create just one session to avoid ID conflicts
        session_name = f"list-test-{uuid.uuid4()}"
        info = Service.create_session(session_name, self.test_workspace)
        self.created_session_ids.append(info.session_id)
        
        # List all sessions
        sessions = Service.list_sessions()
        
        # Verify we have sessions
        self.assertTrue(len(sessions) > 0, "No sessions were returned")
        
        # Despite the type annotation, Service.list_sessions() actually returns a list of SessionInfo
        # Extract session IDs and names from the returned list
        found_ids = [s.session_id for s in sessions]
        found_names = [s.session_name for s in sessions]
        
        # Check that our created session is in the list
        self.assertIn(info.session_id, found_ids, f"Created session ID {info.session_id} not found in returned sessions")
        self.assertIn(info.session_name, found_names, f"Created session name {session_name} not found in returned sessions")
    
    def test_get_last_active_session(self):
        """Test retrieving the last active session."""
        # Create just one session since we're using real components
        session_name = f"active-test-{uuid.uuid4()}"
        info = Service.create_session(session_name, self.test_workspace)
        self.created_session_ids.append(info.session_id)
        
        # Get last active session
        last_session = Service.get_last_active_session()
        
        # Verify we got a session and it matches our newly created one
        self.assertIsNotNone(last_session)
        self.assertEqual(last_session.session_id, info.session_id)
        self.assertEqual(last_session.session_name, info.session_name)
    
    def test_update_session(self):
        """Test updating a session's workspace."""
        try:
            # Create a unique session ID for this test to avoid conflicts
            print("Creating session for update test")
            session_name = f"update-test-{uuid.uuid4()}"
            session_info = Service.create_session(session_name, self.test_workspace)
            session_id = session_info.session_id
            self.created_session_ids.append(session_id)
            print(f"Created session: {session_id}, {session_name}")
            
            # Verify we can get the session
            retrieved = Service.get_session(session_id)
            self.assertIsNotNone(retrieved, "Should be able to get the newly created session")
            print(f"Successfully retrieved session before update: {retrieved}")
            
            # Create a new workspace path
            new_workspace = os.path.join(self.test_dir, "new_workspace")
            os.makedirs(new_workspace, exist_ok=True)
            print(f"Created new workspace directory: {new_workspace}")
            
            # Update the session
            print(f"About to update session {session_id} with new workspace: {new_workspace}")
            updated_session = Service.update_session(session_id, new_workspace)
            print(f"Update result: {updated_session}")
            
            # Verify update was successful
            self.assertIsNotNone(updated_session, "Updated session should not be None")
            self.assertEqual(updated_session.workspace, new_workspace)
            
            # The SessionInfo's workspace should be updated
            self.assertEqual(updated_session.session_id, session_id)
            self.assertEqual(updated_session.session_name, session_name)
        except Exception as e:
            import traceback
            print(f"Error in update_session test: {e}")
            traceback.print_exc()
            raise
    
    def test_update_nonexistent_session(self):
        """Test updating a session that does not exist."""
        # Try to update a session with a made-up ID
        non_existent_id = str(uuid.uuid4())
        updated_session = Service.update_session(non_existent_id, self.test_workspace)
        
        # Verify it returns None
        self.assertIsNone(updated_session)
    
    def test_message_with_existing_session(self):
        """Test sending a message to an existing session."""
        # Create a unique session for this test with proper isolation
        session_name = f"message-test-{uuid.uuid4()}"
        # Using fixed directory to avoid path issues
        test_workspace = os.path.join("/tmp", f"neo_test_workspace_{uuid.uuid4().hex}")
        os.makedirs(test_workspace, exist_ok=True)
        
        # Create the session with our fixed path
        session_info = Service.create_session(session_name, test_workspace)
        session_id = session_info.session_id
        self.created_session_ids.append(session_id)
        
        # Send a test message - using a very simple prompt to minimize tokens
        test_message = "Who are you? (Answer with 'I am Neo, an AI assistant.')"
        
        # Process only the first message to save time/tokens
        response = next(Service.message(test_message, session_id))
        
        # Basic verification
        self.assertIsInstance(response, Message)
        self.assertEqual(response.role, "assistant")
        self.assertTrue(response.content)
        
        # Cleanup the workspace
        try:
            shutil.rmtree(test_workspace)
        except IOError:
            # Silently continue if cleanup fails
            pass
    
    def test_message_with_nonexistent_session(self):
        """Test sending a message to a nonexistent session raises ValueError."""
        # Try to send a message to a nonexistent session
        non_existent_id = str(uuid.uuid4())
        
        # Should raise a ValueError
        with self.assertRaises(ValueError):
            next(Service.message("Test message", non_existent_id))
    
    def test_message_with_temporary_session(self):
        """Test sending a message creates a temporary session when no session_id provided."""
        # Send a message without a session ID
        test_message = "Who are you? (Answer with 'I am Neo, an AI assistant.')"
        
        # Process only the first message to save time/tokens
        response = next(Service.message(test_message))
        
        # Verify we got a response
        self.assertIsInstance(response, Message)
        self.assertEqual(response.role, "assistant")
        self.assertTrue(response.content)

    def test_full_session_lifecycle(self):
        """Test the complete lifecycle of a session."""
        # 1. Create a session with a specific name
        session_name = f"lifecycle-test-{uuid.uuid4()}"
        session_info = Service.create_session(session_name, self.test_workspace)
        session_id = session_info.session_id
        self.created_session_ids.append(session_id)
        
        # Verify session was created with correct attributes
        self.assertIsNotNone(session_info)
        self.assertEqual(session_info.session_name, session_name)
        self.assertEqual(session_info.workspace, self.test_workspace)
        
        # 2. Create a session with auto-generated name
        auto_session = Service.create_session(None, self.test_workspace)
        self.created_session_ids.append(auto_session.session_id)
        self.assertTrue(auto_session.session_name.startswith("session-"))
        
        # 3. Get the session by ID
        retrieved_session = Service.get_session(session_id)
        self.assertIsNotNone(retrieved_session)
        self.assertEqual(retrieved_session.session_id, session_id)
        
        # 4. Try to get a nonexistent session
        nonexistent_id = str(uuid.uuid4())
        self.assertIsNone(Service.get_session(nonexistent_id))
        
        # 5. List sessions and check if our sessions exist
        sessions = Service.list_sessions()
        self.assertIsInstance(sessions, list)
        session_ids = [s.session_id for s in sessions]
        self.assertIn(session_id, session_ids)
        self.assertIn(auto_session.session_id, session_ids)
        
        # 6. Get last active session
        last_active = Service.get_last_active_session()
        self.assertIsNotNone(last_active)
        # The most recently created session should be the last active
        self.assertEqual(last_active.session_id, auto_session.session_id)
        
        # 7. Update the session workspace
        new_workspace = os.path.join(self.test_dir, "new_workspace")
        os.makedirs(new_workspace, exist_ok=True)
        updated_session = Service.update_session(session_id, new_workspace)
        self.assertIsNotNone(updated_session)
        self.assertEqual(updated_session.workspace, new_workspace)
        
        # 8. Send a message to the session
        test_message = "Who are you? (Answer with 'I am Neo, an AI assistant.')"
        response = next(Service.message(test_message, session_id))
        self.assertIsInstance(response, Message)
        self.assertEqual(response.role, "assistant")
        self.assertTrue(response.content)  # Just check that content exists
        
        # 9. Try to send a message to a nonexistent session
        with self.assertRaises(ValueError) as context:
            next(Service.message("Test message", nonexistent_id))
        self.assertIn("Session not found", str(context.exception))
        
        # 10. Send a message with a temporary session
        temp_response = next(Service.message("What is your name?"))
        self.assertIsInstance(temp_response, Message)
        self.assertEqual(temp_response.role, "assistant")
        self.assertTrue(temp_response.content)
        
        # 11. Try to update a nonexistent session
        self.assertIsNone(Service.update_session(nonexistent_id, new_workspace))


if __name__ == "__main__":
    unittest.main()

