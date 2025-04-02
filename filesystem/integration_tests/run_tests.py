#!/usr/bin/env python3
"""
Test runner for MCP filesystem server integration tests.

This script runs all the integration tests for the MCP filesystem server.
"""

import unittest
import sys
import os
from pathlib import Path

# Add the parent directory to sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Initialize the test environment first
from integration_tests.test_init import MockContext


def run_tests():
    """Run all integration tests."""
    # Discover and run all tests in the integration_tests directory
    test_loader = unittest.TestLoader()
    test_suite = test_loader.discover(
        start_dir=os.path.dirname(os.path.abspath(__file__)),
        pattern="test_*.py"
    )

    # Run the tests
    test_runner = unittest.TextTestRunner(verbosity=2)
    result = test_runner.run(test_suite)

    # Return the exit code based on test results
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    # Exit with the appropriate exit code
    sys.exit(run_tests())
