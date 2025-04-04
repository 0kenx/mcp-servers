#!/usr/bin/env python3
"""
Example demonstrating the usage of the JavaScript parser.

This script shows how to use the JavaScriptParser to parse JavaScript code and generate
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


def parse_javascript_code(code: str) -> None:
    """
    Parse JavaScript code and print the AST.
    
    Args:
        code: JavaScript source code to parse
    """
    # Get a JavaScript parser from the factory
    parser = ParserFactory.create_parser('javascript')
    if not parser:
        print("JavaScript parser is not available")
        return
    
    # Parse the code
    ast = parser.parse(code)
    
    # Format AST for output (removes circular references)
    serializable_ast = format_ast_for_output(ast)
    print(json.dumps(serializable_ast, indent=2, default=str))
    
    # Print the symbol table
    print("\nSymbol Table:")
    all_symbols = parser.symbol_table.get_symbols_by_scope()
    
    for scope, symbols in all_symbols.items():
        print(f"\nScope: {scope}")
        for symbol in symbols:
            print(f"  {symbol.name} ({symbol.symbol_type}) at line {symbol.line}, column {symbol.column}")


def main() -> None:
    """Run the example with a sample JavaScript code snippet."""
    # Sample JavaScript code to parse
    sample_code = """
// Factorial function
function factorial(n) {
    if (n <= 1) {
        return 1;
    }
    return n * factorial(n - 1);
}

// Example class
class Example {
    constructor(value) {
        this.value = value;
    }
    
    getValue() {
        return this.value;
    }
}

// Create an example and calculate factorial
const example = new Example(5);
const result = factorial(example.getValue());
console.log(`Factorial of ${example.getValue()} is ${result}`);
"""
    
    parse_javascript_code(sample_code)


if __name__ == "__main__":
    main() 