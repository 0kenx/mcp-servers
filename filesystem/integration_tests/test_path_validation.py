#!/usr/bin/env python3
"""
Integration tests for the MCP filesystem server's path validation.

These tests verify that the path validation functions work correctly and securely:
- Validating paths within allowed directories
- Handling path traversal attempts
- Handling symlinks and other special files
"""

import os
import sys
import unittest
import tempfile
import shutil
from pathlib import Path
import subprocess

# Initialize the test environment first
from integration_tests.test_init import MockContext

# Add the parent directory to the path so we can import the module
sys.path.insert(0, str(Path(__file__).parent.parent))

# Now we can safely import from the filesystem module
from src.filesystem import validate_path, _resolve_path


class TestPathValidation(unittest.TestCase):
    """Test the path validation functions of the MCP filesystem server."""

    @classmethod
    def setUpClass(cls):
        """Set up the test environment once for all tests."""
        # Create a temporary directory for testing
        cls.test_dir = tempfile.mkdtemp(prefix="mcp_fs_path_test_")
        print(f"Test directory: {cls.test_dir}")

        # Set up the global variables needed by the server
        global SERVER_ALLOWED_DIRECTORIES, WORKING_DIRECTORY
        SERVER_ALLOWED_DIRECTORIES = [cls.test_dir]
        WORKING_DIRECTORY = cls.test_dir

    def setUp(self):
        """Set up the test environment for each test."""
        # Create a mock context for the MCP tools
        self.ctx = MockContext()

        # Create test files and directories
        self.test_file = os.path.join(self.test_dir, "test_file.txt")
        with open(self.test_file, "w") as f:
            f.write("This is a test file\n")

        # Create a subdirectory with a file
        self.test_subdir = os.path.join(self.test_dir, "test_subdir")
        os.makedirs(self.test_subdir, exist_ok=True)

        self.test_file2 = os.path.join(self.test_subdir, "test_file2.txt")
        with open(self.test_file2, "w") as f:
            f.write("File in subdirectory\n")

        # Create a symlink if the platform supports it
        if hasattr(os, 'symlink'):
            try:
                # Create a symlink to the test file
                self.symlink_path = os.path.join(self.test_dir, "symlink.txt")
                os.symlink(self.test_file, self.symlink_path)
                self.symlink_created = True
            except (OSError, AttributeError):
                self.symlink_created = False
        else:
            self.symlink_created = False

    def tearDown(self):
        """Clean up after each test."""
        # Remove test files and directories created during the test
        for item in os.listdir(self.test_dir):
            item_path = os.path.join(self.test_dir, item)
            try:
                if os.path.isdir(item_path) and not os.path.islink(item_path):
                    shutil.rmtree(item_path)
                else:
                    os.remove(item_path)
            except Exception as e:
                print(f"Warning: Could not remove {item_path}: {e}")

    @classmethod
    def tearDownClass(cls):
        """Clean up after all tests."""
        # Remove the temporary directory
        try:
            shutil.rmtree(cls.test_dir)
            print(f"Removed test directory: {cls.test_dir}")
        except Exception as e:
            print(f"Warning: Could not remove test directory {cls.test_dir}: {e}")

    def test_validate_path_within_allowed(self):
        """Test validating a path within allowed directories."""
        # Test a valid path
        try:
            result = validate_path(self.test_file)
            self.assertEqual(result, os.path.abspath(self.test_file))
        except Exception as e:
            self.fail(f"validate_path raised {e} unexpectedly!")

    def test_validate_path_nonexistent(self):
        """Test validating a nonexistent path within allowed directories."""
        # Nonexistent paths should still validate if they're in an allowed directory
        nonexistent_path = os.path.join(self.test_dir, "nonexistent.txt")
        try:
            result = validate_path(nonexistent_path)
            self.assertEqual(result, os.path.abspath(nonexistent_path))
        except Exception as e:
            self.fail(f"validate_path raised {e} unexpectedly!")

    def test_validate_path_outside_allowed(self):
        """Test validating a path outside allowed directories."""
        # Test an invalid path outside allowed directories
        with self.assertRaises(Exception):
            validate_path("/tmp/outside_allowed.txt")

    def test_validate_path_traversal_attempt(self):
        """Test path traversal attempts are blocked."""
        # Try a path traversal attack
        traversal_path = os.path.join(self.test_dir, "../../../etc/passwd")
        with self.assertRaises(Exception):
            validate_path(traversal_path)

    def test_validate_path_symlink(self):
        """Test validating a symlink path."""
        if not self.symlink_created:
            self.skipTest("Symlinks not supported on this platform")

        # Symlinks should be resolved to their real path
        try:
            result = validate_path(self.symlink_path)
            # The result should be the absolute path of the symlink,
            # not the target (but it should still be valid)
            self.assertEqual(result, os.path.abspath(self.symlink_path))
        except Exception as e:
            self.fail(f"validate_path raised {e} unexpectedly!")

    def test_resolve_path(self):
        """Test the internal _resolve_path function."""
        # Test resolving a relative path
        relative_path = "test_file.txt"
        resolved_path = _resolve_path(relative_path, self.test_dir)
        self.assertEqual(resolved_path, os.path.join(self.test_dir, relative_path))

    def test_resolve_path_absolute(self):
        """Test the internal _resolve_path function with absolute paths."""
        # Test resolving an absolute path
        resolved_path = _resolve_path(self.test_file, self.test_dir)
        self.assertEqual(resolved_path, self.test_file)

    def test_resolve_path_traversal(self):
        """Test the internal _resolve_path function with traversal attempts."""
        # Test resolving a path with traversal
        traversal_path = "../outside.txt"
        resolved_path = _resolve_path(traversal_path, self.test_dir)
        # Should resolve to the normalized path, which is still outside the working directory
        expected_path = os.path.normpath(os.path.join(self.test_dir, traversal_path))
        self.assertEqual(resolved_path, expected_path)


if __name__ == "__main__":
    unittest.main()
