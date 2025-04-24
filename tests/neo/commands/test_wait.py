"""Tests for the wait command.

This test validates the Wait command functionality:
1. Waiting for specified durations (default and custom)
2. Handling invalid input (negative duration)
3. Testing with FakeClock to control time
"""

import time
import logging
import pytest

from src.neo.session import Session
from src.neo.utils.clock import FakeClock

# Configure logging
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.DEBUG)


@pytest.fixture
def fake_clock():
    """Create a fake clock for testing."""
    return FakeClock(time.time())


@pytest.fixture
def session(fake_clock):
    """Create a session with the fake clock for testing."""
    session = Session.builder().clock(fake_clock).initialize()
    return session


def test_wait_command_default_duration(session, fake_clock):
    """Test that wait command works with default duration (5 seconds)."""
    shell = session.shell
    
    # Execute the wait command asynchronously
    future = shell.execute_async("wait")
    
    # Wait for the thread to start sleeping
    assert fake_clock.await_sleeps(num_threads=1, timeout=1.0), \
        "Timed out waiting for thread to sleep"
    
    # Advance time to complete the wait (5 seconds + buffer)
    fake_clock.advance(5.5)
    
    # Wait for the future to complete
    result = future.result(timeout=1.0)
    
    # Check that the command was successful
    assert result.success, "Command should succeed"
    assert result.content == "Waited for 5 seconds", \
        f"Unexpected output: {result.content}"


def test_wait_command_custom_duration(session, fake_clock):
    """Test that wait command works with a custom duration (3 seconds)."""
    shell = session.shell
    
    # Execute the wait command with a custom duration (3 seconds)
    future = shell.execute_async("wait", "--duration 3")
    
    # Wait for the thread to start sleeping
    assert fake_clock.await_sleeps(num_threads=1, timeout=1.0), \
        "Timed out waiting for thread to sleep"
    
    # Advance time to complete the wait (3 seconds + buffer)
    fake_clock.advance(3.5)
    
    # Wait for the future to complete
    result = future.result(timeout=1.0)
    
    # Check that the command was successful
    assert result.success, "Command should succeed"
    assert result.content == "Waited for 3 seconds", \
        f"Unexpected output: {result.content}"


def test_wait_command_negative_duration(session):
    """Test that wait command fails with a negative duration."""
    shell = session.shell
    
    # Execute the wait command with a negative duration (directly, not async)
    result = shell.execute("wait", "--duration -1")
    
    # Verify the command failed as expected
    assert not result.success, "Command should fail with negative duration"
    
    # Verify the error message contains the expected text
    expected_error = "Duration must be a non-negative number"
    assert expected_error in result.content, \
        f"Expected error message not found in: {result.content}"
