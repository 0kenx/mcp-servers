# MCP Exec Server

A Managed Command Processor (MCP) for executing shell commands, Python scripts, and JavaScript scripts securely. This MCP provides a flexible way for LLMs to interact with the command line and execute code in various languages.

## Features

- Execute arbitrary terminal commands with optional timeout
- Execute shell, Python, and JavaScript scripts provided by the LLM
- Capture and redirect output streams (stdout, stderr) with pipe options (>1, >2, >3)
- Install tools and packages on demand
- Auto-detect the appropriate package manager for tools
- List all installed tools and packages
- Configure the environment with predefined tool sets
- **NEW**: Multi-language development environments (Rust, Go, Python, JS/TS, Solidity)

## Available Tools

### Command Execution

- `execute_command(command, timeout=30, output_type="both", shell=True)`
  - Execute shell commands with configurable timeout and output capture
  - `command`: The command to execute
  - `timeout`: Maximum execution time in seconds
  - `output_type`: Which outputs to return ("stdout", "stderr", "both")
  - `shell`: Whether to run the command in a shell

- `execute_script(script, script_type="bash", timeout=30, output_type="both")`
  - Execute scripts in various languages
  - `script`: The script content to execute
  - `script_type`: Language of the script (bash, python, js)
  - `timeout`: Maximum execution time in seconds
  - `output_type`: Which outputs to return ("stdout", "stderr", "both")

### Package Management

- `list_installed_tools()`
  - List all tools and packages installed in the system

- `install_tool(tool, package_manager=None)`
  - Install a specific tool, autodetecting the appropriate package manager
  - `tool`: Name of the tool or package to install
  - `package_manager`: Optional override for package manager (apt, pip, npm)

- `install_tools(tools)`
  - Install multiple tools at once
  - `tools`: List of tool names to install

- `configure_tools(config)`
  - Install tools based on a configuration dictionary
  - `config`: Dictionary mapping package managers to package lists
  - Example: `{"apt": ["git", "curl"], "pip": ["requests", "numpy"]}`

## Preinstalled Development Environments

The MCP now comes with the following development environments preinstalled:

### Basic Utilities
- bash, curl, wget, vim, nano, git, jq, zip, unzip

### Python Environment
- python 3.12, pip, ipython, requests, pandas, numpy, matplotlib, seaborn
- Development tools: black, flake8, mypy, pytest

### JavaScript/TypeScript Environment
- Node.js (v20.x), npm, yarn
- TypeScript and ts-node globally installed

### Rust Environment
- rustup, cargo, rustc
- Additional components: rustfmt, clippy, rust-analyzer
- Cargo extensions: cargo-watch, cargo-edit, cargo-generate

### Go Environment
- Go 1.22.1 with standard toolchain

### Solidity Environment
- Foundry suite: forge, cast, anvil

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

## Deployment

Build the Docker container locally:

```bash
# Build the image
./build.sh

# Verify all development environments
docker run -it --rm mcp-exec /app/verify_envs.sh
```

## Security Notice

This MCP allows arbitrary command execution, which can be potentially dangerous. Use with caution and consider the following security recommendations:

- Run the container in an isolated environment
- Consider restricting network access for the container
- Monitor resource usage to prevent abuse
- Consider filesystem restrictions
- Review commands before execution in sensitive environments
