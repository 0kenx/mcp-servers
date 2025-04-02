"""
Configuration for integration tests.

This file sets up the pytest environment for testing.
"""

# Import test initialization to set up mocks
from integration_tests.test_init import MockContext

# Define globally available SERVER_ALLOWED_DIRECTORIES and WORKING_DIRECTORY
# for integration tests. These are used by the filesystem.py module.
SERVER_ALLOWED_DIRECTORIES = []
WORKING_DIRECTORY = None

# Make them available in the global namespace
import builtins
builtins.SERVER_ALLOWED_DIRECTORIES = SERVER_ALLOWED_DIRECTORIES
builtins.WORKING_DIRECTORY = WORKING_DIRECTORY
# Import mcp_edit_utils directly
try:
    import mcp_edit_utils
except ImportError:
    # If mcp_edit_utils is not available, provide path hints
    import sys
    import os
    parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    print(f"Adding {parent_dir} to Python path for mcp_edit_utils")
    sys.path.insert(0, parent_dir)

# Export these as pytest fixtures if needed
import pytest

@pytest.fixture
def mock_context():
    """Return a mock context for testing."""
    return MockContext()

@pytest.fixture
def allowed_dirs():
    """Return the allowed directories list for modification in tests."""
    return SERVER_ALLOWED_DIRECTORIES

@pytest.fixture
def working_dir():
    """Return the working directory for modification in tests."""
    return WORKING_DIRECTORY
