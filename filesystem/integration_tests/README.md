# MCP Filesystem Server Integration Tests

This directory contains integration tests for the MCP filesystem server. These tests verify that the server's functionality works correctly in an integrated environment.

## Test Structure

The integration tests are organized into several files, each testing a different aspect of the filesystem server:

- `test_filesystem_server.py`: Tests basic file and directory operations (create, read, move, delete, edit)
- `test_git_directory_tree.py`: Tests directory tree functionality in git repositories
- `test_file_search.py`: Tests file search and code analysis functionality
- `test_path_validation.py`: Tests path validation and security features

## Running the Tests

To run all integration tests, use the test runner script:

```bash
uv run integration_tests/run_tests.py 
```

To run a specific test file:

```bash
uv run integration_tests/test_filesystem_server.py
uv run integration_tests/test_git_directory_tree.py
uv run integration_tests/test_file_search.py
uv run integration_tests/test_path_validation.py
```

## Test Environment

The tests create temporary directories for testing and clean them up afterward. Each test file sets up its own environment with the necessary files and directories for testing.

## Adding New Tests

When adding new tests, follow these guidelines:

1. Create test methods with clear, descriptive names starting with `test_`.
2. Add docstrings to test methods explaining what they test.
3. Use assertions to verify the expected behavior.
4. Clean up any resources created during the test in the `tearDown` method.
5. For new functionality, consider creating a new test file if it doesn't fit into the existing test categories.

## Test Dependencies

The integration tests require:

1. Python 3.12 or later
2. git (for the git-related tests)
3. The MCP filesystem server code

Some tests will be skipped if the required dependencies are not available.
