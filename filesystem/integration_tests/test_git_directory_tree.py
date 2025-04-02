#!/usr/bin/env python3
"""
Integration tests for the MCP filesystem server's directory_tree function in git repositories.

These tests verify that the directory_tree function works correctly in git repositories,
especially the fix for displaying directories correctly when inside a git repository.
"""

import os
import sys
import unittest
import tempfile
import shutil
from pathlib import Path
import subprocess

# Add the parent directory to the path so we can import the module
sys.path.insert(0, str(Path(__file__).parent.parent))

# Import necessary modules
from src.filesystem import full_directory_tree

class MockContext:
    """Mock context for the MCP tools."""

    def __init__(self, client_id="test_client", request_id="test_request"):
        """Initialize a mock context with the given client_id and request_id.

        Args:
            client_id: The client ID to use for the mock context
            request_id: The request ID to use for the mock context
        """
        self.client_id = client_id
        self.request_id = request_id


class TestGitDirectoryTree(unittest.TestCase):
    """Test the directory_tree function with git repositories."""

    @classmethod
    def setUpClass(cls):
        """Set up the test environment once for all tests."""
        # Create a temporary directory for testing
        cls.test_dir = tempfile.mkdtemp(prefix="mcp_fs_git_test_")
        print(f"Git test directory: {cls.test_dir}")

        # Set up the global variables needed by the server
        global SERVER_ALLOWED_DIRECTORIES, WORKING_DIRECTORY
        SERVER_ALLOWED_DIRECTORIES = [cls.test_dir]
        WORKING_DIRECTORY = cls.test_dir

        # Initialize git for testing
        cls._init_git()

        # Import the functions that rely on these globals
        # This needs to be done after setting the globals
        from src.filesystem import directory_tree

        cls.directory_tree = directory_tree

    @classmethod
    def _init_git(cls):
        """Initialize a git repository for testing."""
        # Check if git is available
        if not shutil.which("git"):
            raise unittest.SkipTest("Git not available, skipping tests")

        # Initialize git repository
        subprocess.run(
            ["git", "init"], 
            cwd=cls.test_dir, 
            check=True, 
            capture_output=True
        )

        # Configure git user
        subprocess.run(
            ["git", "config", "user.email", "test@example.com"],
            cwd=cls.test_dir,
            check=True,
            capture_output=True
        )
        subprocess.run(
            ["git", "config", "user.name", "Test User"],
            cwd=cls.test_dir,
            check=True,
            capture_output=True
        )

        # Add git repository to safe.directory to avoid Git security warnings
        subprocess.run(
            ["git", "config", "--global", "--add", "safe.directory", cls.test_dir],
            check=False,
            capture_output=True
        )

    def setUp(self):
        """Set up the test environment for each test."""
        # Create a mock context for the MCP tools
        self.ctx = MockContext()

        # Create test files and directories
        self.tracked_file = os.path.join(self.test_dir, "tracked_file.txt")
        with open(self.tracked_file, "w") as f:
            f.write("This is a tracked file\n")

        # Create subdirectory with a file
        self.test_subdir = os.path.join(self.test_dir, "test_subdir")
        os.makedirs(self.test_subdir, exist_ok=True)
        
        self.tracked_file2 = os.path.join(self.test_subdir, "tracked_file2.txt")
        with open(self.tracked_file2, "w") as f:
            f.write("This is another tracked file\n")

        # Add and commit test files
        subprocess.run(
            ["git", "add", "."],
            cwd=self.test_dir,
            check=True,
            capture_output=True
        )
        subprocess.run(
            ["git", "commit", "-m", "Add test files"],
            cwd=self.test_dir,
            check=True,
            capture_output=True
        )

        # Create an untracked file
        self.untracked_file = os.path.join(self.test_dir, "untracked_file.txt")
        with open(self.untracked_file, "w") as f:
            f.write("This is an untracked file\n")

        # Create a .gitignore file
        self.gitignore_file = os.path.join(self.test_dir, ".gitignore")
        with open(self.gitignore_file, "w") as f:
            f.write("ignored_dir/\n*.ignored\n")

        # Create ignored directory and file
        self.ignored_dir = os.path.join(self.test_dir, "ignored_dir")
        os.makedirs(self.ignored_dir, exist_ok=True)
        
        self.ignored_file = os.path.join(self.ignored_dir, "ignored_file.txt")
        with open(self.ignored_file, "w") as f:
            f.write("This is an ignored file\n")
            
        self.ignored_file2 = os.path.join(self.test_dir, "file.ignored")
        with open(self.ignored_file2, "w") as f:
            f.write("This is another ignored file\n")

        # Add and commit .gitignore
        subprocess.run(
            ["git", "add", ".gitignore"],
            cwd=self.test_dir,
            check=True,
            capture_output=True
        )
        subprocess.run(
            ["git", "commit", "-m", "Add gitignore"],
            cwd=self.test_dir,
            check=True,
            capture_output=True
        )

    def tearDown(self):
        """Clean up after each test."""
        # Clean git repository by removing all files and commits
        try:
            # Clear all files and reset repository
            for item in os.listdir(self.test_dir):
                if item == ".git":
                    continue  # Don't remove the .git directory
                    
                item_path = os.path.join(self.test_dir, item)
                try:
                    if os.path.isdir(item_path):
                        shutil.rmtree(item_path)
                    else:
                        os.remove(item_path)
                except Exception as e:
                    print(f"Warning: Could not remove {item_path}: {e}")
        except Exception as e:
            print(f"Warning: Error cleaning git repository: {e}")

    @classmethod
    def tearDownClass(cls):
        """Clean up after all tests."""
        # Remove the temporary directory
        try:
            shutil.rmtree(cls.test_dir)
            print(f"Removed test directory: {cls.test_dir}")
        except Exception as e:
            print(f"Warning: Could not remove test directory {cls.test_dir}: {e}")

    def test_directory_tree_in_git_repo(self):
        """Test directory_tree function inside a git repository."""
        # Call directory_tree on the root of the git repository
        result = self.directory_tree(self.test_dir)
        
        # Check that tracked files are included
        self.assertIn("tracked_file.txt", result)
        self.assertIn("test_subdir", result)
        self.assertIn("tracked_file2.txt", result)
        self.assertIn(".gitignore", result)
        
        # Check that untracked files are NOT included by default
        self.assertNotIn("untracked_file.txt", result)
        
        # Check that ignored files are NOT included by default
        self.assertNotIn("ignored_dir", result)
        self.assertNotIn("ignored_file.txt", result)
        self.assertNotIn("file.ignored", result)

    def test_directory_tree_include_ignored_files(self):
        """Test directory_tree with show_files_ignored_by_git=True."""
        # Call directory_tree with show_files_ignored_by_git=True
        result = self.directory_tree(self.test_dir, show_files_ignored_by_git=True)
        
        # Now all files should be included
        self.assertIn("tracked_file.txt", result)
        self.assertIn("untracked_file.txt", result)
        self.assertIn("ignored_dir", result)
        self.assertIn("file.ignored", result)

    def test_directory_tree_subdirectory(self):
        """Test directory_tree on a subdirectory of a git repository."""
        # Call directory_tree on a subdirectory
        result = self.directory_tree(self.test_subdir)
        
        # Check that only files in the subdirectory are included
        self.assertIn("tracked_file2.txt", result)
        self.assertNotIn("tracked_file.txt", result)

    def test_directory_tree_with_metadata(self):
        """Test directory_tree with various metadata options."""
        # Call directory_tree with metadata options
        result = self.directory_tree(
            self.test_dir,
            show_line_count=True,
            show_size=True
        )
        
        # Check that tracked files are included with metadata
        self.assertIn("tracked_file.txt", result)
        self.assertIn("lines", result.lower())  # Line count metadata
        self.assertIn("bytes", result.lower())  # Size metadata

    def test_directory_tree_with_working_directory_change(self):
        """Test directory_tree when working directory is different from repository path."""
        # Change the working directory to a subdirectory
        original_cwd = os.getcwd()
        os.chdir(self.test_subdir)
        
        try:
            # Call directory_tree on the root of the git repository
            result = self.directory_tree(self.test_dir)
            
            # Check that tracked files are still included
            self.assertIn("tracked_file.txt", result)
            self.assertIn("test_subdir", result)
            self.assertIn("tracked_file2.txt", result)
        finally:
            # Restore original working directory
            os.chdir(original_cwd)

if __name__ == "__main__":
    unittest.main()
