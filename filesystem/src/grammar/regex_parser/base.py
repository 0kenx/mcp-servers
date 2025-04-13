"""
Base classes and types for language parsers.
"""

import re
from enum import Enum
from typing import List, Dict, Optional, Any, Tuple


class ElementType(Enum):
    """Types of code elements that can be identified by parsers."""

    FUNCTION = "function"
    METHOD = "method"
    CLASS = "class"
    INTERFACE = "interface"
    ENUM = "enum"
    VARIABLE = "variable"
    CONSTANT = "constant"
    IMPORT = "import"
    MODULE = "module"
    STRUCT = "struct"
    TRAIT = "trait"
    IMPL = "impl"
    CONTRACT = "contract"
    TYPE_DEFINITION = "type_definition"
    DECORATOR = "decorator"
    DOCSTRING = "docstring"
    NAMESPACE = "namespace"
    UNKNOWN = "unknown"


class CodeElement:
    """
    Represents a code element such as a function, class, variable, etc.

    The CodeElement stores metadata about code symbols including:
    - docstrings: Documentation strings preceding the symbol definition
    - decorators: Function/class decorators in languages that support them
    - annotations: Type annotations, return types, etc.
    - visibility: Public/private/protected modifiers
    - attributes: Additional language-specific attributes
    """

    def __init__(
        self,
        element_type: ElementType,
        name: str,
        start_line: int,
        end_line: int,
        code: str,
        parent: Optional["CodeElement"] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        """
        Initialize a code element.

        Args:
            element_type: Type of code element
            name: Name of the element
            start_line: Starting line number (1-based)
            end_line: Ending line number (1-based)
            code: Full code of the element
            parent: Parent element if nested
            metadata: Additional information about the element
        """
        self.element_type = element_type
        self.name = name
        self.start_line = start_line
        self.end_line = end_line
        self.code = code
        self.parent = parent
        self.metadata = metadata or {}
        self.children: List[CodeElement] = []

        # If this element has a parent, add it to the parent's children
        if parent:
            parent.children.append(self)

    def __repr__(self):
        return f"{self.element_type.value}('{self.name}', lines {self.start_line}-{self.end_line})"

    def get_full_name(self) -> str:
        """
        Get the fully qualified name including parent names.
        """
        if self.parent:
            parent_name = self.parent.get_full_name()
            return f"{parent_name}.{self.name}" if parent_name else self.name
        return self.name

    def contains_line(self, line_number: int) -> bool:
        """Check if the element contains the given line number."""
        return self.start_line <= line_number <= self.end_line


class BaseParser:
    """
    Base parser class with common utilities for all language parsers.

    Includes support for:
    - Handling incomplete code with unmatched braces or indentation issues
    - Extracting metadata from symbols (docstrings, decorators, etc.)
    - Common utility methods for all parsers
    """

    def __init__(self):
        """Initialize the base parser."""
        self.elements: List[CodeElement] = []
        self.language = "generic"
        self.handle_incomplete_code = True
        self.language_aware_preprocessing = (
            True  # Enable advanced preprocessing by default
        )
        self._metadata_extractor = None
        self._was_code_modified = False
        self._preprocessing_diagnostics = None

    def parse(self, code: str) -> List[CodeElement]:
        """
        Parse the code and return a list of identified elements.

        Args:
            code: Source code to parse

        Returns:
            A list of CodeElement objects
        """
        # First, preprocess the code to handle incomplete syntax if enabled
        if self.handle_incomplete_code:
            preprocessed_code, was_modified = self.preprocess_incomplete_code(code)
            self._was_code_modified = was_modified

            if was_modified:
                # Use the preprocessed code for parsing
                code = preprocessed_code

        # Actual parsing is implemented by subclasses
        raise NotImplementedError("Subclasses must implement parse method")

    def find_function(self, code: str, name: str) -> Optional[CodeElement]:
        """
        Find a function by name in the code.

        Args:
            code: Source code to search
            name: Function name to find

        Returns:
            CodeElement if found, None otherwise
        """
        elements = self.parse(code)
        for element in elements:
            if (
                element.element_type in (ElementType.FUNCTION, ElementType.METHOD)
                and element.name == name
            ):
                return element
        return None

    def find_function_at_line(
        self, code: str, line_number: int
    ) -> Optional[CodeElement]:
        """
        Find the function that contains the given line number.

        Args:
            code: Source code to search
            line_number: Line number to find (1-based)

        Returns:
            CodeElement if found, None otherwise
        """
        elements = self.parse(code)
        for element in elements:
            if element.element_type in (
                ElementType.FUNCTION,
                ElementType.METHOD,
            ) and element.contains_line(line_number):
                return element
        return None

    def get_all_globals(self, code: str) -> Dict[str, CodeElement]:
        """
        Get all global elements in the code.

        Args:
            code: Source code to search

        Returns:
            Dictionary mapping element names to CodeElement objects
        """
        elements = self.parse(code)
        globals_dict = {}

        for element in elements:
            # Only include top-level elements (no parent)
            if not element.parent:
                globals_dict[element.name] = element

        return globals_dict

    def get_functions(self, code: str) -> List[CodeElement]:
        """
        Get all functions in the code.

        Args:
            code: Source code to search

        Returns:
            List of function/method CodeElements
        """
        elements = self.parse(code)
        return [
            e
            for e in elements
            if e.element_type in (ElementType.FUNCTION, ElementType.METHOD)
        ]

    def get_element_by_name(self, code: str, name: str) -> Optional[CodeElement]:
        """
        Find an element by name in the code.

        Args:
            code: Source code to search
            name: Element name to find

        Returns:
            CodeElement if found, None otherwise
        """
        elements = self.parse(code)
        for element in elements:
            if element.name == name:
                return element
        return None

    def check_syntax_validity(self, code: str) -> bool:
        """
        Check if the code has valid syntax according to the language rules.
        Basic implementation that will be overridden by language-specific parsers.

        Args:
            code: Source code to check

        Returns:
            True if syntax appears valid, False otherwise
        """
        # Default implementation always returns True,
        # language-specific parsers should override this
        return True

    @staticmethod
    def _count_indentation(line: str) -> int:
        """Count the number of leading spaces in a line."""
        return len(line) - len(line.lstrip())

    @staticmethod
    def _split_into_lines(code: str) -> List[str]:
        """Split code into lines, preserving line numbers."""
        return code.splitlines()

    @staticmethod
    def _join_lines(lines: List[str]) -> str:
        """Join lines back into a string."""
        return "\n".join(lines)

    @staticmethod
    def _strip_comments(
        code: str,
        single_line_comment: str,
        multi_line_start: Optional[str] = None,
        multi_line_end: Optional[str] = None,
    ) -> str:
        """
        Remove comments from code.

        Args:
            code: Source code
            single_line_comment: Symbol that starts a single-line comment (e.g. '//')
            multi_line_start: Symbol that starts a multi-line comment (e.g. '/*')
            multi_line_end: Symbol that ends a multi-line comment (e.g. '*/')

        Returns:
            Code with comments removed
        """
        lines = code.splitlines()
        result = []
        in_multi_line = False

        for line in lines:
            if not in_multi_line:
                # Check for single line comments
                if single_line_comment in line:
                    # Make sure it's not inside a string
                    parts = re.split(r'([\'"]).*?\1', line)
                    # If we have odd number of parts, we're inside a string
                    if len(parts) % 2 == 1:
                        comment_pos = line.find(single_line_comment)
                        line = line[:comment_pos]

                # Check for start of multi-line comment
                if multi_line_start and multi_line_start in line and multi_line_end:
                    # Make sure it's not inside a string
                    parts = re.split(r'([\'"]).*?\1', line)
                    # If we have odd number of parts, we're inside a string
                    if len(parts) % 2 == 1:
                        start_pos = line.find(multi_line_start)
                        end_pos = line.find(
                            multi_line_end, start_pos + len(multi_line_start)
                        )

                        if end_pos != -1:
                            # Multi-line comment starts and ends on the same line
                            line = (
                                line[:start_pos]
                                + " " * (end_pos + len(multi_line_end) - start_pos)
                                + line[end_pos + len(multi_line_end) :]
                            )
                        else:
                            # Multi-line comment starts but doesn't end on this line
                            line = line[:start_pos]
                            in_multi_line = True
            else:
                # We're in a multi-line comment, look for the end
                if multi_line_end and multi_line_end in line:
                    end_pos = line.find(multi_line_end)
                    line = (
                        " " * (end_pos + len(multi_line_end))
                        + line[end_pos + len(multi_line_end) :]
                    )
                    in_multi_line = False
                else:
                    # Still in multi-line comment, replace line with spaces
                    line = " " * len(line)

            result.append(line)

        return "\n".join(result)

    def preprocess_incomplete_code(self, code: str) -> Tuple[str, bool]:
        """
        Preprocess potentially incomplete code.

        This method applies various strategies to handle incomplete code with
        unmatched braces, incorrect indentation, etc. It ensures the parser
        can still extract useful information even from invalid code.

        By default, uses basic preprocessing. If language_aware_preprocessing is True,
        it will use more advanced language-specific strategies.

        Args:
            code: Source code that might be incomplete

        Returns:
            Tuple of (preprocessed code, was_modified flag)
        """
        if not self.handle_incomplete_code:
            return code, False

        if (
            hasattr(self, "language_aware_preprocessing")
            and self.language_aware_preprocessing
        ):
            # Use advanced language-aware preprocessing
            from .language_aware_preprocessing import get_preprocessor

            preprocessor = get_preprocessor(self.language)
            processed_code, was_modified, self._preprocessing_diagnostics = (
                preprocessor.preprocess_code(code)
            )
            return processed_code, was_modified
        else:
            # Use basic preprocessing
            from .incomplete_code_handler import IncompleteCodeHandler

            return IncompleteCodeHandler.preprocess_code(code)

    def extract_metadata(self, code: str, line_idx: int) -> Dict[str, Any]:
        """
        Extract metadata from code at the given line index.

        Args:
            code: Source code
            line_idx: Line index where the symbol starts

        Returns:
            Dictionary of extracted metadata
        """
        if not self._metadata_extractor:
            from .metadata_extractor import get_metadata_extractor

            self._metadata_extractor = get_metadata_extractor(self.language)

        return self._metadata_extractor.extract_metadata(code, line_idx)

    def was_code_modified(self) -> bool:
        """
        Check if the code was modified during preprocessing.

        Returns:
            True if code was modified to handle incomplete syntax
        """
        return self._was_code_modified

    def get_preprocessing_diagnostics(self) -> Optional[Dict[str, Any]]:
        """
        Get detailed diagnostics about the preprocessing that was applied.

        Returns:
            Dictionary with preprocessing diagnostics or None if no advanced preprocessing was done
        """
        return self._preprocessing_diagnostics
