# MCP Exec Server

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE) ![Version](https://img.shields.io/badge/version-0.1.0-green) ![Docker](https://img.shields.io/badge/Docker-Ready-blue)

A powerful MCP server enabling AI assistants to execute commands and run code across multiple programming languages in secure, isolated environments. This server provides a complete development toolkit with pre-configured language environments and intelligent package management.

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
install_tool("tensorflow")
```

### Configure Multiple Tools

```
configure_tools({
    "apt": ["imagemagick", "ffmpeg"],
    "pip": ["pytorch", "transformers"],
    "npm": ["typescript", "webpack"]
})
```

## Installation and Deployment

### Prerequisites

- **Docker**: Required for containerized deployment (recommended)
- **Git**: For cloning the repository

### Docker Installation (Recommended)

```bash
# Clone the repository
git clone https://github.com/0kenx/mcp-servers.git
cd mcp-servers/exec

# Build the Docker image
./build.sh

# Verify all development environments are properly configured
docker run -it --rm mcp/exec /app/verify_envs.sh
```

### Running the Server

```bash
# Basic usage
docker run -p 3006:3006 -it --rm mcp/exec

# With filesystem access to a local directory
docker run -p 3006:3006 -it --rm \
  --mount type=bind,src=/path/to/projects,dst=/workspace \
  mcp/exec

# With resource limits
docker run -p 3006:3006 -it --rm \
  --cpus=2 --memory=2g \
  --network=restricted \
  mcp/exec
```

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
  
- **Network Restrictions**: Limit or disable network access when possible
  ```bash
  docker run --network=none mcp/exec  # No network access
  # OR
  docker run --network=host --add-host=sandbox.internal:127.0.0.1 mcp/exec  # Limited access
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
