# Commands Component

## Overview

The Commands component provides a consistent framework for file system and utility operations. It implements a set of commands that follow a unified interface, allowing Neo to interact with files, perform searches, execute shell operations, and more. Each command follows a consistent CLI-like syntax with parameter handling and structured output.

## Command Framework

All commands extend the abstract `Command` base class and implement:

- `name`: Property that returns the command name
- `description()`: Returns a short description of the command
- `help()`: Returns detailed help with examples and parameter lists
- `validate()`: Validates command parameters before execution
- `execute()`: Performs the actual command operation

Commands return `CommandResult` objects containing success status, content, and optional structured output.

## Available Commands

### File Operations

#### `read_file`

Reads and displays file contents with various formatting options.

```
read_file PATH [--from <from>] [--until <until>] [--limit <limit>]
```

- Supports line range selection with positive and negative indices
- Line number display with toggle option
- Output limiting for large files
- Workspace security boundaries

#### `write_file`

Creates a new file or overwrites an existing file.

```
write_file PATH｜CONTENT
```

- Automatic parent directory creation
- Line addition/deletion statistics
- Support for relative and absolute paths within workspace
- Safe path handling with workspace boundaries

#### `update_file`

Updates files using a structured diff syntax.

```
update_file PATH｜DIFF
```

- Supports @UPDATE and @DELETE operations
- Uses @@BEFORE and @@AFTER sections to define changes
- Sequential application of diff chunks
- Preserves file formatting and structure

### Search Operations

#### `file_text_search`

Searches for text patterns within files.

```
file_text_search PATTERN PATH [--file-pattern <pattern>] [--ignore-case] [--num-context-lines <lines>]
```

- Regex pattern matching
- File type filtering with include/exclude patterns
- Case sensitivity options
- Context line display around matches

#### `file_path_search`

Finds files based on patterns and criteria.

```
file_path_search PATH [--file-pattern <pattern>] [--type <type>] [--content <pattern>]
```

- File pattern filtering with inclusion/exclusion
- File type filtering (files or directories)
- Content-based filtering with regex patterns
- Workspace-aware search paths

### Shell Operations

#### `shell_run`, `shell_view`, `shell_write`, `shell_terminate`

Execute and interact with shell commands in a managed environment.

```
shell_run [name]｜Command to execute
```

- Persistent shell sessions across command invocations
- Standard output and error capture
- Interactive shell sessions with input capability
- Workspace-aware execution environment

### Utility Commands

#### `wait`

Pauses execution for a specified duration.

```
wait [--duration SECONDS]
```

- Uses the session's clock abstraction
- Supports both real and simulated time
- Useful for rate-limiting and demonstration workflows

#### `output`

Formats and validates structured output data.

```
output [--destination <destination>] [--type <type>]｜<data>
```

- Supports multiple output formats (raw, markdown, JSON)
- Schema validation for structured data
- Output destination targeting

## Implementation Details

### Command Parameters

Commands use a consistent parameter handling system:

- Positional parameters for required inputs
- Named flag arguments with both short and long forms
- Typed parameter validation
- Default values and required parameter enforcement

### Command Results

All commands return structured results:

- Success/failure status
- Content as formatted text
- Specialized output types for different operations:
  - `FileUpdate`: For file modification operations
  - `ShellOutput`: For shell command operations
  - `CommandOutput`: Base type for generic operations

### Design Principles

The command system follows these key principles:

- **Workspace Security**: Commands respect workspace boundaries
- **Consistent Interface**: Unified parameter handling and result formatting
- **Rich Documentation**: Self-documenting commands with examples
- **Robust Error Handling**: Detailed error feedback for troubleshooting

## Integration Points

- **Shell**: Commands are registered and executed through the Shell component
- **Agent**: Accesses commands through the shell in the session
- **Message Structure**: Command results are structured into Message objects

## Example: Creating a Custom Command

```python
from dataclasses import dataclass
from typing import Optional
from src.neo.commands.base import Command
from src.neo.core.messages import CommandResult

@dataclass
class MyCommandArgs:
    """Structured arguments for my custom command."""
    parameter: str

class MyCommand(Command):
    @property
    def name(self) -> str:
        return "my_command"
    
    def description(self) -> str:
        return "A custom command example"
    
    def help(self) -> str:
        return "Documentation with usage examples"
    
    def validate(self, session, statement: str, data: Optional[str] = None) -> None:
        # Parse and validate arguments
        self._parse_statement(statement, data)
    
    def execute(self, session, statement: str, data: Optional[str] = None) -> CommandResult:
        args = self._parse_statement(statement, data)
        # Command implementation
        return CommandResult(content="Command executed successfully", success=True)
```

## Future Considerations

- Additional specialized commands for advanced operations
- Enhanced parameter validation and type checking
- Performance optimizations for large file operations
- Integration with version control systems
