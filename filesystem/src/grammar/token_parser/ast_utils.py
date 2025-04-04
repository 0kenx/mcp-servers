"""
AST utility functions for the grammar parser system.

This module provides common utility functions for working with Abstract Syntax Trees.
"""

from typing import Any, Dict, List, Set, Optional


def remove_circular_refs(node: Any, visited: Optional[Set[int]] = None) -> Any:
    """
    Remove circular references from an AST node for JSON serialization.
    
    Args:
        node: The node to process
        visited: Set of visited node IDs (used for recursion)
        
    Returns:
        The node with circular references removed
    """
    if visited is None:
        visited = set()
    
    # Handle non-dict/list types
    if not isinstance(node, (dict, list)):
        return node
    
    # Handle recursive structures
    node_id = id(node)
    if node_id in visited:
        return None  # or some placeholder like "[Circular]"
    
    visited.add(node_id)
    
    if isinstance(node, dict):
        # Create a new dict excluding 'parent' and any circular references
        result = {}
        for k, v in node.items():
            if k != 'parent':  # Skip parent to avoid circular refs
                result[k] = remove_circular_refs(v, visited.copy())
        return result
    
    elif isinstance(node, list):
        return [remove_circular_refs(item, visited.copy()) for item in node]
    else:
        return node


def format_ast_for_output(ast: Dict[str, Any]) -> Dict[str, Any]:
    """
    Format an AST for output, removing circular references.
    
    Args:
        ast: The AST to format
        
    Returns:
        The formatted AST
    """
    return remove_circular_refs(ast) 