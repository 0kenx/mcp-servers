# MCP Exec Server

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE) ![Version](https://img.shields.io/badge/version-0.1.0-green) ![Python](https://img.shields.io/badge/Python-3.12+-blue) ![Docker](https://img.shields.io/badge/Docker-Ready-blue)

A powerful MCP server enabling AI assistants like Claude to execute commands and run code across multiple programming languages in secure, isolated environments. This server provides a complete development toolkit with pre-configured language environments, intelligent package management, and comprehensive process control.

## Table of Contents
- [Overview](#overview)
- [Features](#features)
- [Requirements](#requirements)
- [Installation](#installation)
- [MCP Tools](#mcp-tools)
- [Usage Examples](#usage-examples)
- [When to Use Each Tool](#when-to-use-each-tool)
- [Security](#security)
- [Contributing](#contributing)
- [License](#license)

## Overview

The MCP Exec Server serves as a powerful bridge between AI assistants and command-line environments. It enables capabilities ranging from simple command execution to running complex scripts in multiple programming languages. By providing a secure, containerized environment with pre-installed development tools, this server allows AI assistants to help with coding, data analysis, and system management tasks. It's designed to be easily integrated with Claude and other AI assistants through the Model Context Protocol (MCP).

## Features

### Command Execution

- **Flexible Command Execution**: Run shell commands with configurable timeouts
- **Multi-Language Support**: Execute scripts in Python, JavaScript, Rust, Go, and Solidity
- **Output Control**: Capture and redirect output streams (stdout, stderr)
- **Process Management**: Asynchronous execution with monitoring capabilities

### Package Management

- **Smart Dependency Installation**: Auto-detect appropriate package managers (apt, pip, npm, cargo)
- **Bulk Configuration**: Set up multiple tools across different package managers simultaneously
- **Environment Discovery**: List installed tools and available commands
- **Cross-Language Integration**: Seamlessly mix dependencies from different ecosystems

### Development Environments

- **Pre-configured Stacks**: Ready-to-use environments for multiple programming languages
- **Full Tool Suites**: Complete development toolchains including compilers, linters, and utilities
- **Data Science Tools**: Python environment with analytical and visualization libraries
- **Web Development**: Complete JavaScript/TypeScript environment with Node.js


## Available Tools

### Command Execution

| Tool | Description | Parameters |
|------|-------------|------------|
| `execute_command` | Run shell commands with timeout and output capture | • `command`: Command to execute<br>• `timeout`: Maximum time in seconds (default: 30)<br>• `output_type`: Output streams to return ("stdout", "stderr", "both")<br>• `shell`: Whether to use shell (default: True) |
| `execute_script` | Run code in various languages | • `script`: Code content to execute<br>• `script_type`: Language ("bash", "python", "js", "rust", "go")<br>• `timeout`: Maximum time in seconds (default: 30)<br>• `output_type`: Output streams to return |
| `read_output` | Read output from a running process | • `session_id`: ID returned by execute_command<br>• `output_type`: Output streams to read |
| `force_terminate` | Kill a running process | • `session_id`: ID returned by execute_command |
| `list_sessions` | Show all active command sessions | *None* |
| `list_processes` | Show all running processes | *None* |
| `kill_process` | Terminate a process by PID | • `pid`: Process ID to kill |

### Package Management

| Tool | Description | Parameters |
|------|-------------|------------|
| `list_installed_commands` | List all available tools and commands | *None* |
| `install_command` | Install a specific package | • `command`: Package name to install<br>• `package_manager`: Optional override (apt, pip, npm, etc.) |
| `configure_packages` | Install multiple packages across package managers | • `config`: Dictionary mapping managers to package lists<br>Example: `{"apt": ["git", "curl"], "pip": ["requests"]}` |
| `block_command` | Block specific commands from execution | • `command`: Command to block |
| `unblock_command` | Allow previously blocked commands | • `command`: Command to unblock |
| `list_blocked_commands` | Show all blocked commands | *None* |

## Requirements

### Software Requirements
- **Python**: Version 3.12 or newer
- **Docker**: For containerized deployment (recommended)

### Python Dependencies
- **System Interaction**: psutil, subprocess
- **API Framework**: fastapi, uvicorn
- **MCP Protocol**: mcp[cli]

## Installation

### Option 1: Local Installation

```bash
# Clone the repository
git clone https://github.com/0kenx/mcp-servers.git
cd mcp-servers/exec

# Build the Docker image
docker build -t mcp/exec .
```

### Configuration with Claude

Add the MCP Exec Server to your Claude configuration file:

```json
{
  "mcpServers": {
    "exec": {
      "command": "docker",
      "args": [
        "run",
        "-p",
        "3006:3006",
        "-i",
        "--rm",
        "mcp/exec"
      ]
    }
  }
}
```

### How It Works

The MCP Exec Server acts as a bridge between Claude (or other AI assistants) and a command-line environment. When Claude invokes one of the MCP tools:

1. The server receives the request with parameters (like commands, scripts, or package installations)
2. It executes the requested operation in a secure, containerized environment
3. For asynchronous operations, it manages the process lifecycle and captures outputs
4. The results are returned to Claude, which can then incorporate them into its response

## MCP Tools

The following tools are exposed via Model Context Protocol (MCP) for AI assistants to use:

### Command Execution

| Tool | Description | Parameters |
|------|-------------|------------|
| `execute_command` | Run shell commands with timeout and output capture | • `command`: Command to execute<br>• `timeout`: Maximum time in seconds (default: 30)<br>• `output_type`: Output streams to return ("stdout", "stderr", "both") |
| `execute_script` | Run code in various languages | • `script`: Code content to execute<br>• `script_type`: Language ("bash", "python", "js", "rust", "go")<br>• `timeout`: Maximum time in seconds (default: 30)<br>• `output_type`: Output streams to return |
| `read_output` | Read output from a running process | • `session_id`: ID returned by execute_command<br>• `output_type`: Output streams to read |
| `force_terminate` | Kill a running process | • `session_id`: ID returned by execute_command |
| `list_sessions` | Show all active command sessions | *None* |
| `list_processes` | Show all running processes | *None* |
| `kill_process` | Terminate a process by PID | • `pid`: Process ID to kill |

### Package Management

| Tool | Description | Parameters |
|------|-------------|------------|
| `list_installed_commands` | List all available tools and commands | *None* |
| `install_command` | Install a specific package | • `command`: Package name to install<br>• `package_manager`: Optional override (apt, pip, npm, etc.) |
| `configure_packages` | Install multiple packages across package managers | • `config`: Dictionary mapping managers to package lists<br>Example: `{"apt": ["git", "curl"], "pip": ["requests"]}` |
| `block_command` | Block specific commands from execution | • `command`: Command to block |
| `unblock_command` | Allow previously blocked commands | • `command`: Command to unblock |
| `list_blocked_commands` | Show all blocked commands | *None* |

## Preinstalled Development Environments

The MCP Exec server provides ready-to-use development environments for multiple programming languages and paradigms:

| Environment | Components | Features |
|-------------|------------|----------|
| **System Utilities** | bash, curl, wget, vim, nano, git, jq, zip, unzip | Core system tools for file management and data processing |
| **Python 3.12** | pip, ipython, venv<br>pandas, numpy, matplotlib, seaborn<br>black, flake8, mypy, pytest | Complete data science stack with visualization libraries and development tools |
| **JavaScript/TypeScript** | Node.js v20, npm, yarn<br>TypeScript, ts-node | Modern JavaScript environment with TypeScript support and package managers |
| **Rust** | rustup, cargo, rustc<br>rustfmt, clippy, rust-analyzer<br>cargo-watch, cargo-edit, cargo-generate | Full Rust development environment with code formatting, linting tools, and useful extensions |
| **Go 1.22.1** | Standard Go toolchain | Core Go compiler and development tools |
| **Solidity** | Foundry suite: forge, cast, anvil | Complete Ethereum smart contract development environment |

## Usage Examples

### Execute a Command

```
execute_command("ls -la", timeout=5, output_type="both")
```

### Run a Python Script

```
execute_script("""
import numpy as np
import matplotlib.pyplot as plt

# Generate some data
x = np.linspace(0, 10, 100)
y = np.sin(x)

# Print the data
print(f"Max value: {y.max()}")
print(f"Min value: {y.min()}")
""", script_type="python", timeout=10)
```

### Compile and Run a Rust Program

```
execute_script("""
fn main() {
    println!("Hello from Rust!");
    
    // Simple fibonacci calculation
    let n = 10;
    let mut a = 0;
    let mut b = 1;
    
    for _ in 0..n {
        let temp = a;
        a = b;
        b = temp + b;
    }
    
    println!("Fibonacci number {} is {}", n, a);
}
""", script_type="rust", timeout=10)
```

### Install a New Tool

```
install_command("tensorflow")
```

### Configure Multiple Tools

```
configure_packages({
    "apt": ["imagemagick", "ffmpeg"],
    "pip": ["pytorch", "transformers"],
    "npm": ["typescript", "webpack"]
})
```

## When to Use Each Tool

The MCP Exec Server provides several tools for different execution scenarios:

- **`execute_command`**: Use when you need to run simple shell commands or Linux utilities. Ideal for file operations, system information retrieval, and basic command-line operations.

- **`execute_script`**: Best for running multi-line code in specific programming languages. Particularly useful for complex operations, algorithms, or when you need language-specific functionality.

- **`read_output`** and **`force_terminate`**: Use with long-running operations to monitor output and control execution when needed.

- **`list_processes`** and **`kill_process`**: Helpful for managing system resources and terminating runaway processes.

- **`install_command`**: Use when you need a package that isn't pre-installed in the environment. Check available commands first with `list_installed_commands`.

- **`configure_packages`**: Ideal for setting up complex environments that require multiple packages across different package managers.

- **`block_command`** and **`unblock_command`**: Use these for security control when you want to prevent certain commands from being executed.

## Security Considerations

### Potential Risks

The Exec MCP Server allows arbitrary command execution, which inherently carries security risks:

- **Code Execution**: AI assistants can run arbitrary code in multiple languages
- **System Modification**: Commands could potentially modify the container environment
- **Resource Consumption**: Intensive operations could consume excessive resources
- **Network Access**: By default, the container has network connectivity

### Security Measures

#### Built-in Protections

- **Command Blocking**: Block dangerous commands via the `block_command` tool
- **Timeouts**: All executions have configurable timeouts to prevent infinite loops
- **Process Management**: Monitor and terminate long-running processes
- **Containerization**: All execution happens within an isolated Docker container

#### Recommended Configuration

- **Resource Limits**: Restrict CPU, memory, and disk usage using Docker's resource controls
  ```bash
  docker run --cpus=2 --memory=2g --storage-opt size=10G mcp/exec
  ```

- **Read-Only Filesystem**: Mount sensitive directories as read-only
  ```bash
  docker run --mount type=bind,src=/data,dst=/data,readonly mcp/exec
  ```
  
- **Capabilities Reduction**: Remove unnecessary Linux capabilities
  ```bash
  docker run --cap-drop=ALL --cap-add=NET_BIND_SERVICE mcp/exec
  ```

#### Operational Security

- Review execution logs regularly for suspicious activity
- Use Docker security scanning tools to verify container security
- Update the image regularly to incorporate security patches
- Consider implementing API authentication for the MCP server

## Contributing

Contributions are welcome! If you'd like to improve this project, please feel free to submit pull requests or open issues on the repository.

## License

This project is licensed under the MIT License - see the LICENSE file for details.
