"""
Mock implementation of MCP dependencies for testing.

This mocks only the external dependencies needed (mcp.server.fastmcp),
not any of the core modules in the filesystem project.
"""

import sys


# Create mock classes
class MockFastMCP:
    """Mock FastMCP class for testing."""

    def __init__(self, server_name=None, *args, **kwargs):
        self.server_name = server_name
        self.tools = {}

    def tool(self):
        """Mock tool decorator."""

        def decorator(func):
            self.tools[func.__name__] = func
            return func

        return decorator

    def run(self):
        """Mock run method."""
        pass

    def prompt(self, name):
        """Mock prompt decorator."""

        def decorator(func):
            return func

        return decorator


class MockContext:
    """Mock Context class for testing."""

    def __init__(self, client_id="test_client", request_id="test_request"):
        self.client_id = client_id
        self.request_id = request_id


# Add the mock to sys.modules
sys.modules["mcp"] = type("mcp", (), {})
sys.modules["mcp.server"] = type("server", (), {})
sys.modules["mcp.server.fastmcp"] = type(
    "fastmcp", (), {"FastMCP": MockFastMCP, "Context": MockContext}
)
