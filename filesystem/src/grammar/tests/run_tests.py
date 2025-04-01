#!/usr/bin/env python3
"""
Test runner for all language parser tests.
This script discovers and runs all test files in the grammar/tests directory.
"""

import unittest
import sys
import os


def run_all_tests():
    """
    Discover and run all tests in the tests directory.
    Returns True if all tests pass, False otherwise.
    """
    # Get the directory of this script
    this_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Create a test loader
    loader = unittest.TestLoader()
    
    # Discover tests in the current directory
    test_suite = loader.discover(this_dir, pattern="test_*.py")
    
    # Create a test runner
    runner = unittest.TextTestRunner(verbosity=2)
    
    # Run the tests
    result = runner.run(test_suite)
    
    # Return True if all tests pass, False otherwise
    return result.wasSuccessful()


def run_specific_test(test_name):
    """
    Run a specific test file.
    
    Args:
        test_name: Name of the test file (without .py extension)
    
    Returns:
        True if tests pass, False otherwise
    """
    # Create a test loader
    loader = unittest.TestLoader()
    
    # Load the specified test module
    module_name = f"tests.{test_name}"
    try:
        suite = loader.loadTestsFromName(module_name)
    except ImportError:
        print(f"Error: Test module '{module_name}' not found.")
        return False
    
    # Create a test runner
    runner = unittest.TextTestRunner(verbosity=2)
    
    # Run the tests
    result = runner.run(suite)
    
    # Return True if all tests pass, False otherwise
    return result.wasSuccessful()


if __name__ == "__main__":
    # If no arguments are provided, run all tests
    if len(sys.argv) == 1:
        success = run_all_tests()
    else:
        # Otherwise, run the specified test
        test_name = sys.argv[1]
        if test_name.endswith(".py"):
            test_name = test_name[:-3]
        success = run_specific_test(test_name)
    
    # Exit with an appropriate status code
    sys.exit(0 if success else 1)
