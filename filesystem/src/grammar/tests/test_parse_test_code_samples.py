"""
Test parsing of sample code files for all language parsers.

This module provides tests to verify that all language parsers can successfully
parse their respective test code samples.
"""

import os
import sys
import unittest
from typing import Dict, List, Type

# Add parent directory to path to import parsers
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.grammar.python import PythonParser
from src.grammar.javascript import JavaScriptParser
from src.grammar.typescript import TypeScriptParser
from src.grammar.c_cpp import CCppParser
from src.grammar.rust import RustParser
from src.grammar.base import BaseParser, CodeElement


class TestCodeSamplesParsing(unittest.TestCase):
    """Test parsing of sample code files for different languages."""

    # Directory containing test code samples
    SAMPLES_DIR = os.path.join(os.path.dirname(__file__), "test_code_samples")

    # Map of file extensions to parser classes
    PARSER_MAP = {
        ".py": PythonParser,
        ".js": JavaScriptParser,
        ".ts": TypeScriptParser,
        ".c": CCppParser,
        ".cpp": CCppParser,
        ".rs": RustParser,
    }

    def test_parse_all_samples(self):
        """Test parsing all sample files."""
        results = {}
        
        # Get all sample files
        for filename in os.listdir(self.SAMPLES_DIR):
            filepath = os.path.join(self.SAMPLES_DIR, filename)
            if not os.path.isfile(filepath):
                continue
                
            # Get file extension
            _, ext = os.path.splitext(filename)
            
            # Check if we have a parser for this extension
            if ext not in self.PARSER_MAP:
                continue
                
            # Parse the file
            parser_class = self.PARSER_MAP[ext]
            elements = self._parse_file(filepath, parser_class)
            
            # Store results
            results[filename] = {
                "elements_count": len(elements),
                "elements": elements,
                "was_modified": self._get_modified_status(parser_class),
            }
            
        # Print the results
        self._print_parsing_results(results)
        
        # Verify all files were parsed successfully
        for filename, result in results.items():
            self.assertGreater(result["elements_count"], 0, f"No elements found in {filename}")

    def _parse_file(self, filepath: str, parser_class: Type[BaseParser]) -> List[CodeElement]:
        """Parse a file with the given parser and return elements."""
        # Read the file
        with open(filepath, 'r', encoding='utf-8') as f:
            code = f.read()
            
        # Create parser and parse the code
        parser = parser_class()
        elements = parser.parse(code)
        
        return elements
        
    def _get_modified_status(self, parser_class: Type[BaseParser]) -> bool:
        """Get whether the code was modified during parsing."""
        # Create a new instance to check if _was_code_modified exists and is True
        parser = parser_class()
        if hasattr(parser, "_was_code_modified"):
            return parser._was_code_modified
        return False

    def _print_parsing_results(self, results: Dict[str, Dict]) -> None:
        """Print parsing results in a formatted way."""
        print("\n" + "=" * 80)
        print("PARSING RESULTS")
        print("=" * 80)
        
        for filename, result in sorted(results.items()):
            elements = result["elements"]
            print(f"\n{filename} ({result['elements_count']} elements):")
            
            if result["was_modified"]:
                print("  [Code was modified during parsing]")
                
            # Group elements by type
            elements_by_type = {}
            for element in elements:
                element_type = element.element_type.value
                if element_type not in elements_by_type:
                    elements_by_type[element_type] = []
                elements_by_type[element_type].append(element)
                
            # Print summary by element type
            for element_type, type_elements in sorted(elements_by_type.items()):
                print(f"  {element_type}: {len(type_elements)}")
                
            # Print details of each element
            print("  Details:")
            for element in elements:
                parent_info = f" (parent: {element.parent.name})" if element.parent else ""
                metadata_info = ""
                
                # Add metadata summary if available
                if hasattr(element, "metadata") and element.metadata:
                    print(element.metadata)
                    metadata_keys = list(element.metadata.keys())
                    if metadata_keys:
                        metadata_info = f" [metadata: {', '.join(metadata_keys)}]"
                        
                print(f"    {element.element_type.value}: {element.name} "
                      f"(lines {element.start_line}-{element.end_line}){parent_info}{metadata_info}")
        
        print("\n" + "=" * 80)


def run_test():
    """Run the test manually."""
    test = TestCodeSamplesParsing()
    test.test_parse_all_samples()


if __name__ == "__main__":
    # Run the test manually when script is executed directly
    run_test()
