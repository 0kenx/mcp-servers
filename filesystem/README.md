# Filesystem MCP Server

A Python server implementing Model Context Protocol (MCP) for secure filesystem operations, designed to enable AI assistants like Claude to interact with your local files in a controlled, secure manner.

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

## Features

- Read/write files with multiple access methods (whole file, line ranges, keyword-based)
- Create/list directories and file trees
- Move files/directories
- Search files by name and content
- Perform diff-based edits with preview support
- Get detailed file metadata (size, permissions, ownership)
- Git-aware directory tree listing respecting .gitignore
- Function/keyword search in files with contextual results
- Multi-file read operations
- Path validation and security checks

**Note**: The server only allows operations within directories specified via command-line arguments.

## Project Structure

The project follows a standard Python package structure:

```
/filesystem/          # Root package directory
  ├── __init__.py    # Package initialization
  ├── main.py        # Entry point wrapper
  └── src/           # Source code directory
      ├── __init__.py
      ├── filesystem.py    # Main server implementation
      ├── mcp_edit_utils.py # Utility functions
      └── grammar/    # Grammar parsing modules
/integration_tests/  # Integration tests
/cli/                # CLI tools
/nvim/               # Neovim integration
```

## Installation

### Prerequisites

- Docker installed and running
- Python 3.12+ (if installing from source)
- Git (optional, required for git-aware features)

### Option 1: Docker Installation (Recommended)


```bash
docker build -t mcp/filesystem .
```

### Option 2: Local Installation

Clone the repository and install dependencies:

```bash
git clone https://github.com/your-repo/filesystem-mcp.git
cd filesystem-mcp
python -m pip install -e .
```

Install the `mcpdiff` CLI tool:

```bash
cd cli
./install.sh
```

### Option 3: Using uv

If you have `uv` installed, you can run the server directly:

```bash
# From the filesystem directory
uv run src/filesystem.py /path/to/allowed/directory

# Or use the provided convenience script
uv run run_server.py /path/to/allowed/directory
```

You can also install it using `uvx`:

```bash
uvx git+https://github.com/0kenx/mcp-servers
```

## Usage

### Docker Usage

```bash
docker run -p 3005:3005 -v /path/to/directory:/data mcp/filesystem /data
```

This will expose port 3005 for the MCP server and allow operations in the mounted `/data` directory.

### Local Usage

Run the server:

```bash
# Direct invocation
python src/filesystem.py /path/to/directory1 /path/to/directory2

# Using the run_server.py wrapper
python run_server.py /path/to/directory1 /path/to/directory2
```

For example, to allow the server to access your Documents and Downloads directories:

```bash
python src/filesystem.py ~/Documents ~/Downloads
```

**Note**: The server will ONLY allow file operations within the specified directories.

### Setting up Claude with the Filesystem Server

1. In the Claude web interface, enable the "Filesystem" tool
2. Configure it to point to your running server
3. Verify the connection is working

### Using the mcpdiff CLI Tool

The `mcpdiff` CLI tool provides a convenient way to examine changes to files during a conversation:

```bash
# Show changes to a file since the start of the conversation
mcpdiff show <file_path>

# Revert changes to a file
mcpdiff revert <file_path>

# List all files modified in the current conversation
mcpdiff list
```

### Neovim Integration

The project includes Neovim integration for mcpdiff:

```bash
# Copy the plugin files to your Neovim configuration
mkdir -p ~/.config/nvim/lua/mcpdiff
cp nvim/lua/mcpdiff/init.lua ~/.config/nvim/lua/mcpdiff/
cp nvim/plugin/mcpdiff_config.lua ~/.config/nvim/plugin/
```

## Security Considerations

The server includes several security measures:

- Path validation to prevent directory traversal attacks
- Restricted operations to allowed directories only
- No shell command execution
- File access controls respect system permissions

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License - see the LICENSE file for details.
