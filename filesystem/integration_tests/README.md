# Integration Tests for MCP Filesystem Server

This directory contains integration tests for the MCP filesystem server. These tests verify various aspects of the server functionality, including file operations, directory management, and fixing specific issues.

## Test Files

- `test_filesystem_server.py`: Comprehensive tests for the MCP filesystem server functionality
- `test_filesystem_issues.py`: Focused tests to verify fixes for specific issues
- `test_fixes.py`: Tests to verify the implemented fixes and improvements

## Running the Tests

You can run the tests in different ways:

### Run all tests

```bash
cd /path/to/project
python -m unittest discover integration_tests
```

### Run a specific test file

```bash
cd /path/to/project
python -m unittest integration_tests/test_filesystem_server.py
```

### Run a specific test case

```bash
cd /path/to/project
python -m unittest integration_tests.test_filesystem_server.TestFilesystemMCPServer.test_delete_file
```

## Test Organization

The tests are organized following best practices:

1. Each test function focuses on testing one specific aspect of the system
2. Tests use clear and descriptive names that indicate what they're testing
3. All tests handle proper setup and teardown to ensure clean test environments
4. Tests are isolated from each other to prevent interdependencies
5. Tests include appropriate assertions to verify correct behavior

## When to Run These Tests

These tests should be run:

1. After making changes to the filesystem server code
2. Before submitting a pull request
3. As part of the continuous integration (CI) pipeline
4. When verifying fixes for specific issues

## Test Environment

The tests use temporary directories to ensure they don't interfere with actual files. Each test creates its own isolated environment, which is cleaned up after the test completes. 