"""Clock abstraction for time-related operations."""

import time
import threading
from abc import ABC, abstractmethod
from typing import Optional, Union, NoReturn


class Clock(ABC):
    """Abstract clock interface for getting current time and sleeping."""

    @abstractmethod
    def time(self) -> float:
        """Get the current time in seconds since epoch.

        Returns:
            Current time in seconds since epoch.
        """
        pass

    @abstractmethod
    def sleep(self, duration: float) -> None:
        """Sleep for the specified duration.

        Args:
            duration: Number of seconds to sleep.
        """
        pass


class RealTimeClock(Clock):
    """Implementation of Clock that uses the actual system time."""

    def time(self) -> float:
        """Get the current real system time.

        Returns:
            Current system time in seconds since epoch.
        """
        return time.time()

    def sleep(self, duration: float) -> None:
        """Sleep for the specified real duration.

        Args:
            duration: Number of seconds to sleep.
        """
        time.sleep(duration)


class FakeClock(Clock):
    """Implementation of Clock that simulates the passage of time.
    
    This is primarily useful for testing time-dependent code without
    actually waiting for real time to pass.
    """

    def __init__(self, initial_time: float):
        """Initialize a FakeClock with a specific time.

        Args:
            initial_time: Initial time in seconds since epoch.
        """
        self._current_time = initial_time
        self._sleeping_threads = 0
        self._sleeping_threads_lock = threading.Lock()
        self._sleep_condition = threading.Condition(self._sleeping_threads_lock)

    def time(self) -> float:
        """Get the current fake time.

        Returns:
            Current fake time in seconds since epoch.
        """
        return self._current_time

    def advance(self, duration: float) -> None:
        """Advance the fake clock by the specified duration.

        Args:
            duration: Number of seconds to advance the clock.
        """
        if duration < 0:
            raise ValueError("Cannot advance clock by negative duration")
        self._current_time += duration
    
    
    def await_sleeps(self, num_threads: int = 1, timeout: float = None) -> bool:
        """Wait until exactly the expected number of threads are waiting on sleep.
        
        This is useful for testing concurrent code where you need to ensure
        that a certain number of threads have reached the sleep function
        before proceeding with the test.
        
        Args:
            num_threads: The number of threads to wait for. Defaults to 1.
            timeout: Maximum time to wait in seconds. If None, waits indefinitely.
                     Defaults to None.
        
        Returns:
            True if the expected number of threads are sleeping, False if the timeout was reached.
        """
        if num_threads < 1:
            raise ValueError("Number of threads must be at least 1")
            
        with self._sleep_condition:
            start_time = time.time()
            while self._sleeping_threads != num_threads:
                if timeout is not None:
                    elapsed = time.time() - start_time
                    if elapsed >= timeout:
                        return False
                    remaining = timeout - elapsed
                    if not self._sleep_condition.wait(timeout=remaining):
                        return False
                else:
                    self._sleep_condition.wait()
            return True

    def sleep(self, duration: float) -> None:
        """Simulate sleeping by polling until enough fake time has passed.

        This method gets the current fake time, then enters a loop that
        checks if enough fake time has passed to satisfy the sleep duration.
        For the fake sleep to complete, the advance() method must be called
        by another thread or process.

        Args:
            duration: Number of seconds to sleep.
        """
        if duration < 0:
            raise ValueError("Cannot sleep for negative duration")
        
        with self._sleeping_threads_lock:
            self._sleeping_threads += 1
            self._sleep_condition.notify_all()  # Notify any threads waiting on await_sleeps
        
        try:    
            initial_time = self.time()
            while self.time() - initial_time < duration:
                # Small yield to prevent 100% CPU usage in tests
                time.sleep(0.01)
        finally:
            with self._sleeping_threads_lock:
                self._sleeping_threads -= 1
