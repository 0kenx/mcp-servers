#!/usr/bin/env python3
"""
Example demonstrating the usage of the Python parser.

This script shows how to use the PythonParser to parse Python code and generate
an abstract syntax tree.
"""

import sys
import json
from pathlib import Path

# Add the parent directory to the Python path
parent_dir = Path(__file__).resolve().parent.parent.parent.parent
sys.path.append(str(parent_dir))

from grammar.token_parser import ParserFactory
from grammar.token_parser.ast_utils import format_ast_for_output


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
    
    # Format AST for output (removes circular references)
    serializable_ast = format_ast_for_output(ast)
    print(json.dumps(serializable_ast, indent=2, default=str))
    
    # # Print the symbol table
    # print("\nSymbol Table:")
    # all_symbols = parser.symbol_table.get_all_symbols()
    
    # for scope, symbols in all_symbols.items():
    #     print(f"\nScope: {scope}")
    #     for symbol in symbols:
    #         print(f"  {symbol.name} ({symbol.symbol_type}) at line {symbol.line}, column {symbol.column}")


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