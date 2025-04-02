#!/usr/bin/env python3
"""
Test runner for MCP filesystem server integration tests.

This script runs all the integration tests for the MCP filesystem server.
"""

import unittest
import sys
import os
from pathlib import Path

# Initialize the test environment first - this must come before other imports
from integration_tests.test_init import MockContext, SERVER_ALLOWED_DIRECTORIES, WORKING_DIRECTORY

# Add the parent directory to sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

def run_tests():
    """Run all integration tests."""
    # Create a test loader and discover tests in the current directory
    test_loader = unittest.TestLoader()
    start_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Load test classes directly to avoid the sys.argv parsing issue
    from integration_tests.test_path_validation import TestPathValidation
    
    # Create a test suite from specific test classes
    test_suite = unittest.TestSuite()
    test_suite.addTest(unittest.makeSuite(TestPathValidation))
    
    # Run the tests
    test_runner = unittest.TextTestRunner(verbosity=2)
    result = test_runner.run(test_suite)
    
    # Return the appropriate exit code
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    # Exit with the appropriate exit code
    sys.exit(run_tests())
