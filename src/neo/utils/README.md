# Utils Component

## Overview

The Utils component provides common utility functions and abstractions used throughout Neo. These utilities handle time-related operations, path management, testing helpers, and other shared functionality. They help maintain consistent patterns and reduce code duplication across the application.

## Key Components

### Clock (`clock.py`)

Provides time-related operations and abstractions:

- **Clock Interface**: Abstract base class for time operations
  - `time()`: Get current time in seconds since epoch
  - `sleep(duration)`: Sleep for specified duration

- **RealTimeClock**: Wraps Python's time module for production use
  - Direct wrapper around system time functions
  - Used in normal application operation

- **FakeClock**: Simulates time passage for deterministic testing
  - `advance(duration)`: Manually advance clock without waiting
  - `await_sleeps(num_threads, timeout)`: Coordinate testing of concurrent code
  - Thread synchronization with condition variables
  - Support for deterministic testing of time-dependent operations

```python
# Using the real clock
from src.neo.utils.clock import RealTimeClock

clock = RealTimeClock()
current_time = clock.time()
clock.sleep(1.0)  # Sleep for 1 second

# Using the fake clock for testing
from src.neo.utils.clock import FakeClock

fake_clock = FakeClock()
start_time = fake_clock.time()  # Initial time
fake_clock.advance(10)  # Advance by 10 seconds without waiting
elapsed = fake_clock.time() - start_time  # Will be 10.0
```

### Path Utilities (`paths.py`)

Functions for handling file paths securely:

- Workspace-aware path resolution
- Path normalization and validation
- Security checks for path traversal attacks
- Directory creation and checking

### String Utilities (`strings.py`)

Helper functions for string manipulation:

- Text formatting and normalization
- Special character handling
- String truncation with ellipsis
- Multi-line text processing

### Testing Helpers (`testing.py`)

Utilities to simplify writing tests:

- Test fixtures and factories
- Mock objects for dependencies
- Assertion helpers
- Test data generators

## Features

### Time Abstraction

The Clock abstraction enables several key capabilities:

- Consistent time handling across the application
- Deterministic testing without actual waiting
- Thread synchronization for concurrent testing
- Simple interface switching between real and fake implementations

### Path Safety

Path utilities ensure secure file operations:

- Prevention of directory traversal attacks
- Consistent workspace boundaries
- Proper handling of relative and absolute paths
- Cross-platform path normalization

### Testing Support

Testing utilities make it easier to write robust tests:

- Predictable time management
- Reduced test flakiness
- Easier assertion of time-dependent behavior
- Support for concurrent testing scenarios

## Integration Points

- **Commands**: Use path utilities for file operations
- **Shell**: Uses path resolution for command execution
- **Agent**: Uses the clock for timing operations
- **Testing**: Test suites use fake clock for deterministic tests

## Usage Example

```python
from src.neo.utils.clock import FakeClock
import threading

# Create a fake clock for testing
clock = FakeClock()

# Function that uses the clock
def delayed_operation(clock, delay):
    print(f"Starting operation at {clock.time()}")
    clock.sleep(delay)  # This won't actually sleep when using FakeClock
    print(f"Finished operation at {clock.time()}")
    return "Done"

# Start multiple threads that will sleep
threads = []
for i in range(3):
    thread = threading.Thread(
        target=delayed_operation, 
        args=(clock, 5.0)
    )
    thread.start()
    threads.append(thread)

# Wait for all threads to reach their sleep point
# This will block until all threads call clock.sleep()
clock.await_sleeps(3, timeout=1.0)

# Advance the clock to wake all threads simultaneously
print(f"Advancing clock at {clock.time()}")
clock.advance(5.0)

# Wait for threads to complete
for thread in threads:
    thread.join()

print(f"All operations complete at {clock.time()}")
```

## Future Considerations

- Additional time utilities for scheduling and recurring operations
- Enhanced path manipulation for complex file operations
- Data validation and sanitization helpers
- Performance profiling utilities
