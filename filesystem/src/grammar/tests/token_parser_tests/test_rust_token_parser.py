"""
Integration tests for the Rust token parser.

This module tests the Rust token parser against a set of test files and
verifies the results against expected JSON outputs.
"""

import os
import json
import unittest
from typing import List, Dict, Any

from token_parser.parser_factory import ParserFactory
from token_parser.base import CodeElement


class TestRustTokenParser(unittest.TestCase):
    """Test class for Rust token parser."""

    def setUp(self):
        """Set up the test environment."""
        self.parser = ParserFactory.create_parser("rust")
        self.test_data_dir = os.path.join("tests", "test_data", "rs")

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

            # Add parameters if available
            if hasattr(element, "parameters") and element.parameters:
                serialized["parameters"] = element.parameters

            # Add return type if available
            if hasattr(element, "return_type") and element.return_type:
                serialized["return_type"] = element.return_type

            # Add Rust-specific properties if available
            if hasattr(element, "is_pub") and element.is_pub:
                serialized["is_pub"] = element.is_pub

            if hasattr(element, "is_async") and element.is_async:
                serialized["is_async"] = element.is_async

            if hasattr(element, "is_unsafe") and element.is_unsafe:
                serialized["is_unsafe"] = element.is_unsafe

            if hasattr(element, "impl_for") and element.impl_for:
                serialized["impl_for"] = element.impl_for

            if hasattr(element, "trait_name") and element.trait_name:
                serialized["trait_name"] = element.trait_name

            if hasattr(element, "generic_params") and element.generic_params:
                serialized["generic_params"] = element.generic_params

            if hasattr(element, "lifetime_params") and element.lifetime_params:
                serialized["lifetime_params"] = element.lifetime_params

            if hasattr(element, "derives") and element.derives:
                serialized["derives"] = element.derives

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

    def test_all_rust_files(self):
        """Test all Rust files that have corresponding expected JSON files."""
        # Get all Rust files in the test data directory
        for file in os.listdir(self.test_data_dir):
            if file.endswith(".rs"):
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
