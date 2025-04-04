"""
Base token parser for the grammar parser system.

This module provides the TokenParser base class that all language-specific
token parsers inherit from.
"""

from typing import List, Dict, Set, Tuple, Optional, Any, Union, Callable
from .token import Token, TokenType
from .tokenizer import Tokenizer
from .parser_state import ParserState
from .symbol_table import SymbolTable
from .context_tracker import ContextTracker
from ..base import BaseParser, CodeElement, ElementType


class TokenParser(BaseParser):
    """
    Base parser that uses tokens for parsing.
    
    This is an abstract base class. Language-specific parsers should
    inherit from this class and implement the required methods.
    """
    
    def __init__(self):
        """Initialize the token parser."""
        super().__init__()
        self.tokenizer = None  # Should be set by subclasses
        self.elements: List[CodeElement] = []
        self.state: Optional[ParserState] = None
        self.symbol_table: Optional[SymbolTable] = None
        self.context_tracker: Optional[ContextTracker] = None
    
    def parse(self, code: str) -> List[CodeElement]:
        """
        Parse the code and return a list of code elements.
        
        Args:
            code: Source code to parse
        
        Returns:
            List of code elements
        """
        # Initialize state
        self.elements = []
        self.state = ParserState()
        self.symbol_table = SymbolTable()
        self.context_tracker = ContextTracker()
        
        # Tokenize
        tokens = self.tokenize(code)
        
        # Build AST
        self.build_ast(tokens)
        
        # Validate and repair AST
        self.validate_and_repair_ast()
        
        return self.elements
    
    def tokenize(self, code: str) -> List[Token]:
        """
        Tokenize the code.
        
        Args:
            code: Source code to tokenize
        
        Returns:
            List of tokens
        """
        if not self.tokenizer:
            raise ValueError("Tokenizer not set")
        
        return self.tokenizer.tokenize(code)
    
    def build_ast(self, tokens: List[Token]) -> Dict[str, Any]:
        """
        Build an abstract syntax tree from the tokens.
        
        Args:
            tokens: List of tokens
            
        Returns:
            Dictionary representing the abstract syntax tree
        """
        raise NotImplementedError("Subclasses must implement build_ast")
    
    def validate_and_repair_ast(self) -> None:
        """
        Validate the AST and repair any issues.
        """
        self._check_for_overlapping_elements()
        self._validate_parent_child_relationships()
        self._fix_orphaned_elements()
        self._fix_element_types()
    
    def enter_context(self, type_: str, name: Optional[str] = None, 
                     metadata: Optional[Dict[str, Any]] = None,
                     start: int = -1) -> None:
        """
        Enter a new parsing context.
        
        This updates both the context_tracker and state for backward compatibility.
        
        Args:
            type_: Type of the context
            name: Optional name for the context
            metadata: Optional metadata for the context
            start: Start position of the context
        """
        if self.context_tracker:
            self.context_tracker.enter_context(type_, name, metadata, start)
        
        # For backward compatibility with state
        if self.state:
            self.state.enter_context(type_, metadata)
    
    def exit_context(self, end: int = -1) -> None:
        """
        Exit the current context.
        
        This updates both the context_tracker and state for backward compatibility.
        
        Args:
            end: End position of the context
        """
        if self.context_tracker:
            self.context_tracker.exit_context(end)
        
        # For backward compatibility with state
        if self.state:
            self.state.exit_context()
    
    def get_current_context_type(self) -> str:
        """
        Get the current context type.
        
        Returns:
            The current context type
        """
        if self.context_tracker and self.context_tracker.get_current_context():
            return self.context_tracker.get_current_context().type
        
        # Fallback to state
        if self.state:
            return self.state.context_type
        
        return "code"
    
    def is_in_context(self, *context_types: str) -> bool:
        """
        Check if currently in any of the given context types.
        
        Args:
            *context_types: Context types to check
            
        Returns:
            True if in any of the given context types
        """
        if self.context_tracker:
            for context_type in context_types:
                if self.context_tracker.get_context_of_type(context_type):
                    return True
            return False
        
        # Fallback to state
        if self.state:
            return self.state.is_in_context(*context_types)
        
        return False
    
    def _check_for_overlapping_elements(self) -> None:
        """
        Check for elements with overlapping ranges and fix them.
        """
        # Sort elements by start line
        sorted_elements = sorted(self.elements, key=lambda e: (e.start_line, e.end_line))
        
        # Check for overlaps
        for i in range(len(sorted_elements) - 1):
            elem1 = sorted_elements[i]
            elem2 = sorted_elements[i + 1]
            
            # If elem1 contains elem2 but they're not properly nested
            if (elem1.start_line <= elem2.start_line and 
                elem1.end_line >= elem2.end_line and
                elem2.parent != elem1):
                
                # Set parent-child relationship
                elem2.parent = elem1
                if elem2 not in elem1.children:
                    elem1.children.append(elem2)
    
    def _validate_parent_child_relationships(self) -> None:
        """
        Validate parent-child relationships.
        """
        for element in self.elements:
            # Ensure parent's range contains child's range
            if element.parent:
                if not (element.parent.start_line <= element.start_line and 
                        element.parent.end_line >= element.end_line):
                    # Remove invalid relationship
                    if element in element.parent.children:
                        element.parent.children.remove(element)
                    element.parent = None
    
    def _fix_orphaned_elements(self) -> None:
        """
        Find orphaned elements and try to find a parent for them.
        """
        # Find elements without a parent
        orphans = [e for e in self.elements if e.parent is None]
        
        for orphan in orphans:
            # Skip top-level elements
            if orphan.start_line == 1:
                continue
                
            # Try to find a parent
            potential_parent = self._find_most_likely_parent(orphan)
            if potential_parent:
                orphan.parent = potential_parent
                if orphan not in potential_parent.children:
                    potential_parent.children.append(orphan)
    
    def _find_most_likely_parent(self, element: CodeElement) -> Optional[CodeElement]:
        """
        Find the most likely parent for an element.
        
        Args:
            element: Element to find a parent for
        
        Returns:
            Most likely parent, or None if no suitable parent found
        """
        candidates = []
        
        for potential_parent in self.elements:
            # Skip the element itself
            if potential_parent == element:
                continue
                
            # Skip elements that already have this element as a parent
            if potential_parent.parent == element:
                continue
                
            # Check if potential_parent contains element
            if (potential_parent.start_line <= element.start_line and
                potential_parent.end_line >= element.end_line):
                candidates.append(potential_parent)
        
        # No candidates
        if not candidates:
            return None
            
        # Find the smallest containing element
        candidates.sort(key=lambda e: (e.end_line - e.start_line))
        return candidates[0]
    
    def _fix_element_types(self) -> None:
        """
        Fix element types based on context.
        """
        for element in self.elements:
            if element.element_type == ElementType.FUNCTION and element.parent:
                if element.parent.element_type in (
                    ElementType.CLASS,
                    ElementType.STRUCT,
                    ElementType.INTERFACE,
                    ElementType.IMPL,
                    ElementType.TRAIT,
                ):
                    element.element_type = ElementType.METHOD
    
    def _is_start_of_definition(self, tokens: List[Token], index: int) -> bool:
        """
        Check if tokens at the given index represent the start of a definition.
        
        Args:
            tokens: List of tokens
            index: Index to check
        
        Returns:
            True if tokens represent start of definition
        """
        raise NotImplementedError("Subclasses must implement _is_start_of_definition")
    
    def _parse_definition(self, tokens: List[Token], index: int) -> Tuple[Optional[CodeElement], int]:
        """
        Parse a definition at the given token index.
        
        Args:
            tokens: List of tokens
            index: Index to start parsing from
        
        Returns:
            Tuple of (parsed element or None, new index)
        """
        raise NotImplementedError("Subclasses must implement _parse_definition")
    
    def _get_token_context(self, tokens: List[Token], index: int, count: int) -> List[Token]:
        """
        Get a window of tokens around the given index.
        
        Args:
            tokens: List of tokens
            index: Center index
            count: Number of tokens to include (approximately)
        
        Returns:
            List of tokens around the given index
        """
        start = max(0, index - count // 2)
        end = min(len(tokens), index + count // 2 + 1)
        return tokens[start:end] 