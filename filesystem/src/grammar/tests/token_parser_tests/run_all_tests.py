"""
Test runner for token parser integration tests.

This module discovers and runs all token parser integration tests.
"""

import unittest
import os
import sys

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))


def run_all_tests():
    """
    Discover and run all token parser tests.
    
    Returns:
        The TestResult object from running the tests
    """
    # Discover tests in the token_parser_tests directory
    test_loader = unittest.TestLoader()
    test_suite = test_loader.discover(
        start_dir=os.path.dirname(__file__),
        pattern='test_*_token_parser.py'
    )
    
    # Run the tests
    test_runner = unittest.TextTestRunner(verbosity=2)
    result = test_runner.run(test_suite)
    
    return result


if __name__ == "__main__":
    result = run_all_tests()
    
    # Exit with non-zero code if there were failures
    if not result.wasSuccessful():
        sys.exit(1)
