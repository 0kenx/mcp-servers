"""
Integration tests for the Python token parser.

This module tests the Python token parser against a set of test files and
verifies the results against expected JSON outputs.
"""

import os
import json
import unittest
from typing import List, Dict, Any, Union

from token_parser.parser_factory import ParserFactory


class TestPythonTokenParser(unittest.TestCase):
    """Test class for Python token parser."""

    def setUp(self):
        """Set up the test environment."""
        self.parser = ParserFactory.create_parser("python")
        self.test_data_dir = os.path.join("tests", "test_data", "py")

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

    def _serialize_elements(self, elements: List[Any]) -> List[Dict[str, Any]]:
        """
        Serialize code elements to a comparable format.

        Args:
            elements: List of code elements

        Returns:
            List of serialized elements
        """
        result = []

        if not elements:
            return []

        for element in elements:
            # Now we're primarily dealing with CodeElement objects
            if hasattr(element, "element_type"):
                # Convert element_type enum to string
                element_type = element.element_type.value if hasattr(element.element_type, "value") else str(element.element_type)
                
                serialized = {
                    "name": element.name if hasattr(element, "name") else "",
                    "element_type": element_type,
                    "start_line": element.start_line if hasattr(element, "start_line") else 0,
                    "end_line": element.end_line if hasattr(element, "end_line") else 0,
                    "children": self._serialize_elements(element.children if hasattr(element, "children") else [])
                }
                
                # Add parameters if available
                if hasattr(element, "parameters") and element.parameters:
                    serialized["parameters"] = element.parameters
                
                # Add return type if available
                if hasattr(element, "return_type") and element.return_type is not None:
                    serialized["return_type"] = element.return_type
                    
            # Fallback for dict representation (for backward compatibility)
            elif isinstance(element, dict):
                serialized = {}
                
                # Map common fields
                if 'name' in element:
                    serialized['name'] = element['name']
                
                # Map 'type' to 'element_type'
                if 'type' in element:
                    serialized['element_type'] = element['type']
                
                # Line numbers
                serialized['start_line'] = element.get('start_line', element.get('start', 1))
                serialized['end_line'] = element.get('end_line', element.get('end', 1))
                
                # Process children recursively
                serialized['children'] = self._serialize_elements(element.get('children', []))
                
                # Add parameters if available
                if 'parameters' in element:
                    serialized['parameters'] = element['parameters']
                
                # Add return type if available
                if 'return_type' in element:
                    serialized['return_type'] = element['return_type']
            else:
                # Skip unknown element types
                continue
                
            result.append(serialized)
        return result

    def _test_file(self, test_file: str):
        """
        Test a specific file.

        Args:
            test_file: Name of the test file
        """
        source_path = os.path.join(self.test_data_dir, test_file)
        expected_path = os.path.join(self.test_data_dir, f"{os.path.splitext(test_file)[0]}.expected.json")

        print(f"Testing file: {test_file}")
        print(f"Source path: {source_path}")
        print(f"Expected path: {expected_path}")

        # Skip if expected JSON doesn't exist
        if not os.path.exists(expected_path):
            print(f"Expected result file not found: {expected_path}")
            self.skipTest(f"Expected result file not found: {expected_path}")

        # Read the source code
        try:
            with open(source_path, "r") as f:
                code = f.read()
            print(f"Source code length: {len(code)} characters")
            print(f"Source code preview: {code[:100]}...")
        except Exception as e:
            self.fail(f"Error reading source file: {e}")

        # Parse the code
        try:
            parsed_result = self.parser.parse(code)
            print(f"Parser result type: {type(parsed_result)}")

            # We now expect a list of CodeElement objects
            elements = parsed_result
            print(f"Elements type: {type(elements)}")
            if hasattr(elements, "__len__"):
                print(f"Number of elements: {len(elements)}")
                if len(elements) > 0:
                    print(f"First element type: {type(elements[0])}")
                    print(f"First element name: {elements[0].name}")
                    if hasattr(elements[0], "parameters"):
                        print(f"Parameters: {elements[0].parameters}")
                    if hasattr(elements[0], "return_type"):
                        print(f"Return type: {elements[0].return_type}")
        except Exception as e:
            self.fail(f"Error parsing code: {e}")

        # Load the expected result
        try:
            expected = self._load_expected_result(expected_path)
            print(f"Expected result length: {len(expected)}")
            print(f"Expected result preview: {expected}")
        except Exception as e:
            self.fail(f"Error loading expected result: {e}")

        # Serialize and compare results
        try:
            serialized = self._serialize_elements(elements)
            print(f"Serialized result length: {len(serialized)}")
            print(f"Serialized result preview: {serialized}")

            self.assertEqual(
                expected, serialized,
                f"Mismatch in parsing {test_file}: Expected {expected}, got {serialized}"
            )
            print("Test passed successfully!")
        except Exception as e:
            print(f"Error during comparison: {e}")
            raise

    def test_specific_file(self):
        """Test a specific Python file that we know exists."""
        test_file = "test_python_parser_1.py"
        expected_path = os.path.join(self.test_data_dir, "test_python_parser_1.expected.json")

        if not os.path.exists(os.path.join(self.test_data_dir, test_file)):
            self.fail(f"Test file not found: {test_file}")

        if not os.path.exists(expected_path):
            self.fail(f"Expected JSON not found: {expected_path}")

        self._test_file(test_file)
        
    def test_all_python_files(self):
        """Test all Python files with corresponding expected JSON files."""
        # This test can be uncommented when more expected JSON files are created
        json_files = [f for f in os.listdir(self.test_data_dir) if f.endswith('.expected.json')]
        
        if not json_files:
            self.skipTest("No expected JSON files found")
        
        print(f"Found {len(json_files)} expected JSON files")
        
        # For each JSON file, test the corresponding Python file
        for json_file in json_files:
            py_file = json_file.replace('.expected.json', '.py')
            py_path = os.path.join(self.test_data_dir, py_file)
            
            if os.path.exists(py_path):
                with self.subTest(file=py_file):
                    self._test_file(py_file)


if __name__ == "__main__":
    unittest.main()
