# MCP Servers for Coders

A powerful suite of Model Context Protocol (MCP) servers designed to enable AI assistants like Claude to interact with your local environment, execute code, and process web content.

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

![MCP Servers](https://img.shields.io/badge/MCP-Servers-blue) ![Docker](https://img.shields.io/badge/Docker-Ready-blue) ![Python](https://img.shields.io/badge/Python-3.12+-blue)

## Overview

This repository contains multiple Model Context Protocol (MCP) servers that dramatically extend the capabilities of AI assistants like Claude:

1. **Filesystem MCP Server** - Enables secure file operations with advanced diff tracking and version control
2. **Exec MCP Server** - Provides command execution and multi-language script execution in isolated environments
3. **Web Processing MCP Server** - Allows web content fetching, crawling, and AI-powered content analysis

These servers work independently or together, providing AI assistants with the tools needed to perform complex tasks directly in your local environment without sacrificing security.

## Servers

### 1. Filesystem MCP Server

A secure Python server that enables AI assistants to interact with your local files, with comprehensive features for file management and code analysis:

- **Advanced File Operations**: Read and write files using multiple access methods (whole file, line ranges, keyword-based)
- **Intelligent Code Analysis**: Parse and understand code structure across multiple languages
- **Version Control**: Track all AI-made changes with diff-based editing and selective accept/reject functionality
- **Security-First Design**: Path validation, directory restrictions, and permissions checking
- **Git Integration**: Git-aware directory listings respecting .gitignore rules
- **Editor Integration**: Neovim plugin for seamless workflow

**Key Security Feature**: Operations are strictly limited to explicitly allowed directories with full path validation.

[Read more about the Filesystem MCP Server](filesystem/README.md)

### 2. Exec MCP Server

A powerful execution environment that allows AI assistants to run code and commands within isolated containers:

- **Multi-Language Support**: Execute code in Python, JavaScript, Rust, Go, and Solidity
- **Smart Package Management**: Auto-detect and install required dependencies across package managers
- **Execution Control**: Set timeouts, redirect output streams, and handle long-running processes
- **Complete Development Environments**: Pre-configured setups for multiple programming languages
- **Security Controls**: Configurable execution boundaries and resource limits

**Included Development Environments**:
- **Python 3.12**: Full data science stack (pandas, numpy, matplotlib) and dev tools (black, pytest)
- **JavaScript/TypeScript**: Node.js v20 with npm and yarn
- **Rust**: Complete toolchain with rustup, cargo, and extensions
- **Go 1.22.1**: Standard toolchain and common libraries
- **Solidity**: Foundry suite with forge, cast, and anvil

[Read more about the Exec MCP Server](exec/README.md)

### 3. Web Processing MCP Server

A sophisticated web content retrieval and analysis system that enables AI assistants to gather and process information from the internet:

- **Flexible Content Retrieval**: Fetch single pages or crawl entire websites with configurable parameters
- **Intelligent Crawling**: Control depth, page limits, domain restrictions, and timeouts
- **AI-Powered Analysis**: Process web content using OpenAI models with customizable instructions
- **Multiple Output Formats**: Convert results to Markdown, HTML, Text, JSON, or Raw formats
- **Robust Error Handling**: Gracefully manage timeouts, redirects, and connection issues
- **Content Processing**: Automatic handling of large pages with size limits and truncation

**Key Feature**: Seamlessly combines web scraping with AI analysis for turning raw web content into structured, useful information.

[Read more about the Web Processing MCP Server](web/README.md)

## Getting Started

### Installation

All servers support Docker installation, which is the recommended approach for most users. Each server also has alternative installation methods documented in its individual README.

#### Docker Installation (Recommended)

```bash
# Clone the repository
git clone https://github.com/0kenx/mcp-servers.git
cd mcp-servers

# Build the Filesystem MCP server
cd filesystem
docker build . -t mcp/filesystem

# Build the Exec MCP server
cd ../exec
docker build . -t mcp/exec

# Build the Web MCP server
cd ../web
docker build . -t mcp/web
```

### Configuration with Claude

To configure Claude Desktop or other Claude interfaces to use these MCP servers, add them to your configuration file:

```json
{
  "mcpServers": {
    "filesystem": {
      "command": "docker",
      "args": [
          "run",
          "-i",
          "--rm",
          "--mount",
          "type=bind,src=/home/username/projects,dst=/fs",
          "mcp/filesystem",
          "/fs"
      ]
    },
    "exec": {
      "command": "docker",
      "args": [
          "run",
          "-i",
          "--rm",
          "--mount",
          "type=bind,src=/home/username/projects,dst=/fs",
          "mcp/exec",
          "/fs"
      ]
    },
    "web": {
      "command": "docker",
      "args": [
          "run",
          "-i",
          "--rm",
          "mcp/web",
          "sk-YOUR_OPENAI_API_KEY"
      ]
    }
  }
}
```

### Verifying Installation

After configuration, verify the servers are working properly:

1. Start Claude and enable the MCP servers in the interface
2. Test each server with basic commands:
   - **Filesystem**: Ask Claude to list files in a directory
   - **Exec**: Ask Claude to run a simple command like `echo "Hello, World!"`
   - **Web**: Ask Claude to fetch content from a URL

## Security Considerations

These MCP servers provide powerful capabilities to AI assistants, which requires careful attention to security:

### Filesystem Server
- **Path Validation**: Prevents directory traversal attacks and restricts operations to allowed directories
- **Permission Checking**: Respects existing system file permissions
- **No Shell Execution**: Avoids command injection vulnerabilities
- **Change Tracking**: All modifications are logged and can be reverted

### Exec Server
- **Isolation**: Consider running in a sandboxed environment or container
- **Resource Limits**: Configure container resource limits to prevent abuse
- **Network Restrictions**: Limit network access when executing untrusted code
- **Review Critical Commands**: Exercise caution with system-modifying operations

### Web Server
- **API Key Security**: Protect your OpenAI API key and monitor usage
- **Domain Restrictions**: Use the allowed_domains parameter to prevent unintended crawling
- **Rate Limiting**: Be mindful of rate limits when crawling websites

**General Recommendation**: For sensitive environments, run these servers in isolated containers with minimal permissions and carefully review AI assistant actions.

## Use Cases

These MCP servers enable Claude and other AI assistants to perform powerful tasks:

### Software Development
- Code analysis and refactoring across large codebases
- Implementing features based on specifications
- Debugging issues by running tests and analyzing logs
- Setting up development environments and dependencies

### Data Analysis
- Retrieving, processing, and visualizing data
- Running analysis scripts on local datasets
- Crawling web sources to gather information
- Generating reports from multiple sources

### System Administration
- Executing diagnostic commands and reporting issues
- Installing and configuring software packages
- Managing files and directories safely
- Analyzing logs and system status

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Author

0kenx - [GitHub](https://github.com/0kenx/mcp-servers)
