"""Mock module for MCP dependencies in integration tests.

This module MUST be imported before any other imports that might use the mcp module.
It provides mock implementations to avoid the need to install the actual mcp package.
"""

# This needs to be at the very top
import sys

# Add the mock to sys.modules immediately
sys.modules['mcp'] = type('mcp', (), {})
sys.modules['mcp.server'] = type('server', (), {})

# Create mock classes
class MockFastMCP:
    """Mock FastMCP class for testing."""
    def __init__(self):
        pass

class MockContext:
    """Mock Context class for testing."""
    def __init__(self, client_id="test_client", request_id="test_request"):
        self.client_id = client_id
        self.request_id = request_id

# Update the sys.modules with our classes
sys.modules['mcp.server.fastmcp'] = type('fastmcp', (), {'FastMCP': MockFastMCP, 'Context': MockContext})
