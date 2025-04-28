# Neo Project

## Overview

Neo is an AI assistant that helps users with various tasks through both CLI and web interfaces. It's designed to understand requirements, provide information, and engage in thoughtful conversation while offering powerful file and system operations.

## Key Features

- **Multiple Interfaces**: Both CLI and web-based interfaces
- **File Operations**: Reading, writing, and updating files in the workspace
- **Search Capabilities**: Finding files and searching file contents
- **Conversation Management**: Persistent chat history with session support
- **Extensible Architecture**: Modular design for easy feature additions

## Quick Start

### CLI Interface

```bash
python -m src.apps.cli [--workspace PATH]
```

### Web Interface

```bash
python -m src.apps.web.app [--host HOST] [--port PORT] [--debug] [--workspace PATH]
```

Options:
- `--host`: Host to run the server on (default: 127.0.0.1)
- `--port`: Port to run the server on (default: 8888)
- `--debug`: Run in debug mode
- `--workspace`: Path to the workspace directory

## Architecture

Neo follows a modular architecture with clear separation of concerns:

```
┌─────────────────┐     ┌─────────────────┐
│      CLI        │     │      Web        │  Application entry points
└────────┬────────┘     └────────┬────────┘
         │                       │
         └───────────┬───────────┘
                     │
                     ▼
┌─────────────────────────────────┐
│           Service               │  Session management and persistence
└────────────────┬────────────────┘
                 │
                 ▼
┌─────────────────────────────────┐
│            Agent                │  Orchestrates conversation and commands
└────────┬──────────────┬─────────┘
         │              │
         ▼              ▼
┌─────────────┐  ┌─────────────────┐
│   Client    │  │      Shell      │
└──────┬──────┘  └────────┬────────┘
       │                  │
       ▼                  ▼
┌─────────────┐  ┌─────────────────┐
│    LLM      │  │    Commands     │
└─────────────┘  └─────────────────┘
                        │
                        ▼
              ┌─────────────────────┐
              │  Message Structure  │  Content blocks for different data types
              └─────────────────────┘
```

## Component Documentation

Each major component has its own dedicated documentation:

- [Agent](src/neo/agent/README.md): Conversation management and orchestration
- [Client](src/neo/client/README.md): LLM communication and response processing
- [Commands](src/neo/commands/README.md): File and system operations
- [Shell](src/neo/shell/README.md): Command execution and validation
- [Service](src/neo/service/README.md): Session management and persistence
- [Core](src/neo/core/README.md): Message structures and constants
- [Utils](src/neo/utils/README.md): Utility components and helpers
- [Apps](src/apps/README.md): CLI and web interfaces

## Available Commands

Neo provides a consistent command framework for interacting with files, searching, and more:

- `read_file`: Read and display file contents with line selection
- `write_file`: Create or overwrite files with automatic directory creation
- `update_file`: Apply structured diffs to update files
- `file_text_search`: Search file contents with pattern matching
- `file_path_search`: Find files based on patterns and types 
- `shell_run`: Execute shell commands in a managed environment
- `wait`: Sleep for specified duration

## Requirements

- Python 3.8+
- OpenAI API or compatible endpoint
- Flask (for web interface)
- Rich (for CLI interface)
- SQLite (for persistent storage)

## Best Practices

- Make incremental, focused changes rather than complete rewrites
- Explain reasoning and offer context before making changes
- Test changes before submitting when possible
