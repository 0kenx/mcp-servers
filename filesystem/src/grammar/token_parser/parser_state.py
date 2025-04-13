"""
Parser state for the grammar parser system.

This module provides the ParserState class that tracks the state during parsing.
"""

from typing import Dict, Optional, Any
from .base import CodeElement


class ContextInfo:
    """
    Information about a parsing context.
    """

    def __init__(self, context_type: str, metadata: Optional[Dict[str, Any]] = None):
        """
        Initialize context information.

        Args:
            context_type: Type of context ("code", "string", "comment", etc.)
            metadata: Additional information about the context
        """
        self.context_type = context_type
        self.metadata = metadata or {}

    def __repr__(self):
        return f"Context({self.context_type})"


class ParserState:
    """
    Tracks the state of the parser during the parsing process.

    The parser state includes information about the current scope,
    context, and other state needed during parsing.
    """

    def __init__(self):
        """Initialize the parser state."""
        self.current_scope = None  # Current parent element
        self.scope_stack = []  # Stack of scopes for nested elements
        self.context_type = "code"  # Current context: "code", "string", "comment", etc.
        self.brace_depth = 0  # Current nesting level of braces
        self.paren_depth = 0  # Current nesting level of parentheses
        self.bracket_depth = 0  # Current nesting level of brackets
        self.last_token = None  # Previous significant token
        self.in_string = False  # Whether currently in a string
        self.string_delimiter = None  # Current string delimiter (', ", or `)
        self.in_comment = False  # Whether currently in a comment
        self.contexts = []  # Stack of contexts
        self.language_context = {}  # Language-specific state data

    def enter_scope(self, element: CodeElement) -> None:
        """
        Enter a new scope.

        Args:
            element: The element that defines the new scope
        """
        self.scope_stack.append(self.current_scope)
        self.current_scope = element

    def exit_scope(self) -> Optional[CodeElement]:
        """
        Exit the current scope and return to the parent scope.

        Returns:
            The scope that was exited, or None if there was no scope to exit
        """
        exited_scope = self.current_scope
        if self.scope_stack:
            self.current_scope = self.scope_stack.pop()
        else:
            self.current_scope = None
        return exited_scope

    def enter_context(
        self, context_type: str, metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Enter a new context.

        Args:
            context_type: Type of context
            metadata: Additional information about the context
        """
        self.contexts.append(ContextInfo(context_type, metadata))
        self.context_type = context_type

    def exit_context(self) -> Optional[ContextInfo]:
        """
        Exit the current context and return to the previous context.

        Returns:
            The context that was exited, or None if there was no context to exit
        """
        if not self.contexts:
            return None

        exited_context = self.contexts.pop()

        # Update current context
        if self.contexts:
            self.context_type = self.contexts[-1].context_type
        else:
            self.context_type = "code"

        return exited_context

    def is_in_context(self, *context_types: str) -> bool:
        """
        Check if the parser is currently in any of the specified contexts.

        Args:
            *context_types: Context types to check for

        Returns:
            True if the parser is in any of the specified contexts
        """
        if not context_types:
            return False

        if self.context_type in context_types:
            return True

        return any(context.context_type in context_types for context in self.contexts)
