"""
Utility functions and classes for parser tests.
"""

import os
import tempfile
from typing import List, Dict, Any, Type, Optional
from src.grammar.base import BaseParser, CodeElement, ElementType


def create_temp_file(content: str) -> str:
    """
    Create a temporary file with the given content.

    Args:
        content: Content to write to the file

    Returns:
        Path to the temporary file
    """
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".tmp") as f:
        f.write(content)
        return f.name


def cleanup_temp_file(file_path: str) -> None:
    """
    Delete a temporary file.

    Args:
        file_path: Path to the file to delete
    """
    if os.path.exists(file_path):
        os.unlink(file_path)


def find_element_by_type_and_name(
    elements: List[CodeElement], element_type: ElementType, name: str
) -> Optional[CodeElement]:
    """
    Find an element with the specified type and name.

    Args:
        elements: List of code elements to search
        element_type: Type of element to find
        name: Name of element to find

    Returns:
        The matching element, or None if not found
    """
    for element in elements:
        if element.element_type == element_type and element.name == name:
            return element
    return None


def count_elements_by_type(
    elements: List[CodeElement], element_type: ElementType
) -> int:
    """
    Count elements of a specific type.

    Args:
        elements: List of code elements to count
        element_type: Type of element to count

    Returns:
        Count of matching elements
    """
    return sum(1 for e in elements if e.element_type == element_type)


def get_children_of_element(
    elements: List[CodeElement], parent: CodeElement
) -> List[CodeElement]:
    """
    Get all child elements of a parent element.

    Args:
        elements: List of all code elements
        parent: Parent element

    Returns:
        List of child elements
    """
    return [e for e in elements if e.parent == parent]


def verify_element_properties(
    element: CodeElement, expected_properties: Dict[str, Any]
) -> List[str]:
    """
    Verify properties of an element match expected values.

    Args:
        element: Element to check
        expected_properties: Dictionary of expected properties

    Returns:
        List of error messages, empty if all properties match
    """
    errors = []

    # Check element properties
    for prop, expected_value in expected_properties.items():
        if prop == "metadata":
            # Handle metadata specially
            for meta_key, meta_value in expected_value.items():
                actual_value = element.metadata.get(meta_key)
                if isinstance(meta_value, str) and isinstance(actual_value, str):
                    if meta_value not in actual_value:
                        errors.append(
                            f"Metadata '{meta_key}' value '{actual_value}' does not contain '{meta_value}'"
                        )
                elif actual_value != meta_value:
                    errors.append(
                        f"Metadata '{meta_key}' expected '{meta_value}', got '{actual_value}'"
                    )
        else:
            # Check regular property
            actual_value = getattr(element, prop)
            if actual_value != expected_value:
                errors.append(
                    f"Property '{prop}' expected '{expected_value}', got '{actual_value}'"
                )

    return errors


class ParserTestHelper:
    """
    Helper class for parser tests.
    """

    def __init__(self, parser_class: Type[BaseParser]):
        """Initialize with a parser class."""
        self.parser = parser_class()

    def parse_code(self, code: str) -> List[CodeElement]:
        """Parse code and return elements."""
        return self.parser.parse(code)

    def find_element(
        self, elements: List[CodeElement], element_type: ElementType, name: str
    ) -> Optional[CodeElement]:
        """Find an element by type and name."""
        return find_element_by_type_and_name(elements, element_type, name)

    def count_elements(
        self, elements: List[CodeElement], element_type: ElementType
    ) -> int:
        """Count elements of a specific type."""
        return count_elements_by_type(elements, element_type)

    def get_children(
        self, elements: List[CodeElement], parent: CodeElement
    ) -> List[CodeElement]:
        """Get children of a parent element."""
        return get_children_of_element(elements, parent)

    def verify_properties(
        self, element: CodeElement, expected_properties: Dict[str, Any]
    ) -> List[str]:
        """Verify element properties."""
        return verify_element_properties(element, expected_properties)
