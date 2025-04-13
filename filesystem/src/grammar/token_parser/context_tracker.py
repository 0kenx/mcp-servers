"""
Context tracking for the grammar parser system.

This module provides classes for tracking hierarchical contexts during parsing.
"""

from typing import Dict, List, Optional, Any
from dataclasses import dataclass


@dataclass
class Context:
    """
    Represents a parsing context with hierarchy.

    Attributes:
        type: The type of context (e.g., "function", "class", "loop")
        name: Optional name for the context
        parent: Optional parent context
        metadata: Optional metadata for the context
        children: List of child contexts
        start: Start position of the context
        end: End position of the context
    """

    type: str
    name: Optional[str] = None
    parent: Optional["Context"] = None
    metadata: Optional[Dict[str, Any]] = None
    children: List["Context"] = None
    start: int = -1
    end: int = -1

    def __post_init__(self):
        if self.children is None:
            self.children = []
        if self.metadata is None:
            self.metadata = {}

    def add_child(self, child: "Context") -> None:
        """Add a child context to this context."""
        self.children.append(child)
        child.parent = self


class ContextTracker:
    """
    Tracks hierarchical contexts during parsing.

    This class maintains a tree of contexts, allowing the parser to track
    nested structures like functions within classes, loops within functions, etc.
    """

    def __init__(self):
        """Initialize the context tracker."""
        # Root context is a special context that serves as the parent for top-level contexts
        self.root = Context(type="root")
        self.current = self.root

    def enter_context(
        self,
        type_: str,
        name: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        start: int = -1,
    ) -> Context:
        """
        Enter a new context.

        Args:
            type_: Type of the context
            name: Optional name for the context
            metadata: Optional metadata for the context
            start: Start position of the context

        Returns:
            The new context
        """
        context = Context(type=type_, name=name, metadata=metadata, start=start)
        self.current.add_child(context)
        self.current = context
        return context

    def exit_context(self, end: int = -1) -> Optional[Context]:
        """
        Exit the current context.

        Args:
            end: End position of the context

        Returns:
            The parent context, or None if already at root
        """
        if self.current == self.root:
            return None

        self.current.end = end
        self.current = self.current.parent
        return self.current

    def get_current_context(self) -> Context:
        """Get the current context."""
        return self.current

    def get_context_stack(self) -> List[Context]:
        """
        Get the stack of contexts from root to current.

        Returns:
            List of contexts from root to current
        """
        stack = []
        context = self.current
        while context != self.root:
            stack.append(context)
            context = context.parent

        return list(reversed(stack))

    def get_context_of_type(self, type_: str) -> Optional[Context]:
        """
        Find the nearest enclosing context of the specified type.

        Args:
            type_: Type of context to find

        Returns:
            The nearest context of the specified type, or None if not found
        """
        context = self.current
        while context != self.root:
            if context.type == type_:
                return context
            context = context.parent

        return None

    def reset(self) -> None:
        """Reset the context tracker to initial state."""
        self.root = Context(type="root")
        self.current = self.root
