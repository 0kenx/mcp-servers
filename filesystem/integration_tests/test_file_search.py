#!/usr/bin/env python3
"""
Integration tests for the MCP filesystem server's file search functionality.

These tests verify that the file search operations work correctly, including:
- Reading files by keyword
- Reading files by regex pattern
- Reading functions by keyword
- Getting symbols from files
"""

import os
import sys
import unittest
import tempfile
import shutil
from pathlib import Path

# Initialize the test environment first
from integration_tests.test_init import MockContext

# Add the parent directory to the path so we can import the module
sys.path.insert(0, str(Path(__file__).parent.parent))

# Import the patched filesystem functions
from integration_tests.patched_filesystem import (
    _resolve_path,
    validate_path,
    _get_or_create_conversation_id,
    read_file_by_keyword,
    read_function_by_keyword,
    get_symbols,
    get_function_code,
)


class TestFileSearchMCP(unittest.TestCase):
    """Test the file search functionality of the MCP filesystem server."""

    @classmethod
    def setUpClass(cls):
        """Set up the test environment once for all tests."""
        # Create a temporary directory for testing
        cls.test_dir = tempfile.mkdtemp(prefix="mcp_fs_search_test_")
        print(f"Test directory: {cls.test_dir}")

        # Set up the global variables needed by the server
        from integration_tests.patched_filesystem import SERVER_ALLOWED_DIRECTORIES, WORKING_DIRECTORY
        SERVER_ALLOWED_DIRECTORIES.append(cls.test_dir)
        WORKING_DIRECTORY = cls.test_dir

    def setUp(self):
        """Set up the test environment for each test."""
        # Create a mock context for the MCP tools
        self.ctx = MockContext()

        # Sample Python file with multiple functions
        python_content = """#!/usr/bin/env python3
\"\"\"
Sample Python file for testing function parsing.
\"\"\"

import os
import sys
from typing import List, Dict, Optional

def simple_function():
    \"\"\"A simple function that does nothing.\"\"\"
    pass

def function_with_arguments(arg1: str, arg2: int = 0) -> bool:
    \"\"\"A function with arguments and a return type.
    
    Args:
        arg1: A string argument
        arg2: An integer argument with default value
        
    Returns:
        A boolean indicating success
    \"\"\"
    if arg1 and arg2 > 0:
        return True
    return False

class TestClass:
    \"\"\"A test class with methods.\"\"\"
    
    def __init__(self, value: str):
        \"\"\"Initialize the class.\"\"\"
        self.value = value
        
    def get_value(self) -> str:
        \"\"\"Get the stored value.\"\"\"
        return self.value
        
    def set_value(self, new_value: str) -> None:
        \"\"\"Set a new value.\"\"\"
        self.value = new_value

# A global variable
GLOBAL_CONSTANT = "This is a global constant"

def main():
    \"\"\"Main function.\"\"\"
    test = TestClass("test")
    print(test.get_value())
    
if __name__ == "__main__":
    main()
"""
        self.python_file = os.path.join(self.test_dir, "sample.py")
        with open(self.python_file, "w") as f:
            f.write(python_content)

        # Sample JavaScript file
        js_content = """/**
 * Sample JavaScript file for testing function parsing.
 */

// Import some modules
const fs = require('fs');
const path = require('path');

// A global variable
const GLOBAL_CONSTANT = "This is a global constant";

/**
 * A simple function that does nothing.
 */
function simpleFunction() {
    // This function does nothing
}

/**
 * A function with arguments and a return value.
 * @param {string} arg1 - A string argument
 * @param {number} arg2 - A number argument with default value
 * @returns {boolean} - A boolean indicating success
 */
function functionWithArguments(arg1, arg2 = 0) {
    if (arg1 && arg2 > 0) {
        return true;
    }
    return false;
}

// An arrow function
const arrowFunction = (x) => {
    return x * 2;
};

// A class with methods
class TestClass {
    /**
     * Initialize the class.
     * @param {string} value - The initial value
     */
    constructor(value) {
        this.value = value;
    }
    
    /**
     * Get the stored value.
     * @returns {string} - The stored value
     */
    getValue() {
        return this.value;
    }
    
    /**
     * Set a new value.
     * @param {string} newValue - The new value to store
     */
    setValue(newValue) {
        this.value = newValue;
    }
}

// Main function
function main() {
    const test = new TestClass("test");
    console.log(test.getValue());
}

// Call the main function
main();
"""
        self.js_file = os.path.join(self.test_dir, "sample.js")
        with open(self.js_file, "w") as f:
            f.write(js_content)

        # Sample text file with keywords
        text_content = """This is a sample text file with some keywords.
It contains multiple lines.
Line with IMPORTANT information.
Another line.
Line with DEBUG information.
More content.
Line with ERROR information.
Final line.
"""
        self.text_file = os.path.join(self.test_dir, "sample.txt")
        with open(self.text_file, "w") as f:
            f.write(text_content)

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

    def test_read_file_by_keyword(self):
        """Test reading a file by keyword."""
        # Read the text file by keyword
        result = read_file_by_keyword(self.ctx, self.text_file, "IMPORTANT")

        # Check the result contains the expected content
        self.assertIn("matching IMPORTANT", result)

    def test_read_file_by_keyword_with_context(self):
        """Test reading a file by keyword with context lines."""
        # Read the text file by keyword with context lines
        result = read_file_by_keyword(
            self.ctx,
            self.text_file,
            "IMPORTANT",
            include_lines_before=1,
            include_lines_after=1
        )

        # Check the result contains the expected content and context
        self.assertIn("matching IMPORTANT", result)

    def test_read_file_by_regex(self):
        """Test reading a file by regex pattern."""
        # Read the text file by regex pattern
        result = read_file_by_keyword(
            self.ctx,
            self.text_file,
            ".*IMPORTANT|ERROR.*",
            use_regex=True
        )

        # Check the result contains the expected content
        self.assertIn("matching .*IMPORTANT|ERROR.*", result)

    def test_read_file_by_keyword_case_insensitive(self):
        """Test reading a file by keyword with case insensitivity."""
        # Read the text file by keyword case insensitive
        result = read_file_by_keyword(
            self.ctx,
            self.text_file,
            "important",
            ignore_case=True
        )

        # Check the result contains the expected content
        self.assertIn("matching important", result)

    def test_read_function_by_keyword(self):
        """Test reading a function by keyword from a Python file."""
        # Read a function by keyword
        result = read_function_by_keyword(self.ctx, self.python_file, "function_with_arguments")

        # Check the result contains the expected function
        self.assertIn("matching function_with_arguments", result)

    def test_read_function_by_keyword_from_js(self):
        """Test reading a function by keyword from a JavaScript file."""
        # Read a function by keyword from JavaScript
        result = read_function_by_keyword(self.ctx, self.js_file, "functionWithArguments")

        # Check the result contains the expected function
        self.assertIn("matching functionWithArguments", result)

    def test_get_symbols(self):
        """Test getting all symbols from a Python file."""
        # Get all symbols from a Python file
        result = get_symbols(self.ctx, self.python_file)

        # Check the result contains the expected symbols
        self.assertIn("Symbols in", result)

    def test_get_symbols_with_filter(self):
        """Test getting filtered symbols from a Python file."""
        # Get only function symbols from a Python file
        result = get_symbols(self.ctx, self.python_file, symbol_type="function")

        # Check the result contains the expected functions
        self.assertIn("Symbols in", result)

    def test_get_function_code(self):
        """Test getting the code for a specific function."""
        # Get the code for a specific function
        result = get_function_code(self.ctx, self.python_file, "function_with_arguments")

        # Check the result contains only the expected function
        self.assertIn("function_with_arguments", result)


if __name__ == "__main__":
    unittest.main()
