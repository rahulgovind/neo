
# Neo Service Testing

## Overview

This directory contains tests for the Neo Service layer. The Service class provides a high-level API for interacting with the Neo system, including session management, message processing, and workspace configuration.

## Testing Approach

### Test Isolation

Testing the Service class presents unique challenges because:

1. The Neo system uses a global `NEO_HOME` variable that's defined when modules are imported
2. Database connections are established using this `NEO_HOME` path
3. Session IDs are generated based on timestamps, leading to potential conflicts in tests

Two approaches are provided for testing:

1. `test_service.py` - Traditional unit tests with some isolation between test methods
2. `test_single_isolated.py` - A standalone script that provides complete isolation by setting up the environment before any Neo imports

### Key Insights

- NEO_HOME must be set *before* importing any Neo modules
- Each test should use a completely isolated database file
- The timestamps used for session IDs need sufficient granularity to avoid conflicts
- Using real (non-mocked) components improves test fidelity but requires careful setup

## Running Tests

For basic test runs (some tests may fail due to isolation issues):
```
python -m pytest tests/neo/service/test_service.py
```

For fully isolated testing:
```
python tests/neo/service/test_single_isolated.py
```

## Service API Notes

- `Service.list_sessions()` - Returns a list of `SessionInfo` objects (fixed type annotation to match implementation)
- `Service.create_session()` - Creates a new session and returns its info
- `Service.get_session()` - Retrieves session info by ID, returns None if not found
- `Service.update_session()` - Updates a session's workspace, returns updated info or None
- `Service.message()` - Sends a message to a session, returns a generator of `Message` objects


## Improvements

Future improvements to the test suite could include:

1. Updating `src/__init__.py` to respect `NEO_HOME` environment variable even in pytest mode
2. Creating a test fixture that ensures proper isolation between test methods
3. Adding parametrized tests to cover a wider range of inputs
4. Implementing cleanup functions that work reliably even when tests fail
