"""
Integration tests for the CSS token parser.

This module tests the CSS token parser against a set of test files and
verifies the results against expected JSON outputs.
"""

import os
import json
import unittest
from typing import List, Dict, Any

from token_parser.parser_factory import ParserFactory
from token_parser.base import CodeElement


class TestCSSTokenParser(unittest.TestCase):
    """Test class for CSS token parser."""

    def setUp(self):
        """Set up the test environment."""
        self.parser = ParserFactory.create_parser("css")
        # CSS tests might be in a different location, adjust as needed
        self.test_data_dir = os.path.join("tests", "test_data", "css")

        # Create directory if it doesn't exist
        if not os.path.exists(self.test_data_dir):
            os.makedirs(self.test_data_dir)

    def _load_expected_result(self, expected_path: str) -> List[Dict[str, Any]]:
        """
        Load expected result from a JSON file.

        Args:
            expected_path: Path to the expected result JSON file

        Returns:
            List of dictionaries containing expected elements
        """
        with open(expected_path, "r") as f:
            return json.load(f)

    def _serialize_elements(self, elements: List[CodeElement]) -> List[Dict[str, Any]]:
        """
        Serialize code elements to a comparable format.

        Args:
            elements: List of code elements

        Returns:
            List of serialized elements
        """
        result = []
        for element in elements:
            serialized = {
                "name": element.name,
                "element_type": element.element_type.value
                if hasattr(element.element_type, "value")
                else element.element_type,
                "start_line": element.start_line,
                "end_line": element.end_line,
                "children": self._serialize_elements(element.children),
            }

            # Add CSS-specific properties if available
            if hasattr(element, "selector") and element.selector:
                serialized["selector"] = element.selector

            if hasattr(element, "properties") and element.properties:
                serialized["properties"] = element.properties

            if hasattr(element, "media_query") and element.media_query:
                serialized["media_query"] = element.media_query

            if hasattr(element, "is_keyframes") and element.is_keyframes:
                serialized["is_keyframes"] = element.is_keyframes

            if hasattr(element, "is_import") and element.is_import:
                serialized["is_import"] = element.is_import

            result.append(serialized)
        return result

    def _test_file(self, test_file: str):
        """
        Test a specific file.

        Args:
            test_file: Name of the test file
        """
        source_path = os.path.join(self.test_data_dir, test_file)
        expected_path = os.path.join(
            self.test_data_dir, f"{os.path.splitext(test_file)[0]}.expected.json"
        )

        # Skip if expected JSON doesn't exist
        if not os.path.exists(expected_path):
            self.skipTest(f"Expected result file not found: {expected_path}")

        # Read the source code
        with open(source_path, "r") as f:
            code = f.read()

        # Parse the code
        elements = self.parser.parse(code)

        # Load the expected result
        expected = self._load_expected_result(expected_path)

        # Compare results
        serialized = self._serialize_elements(elements)
        self.assertEqual(
            expected,
            serialized,
            f"Mismatch in parsing {test_file}: Expected {expected}, got {serialized}",
        )

    def test_all_css_files(self):
        """Test all CSS files that have corresponding expected JSON files."""
        # Get all CSS files in the test data directory
        if not os.path.exists(self.test_data_dir):
            self.skipTest(f"Test data directory not found: {self.test_data_dir}")

        for file in os.listdir(self.test_data_dir):
            if file.endswith(".css"):
                # Check if there's a corresponding expected JSON file
                base_name = os.path.splitext(file)[0]
                expected_path = os.path.join(
                    self.test_data_dir, f"{base_name}.expected.json"
                )

                if os.path.exists(expected_path):
                    with self.subTest(file=file):
                        self._test_file(file)


if __name__ == "__main__":
    unittest.main()
