#!/usr/bin/env python3
"""
Example demonstrating the usage of the TypeScript parser.

This script shows how to use the TypeScriptParser and ParserFactory
to parse TypeScript code and generate an abstract syntax tree.
"""

import sys
import json
from pathlib import Path

# Add the parent directory to the Python path
parent_dir = Path(__file__).resolve().parent.parent.parent.parent
sys.path.append(str(parent_dir))

from grammar.token_parser import ParserFactory


def parse_typescript_code(code: str) -> None:
    """
    Parse TypeScript code and print the AST.

    Args:
        code: TypeScript source code to parse
    """
    # Get a TypeScript parser from the factory
    parser = ParserFactory.create_parser("typescript")
    if not parser:
        print("TypeScript parser is not available")
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
                if k != "parent":  # Skip parent to avoid circular refs
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
    for symbol in parser.symbol_table.get_symbols_by_scope():
        print(
            f"{symbol.name} ({symbol.symbol_type}) at line {symbol.line}, column {symbol.column}"
        )


def main() -> None:
    """Run the example with a sample TypeScript code snippet."""
    # Sample TypeScript code to parse
    sample_code = """
// Interface for a person
interface Person {
    name: string;
    age: number;
    greet(): void;
}

// Type alias for a function type
type GreetingFunction = (name: string) => string;

// Enum for weekdays
enum Weekday {
    Monday,
    Tuesday,
    Wednesday,
    Thursday,
    Friday
}

// Namespace for utilities
namespace Utils {
    export function formatName(name: string): string {
        return name.toUpperCase();
    }
}

// Generic class with type parameters
class Container<T> {
    private value: T;
    
    constructor(value: T) {
        this.value = value;
    }
    
    getValue(): T {
        return this.value;
    }
}

// Create an instance with type annotation
const person: Person = {
    name: "John",
    age: 30,
    greet() {
        console.log(`Hello, my name is ${this.name}`);
    }
};

// Use the generic class with a specific type
const numberContainer: Container<number> = new Container<number>(42);
console.log(numberContainer.getValue());
"""

    parse_typescript_code(sample_code)


if __name__ == "__main__":
    main()
