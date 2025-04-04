#!/usr/bin/env python3
"""
Test script for the grammar parser system.

This script demonstrates using both Python and JavaScript parsers,
showing how the parser factory can be used to choose a parser based on
the language of the input code.
"""

import sys
import json
from pathlib import Path

# Add the parent directory to the Python path
parent_dir = Path(__file__).resolve().parent.parent.parent.parent
sys.path.append(str(parent_dir))

from grammar.token_parser import ParserFactory


def parse_code(code: str, language: str) -> None:
    """
    Parse code using the appropriate parser.
    
    Args:
        code: Source code to parse
        language: Programming language of the code
    """
    print(f"\n=== Parsing {language.upper()} Code ===\n")
    
    # Get the appropriate parser from the factory
    parser = ParserFactory.create_parser(language)
    if not parser:
        print(f"{language} parser is not available")
        return
    
    # Parse the code
    ast = parser.parse(code)
    
    # Print basic info about the AST
    print(f"AST Type: {ast.get('type')}")
    print(f"Body Length: {len(ast.get('body', []))}")
    print(f"Children: {len(ast.get('children', []))}")
    
    # Print the symbol table
    print("\nSymbol Table:")
    for symbol in parser.symbol_table.get_all_symbols():
        print(f"{symbol.name} ({symbol.symbol_type}) at line {symbol.line}, column {symbol.column}")


def main() -> None:
    """Test the parsers with sample code."""
    # Print available parsers
    supported_languages = ParserFactory.get_supported_languages()
    print(f"Supported languages: {', '.join(supported_languages)}")
    
    # Sample Python code
    python_code = """
def greeting(name: str) -> str:
    return f"Hello, {name}!"

class User:
    def __init__(self, name: str):
        self.name = name
    
    def greet(self):
        return greeting(self.name)

# Create user and greet
user = User("World")
message = user.greet()
print(message)
"""
    
    # Sample JavaScript code
    javascript_code = """
function greeting(name) {
    return `Hello, ${name}!`;
}

class User {
    constructor(name) {
        this.name = name;
    }
    
    greet() {
        return greeting(this.name);
    }
}

// Create user and greet
const user = new User("World");
const message = user.greet();
console.log(message);
"""
    
    # Parse both languages
    parse_code(python_code, "python")
    parse_code(javascript_code, "javascript")


if __name__ == "__main__":
    main() 