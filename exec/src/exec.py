import os
import sys
import json
import subprocess
import tempfile
import time
import signal
import asyncio
import psutil
import shutil
from datetime import datetime
from dataclasses import dataclass
from enum import Enum
from typing import Optional, List, Dict, Any, Union, Tuple, Set


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
    },
    "cargo": {
        "install": ["cargo", "install"],
        "search": ["cargo", "search"],
        "list": ["cargo", "install", "--list"],
    },
}

# List of pre-installed commands
PREINSTALLED_COMMANDS = [
    # Basic utilities
    "bash",
    "curl",
    "wget",
    "nano",
    "git",
    "jq",
    "zip",
    "unzip",
    "rg",
    "cat",
    "sed",
    "uniq",
    "grep",
    # Additional commands
    "less",
    "netstat",
    "ifconfig",
    "ping",
    "nslookup",
    "ip",
    # Security and SSH
    "gpg",
    "ssh",
    "scp",
    "ssh-keygen",
    "ssh-agent",
    # Python and packages
    "python",
    "pip",
    "ipython",
    "requests",
    "pandas",
    "numpy",
    "matplotlib",
    "seaborn",
    "black",
    "flake8",
    "mypy",
    "pytest",
    # Node.js and npm
    "nodejs",
    "npm",
    "yarn",
    "typescript",
    "ts-node",
    # Rust ecosystem
    "rustc",
    "cargo",
    "rustup",
    "rustfmt",
    "clippy",
    "rust-analyzer",
    "cargo-watch",
    "cargo-edit",
    "cargo-generate",
    # Go ecosystem
    "go",
    "gofmt",
    "godoc",
    # Build essentials and development tools
    "gcc",
    "g++",
    "make",
    "cmake",
    "pkg-config",
    "libssl-dev",
]

# List of blacklisted commands
BLACKLISTED_COMMANDS = [c for c in sys.argv[1:]]  # TODO: read from json config


class OutputType(Enum):
    STDOUT = "stdout"
    STDERR = "stderr"
    BOTH = "both"


@dataclass
class Session:
    id: str
    process: asyncio.subprocess.Process
    command: str
    start_time: datetime
    stdout_buffer: str
    stderr_buffer: str
    last_read: datetime


# Global state
active_sessions: Dict[str, Session] = {}
last_session_id: int = 0
blocked_commands: Set[str] = set(BLACKLISTED_COMMANDS)


def is_command_blacklisted(command: str) -> bool:
    """Check if a command is blacklisted"""
    cmd_parts = command.split()
    return any(cmd in blocked_commands for cmd in cmd_parts)


async def create_async_process(
    command: Union[str, List[str]],
) -> asyncio.subprocess.Process:
    """Create an async subprocess"""
    if isinstance(command, list):
        command = " ".join(command)

    return await asyncio.create_subprocess_shell(
        command, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )


def format_output(result: Dict[str, Any], output_type: OutputType) -> str:
    """Format the command output based on the requested output type"""
    output = []

    # Add execution summary
    if result["returncode"] is not None:
        output.append(f"Return code: {result['returncode']}")
        output.append(f"Execution time: {result['execution_time']:.2f} seconds")

    if result["timed_out"]:
        output.append(
            f"Command still running in background. Session ID: {result['session_id']}"
        )
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


def is_command_installed(name: str) -> bool:
    """Check if a terminal command is installed"""
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

    # Rust package (crate)
    if package.startswith("rust-") or package.startswith("cargo-"):
        return "cargo"

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
            "message": f"Unsupported package manager: {package_manager}",
        }

    # Update repositories if using apt
    if package_manager == "apt":
        update_cmd = PACKAGE_MANAGERS[package_manager]["update"]
        update_result = run_command(update_cmd)
        if update_result["returncode"] != 0:
            return {
                "success": False,
                "message": f"Failed to update package lists: {update_result['stderr']}",
            }

    # Install the package
    install_cmd = PACKAGE_MANAGERS[package_manager]["install"] + [package]
    install_result = run_command(
        install_cmd, timeout=300
    )  # Allow longer timeout for installations

    if install_result["returncode"] == 0:
        return {
            "success": True,
            "message": f"Successfully installed {package} using {package_manager}",
            "output": install_result["stdout"],
        }
    else:
        return {
            "success": False,
            "message": f"Failed to install {package} using {package_manager}",
            "error": install_result["stderr"],
        }


# Define tool implementations
@mcp.tool()
async def execute_command(
    command: str, timeout: int = DEFAULT_TIMEOUT, output_type: str = "both"
) -> str:
    """
    Execute a command asynchronously. Returns formatted output from the command if execution completed before timeout. Otherwise, returns a session ID for the running command.

    Args:
        command: The command to execute
        timeout: Maximum execution time in seconds (default: 30)
        output_type: Which outputs to return ("stdout", "stderr", "both")
    """
    # Check for blacklisted commands
    if is_command_blacklisted(command):
        return "Error: This command has been blacklisted"

    # Create unique session ID
    last_session_id += 1
    session_id = str(last_session_id)

    # Start the process
    process = await create_async_process(command)

    # Create session
    session = Session(
        id=session_id,
        process=process,
        command=command,
        start_time=datetime.now(),
        stdout_buffer="",
        stderr_buffer="",
        last_read=datetime.now(),
    )
    active_sessions[session_id] = session

    # Create tasks for reading stdout and stderr
    async def read_stream(stream, buffer: List[str]):
        while True:
            line = await stream.readline()
            if not line:
                break
            buffer.append(line.decode().rstrip("\n"))

    stdout_buffer = []
    stderr_buffer = []
    stdout_task = asyncio.create_task(read_stream(process.stdout, stdout_buffer))
    stderr_task = asyncio.create_task(read_stream(process.stderr, stderr_buffer))

    try:
        # Wait for process to complete or timeout
        await asyncio.wait_for(process.wait(), timeout=timeout)

        # Wait for output readers to complete
        await stdout_task
        await stderr_task

        session.stdout_buffer = "\n".join(stdout_buffer)
        session.stderr_buffer = "\n".join(stderr_buffer)

        return format_output(
            {
                "stdout": session.stdout_buffer,
                "stderr": session.stderr_buffer,
                "returncode": process.returncode,
                "execution_time": (datetime.now() - session.start_time).total_seconds(),
                "timed_out": False,
                "session_id": session_id,
            },
            OutputType(output_type.lower()),
        )
    except asyncio.TimeoutError:
        # Cancel output readers
        stdout_task.cancel()
        stderr_task.cancel()

        # Store current output in session
        session.stdout_buffer = "\n".join(stdout_buffer)
        session.stderr_buffer = "\n".join(stderr_buffer)

        return format_output(
            {
                "stdout": session.stdout_buffer,
                "stderr": session.stderr_buffer,
                "returncode": None,
                "execution_time": timeout,
                "timed_out": True,
                "session_id": session_id,
            },
            OutputType(output_type.lower()),
        )


@mcp.tool()
async def read_output(session_id: str, output_type: str = "both") -> str:
    """
    Read new output from a running session using the session ID returned by execute_command.

    Args:
        session_id: The session ID returned by execute_command
        output_type: Which outputs to return ("stdout", "stderr", "both")
    """
    session = active_sessions.get(session_id)
    if not session:
        return f"Error: Session {session_id} not found"

    # Read any new output
    stdout_data, stderr_data = await session.process.communicate()

    # Update buffers
    if stdout_data:
        session.stdout_buffer += stdout_data.decode()
    if stderr_data:
        session.stderr_buffer += stderr_data.decode()

    session.last_read = datetime.now()

    # Check if process has completed
    returncode = session.process.returncode
    is_running = returncode is None

    # Clean up session if process has completed
    if not is_running:
        del active_sessions[session_id]

    # Format output
    return format_output(
        {
            "stdout": session.stdout_buffer,
            "stderr": session.stderr_buffer,
            "returncode": returncode,
            "execution_time": (datetime.now() - session.start_time).total_seconds(),
            "timed_out": is_running,
            "session_id": session_id,
        },
        OutputType(output_type.lower()),
    )


@mcp.tool()
async def force_terminate(session_id: str) -> str:
    """Force terminate a running session using the session ID returned by execute_command."""
    session = active_sessions.get(session_id)
    if not session:
        return f"Error: Session {session_id} not found"

    session.process.terminate()
    try:
        await asyncio.wait_for(session.process.wait(), timeout=5.0)
    except asyncio.TimeoutError:
        session.process.kill()

    del active_sessions[session_id]
    return f"Session {session_id} terminated"


@mcp.tool()
def list_sessions() -> str:
    """List all active sessions"""
    if not active_sessions:
        return "No active sessions"

    output = []
    for session_id, session in active_sessions.items():
        runtime = (datetime.now() - session.start_time).total_seconds()
        output.append(f"Session {session_id}:")
        output.append(f"  Command: {session.command}")
        output.append(f"  Runtime: {runtime:.1f} seconds")
        output.append(f"  Last read: {session.last_read.strftime('%H:%M:%S')}")

    return "\n".join(output)


@mcp.tool()
def list_processes() -> str:
    """List all running processes"""
    output = ["PID\tCPU%\tMEM%\tCOMMAND"]

    for proc in psutil.process_iter(["pid", "name", "cpu_percent", "memory_percent"]):
        try:
            info = proc.info
            output.append(
                f"{info['pid']}\t{info['cpu_percent']:.1f}\t{info['memory_percent']:.1f}\t{info['name']}"
            )
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    return "\n".join(output)


@mcp.tool()
def kill_process(pid: int) -> str:
    """Kill a process by PID"""
    try:
        process = psutil.Process(pid)
        process.terminate()
        return f"Process {pid} terminated"
    except psutil.NoSuchProcess:
        return f"Error: Process {pid} not found"
    except psutil.AccessDenied:
        return f"Error: Permission denied to terminate process {pid}"


@mcp.tool()
def block_command(command: str) -> str:
    """Add a command to the blacklist"""
    blocked_commands.add(command)
    return f"Command '{command}' has been blocked"


@mcp.tool()
def unblock_command(command: str) -> str:
    """Remove a command from the blacklist"""
    if command in blocked_commands:
        blocked_commands.remove(command)
        return f"Command '{command}' has been unblocked"
    return f"Command '{command}' was not blocked"


@mcp.tool()
def list_blocked_commands() -> str:
    """List all blocked commands"""
    if not blocked_commands:
        return "No commands are currently blocked"
    return "\n".join(sorted(blocked_commands))


@mcp.tool()
async def execute_script(
    script: str,
    script_type: str = "bash",
    timeout: int = DEFAULT_TIMEOUT,
    output_type: str = "both",
) -> str:
    """
    Execute a script asynchronously and return the result.

    Args:
        script: The script content to execute
        script_type: Type of script (bash, python, js, go, rust)
        timeout: Maximum execution time in seconds
        output_type: Which outputs to return ("stdout", "stderr", "both")

    Returns:
        Formatted output from the script execution
    """
    output_enum = OutputType(output_type.lower())

    # Create a temporary file for the script
    with tempfile.NamedTemporaryFile(
        mode="w", delete=False, suffix=f".{script_type}"
    ) as script_file:
        script_file.write(script)
        script_path = script_file.name

    try:
        # Set executable permissions
        os.chmod(script_path, 0o755)

        # Build command based on script type
        if script_type == "bash" or script_type == "sh":
            command = f"bash {script_path}"
        elif script_type == "python" or script_type == "py":
            command = f"python {script_path}"
        elif script_type == "js" or script_type == "javascript":
            command = f"node {script_path}"
        elif script_type == "ts" or script_type == "typescript":
            command = f"ts-node {script_path}"
        elif script_type == "rust" or script_type == "rs":
            # For Rust, we need to compile and then run
            rust_dir = tempfile.mkdtemp()
            src_dir = os.path.join(rust_dir, "src")
            os.makedirs(src_dir)

            # Move the script to the src directory
            rs_file = os.path.join(src_dir, "main.rs")
            shutil.move(script_path, rs_file)

            # Create a simple Cargo.toml
            with open(os.path.join(rust_dir, "Cargo.toml"), "w") as f:
                f.write(
                    """
[package]
name = "temp_script"
version = "0.1.0"
edition = "2021"

[dependencies]
                """.strip()
                )

            # Compile and run
            compile_process = await create_async_process(
                f"cd {rust_dir} && cargo build --release"
            )
            try:
                compile_stdout, compile_stderr = await asyncio.wait_for(
                    compile_process.communicate(), timeout=60
                )
                if compile_process.returncode == 0:
                    command = (
                        f"{os.path.join(rust_dir, 'target', 'release', 'temp_script')}"
                    )
                else:
                    return format_output(
                        {
                            "stdout": compile_stdout.decode() if compile_stdout else "",
                            "stderr": compile_stderr.decode() if compile_stderr else "",
                            "returncode": compile_process.returncode,
                            "execution_time": 60,
                            "timed_out": False,
                        },
                        output_enum,
                    )
            except asyncio.TimeoutError:
                return "Rust compilation timed out"

        elif script_type == "go":
            # For Go, we need to compile and then run
            go_file = script_path
            exe_file = script_path + ".exe"

            # Compile the Go code
            compile_process = await create_async_process(
                f"go build -o {exe_file} {go_file}"
            )
            try:
                compile_stdout, compile_stderr = await asyncio.wait_for(
                    compile_process.communicate(), timeout=60
                )
                if compile_process.returncode == 0:
                    command = exe_file
                else:
                    return format_output(
                        {
                            "stdout": compile_stdout.decode() if compile_stdout else "",
                            "stderr": compile_stderr.decode() if compile_stderr else "",
                            "returncode": compile_process.returncode,
                            "execution_time": 60,
                            "timed_out": False,
                        },
                        output_enum,
                    )
            except asyncio.TimeoutError:
                return "Go compilation timed out"
        else:
            os.unlink(script_path)
            return f"Unsupported script type: {script_type}"

        # Execute the script using execute_command
        return await execute_command(command, timeout, output_type)
    finally:
        # Clean up temporary files
        if os.path.exists(script_path):
            os.unlink(script_path)


@mcp.tool()
def list_installed_commands() -> str:
    """List all the commands installed in the system."""
    return "\n".join(PREINSTALLED_COMMANDS)


@mcp.tool()
def install_command(command: str, package_manager: str = None) -> str:
    """
    Install a command or package.

    Args:
        command: Name of the command or package to install
        package_manager: Override the auto-detected package manager (apt, pip, npm)

    Returns:
        Installation result message
    """
    # Check if the command is already installed
    if is_command_installed(command) or command in PREINSTALLED_COMMANDS:
        return f"{command} is already installed"

    # Install the package
    result = install_package(command, package_manager)

    if result["success"]:
        # Add to preinstalled commands list for future reference
        PREINSTALLED_COMMANDS.append(command)
        return result["message"]
    else:
        error_details = result.get("error", "")
        return f"{result['message']}\n{error_details}"


@mcp.tool()
def configure_packages(config: Dict[str, List[str]]) -> str:
    """
    Configure and install packages based on a configuration dictionary.

    Args:
        config: Dictionary mapping package managers to lists of packages
               Example: {"apt": ["git", "curl"], "pip": ["requests", "numpy"]}

    Returns:
        Installation results for each package
    """
    results = []

    for package_manager, packages in config.items():
        if package_manager not in PACKAGE_MANAGERS:
            results.append(f"Unsupported package manager: {package_manager}")
            continue

        for package in packages:
            result = install_package(package, package_manager)
            results.append(f"{package} ({package_manager}): {result}")

    return "\n".join(results)


if __name__ == "__main__":
    print("Command Execution MCP Server running", file=sys.stderr)
    mcp.run()
