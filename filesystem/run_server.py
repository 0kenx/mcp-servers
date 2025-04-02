#!/usr/bin/env python3
"""
Compatibility script to run the MCP Filesystem Server.

This script ensures that the server can be run with `uv run src/filesystem.py`
while also allowing for installation as a package.
"""

import os
import sys
from pathlib import Path

if __name__ == "__main__":
    # Get the directory containing this script
    script_dir = Path(__file__).parent.absolute()

    # Add the script directory to the Python path
    sys.path.insert(0, str(script_dir))

    # Arguments are expected to be directories to allow access to
    args = sys.argv[1:]
    if not args:
        print(
            "Usage: python run_server.py <allowed-directory> [additional-directories...]"
        )
        sys.exit(1)

    # Run the filesystem server module
    server_path = os.path.join(script_dir, "src", "filesystem.py")
    os.execv(sys.executable, [sys.executable, server_path] + args)
