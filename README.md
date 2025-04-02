# MCP Servers for Coders

A suite of Model Context Protocol (MCP) servers designed to enable LLMs like Claude to help solve coding challenges.

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

## Overview

This repository contains multiple MCP servers, each with a distinct purpose:

1. **Filesystem MCP Server** - Enables secure file operations
2. **Exec MCP Server** - Provides command execution and script running capabilities
3. **Web Processing Agent MCP Server** - Allows web content fetching, crawling, and AI agent processing

Together, these servers provide a powerful set of tools for LLMs to solve complex coding challenges through direct interaction with your local environment.

## Servers

### 1. Filesystem MCP Server

A Python server for secure filesystem operations, allowing LLMs to:

- Read and write files using multiple access methods
- Create and list directories and file trees
- Move and search for files
- Perform diff-based edits with preview support
- Get detailed file metadata
- Work with git-aware features

**Key Security Feature**: Only allows operations within explicitly allowed directories.

[Read more about the Filesystem MCP Server](filesystem/README.md)

### 2. Exec MCP Server

An MCP server for executing commands and running scripts securely, enabling LLMs to:

- Execute shell commands with configurable timeout
- Run Python, JavaScript, and other scripts provided by the LLM
- Install tools and packages on demand
- Configure the environment with predefined tool sets

**Included Development Environments**:
- Python 3.12 with common data science libraries
- JavaScript/TypeScript with Node.js
- Rust with cargo and extensions
- Go 1.22.1
- Solidity with Foundry

[Read more about the Exec MCP Server](exec/README.md)

### 3. Web Processing MCP Server

A powerful web scraping and analysis server that allows LLMs to:

- Fetch content from any URL with proper error handling
- Crawl websites with configurable depth and page limits
- Process web content using OpenAI models
- Return results in various formats (Markdown, HTML, Text, JSON)

**Key Feature**: Combines web scraping with AI analysis for comprehensive web data processing.

[Read more about the Web Processing MCP Server](web/README.md)

## Getting Started

### Installation

Each server has its own installation instructions. See the individual README files for specific details.

#### Docker Installation (Recommended)

Each server provides Docker build instructions for containerized deployment:

```bash
# Build the Filesystem MCP server
cd filesystem
docker build . -t mcp/filesystem

# Build the Exec MCP server
cd exec
docker build . -t mcp/exec

# Build the Web MCP server
cd web
docker build . -t mcp/web
```

### Usage with Claude

```
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

## Security Considerations

- The Filesystem server limits operations to explicitly allowed directories
- The Exec server enables arbitrary command execution and should be used with caution
- The Web server requires an OpenAI API key for AI processing capabilities

Consider running these servers in isolated environments when working with sensitive systems.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Author

0kenx - [GitHub](https://github.com/0kenx/mcp-servers)
