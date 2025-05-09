#!/usr/bin/env python3
"""
Integration tests for the MCP filesystem server.

These tests verify that the filesystem operations work correctly, including:
- File creation, reading, and deletion
- File moving/renaming
- Directory creation and listing
- File editing
"""

import os
import sys
import unittest
import tempfile
import shutil

# Import for git tests disabled due to module dependency issues
# Run test_git_directory_tree_fix.py separately:
# python -m integration_tests.test_git_directory_tree_fix
from pathlib import Path

# Initialize the test environment first
from integration_tests.test_init import MockContext

# Add the parent directory to the path so we can import the module
sys.path.insert(0, str(Path(__file__).parent.parent))

# Import the necessary modules


class TestFilesystemMCPServer(unittest.TestCase):
    """Test the filesystem MCP server."""

    @classmethod
    def setUpClass(cls):
        """Set up the test environment once for all tests."""
        # Create a temporary directory for testing
        cls.test_dir = tempfile.mkdtemp(prefix="mcp_fs_test_")
        print(f"Test directory: {cls.test_dir}")

        # Set up the global variables needed by the server
        global SERVER_ALLOWED_DIRECTORIES, WORKING_DIRECTORY
        SERVER_ALLOWED_DIRECTORIES = [cls.test_dir]
        WORKING_DIRECTORY = cls.test_dir

        # Import the functions that rely on these globals
        # This needs to be done after setting the globals
        from src.filesystem import (
            write_file,
            delete_file,
            move_file,
            create_directory,
            list_directory,
            read_file,
            read_multiple_files,
            edit_file_diff,
            directory_tree,
        )

        cls.write_file = write_file
        cls.delete_file = delete_file
        cls.move_file = move_file
        cls.create_directory = create_directory
        cls.list_directory = list_directory
        cls.read_file = read_file
        cls.read_multiple_files = read_multiple_files
        cls.edit_file_diff = edit_file_diff
        cls.directory_tree = directory_tree

    def setUp(self):
        """Set up the test environment for each test."""
        # Create a mock context for the MCP tools
        self.ctx = MockContext()

        # Create test files and directories for each test
        self.test_file = os.path.join(self.test_dir, "test_file.txt")
        self.test_content = "This is a test file\nLine 2\nLine 3\n"
        with open(self.test_file, "w") as f:
            f.write(self.test_content)

        # Create a subdirectory with a file
        self.test_subdir = os.path.join(self.test_dir, "test_subdir")
        os.makedirs(self.test_subdir, exist_ok=True)

        self.test_file2 = os.path.join(self.test_subdir, "test_file2.txt")
        with open(self.test_file2, "w") as f:
            f.write("File in subdirectory\n")

    def tearDown(self):
        """Clean up after each test."""
        # Remove test files and directories created during the test
        for item in os.listdir(self.test_dir):
            item_path = os.path.join(self.test_dir, item)
            try:
                if os.path.isdir(item_path):
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

    def test_delete_file(self):
        """Test that the delete_file function properly deletes a file."""
        # Verify the file exists before deletion
        self.assertTrue(os.path.exists(self.test_file))

        # Delete the file
        result = self.delete_file(self.ctx, self.test_file)

        # Check the result message
        self.assertIn("Successfully deleted", result)

        # Verify the file has been deleted
        self.assertFalse(os.path.exists(self.test_file))

    def test_delete_nonexistent_file(self):
        """Test that delete_file handles nonexistent files appropriately."""
        # Path to a nonexistent file
        nonexistent_file = os.path.join(self.test_dir, "nonexistent.txt")

        # Verify the file doesn't exist
        self.assertFalse(os.path.exists(nonexistent_file))

        # Try to delete the nonexistent file
        result = self.delete_file(self.ctx, nonexistent_file)

        # Check the result message
        self.assertIn("Error", result)

    def test_delete_directory(self):
        """Test that delete_file handles directory inputs appropriately."""
        # Try to delete a directory with delete_file
        result = self.delete_file(self.ctx, self.test_subdir)

        # Check the result message
        self.assertIn("Error", result)
        self.assertIn("is a directory", result)

        # Verify the directory still exists
        self.assertTrue(os.path.isdir(self.test_subdir))

    def test_move_file(self):
        """Test that the move_file function properly moves/renames a file."""
        # Verify the source file exists
        self.assertTrue(os.path.exists(self.test_file))

        # Define the destination path
        dest_file = os.path.join(self.test_dir, "moved_file.txt")

        # Verify the destination file doesn't exist yet
        self.assertFalse(os.path.exists(dest_file))

        # Move the file
        result = self.move_file(self.ctx, self.test_file, dest_file)

        # Check the result message
        self.assertIn("Successfully moved", result)

        # Verify the source file no longer exists
        self.assertFalse(os.path.exists(self.test_file))

        # Verify the destination file exists
        self.assertTrue(os.path.exists(dest_file))

        # Verify the content was preserved
        with open(dest_file, "r") as f:
            content = f.read()
        self.assertEqual(content, self.test_content)

    def test_move_file_to_existing_destination(self):
        """Test that move_file handles existing destination files appropriately."""
        # Create destination file
        dest_file = os.path.join(self.test_dir, "existing_dest.txt")
        with open(dest_file, "w") as f:
            f.write("Existing destination file\n")

        # Try to move to an existing destination
        result = self.move_file(self.ctx, self.test_file, dest_file)

        # Check the result message
        self.assertIn("Error", result)
        self.assertIn("already exists", result)

        # Verify the source file still exists
        self.assertTrue(os.path.exists(self.test_file))

    def test_move_file_nonexistent_source(self):
        """Test that move_file handles nonexistent source files appropriately."""
        # Path to a nonexistent source file
        nonexistent_file = os.path.join(self.test_dir, "nonexistent.txt")
        dest_file = os.path.join(self.test_dir, "dest_from_nonexistent.txt")

        # Try to move a nonexistent file
        result = self.move_file(self.ctx, nonexistent_file, dest_file)

        # Check the result message
        self.assertIn("Error", result)

    def test_create_directory_new(self):
        """Test creating a new directory."""
        # Define a new directory path
        new_dir = os.path.join(self.test_dir, "new_directory")

        # Verify it doesn't exist yet
        self.assertFalse(os.path.exists(new_dir))

        # Create the directory
        result = self.create_directory(new_dir)

        # Check the result message
        self.assertIn("Successfully created directory", result)

        # Verify the directory now exists
        self.assertTrue(os.path.isdir(new_dir))

    def test_create_directory_existing(self):
        """Test creating a directory that already exists."""
        # The directory already exists
        result = self.create_directory(self.test_subdir)

        # With the improved behavior, it should return the directory listing
        self.assertIn("Contents of", result)
        self.assertIn("test_file2.txt", result)

    def test_create_nested_directory(self):
        """Test creating a nested directory structure."""
        # Define a nested directory path
        nested_dir = os.path.join(self.test_dir, "parent/child/grandchild")

        # Verify it doesn't exist yet
        self.assertFalse(os.path.exists(nested_dir))

        # Create the nested directory
        result = self.create_directory(nested_dir)

        # Check the result message
        self.assertIn("Successfully created directory", result)

        # Verify all levels of the directory now exist
        self.assertTrue(os.path.isdir(os.path.join(self.test_dir, "parent")))
        self.assertTrue(os.path.isdir(os.path.join(self.test_dir, "parent/child")))
        self.assertTrue(os.path.isdir(nested_dir))

    def test_edit_file_diff(self):
        """Test editing a file using edit_file_diff."""
        # Define replacements to make
        replacements = {"Line 2": "Modified Line 2"}

        # Edit the file
        result = self.edit_file_diff(
            self.ctx, self.test_file, replacements=replacements
        )

        # Check the result message
        self.assertIn("Applied", result)

        # With the improved behavior, it should include the diff for small changes
        self.assertIn("Diff", result)

        # Verify the content was modified correctly
        with open(self.test_file, "r") as f:
            content = f.read()
        self.assertIn("Modified Line 2", content)
        self.assertIn("This is a test file", content)
        self.assertIn("Line 3", content)

    def test_edit_file_diff_insert(self):
        """Test editing a file using edit_file_diff with insertions."""

        # Define insertions to make
        inserts = {"Line 3\n": "Additional line after Line 3\n"}

        # Edit the file
        result = self.edit_file_diff(self.ctx, self.test_file, inserts=inserts)

        # Check the result message
        self.assertIn("Applied", result)

        # With the improved behavior, it should include the diff for small changes
        self.assertIn("Diff", result)

        # Verify the content was modified correctly
        with open(self.test_file, "r") as f:
            content = f.read()
        self.assertIn("Additional line after Line 3", content)

    def test_write_file_new(self):
        """Test writing to a new file."""
        # Define a new file path
        new_file = os.path.join(self.test_dir, "new_file.txt")
        content = "This is a new file\nWith multiple lines\n"

        # Verify the file doesn't exist yet
        self.assertFalse(os.path.exists(new_file))

        # Write the file
        result = self.write_file(self.ctx, new_file, content)

        # Check the result message
        self.assertIn("Successfully wrote", result)

        # Verify the file exists and has the correct content
        self.assertTrue(os.path.exists(new_file))
        with open(new_file, "r") as f:
            file_content = f.read()
        self.assertEqual(file_content, content)

    def test_write_file_existing(self):
        """Test overwriting an existing file."""
        # Use the existing test file
        new_content = "This is updated content\nIn the existing file\n"

        # Write the file
        result = self.write_file(self.ctx, self.test_file, new_content)

        # Check the result message
        self.assertIn("Successfully wrote", result)

        # Verify the file has the updated content
        with open(self.test_file, "r") as f:
            file_content = f.read()
        self.assertEqual(file_content, new_content)
        self.assertNotEqual(
            file_content, self.test_content
        )  # Should be different from original

    def test_write_file_invalid_path(self):
        """Test writing to an invalid path."""
        # Define an invalid path (outside allowed directories)
        invalid_path = "/tmp/outside_allowed_dir.txt"
        content = "Content that should not be written"

        # Attempt to write to an invalid path
        with self.assertRaises(Exception):
            self.write_file(self.ctx, invalid_path, content)

    def test_list_directory(self):
        """Test listing directory contents."""
        # List the test directory
        result = self.list_directory(self.test_dir)

        # Check the result contains expected files and directories
        self.assertIn("Contents of", result)
        self.assertIn("test_file.txt", result)
        self.assertIn("test_subdir", result)

    def test_list_nonexistent_directory(self):
        """Test listing a nonexistent directory."""
        # Path to a nonexistent directory
        nonexistent_dir = os.path.join(self.test_dir, "nonexistent_dir")

        # Try to list a nonexistent directory
        result = self.list_directory(nonexistent_dir)

        # Check the result message
        self.assertIn("Error", result)
        self.assertIn("not a directory", result)

    def test_read_file(self):
        """Test reading a file."""
        # Read the test file
        result = self.read_file(self.test_file)

        # Check the result contains the expected content
        self.assertIn("This is a test file", result)
        self.assertIn("Line 2", result)
        self.assertIn("Line 3", result)

    def test_read_nonexistent_file(self):
        """Test reading a nonexistent file."""
        # Path to a nonexistent file
        nonexistent_file = os.path.join(self.test_dir, "nonexistent.txt")

        # Try to read a nonexistent file
        result = self.read_file(nonexistent_file)

        # Check the result message
        self.assertIn("Error", result)

    def test_read_multiple_files(self):
        """Test reading multiple files simultaneously."""
        # Create additional test files
        test_file2 = os.path.join(self.test_dir, "another_file.txt")
        with open(test_file2, "w") as f:
            f.write("Content of another file\nLine 2\n")

        # Read multiple files
        paths = [self.test_file, test_file2]
        result = self.read_multiple_files(self.ctx, paths)

        # Check the result contains the content of both files
        self.assertIn("test_file.txt", result)
        self.assertIn("another_file.txt", result)
        self.assertIn("This is a test file", result)
        self.assertIn("Content of another file", result)

    def test_read_multiple_nonexistent_files(self):
        """Test reading multiple files with some nonexistent."""
        # Create a list with one existing and one nonexistent file
        nonexistent_file = os.path.join(self.test_dir, "nonexistent.txt")
        paths = [self.test_file, nonexistent_file]

        # Read multiple files
        result = self.read_multiple_files(self.ctx, paths)

        # Check the result contains the content of the existing file
        # and an error for the nonexistent file
        self.assertIn("test_file.txt", result)
        self.assertIn("This is a test file", result)
        self.assertIn("Error", result)  # Should show error for nonexistent file

    def test_directory_tree_basic(self):
        """Test the directory_tree function for basic functionality."""
        # Create a nested directory structure
        nested_dir = os.path.join(self.test_dir, "tree_test/level1/level2")
        os.makedirs(nested_dir, exist_ok=True)

        # Create some files at different levels
        with open(os.path.join(self.test_dir, "tree_test/root.txt"), "w") as f:
            f.write("Root level file\n")

        with open(os.path.join(self.test_dir, "tree_test/level1/mid.txt"), "w") as f:
            f.write("Mid level file\n")

        with open(
            os.path.join(self.test_dir, "tree_test/level1/level2/leaf.txt"), "w"
        ) as f:
            f.write("Leaf level file\n")

        # Get directory tree
        result = self.directory_tree(os.path.join(self.test_dir, "tree_test"))

        # Check the result contains all directories and files
        self.assertIn("tree_test", result)
        self.assertIn("level1", result)
        self.assertIn("level2", result)
        self.assertIn("root.txt", result)
        self.assertIn("mid.txt", result)
        self.assertIn("leaf.txt", result)

    def test_directory_tree_with_metadata(self):
        """Test the directory_tree function with metadata options."""
        # Create a test file with known content
        test_file = os.path.join(self.test_dir, "metadata_test.txt")
        with open(test_file, "w") as f:
            f.write("Line 1\nLine 2\nLine 3\n")

        # Get directory tree with metadata
        result = self.directory_tree(
            self.test_dir, show_line_count=True, show_size=True
        )

        # Check that metadata is included
        self.assertIn("metadata_test.txt", result)
        self.assertIn("lines", result.lower())  # Line count metadata
        self.assertIn("bytes", result.lower())  # Size metadata


if __name__ == "__main__":
    unittest.main()
