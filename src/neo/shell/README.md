# Shell Component

## Overview

The Shell component acts as the command execution layer in Neo, serving as the interface between the Agent and the Commands. It manages command registration, validation, parsing, and execution, providing a consistent way to interact with the file system and perform utility operations.

## Key Components

### Shell (`shell.py`)

The primary class that handles command execution:

- Maintains a registry of available commands
- Processes command calls from the Agent
- Validates command syntax before execution
- Routes commands to their implementations
- Returns structured command results

```python
shell = Shell(workspace="/path/to/workspace")
result = shell.run("read_file example.py")
print(result.content)
```

### CommandParser (`parser.py`)

Handles parsing of command strings into structured arguments:

- Processes command text into command name and arguments
- Handles quotes, special characters, and escaping
- Separates command arguments from piped data
- Supports both positional and named arguments

### CommandResult (`command.py`)

Represents the result of a command execution:

- Contains success/failure status
- Structured content and error messages
- Support for different result types (FileUpdate, ShellOutput, etc.)
- Consistent formatting for display

## Features

### Command Registry

The shell maintains a registry of all available commands:

- Automatic registration of command implementations
- Support for command aliasing
- Command discovery and enumeration
- Permission-based command availability

### Workspace Awareness

All commands execute within a workspace context for security:

- Path validation to prevent traversal attacks
- Workspace boundary enforcement
- Relative path resolution
- Support for both absolute and relative paths

### Command Validation

Commands undergo validation before execution:

- Parameter validation against command definitions
- Type checking for parameter values
- Required parameter enforcement
- Input data validation

### Error Handling

Comprehensive error management for command execution:

- Structured error messages with context
- Exception handling and conversion to user-friendly messages
- Path resolution errors and handling
- Permission and access errors

## Integration Points

- **Agent**: Uses the shell to execute commands
- **Commands**: Registered with the shell for execution
- **Session**: Provides the shell instance to other components
- **Message Structure**: Command results are converted to content blocks

## Usage Example

```python
from src.neo.shell import Shell
from src.neo.core.messages import CommandResult

# Initialize the shell with a workspace
shell = Shell(workspace="/path/to/workspace")

# List available commands
commands = shell.list_commands()
print(f"Available commands: {', '.join(commands)}")

# Execute a command
result = shell.run("file_path_search . --file-pattern '*.py'")
if result.success:
    print("Files found:")
    print(result.content)
else:
    print(f"Error: {result.error}")
    
# Get help for a command
help_text = shell.describe("read_file")
print(help_text)
```

## Command Definition

The shell works with the command framework, which has a consistent structure:

```python
@dataclass
class CommandTemplate:
    """Defines a command's structure and documentation."""
    name: str
    description: str
    parameters: List[CommandParameter]
    accepts_data: bool = False
    
@dataclass
class CommandParameter:
    """Defines parameters for commands."""
    name: str
    description: str
    required: bool = False
    positional: bool = False
    default: Any = None
    hidden: bool = False
```

## Future Considerations

- Pipeline capability for chaining multiple commands
- Advanced permission model for command execution
- Command execution history and audit logging
- Cache management for command results
