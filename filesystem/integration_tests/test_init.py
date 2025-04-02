"""
Initialize test environment for the MCP filesystem server integration tests.

This module sets up the test environment by:
1. Mocking the mcp.server.fastmcp module
2. Setting up the SERVER_ALLOWED_DIRECTORIES and WORKING_DIRECTORY globals

It should be imported first in all test modules.
"""

import os
import sys
from pathlib import Path

# Import mock context 
from integration_tests.mock_imports import MockContext

# We need to mock these before importing filesystem.py
import builtins

# Create temp dir for testing
import tempfile
temp_dir = tempfile.mkdtemp(prefix="mcp_fs_test_")

# Set up the globals that filesystem.py will look for
SERVER_ALLOWED_DIRECTORIES = [temp_dir]
WORKING_DIRECTORY = temp_dir

# Add the globals to builtins
builtins.SERVER_ALLOWED_DIRECTORIES = SERVER_ALLOWED_DIRECTORIES
builtins.WORKING_DIRECTORY = WORKING_DIRECTORY

# Mock command line arguments for src/filesystem.py
# This is crucial - it prevents filesystem.py from exiting during import
sys.argv = ['python', temp_dir]

# These variables are already set above
# Don't redefine them here

# Make variables available
__all__ = ['MockContext', 'SERVER_ALLOWED_DIRECTORIES', 'WORKING_DIRECTORY', 'temp_dir']
