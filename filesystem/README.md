# Filesystem MCP Server

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE) ![Version](https://img.shields.io/badge/version-0.1.0-green) ![Python](https://img.shields.io/badge/Python-3.12+-blue)

A secure, feature-rich Python server implementing Model Context Protocol (MCP) for filesystem operations. This server enables AI assistants like Claude to interact with your local files in a controlled, secure manner with advanced version tracking and code analysis capabilities.

## Features

### File Operations
- **Multiple Read Methods**: Whole file, specific line ranges, or content matching keywords
- **Smart Write Operations**: Full file writes, targeted diff-based edits with preview support
- **Directory Management**: Create, list, and navigate directory structures
- **File Organization**: Move, search, and manage files efficiently

### Code Intelligence
- **Grammar-Based Parsing**: Understand code structure in Python, JavaScript, C/C++, and TypeScript
- **Function Discovery**: Find and extract functions, classes, and other code elements
- **Contextual Search**: Search for code patterns with surrounding context
- **Multi-File Analysis**: Work across multiple files seamlessly

### Version Control
- **Edit History**: Track all changes with detailed metadata
- **Selective Reverting**: Accept or reject individual edits
- **Diff Visualization**: See changes in a unified diff format
- **Git Integration**: Directory listings respect .gitignore rules

### Security
- **Path Validation**: Prevent directory traversal attacks
- **Restricted Access**: Operations limited to explicitly allowed directories
- **Permission Enforcement**: Respect system file permissions
- **Detailed Metadata**: Access file ownership and permission information

**Note**: The server only allows operations within directories explicitly specified via command-line arguments.

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

- **Docker**: Recommended for containerized deployment (required for Option 1)
- **Python**: Version 3.12 or newer (required for Options 2 and 3)
- **Git**: Optional, enhances directory listing features
- **uv**: Optional, provides faster Python package management (Option 3)

### Option 1: Docker Installation (Recommended)

The Docker installation provides the simplest setup with all dependencies pre-configured in an isolated container:

```bash
# Clone the repository
git clone https://github.com/0kenx/mcp-servers.git
cd mcp-servers/filesystem

# Build the Docker image
docker build -t mcp/filesystem .
```

### Option 2: Local Installation

For users who prefer direct local installation:

```bash
# Clone the repository
git clone https://github.com/0kenx/mcp-servers.git
cd mcp-servers/filesystem

# Install the package in development mode
python -m pip install -e .

# Install the mcpdiff CLI tool for version control features
cd cli
./install.sh
cd ..
```

### Option 3: Using uv (Fastest Python Package Manager)

For users with `uv` installed, this provides the fastest setup experience:

```bash
# Install uv if you don't have it
pip install uv

# From the filesystem directory
uv run src/filesystem.py /path/to/allowed/directory

# Or use the provided convenience script
uv run run_server.py /path/to/allowed/directory
```

You can also install directly using `uvx`:

```bash
uvx git+https://github.com/0kenx/mcp-servers
```

## Usage

### Running the Server

#### Docker Usage (Recommended)

```bash
# Run with a single allowed directory
docker run -p 3005:3005 -v /path/to/directory:/data mcp/filesystem /data

# Run with multiple allowed directories
docker run -p 3005:3005 \
  -v /path/to/projects:/projects \
  -v /path/to/documents:/docs \
  mcp/filesystem /projects /docs
```

This exposes port 3005 for the MCP server and allows operations only in the mounted directories.

#### Local Usage

```bash
# Direct invocation with a single directory
python src/filesystem.py /path/to/directory

# Using the wrapper with multiple directories
python run_server.py ~/Documents ~/Downloads ~/Projects

# Specify a custom port (default: 3005)
python src/filesystem.py --port 3000 /path/to/directory
```

**Important**: The server will ONLY allow file operations within the explicitly specified directories.

### Integrating with Claude

1. **Start the Server**: Run the server using one of the methods above

2. **Configure Claude**:
   - Open the Claude web interface or desktop app
   - Navigate to Settings > Tools > Filesystem
   - Enter `http://localhost:3005` as the server URL (or your custom port)
   - Save the configuration

3. **Test the Connection**:
   - Ask Claude to list files in one of your allowed directories
   - Example: "List the files in /projects/my-repo"

### Version Control with mcpdiff

The `mcpdiff` CLI tool allows you to track, review, and manage changes made by Claude:

```bash
# Show status of all recent edits
mcpdiff status

# Show specific changes from an edit or conversation
mcpdiff show <edit_id or conversation_id>

# Accept changes from a conversation
mcpdiff accept -c <conversation_id>

# Reject specific edits
mcpdiff reject -e <edit_id>

# Interactive review of all pending changes
mcpdiff review
```

See the [mcpdiff guide](cli/mcpdiff-guide.md) and [reference](cli/mcpdiff-reference.md) for detailed usage.

### Editor Integration

#### Neovim Plugin

For Neovim users, the included plugin provides seamless integration with the mcpdiff tool:

```bash
# Create the necessary directories
mkdir -p ~/.config/nvim/lua/mcpdiff

# Copy the plugin files
cp -r nvim/lua/mcpdiff/* ~/.config/nvim/lua/mcpdiff/
cp nvim/plugin/mcpdiff_config.lua ~/.config/nvim/plugin/
```

Once installed, you can use commands like `:McpdiffStatus`, `:McpdiffShow`, and `:McpdiffReview` directly in Neovim. See the [Neovim integration guide](nvim/README.md) for detailed setup and usage.

## Available MCP Tools

The Filesystem MCP Server provides a rich set of tools that Claude can use to interact with your files:

### File Operations

- `read_file(path, ranges=None)` - Read whole files or specific line ranges
- `read_file_by_keyword(path, keyword, include_lines_before=0, include_lines_after=0)` - Find and read sections containing keywords
- `read_multiple_files(paths)` - Read multiple files in a single operation
- `write_file(path, content)` - Create or overwrite files
- `edit_file_diff(path, replacements=None, inserts=None)` - Make targeted changes with diff-based editing
- `move_file(source, destination)` - Move or rename files
- `delete_file(path)` - Delete files

### Directory Operations

- `create_directory(path)` - Create new directories
- `list_directory(path)` - List contents of a directory
- `directory_tree(path, show_size=False)` - Get recursive directory listings
- `search_files(path, pattern)` - Find files matching patterns
- `search_directories(path, pattern)` - Find directories matching patterns

### Code Analysis

- `get_symbols(path)` - Extract code symbols (functions, classes, etc.) from files
- `get_function_code(path, function_name)` - Extract complete function definitions
- `read_function_by_keyword(path, keyword)` - Find functions containing specific keywords

### Metadata & Validation

- `get_file_info(path)` - Get detailed file metadata
- `list_allowed_directories()` - List directories the server is allowed to access
- `changes_since_last_commit()` - Show changes in git repositories

## Security Considerations

The server implements multiple layers of security to provide safe operation:

### Path Safety

- **Path Validation**: Prevents directory traversal attacks using `../` or symbolic links
- **Restricted Operations**: All file operations strictly limited to allowed directories
- **Whitelist Approach**: Only explicitly allowed paths can be accessed

### Operation Safety

- **No Shell Execution**: File operations never execute shell commands
- **Permission Enforcement**: File access controls respect your system permissions
- **Edit History**: All modifications are tracked and can be audited or reverted

### Best Practices

- Mount only the specific directories you need when using Docker
- Review changes with `mcpdiff` before accepting them
- Use read-only mounts for directories that shouldn't be modified
- Monitor server logs for unexpected access attempts

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License - see the LICENSE file for details.
