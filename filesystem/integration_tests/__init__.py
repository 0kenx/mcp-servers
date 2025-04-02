"""Integration tests for the MCP filesystem server.

This package contains integration tests for the MCP filesystem server.
It includes mock dependencies to avoid requiring the actual mcp module.
"""

# Import our mock module first to ensure dependencies are mocked before any imports
from integration_tests.mock_imports import MockContext

# Cleanup
del MockContext
