#!/usr/bin/env python3
"""
Test runner for MCP filesystem server integration tests.

This script runs all the integration tests for the MCP filesystem server.
"""

import unittest
import sys
from pathlib import Path
import tempfile

# Initialize the test environment first - this must come before other imports

# Add the parent directory to sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))


def import_test_classes():
    """Import test classes from test modules."""
    try:
        # Import the test classes from the modules
        global \
            TestPathValidation, \
            TestAdvancedPathResolution, \
            TestRealWorldPathScenarios
        from integration_tests.test_path_validation import (
            TestPathValidation,
            TestAdvancedPathResolution,
            TestRealWorldPathScenarios,
        )

        return True
    except Exception as e:
        print(f"Error importing test classes: {e}")
        import traceback

        traceback.print_exc()
        return False


def run_tests():
    """Run all integration tests."""
    print("Loading test modules...")

    # Create a test suite
    test_suite = unittest.TestSuite()

    # Import and add test classes to the test suite
    if not import_test_classes():
        return False

    print("Successfully imported test classes")

    # Add tests to the suite
    add_tests_to_suite(test_suite)

    # Run the tests
    print("Running tests...")

    # Run the tests with TextTestRunner
    test_runner = unittest.TextTestRunner()
    result = test_runner.run(test_suite)

    success = result.wasSuccessful()
    print(f"Tests complete. Success: {success}")
    return success


def add_tests_to_suite(test_suite):
    """Add the test classes to the test suite."""

    # Create a TestLoader instance
    loader = unittest.TestLoader()

    print("Adding TestPathValidation to test suite")
    test_suite.addTest(loader.loadTestsFromTestCase(TestPathValidation))

    print("Adding TestAdvancedPathResolution to test suite")
    test_suite.addTest(loader.loadTestsFromTestCase(TestAdvancedPathResolution))

    print("Adding TestRealWorldPathScenarios to test suite")
    test_suite.addTest(loader.loadTestsFromTestCase(TestRealWorldPathScenarios))


if __name__ == "__main__":
    # In script mode, set up any environment
    # Configure server allowed directories
    allowed_dir = tempfile.mkdtemp(prefix="mcp_fs_test_")
    if "SERVER_ALLOWED_DIRECTORIES" in globals():
        globals()["SERVER_ALLOWED_DIRECTORIES"].append(allowed_dir)
    else:
        globals()["SERVER_ALLOWED_DIRECTORIES"] = [allowed_dir]

    # Create builtins globals for tests
    import builtins

    if not hasattr(builtins, "SERVER_ALLOWED_DIRECTORIES"):
        builtins.SERVER_ALLOWED_DIRECTORIES = globals()["SERVER_ALLOWED_DIRECTORIES"]

    result = run_tests()

    # Return appropriate exit code
    sys.exit(0 if result else 1)
