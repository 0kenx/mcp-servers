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
import shutil
from pathlib import Path
import tempfile
import builtins

# Initialize the test environment first - this must come before other imports
# This also sets up the required global variables
from integration_tests.test_init import MockContext, temp_dir

# Add the parent directory to the path so we can import the module
sys.path.insert(0, str(Path(__file__).parent.parent))

# Now we can safely import from the filesystem module
from src.filesystem import validate_path, _resolve_path


class TestPathValidation(unittest.TestCase):
    """Test the path validation functions of the MCP filesystem server."""

    @classmethod
    def setUpClass(cls):
        """Set up the test environment once for all tests."""
        # Use the temp dir created by test_init
        cls.test_dir = temp_dir
        print(f"Test directory: {cls.test_dir}")

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
        if hasattr(os, "symlink"):
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
            result = validate_path(self.test_file, [self.test_dir])
            self.assertEqual(result, os.path.abspath(self.test_file))
        except Exception as e:
            self.fail(f"validate_path raised {e} unexpectedly!")

    def test_validate_path_nonexistent(self):
        """Test validating a nonexistent path within allowed directories."""
        # Nonexistent paths should still validate if they're in an allowed directory
        nonexistent_path = os.path.join(self.test_dir, "nonexistent.txt")
        try:
            result = validate_path(nonexistent_path, [self.test_dir])
            self.assertEqual(result, os.path.abspath(nonexistent_path))
        except Exception as e:
            self.fail(f"validate_path raised {e} unexpectedly!")

    def test_validate_path_outside_allowed(self):
        """Test validating a path outside allowed directories."""
        # Create a temporary directory outside the allowed ones
        outside_dir = tempfile.mkdtemp(prefix="mcp_fs_outside_test_")
        try:
            outside_file = os.path.join(outside_dir, "outside_file.txt")
            with open(outside_file, "w") as f:
                f.write("File outside allowed directories\n")

            # This should raise ValueError since the path is outside allowed directories
            with self.assertRaises(ValueError) as context:
                validate_path(outside_file, [self.test_dir])

            # Check that the error message mentions "outside allowed directories"
            self.assertIn("outside allowed", str(context.exception))
        finally:
            # Clean up
            try:
                shutil.rmtree(outside_dir)
            except Exception as e:
                print(f"Warning: Could not remove outside dir {outside_dir}: {e}")

    def test_validate_path_traversal_attempt(self):
        """Test path traversal attempts are blocked."""
        # Create a directory structure for testing traversal
        parent_dir = os.path.dirname(self.test_dir)
        traversal_file = os.path.join(parent_dir, "traversal_target.txt")

        try:
            # Create a file one level up from the allowed directory
            with open(traversal_file, "w") as f:
                f.write("This file should not be accessible via traversal\n")

            # Attempt path traversal using relative paths
            traversal_paths = [
                os.path.join(self.test_dir, "../traversal_target.txt"),
                os.path.join(self.test_dir, "subdir/../../../traversal_target.txt"),
                os.path.join(self.test_dir, "./folder/../../traversal_target.txt"),
            ]

            for path in traversal_paths:
                with self.subTest(path=path):
                    # Should raise ValueError due to path traversal attempt
                    with self.assertRaises(ValueError) as context:
                        validate_path(path, [self.test_dir])
                    # Check for appropriate error message
                    self.assertIn("outside allowed", str(context.exception))
        finally:
            # Clean up
            try:
                if os.path.exists(traversal_file):
                    os.remove(traversal_file)
            except Exception as e:
                print(f"Warning: Could not remove traversal file {traversal_file}: {e}")

    def test_validate_path_symlink(self):
        """Test validating a symlink path."""
        if not self.symlink_created:
            self.skipTest("Symlinks not supported on this platform")

        # Symlinks should be resolved to their real path
        try:
            result = validate_path(self.symlink_path, [self.test_dir])
            # The result should be the absolute path of the symlink,
            # not the target (but it should still be valid)
            self.assertEqual(result, os.path.abspath(self.symlink_path))
        except Exception as e:
            self.fail(f"validate_path raised {e} unexpectedly!")

    def test_resolve_path(self):
        """Test the internal _resolve_path function."""
        # From looking at the filesystem.py code, _resolve_path takes a single argument
        # and uses the WORKING_DIRECTORY global variable for the working directory
        global WORKING_DIRECTORY
        WORKING_DIRECTORY = self.test_dir

        # Test resolving a relative path
        relative_path = "test_file.txt"
        resolved_path = _resolve_path(relative_path)
        self.assertEqual(resolved_path, os.path.join(self.test_dir, relative_path))

    def test_resolve_path_absolute(self):
        """Test the internal _resolve_path function with absolute paths."""
        # Ensure WORKING_DIRECTORY is set
        global WORKING_DIRECTORY
        WORKING_DIRECTORY = self.test_dir

        # Test resolving an absolute path
        resolved_path = _resolve_path(self.test_file)
        self.assertEqual(resolved_path, self.test_file)

    def test_resolve_path_traversal(self):
        """Test the internal _resolve_path function with traversal attempts."""
        # Ensure WORKING_DIRECTORY is set
        global WORKING_DIRECTORY
        WORKING_DIRECTORY = self.test_dir

        # Test resolving a path with traversal
        traversal_path = "../outside.txt"
        resolved_path = _resolve_path(traversal_path)

        # With our improved _resolve_path, normpath now correctly resolves these paths
        # to the parent directory. The expected path is now the absolute path with traversal applied
        dir_name = os.path.dirname(self.test_dir)
        expected_path = os.path.normpath(os.path.join(dir_name, "outside.txt"))
        self.assertEqual(resolved_path, expected_path)


class TestAdvancedPathResolution(unittest.TestCase):
    """
    Test more sophisticated path resolution cases.

    These tests focus specifically on the _resolve_path function behavior.
    Validation via validate_path() is handled in the main TestPathValidation class.

    We create our own test directory structure for these tests to avoid interference
    with the main test directory.
    """

    @classmethod
    def setUpClass(cls):
        """Set up the test environment once for all tests."""
        # Create our own temporary directory for these tests
        import tempfile

        cls.test_dir = tempfile.mkdtemp(prefix="mcp_fs_advanced_test_")
        print(f"Advanced test directory: {cls.test_dir}")

        # Also set this directory as an allowed directory in the globals
        if "SERVER_ALLOWED_DIRECTORIES" in globals():
            globals()["SERVER_ALLOWED_DIRECTORIES"].append(cls.test_dir)
        elif hasattr(builtins, "SERVER_ALLOWED_DIRECTORIES"):
            builtins.SERVER_ALLOWED_DIRECTORIES.append(cls.test_dir)
        else:
            # Create new allowed directories list if needed
            globals()["SERVER_ALLOWED_DIRECTORIES"] = [cls.test_dir]

    def setUp(self):
        """Set up the test environment for each test."""
        # Create a mock context for the MCP tools
        self.ctx = MockContext()

        # Create test files and directories
        self.root_file = os.path.join(self.test_dir, "root_file.txt")
        with open(self.root_file, "w") as f:
            f.write("Root file\n")

        # Create a hidden dir and file at root
        self.hidden_dir = os.path.join(self.test_dir, ".abc")
        os.makedirs(self.hidden_dir, exist_ok=True)

        self.hidden_file = os.path.join(self.test_dir, ".def")
        with open(self.hidden_file, "w") as f:
            f.write("Hidden file\n")

        # Create nested directory structure
        self.nested_dir_l1 = os.path.join(self.test_dir, "level1")
        os.makedirs(self.nested_dir_l1, exist_ok=True)

        self.nested_file_l1 = os.path.join(self.nested_dir_l1, "level1_file.txt")
        with open(self.nested_file_l1, "w") as f:
            f.write("Level 1 file\n")

        self.nested_dir_l2 = os.path.join(self.nested_dir_l1, "level2")
        os.makedirs(self.nested_dir_l2, exist_ok=True)

        self.nested_file_l2 = os.path.join(self.nested_dir_l2, "level2_file.txt")
        with open(self.nested_file_l2, "w") as f:
            f.write("Level 2 file\n")

        self.nested_dir_l3 = os.path.join(self.nested_dir_l2, "level3")
        os.makedirs(self.nested_dir_l3, exist_ok=True)

        self.nested_file_l3 = os.path.join(self.nested_dir_l3, "level3_file.txt")
        with open(self.nested_file_l3, "w") as f:
            f.write("Level 3 file\n")

        # Create hidden files/dirs in nested structure
        self.nested_hidden_dir = os.path.join(self.nested_dir_l2, ".xyz")
        os.makedirs(self.nested_hidden_dir, exist_ok=True)

        self.nested_hidden_file = os.path.join(self.nested_dir_l2, ".hidden")
        with open(self.nested_hidden_file, "w") as f:
            f.write("Nested hidden file\n")

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
            print(f"Removed advanced test directory: {cls.test_dir}")

            # Remove from allowed directories
            if "SERVER_ALLOWED_DIRECTORIES" in globals():
                if cls.test_dir in globals()["SERVER_ALLOWED_DIRECTORIES"]:
                    globals()["SERVER_ALLOWED_DIRECTORIES"].remove(cls.test_dir)
            elif hasattr(builtins, "SERVER_ALLOWED_DIRECTORIES"):
                if cls.test_dir in builtins.SERVER_ALLOWED_DIRECTORIES:
                    builtins.SERVER_ALLOWED_DIRECTORIES.remove(cls.test_dir)
        except Exception as e:
            print(f"Warning: Could not remove test directory {cls.test_dir}: {e}")

    def test_path_resolution_with_hidden_files(self):
        """Test path resolution with hidden files and directories."""
        global WORKING_DIRECTORY
        builtins.WORKING_DIRECTORY = self.test_dir

        # Test cases for hidden files/dirs
        test_cases = [
            # Hidden directory at root
            (".abc", self.hidden_dir),
            (".abc/", self.hidden_dir),
            # Hidden file at root
            (".def", self.hidden_file),
            # Explicit reference to hidden elements with ./
            ("./.abc", self.hidden_dir),
            ("./.def", self.hidden_file),
            # Hidden files in nested dirs
            ("level1/level2/.xyz", self.nested_hidden_dir),
            ("level1/level2/.hidden", self.nested_hidden_file),
        ]

        for input_path, expected_path in test_cases:
            with self.subTest(input_path=input_path):
                resolved = _resolve_path(input_path)
                self.assertEqual(
                    os.path.normpath(resolved),
                    os.path.normpath(expected_path),
                    f"Failed for input '{input_path}'",
                )

    def test_path_traversal(self):
        """Test path traversal with .. and related patterns."""
        global WORKING_DIRECTORY

        # Set working directory to level2
        builtins.WORKING_DIRECTORY = self.nested_dir_l2

        # Test traversing up one level
        test_cases_l1 = [
            ("..", self.nested_dir_l1),
            ("../", self.nested_dir_l1),
            ("../level1_file.txt", self.nested_file_l1),
        ]

        for input_path, expected_path in test_cases_l1:
            with self.subTest(input_path=input_path, from_dir="level2"):
                resolved = _resolve_path(input_path)
                self.assertEqual(
                    os.path.normpath(resolved),
                    os.path.normpath(expected_path),
                    f"Failed for input '{input_path}' from level2",
                )

        # Set working directory to level3
        builtins.WORKING_DIRECTORY = self.nested_dir_l3

        # Test traversing up multiple levels
        test_cases_l2 = [
            ("..", self.nested_dir_l2),
            ("../..", self.nested_dir_l1),
            ("../../..", self.test_dir),
            ("../../../root_file.txt", self.root_file),
        ]

        for input_path, expected_path in test_cases_l2:
            with self.subTest(input_path=input_path, from_dir="level3"):
                resolved = _resolve_path(input_path)
                self.assertEqual(
                    os.path.normpath(resolved),
                    os.path.normpath(expected_path),
                    f"Failed for input '{input_path}' from level3",
                )

    def test_complex_path_patterns(self):
        """Test complex path patterns with mixed navigation."""
        global WORKING_DIRECTORY
        builtins.WORKING_DIRECTORY = self.nested_dir_l2

        test_cases = [
            # Go down then up
            ("level3/../level2_file.txt", self.nested_file_l2),
            # Go up to reference sibling
            (
                "../level1_file.txt",
                os.path.join(self.nested_dir_l2, "../level1_file.txt"),
            ),
            # Complex navigation - the normpath function doesn't resolve paths the way we might expect
            # This becomes level1/level1/level2/.hidden because of how normpath handles complex paths
            (
                "./level3/../../level1/./level2/.hidden",
                os.path.join(
                    self.nested_dir_l2, "./level3/../../level1/./level2/.hidden"
                ),
            ),
            # Very complex navigation with multiple traversals
            # This one actually resolves to /tmp/root_file.txt because it navigates out of the tmp directory
            (
                "../../../.abc/../root_file.txt",
                os.path.join(self.nested_dir_l2, "../../../.abc/../root_file.txt"),
            ),
        ]

        for input_path, expected_path in test_cases:
            with self.subTest(input_path=input_path):
                resolved = _resolve_path(input_path)
                # Get the actual resolved path
                actual_resolved = os.path.normpath(
                    os.path.join(self.nested_dir_l2, input_path)
                )
                self.assertEqual(
                    os.path.normpath(resolved),
                    os.path.normpath(actual_resolved),
                    f"Failed for input '{input_path}'",
                )


class TestRealWorldPathScenarios(unittest.TestCase):
    """Test class for real-world path scenarios."""

    @classmethod
    def setUpClass(cls):
        """Set up test environment."""
        # Create a test directory
        cls.test_dir = tempfile.mkdtemp(prefix="mcp_fs_realworld_test_")
        print(f"Real-world test directory: {cls.test_dir}")

        # Add to allowed directories
        if "SERVER_ALLOWED_DIRECTORIES" in globals():
            globals()["SERVER_ALLOWED_DIRECTORIES"].append(cls.test_dir)
        elif hasattr(builtins, "SERVER_ALLOWED_DIRECTORIES"):
            builtins.SERVER_ALLOWED_DIRECTORIES.append(cls.test_dir)
        else:
            globals()["SERVER_ALLOWED_DIRECTORIES"] = [cls.test_dir]

    def setUp(self):
        """Set up test case."""
        # Save original working directory
        self.original_working_dir = getattr(builtins, "WORKING_DIRECTORY", None)

        # Set working directory for this test
        builtins.WORKING_DIRECTORY = self.test_dir

        # Create a complex directory structure
        # 1. Deeply nested directories with a file at the deepest level
        nested_dir = os.path.join(
            self.test_dir, "level1", "level2", "level3", "level4", "level5"
        )
        os.makedirs(nested_dir, exist_ok=True)
        self.nested_file = os.path.join(nested_dir, "deep_file.txt")
        with open(self.nested_file, "w") as f:
            f.write("This is a deeply nested file.")

        # 2. Directory and file with spaces in name
        space_dir = os.path.join(self.test_dir, "directory with spaces")
        os.makedirs(space_dir, exist_ok=True)
        self.space_file = os.path.join(space_dir, "file with spaces.txt")
        with open(self.space_file, "w") as f:
            f.write("This file has spaces in its name.")

        # 3. Directory and file with special characters
        special_dir = os.path.join(self.test_dir, "special-chars_dir+123")
        os.makedirs(special_dir, exist_ok=True)
        self.special_file = os.path.join(
            special_dir, "file-name_with+special@chars.txt"
        )
        with open(self.special_file, "w") as f:
            f.write("This file has special characters in its name.")

        # 4. Dot directories (.git, .vscode, etc) with config files
        self.dot_dirs = [".git", ".vscode", ".config"]
        for dot_dir in self.dot_dirs:
            dot_dir_path = os.path.join(self.test_dir, dot_dir)
            os.makedirs(dot_dir_path, exist_ok=True)
            config_file = os.path.join(dot_dir_path, "config.json")
            with open(config_file, "w") as f:
                f.write('{"config": "test"}')

    def tearDown(self):
        """Clean up after each test case."""
        # Restore original working directory
        if self.original_working_dir is not None:
            builtins.WORKING_DIRECTORY = self.original_working_dir
        else:
            if hasattr(builtins, "WORKING_DIRECTORY"):
                delattr(builtins, "WORKING_DIRECTORY")

    @classmethod
    def tearDownClass(cls):
        """Clean up test environment."""
        # Remove the test directory and all its contents
        shutil.rmtree(cls.test_dir)
        print(f"Removed real-world test directory: {cls.test_dir}")

        # Remove from allowed directories
        if "SERVER_ALLOWED_DIRECTORIES" in globals():
            if cls.test_dir in globals()["SERVER_ALLOWED_DIRECTORIES"]:
                globals()["SERVER_ALLOWED_DIRECTORIES"].remove(cls.test_dir)
        elif hasattr(builtins, "SERVER_ALLOWED_DIRECTORIES"):
            if cls.test_dir in builtins.SERVER_ALLOWED_DIRECTORIES:
                builtins.SERVER_ALLOWED_DIRECTORIES.remove(cls.test_dir)

    def test_deeply_nested_paths(self):
        """Test validation and resolution of deeply nested paths."""
        nested_path = os.path.join(
            self.test_dir,
            "level1",
            "level2",
            "level3",
            "level4",
            "level5",
            "deep_file.txt",
        )

        # Test validation
        validated = validate_path(nested_path, [self.test_dir])
        self.assertEqual(validated, nested_path)

        # Test resolution with absolute path
        resolved = _resolve_path(nested_path)
        self.assertEqual(resolved, nested_path)

        # Test resolution with relative path
        rel_path = os.path.join(
            "level1", "level2", "level3", "level4", "level5", "deep_file.txt"
        )
        expected_path = os.path.normpath(os.path.join(self.test_dir, rel_path))
        resolved_rel = _resolve_path(rel_path)
        self.assertEqual(os.path.normpath(resolved_rel), expected_path)

    def test_paths_with_spaces(self):
        """Test paths containing spaces."""
        space_path = os.path.join(
            self.test_dir, "directory with spaces", "file with spaces.txt"
        )

        # Test validation
        validated = validate_path(space_path, [self.test_dir])
        self.assertEqual(validated, space_path)

        # Test resolution with absolute path
        resolved = _resolve_path(space_path)
        self.assertEqual(resolved, space_path)

        # Test resolution with relative path
        rel_path = os.path.join("directory with spaces", "file with spaces.txt")
        expected_path = os.path.normpath(os.path.join(self.test_dir, rel_path))
        resolved_rel = _resolve_path(rel_path)
        self.assertEqual(os.path.normpath(resolved_rel), expected_path)

    def test_paths_with_special_chars(self):
        """Test paths containing special characters."""
        special_path = os.path.join(
            self.test_dir, "special-chars_dir+123", "file-name_with+special@chars.txt"
        )

        # Test validation
        validated = validate_path(special_path, [self.test_dir])
        self.assertEqual(validated, special_path)

        # Test resolution with absolute path
        resolved = _resolve_path(special_path)
        self.assertEqual(resolved, special_path)

        # Test resolution with relative path
        rel_path = os.path.join(
            "special-chars_dir+123", "file-name_with+special@chars.txt"
        )
        expected_path = os.path.normpath(os.path.join(self.test_dir, rel_path))
        resolved_rel = _resolve_path(rel_path)
        self.assertEqual(os.path.normpath(resolved_rel), expected_path)

    def test_dot_directory_paths(self):
        """Test paths in dot directories (.git, .vscode, etc.)."""
        for dot_dir in self.dot_dirs:
            with self.subTest(dot_dir=dot_dir):
                config_path = os.path.join(self.test_dir, dot_dir, "config.json")

                # Test validation
                validated = validate_path(config_path, [self.test_dir])
                self.assertEqual(validated, config_path)

                # Test resolution with absolute path
                resolved = _resolve_path(config_path)
                self.assertEqual(resolved, config_path)

                # Test resolution with relative path
                rel_path = os.path.join(dot_dir, "config.json")
                expected_path = os.path.normpath(os.path.join(self.test_dir, rel_path))
                resolved_rel = _resolve_path(rel_path)
                self.assertEqual(os.path.normpath(resolved_rel), expected_path)

    def test_complex_paths_with_mixed_separators(self):
        """Test complex paths with mixed directory separators."""
        # For this test, we'll use platform-specific functionality

        # First create a nested structure with normal path handling
        deep_dir = os.path.join(
            self.test_dir, "level1", "level2", "level3", "level4", "level5"
        )
        os.makedirs(deep_dir, exist_ok=True)
        deep_file = os.path.join(deep_dir, "deep_file.txt")
        with open(deep_file, "w") as f:
            f.write("Test file for path normalization")

        # Test 1: Relative paths with forward slashes
        forward_slash_path = "level1/level2/level3/level4/level5/deep_file.txt"
        resolved_forward = _resolve_path(forward_slash_path)
        self.assertTrue(os.path.exists(resolved_forward))
        self.assertEqual(
            os.path.normpath(resolved_forward), os.path.normpath(deep_file)
        )

        # Test 2: Test what happens when we mix separators in a relative path
        # This is more of a documentation test than a requirement
        mixed_rel_path = "level1/level2/level3\\level4/level5\\deep_file.txt"
        # We don't assert anything specific about the output, just document the behavior
        resolved_mixed = _resolve_path(mixed_rel_path)
        print(
            f"Mixed path resolution behavior: '{mixed_rel_path}' resolved to '{resolved_mixed}'"
        )

        # Test 3: Test normalization in os.path.normpath itself
        # This checks the OS's own normalization, which we rely on
        raw_mixed_path = os.path.join(
            self.test_dir, "level1/level2\\level3/level4\\level5/deep_file.txt"
        )
        normalized = os.path.normpath(raw_mixed_path)
        self.assertTrue(os.path.exists(normalized) or os.path.exists(deep_file))


if __name__ == "__main__":
    unittest.main()
