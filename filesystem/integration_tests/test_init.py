"""
Initialize the test environment.

This module should be imported first by all test modules to ensure
that the mcp module is properly mocked before any imports happen.
"""

# Import mock_imports first to ensure the mcp module is mocked
from integration_tests.mock_imports import MockContext  # noqa

# Re-export for convenience
__all__ = ['MockContext']
