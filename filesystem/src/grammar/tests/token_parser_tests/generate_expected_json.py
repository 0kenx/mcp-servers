"""
Utility script to generate expected JSON files for token parser tests.

This script parses a source file and generates the corresponding expected JSON output.
It's helpful for creating new test cases.
"""

import os
import json
import argparse
import sys
from typing import List, Dict, Any

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from token_parser.parser_factory import ParserFactory
from token_parser.base import CodeElement


def serialize_element(element: CodeElement) -> Dict[str, Any]:
    """
    Serialize a code element to a dictionary.

    Args:
        element: The code element to serialize

    Returns:
        Dictionary representation of the element
    """
    result = {
        "name": element.name,
        "element_type": element.element_type.value if hasattr(element.element_type, "value") else element.element_type,
        "start_line": element.start_line,
        "end_line": element.end_line,
        "children": [serialize_element(child) for child in element.children]
    }
    
    # Add common attributes if available
    if hasattr(element, "parameters") and element.parameters:
        result["parameters"] = element.parameters
        
    if hasattr(element, "return_type") and element.return_type:
        result["return_type"] = element.return_type
    
    # Add language-specific attributes (not exhaustive, add more as needed)
    # JavaScript/TypeScript
    if hasattr(element, "is_async") and element.is_async:
        result["is_async"] = element.is_async
        
    if hasattr(element, "is_generator") and element.is_generator:
        result["is_generator"] = element.is_generator
        
    if hasattr(element, "is_arrow_function") and element.is_arrow_function:
        result["is_arrow_function"] = element.is_arrow_function
    
    # C/C++
    if hasattr(element, "is_static") and element.is_static:
        result["is_static"] = element.is_static
        
    if hasattr(element, "storage_class") and element.storage_class:
        result["storage_class"] = element.storage_class
    
    # Rust
    if hasattr(element, "is_pub") and element.is_pub:
        result["is_pub"] = element.is_pub
        
    if hasattr(element, "is_unsafe") and element.is_unsafe:
        result["is_unsafe"] = element.is_unsafe
    
    return result


def generate_expected_json(source_path: str, language: str) -> List[Dict[str, Any]]:
    """
    Generate expected JSON for a source file.

    Args:
        source_path: Path to the source file
        language: Language of the source file

    Returns:
        List of serialized elements
    """
    parser = ParserFactory.create_parser(language)
    if not parser:
        raise ValueError(f"No parser found for language: {language}")
    
    with open(source_path, "r") as f:
        code = f.read()
    
    elements = parser.parse(code)
    return [serialize_element(element) for element in elements]


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Generate expected JSON for token parser tests")
    parser.add_argument("source_file", help="Path to the source file")
    parser.add_argument("--language", "-l", required=True, help="Language of the source file")
    parser.add_argument("--output", "-o", help="Output JSON file path (defaults to source_file.expected.json)")
    
    args = parser.parse_args()
    
    source_path = args.source_file
    language = args.language
    
    if not os.path.exists(source_path):
        print(f"Error: Source file not found: {source_path}")
        sys.exit(1)
    
    output_path = args.output or f"{os.path.splitext(source_path)[0]}.expected.json"
    
    try:
        result = generate_expected_json(source_path, language)
        
        with open(output_path, "w") as f:
            json.dump(result, f, indent=2)
        
        print(f"Generated expected JSON: {output_path}")
    
    except Exception as e:
        print(f"Error generating expected JSON: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
