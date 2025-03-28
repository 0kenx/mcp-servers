import os
import sys
import json
import subprocess
import tempfile
import time
import signal
from enum import Enum
from typing import Optional, List, Dict, Any, Union, Tuple
import shutil

from mcp.server.fastmcp import FastMCP, Context

# Create MCP server
mcp = FastMCP("command-execution-server")

# Default timeout for commands (in seconds)
DEFAULT_TIMEOUT = 30

# Package managers and their installation commands
PACKAGE_MANAGERS = {
    "apt": {
        "update": ["apt-get", "update"],
        "install": ["apt-get", "install", "-y"],
        "search": ["apt-cache", "search"],
        "list": ["apt", "list", "--installed"],
    },
    "pip": {
        "install": ["pip", "install"],
        "search": ["pip", "search"],
        "list": ["pip", "list"],
    },
    "npm": {
        "install": ["npm", "install", "-g"],
        "search": ["npm", "search"],
        "list": ["npm", "list", "-g", "--depth=0"],
    }
}

# List of pre-installed tools
PREINSTALLED_TOOLS = [
    # Basic utilities
    "bash", "curl", "wget", "vim", "nano", "git", "jq", "zip", "unzip",
    # Python and packages
    "python", "pip", "ipython", "requests", "pandas", "numpy", "matplotlib", "seaborn", 
    "scikit-learn", "jupyterlab", "black", "flake8", "mypy", "pytest",
    # Node.js and npm
    "nodejs", "npm"
]

class OutputType(Enum):
    STDOUT = "stdout"
    STDERR = "stderr"
    BOTH = "both"


def run_command(
    command: List[str], 
    timeout: int = DEFAULT_TIMEOUT, 
    output_type: OutputType = OutputType.BOTH,
    shell: bool = False
) -> Dict[str, Any]:
    """
    Run a shell command with timeout and return the result.
    
    Args:
        command: The command to run
        timeout: Maximum execution time in seconds
        output_type: Which output streams to capture (stdout, stderr, or both)
        shell: Whether to run the command in a shell
        
    Returns:
        Dictionary with stdout, stderr, return code, and execution time
    """
    # For security, if shell=True, ensure command is a string
    if shell and isinstance(command, list):
        command = " ".join(command)
    
    start_time = time.time()
    
    try:
        # Run the command with timeout
        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE if output_type in [OutputType.STDOUT, OutputType.BOTH] else subprocess.DEVNULL,
            stderr=subprocess.PIPE if output_type in [OutputType.STDERR, OutputType.BOTH] else subprocess.DEVNULL,
            text=True,
            shell=shell
        )
        
        stdout, stderr = process.communicate(timeout=timeout)
        
        execution_time = time.time() - start_time
        
        return {
            "stdout": stdout,
            "stderr": stderr,
            "returncode": process.returncode,
            "execution_time": execution_time,
            "timed_out": False
        }
    except subprocess.TimeoutExpired:
        # Kill the process if it times out
        process.kill()
        stdout, stderr = process.communicate()
        
        execution_time = time.time() - start_time
        
        return {
            "stdout": stdout if stdout else "",
            "stderr": stderr if stderr else "Command timed out after {timeout} seconds",
            "returncode": -1,
            "execution_time": execution_time,
            "timed_out": True
        }
    except Exception as e:
        return {
            "stdout": "",
            "stderr": f"Error executing command: {str(e)}",
            "returncode": -1,
            "execution_time": time.time() - start_time,
            "timed_out": False
        }


def format_output(result: Dict[str, Any], output_type: OutputType) -> str:
    """Format the command output based on the requested output type"""
    output = []
    
    # Add execution summary
    output.append(f"Return code: {result['returncode']}")
    output.append(f"Execution time: {result['execution_time']:.2f} seconds")
    
    if result['timed_out']:
        output.append("Status: Command timed out")
    else:
        output.append(f"Status: {'Success' if result['returncode'] == 0 else 'Failed'}")
    
    # Add stdout if requested
    if output_type in [OutputType.STDOUT, OutputType.BOTH] and result["stdout"]:
        output.append("\n=== STDOUT ===")
        output.append(result["stdout"])
    
    # Add stderr if requested
    if output_type in [OutputType.STDERR, OutputType.BOTH] and result["stderr"]:
        output.append("\n=== STDERR ===")
        output.append(result["stderr"])
    
    return "\n".join(output)


def is_tool_installed(name: str) -> bool:
    """Check if a command-line tool is installed"""
    return shutil.which(name) is not None


def detect_package_manager(package: str) -> str:
    """
    Attempt to determine the appropriate package manager for a package
    Returns the package manager name or "unknown"
    """
    # Python package
    if package.startswith("py") or package.endswith("py"):
        return "pip"
    
    # Node.js package
    if package.startswith("node-"):
        return "npm"
    
    # Default to apt for system packages
    return "apt"


def install_package(package: str, package_manager: str = None) -> Dict[str, Any]:
    """
    Install a package using the appropriate package manager
    
    Args:
        package: Name of the package to install
        package_manager: Override the auto-detected package manager
        
    Returns:
        Dictionary with installation result
    """
    if not package_manager:
        package_manager = detect_package_manager(package)
    
    if package_manager not in PACKAGE_MANAGERS:
        return {
            "success": False,
            "message": f"Unsupported package manager: {package_manager}"
        }
    
    # Update repositories if using apt
    if package_manager == "apt":
        update_cmd = PACKAGE_MANAGERS[package_manager]["update"]
        update_result = run_command(update_cmd)
        if update_result["returncode"] != 0:
            return {
                "success": False,
                "message": f"Failed to update package lists: {update_result['stderr']}"
            }
    
    # Install the package
    install_cmd = PACKAGE_MANAGERS[package_manager]["install"] + [package]
    install_result = run_command(install_cmd, timeout=300)  # Allow longer timeout for installations
    
    if install_result["returncode"] == 0:
        return {
            "success": True,
            "message": f"Successfully installed {package} using {package_manager}",
            "output": install_result["stdout"]
        }
    else:
        return {
            "success": False,
            "message": f"Failed to install {package} using {package_manager}",
            "error": install_result["stderr"]
        }


# Define tool implementations
@mcp.tool()
def execute_command(
    command: str,
    timeout: int = DEFAULT_TIMEOUT,
    output_type: str = "both",
    shell: bool = True
) -> str:
    """
    Execute a shell command and return the result.
    
    Args:
        command: The command to execute
        timeout: Maximum execution time in seconds (default: 30)
        output_type: Which outputs to return ("stdout", "stderr", "both")
        shell: Whether to run the command in a shell (default: True)
        
    Returns:
        Formatted output from the command
    """
    # Map output_type string to enum
    output_enum = OutputType(output_type.lower())
    
    # Run the command
    result = run_command(command, timeout, output_enum, shell)
    
    # Format and return the output
    return format_output(result, output_enum)


@mcp.tool()
def execute_script(
    script: str,
    script_type: str = "bash",
    timeout: int = DEFAULT_TIMEOUT,
    output_type: str = "both"
) -> str:
    """
    Execute a script and return the result.
    
    Args:
        script: The script content to execute
        script_type: Type of script (bash, python, js)
        timeout: Maximum execution time in seconds
        output_type: Which outputs to return ("stdout", "stderr", "both")
        
    Returns:
        Formatted output from the script execution
    """
    # Map output_type string to enum
    output_enum = OutputType(output_type.lower())
    
    # Create a temporary file for the script
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=f".{script_type}") as script_file:
        script_file.write(script)
        script_path = script_file.name
    
    try:
        # Set executable permissions
        os.chmod(script_path, 0o755)
        
        # Build command based on script type
        if script_type == "bash" or script_type == "sh":
            command = ["bash", script_path]
        elif script_type == "python" or script_type == "py":
            command = ["python", script_path]
        elif script_type == "js" or script_type == "javascript":
            command = ["node", script_path]
        else:
            os.unlink(script_path)
            return f"Unsupported script type: {script_type}"
        
        # Run the script
        result = run_command(command, timeout, output_enum)
        
        # Format and return the output
        return format_output(result, output_enum)
    finally:
        # Clean up the temporary file
        os.unlink(script_path)


@mcp.tool()
def list_installed_tools() -> str:
    """
    List all the tools and packages installed in the system.
    
    Returns:
        Formatted list of installed tools and packages
    """
    output = ["# Installed Tools and Packages", ""]
    
    # List installed apt packages
    apt_result = run_command(PACKAGE_MANAGERS["apt"]["list"])
    if apt_result["returncode"] == 0:
        packages = apt_result["stdout"].strip().split("\n")
        output.append("## System Packages (apt)")
        for package in packages:
            if package and "installed" in package:
                output.append(f"- {package.split('/')[0]}")
        output.append("")
    
    # List installed pip packages
    pip_result = run_command(PACKAGE_MANAGERS["pip"]["list"])
    if pip_result["returncode"] == 0:
        packages = pip_result["stdout"].strip().split("\n")[2:]  # Skip header rows
        output.append("## Python Packages (pip)")
        for package in packages:
            if package:
                parts = package.split()
                if len(parts) >= 2:
                    output.append(f"- {parts[0]} ({parts[1]})")
        output.append("")
    
    # List installed npm packages
    npm_result = run_command(PACKAGE_MANAGERS["npm"]["list"])
    if npm_result["returncode"] == 0:
        packages = npm_result["stdout"].strip().split("\n")[1:]  # Skip first line
        output.append("## Node.js Packages (npm)")
        for package in packages:
            if package and "├──" in package:
                package_info = package.split("├──")[1].strip()
                if package_info:
                    output.append(f"- {package_info}")
        output.append("")
    
    return "\n".join(output)


@mcp.tool()
def install_tool(tool: str, package_manager: str = None) -> str:
    """
    Install a tool or package.
    
    Args:
        tool: Name of the tool or package to install
        package_manager: Override the auto-detected package manager (apt, pip, npm)
        
    Returns:
        Installation result message
    """
    # Check if the tool is already installed
    if is_tool_installed(tool) or tool in PREINSTALLED_TOOLS:
        return f"{tool} is already installed"
    
    # Install the package
    result = install_package(tool, package_manager)
    
    if result["success"]:
        # Add to preinstalled tools list for future reference
        PREINSTALLED_TOOLS.append(tool)
        return result["message"]
    else:
        error_details = result.get("error", "")
        return f"{result['message']}\n{error_details}"


@mcp.tool()
def install_tools(tools: List[str]) -> str:
    """
    Install multiple tools or packages.
    
    Args:
        tools: List of tool/package names to install
        
    Returns:
        Installation results for each tool
    """
    results = []
    for tool in tools:
        result = install_tool(tool)
        results.append(f"{tool}: {result}")
    
    return "\n".join(results)


@mcp.tool()
def configure_tools(config: Dict[str, List[str]]) -> str:
    """
    Configure and install tools based on a configuration dictionary.
    
    Args:
        config: Dictionary mapping package managers to lists of packages
               Example: {"apt": ["git", "curl"], "pip": ["requests", "numpy"]}
        
    Returns:
        Installation results for each tool
    """
    results = []
    
    for package_manager, packages in config.items():
        if package_manager not in PACKAGE_MANAGERS:
            results.append(f"Unsupported package manager: {package_manager}")
            continue
        
        for package in packages:
            result = install_tool(package, package_manager)
            results.append(f"{package} ({package_manager}): {result}")
    
    return "\n".join(results)


if __name__ == "__main__":
    print("Command Execution MCP Server running", file=sys.stderr)
    mcp.run()
