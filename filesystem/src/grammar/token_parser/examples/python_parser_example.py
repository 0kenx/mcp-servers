#!/usr/bin/env python3
"""
Example demonstrating the usage of the Python parser.

This script shows how to use the PythonParser and ParserFactory
to parse Python code and generate an abstract syntax tree.
"""

import sys
import json
from pathlib import Path

# Add the parent directory to the Python path
parent_dir = Path(__file__).resolve().parent.parent.parent.parent
sys.path.append(str(parent_dir))

from grammar.token_parser import ParserFactory


def parse_python_code(code: str) -> None:
    """
    Parse Python code and print the AST.
    
    Args:
        code: Python source code to parse
    """
    # Get a Python parser from the factory
    parser = ParserFactory.create_parser('python')
    if not parser:
        print("Python parser is not available")
        return
    
    # Parse the code
    ast = parser.parse(code)
    
    # Create a function to remove circular references for JSON serialization
    def remove_circular_refs(node, visited=None):
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
    
    # Remove circular references and print the AST as JSON
    serializable_ast = remove_circular_refs(ast)
    print(json.dumps(serializable_ast, indent=2, default=str))
    
    # Print the symbol table
    print("\nSymbol Table:")
    for symbol in parser.symbol_table.get_all_symbols():
        print(f"{symbol.name} ({symbol.symbol_type}) at line {symbol.line}, column {symbol.column}")


def main() -> None:
    """Run the example with a sample Python code snippet."""
    # Sample Python code to parse
    sample_code = """
def factorial(n: int) -> int:
    if n <= 1:
        return 1
    return n * factorial(n - 1)

class Example:
    def __init__(self, value):
        self.value = value
    
    def get_value(self):
        return self.value

# Create an example and calculate factorial
example = Example(5)
result = factorial(example.get_value())
print(f"Factorial: {result}")
"""
    
    parse_python_code(sample_code)


if __name__ == "__main__":
    main()