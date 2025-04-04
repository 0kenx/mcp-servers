#!/usr/bin/env python3
"""
Example demonstrating the usage of the C parser.

This script shows how to use the CParser and ParserFactory
to parse C code and generate an abstract syntax tree.
"""

import sys
import json
from pathlib import Path

# Add the parent directory to the Python path
parent_dir = Path(__file__).resolve().parent.parent.parent.parent
sys.path.append(str(parent_dir))

from grammar.token_parser import ParserFactory


def parse_c_code(code: str) -> None:
    """
    Parse C code and print the AST.
    
    Args:
        code: C source code to parse
    """
    # Get a C parser from the factory
    parser = ParserFactory.create_parser('c')
    if not parser:
        print("C parser is not available")
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
    for symbol in parser.symbol_table.get_symbols_by_scope():
        print(f"{symbol.name} ({symbol.symbol_type}) at line {symbol.line}, column {symbol.column}")


def main() -> None:
    """Run the example with a sample C code snippet."""
    # Sample C code to parse
    sample_code = """
#include <stdio.h>
#include <stdlib.h>

#define MAX_SIZE 100
#define DEBUG 1

// Structure for a person
struct Person {
    char name[50];
    int age;
    float height;
};

// Union example
union Data {
    int i;
    float f;
    char str[20];
};

// Enum for days of the week
enum Weekday {
    Monday,
    Tuesday,
    Wednesday,
    Thursday,
    Friday,
    Saturday,
    Sunday
};

// Typedef for a custom data type
typedef struct Person Person_t;
typedef int* IntPtr;

// Function prototype
void print_person(Person_t *person);

// Global variable
int global_var = 42;

int main(int argc, char *argv[]) {
    // Local variables
    Person_t person;
    enum Weekday today = Monday;
    union Data data;
    
    // Initialize person
    strcpy(person.name, "John Doe");
    person.age = 30;
    person.height = 1.75;
    
    // Conditional compilation
#ifdef DEBUG
    printf("Debug mode is enabled\\n");
#endif
    
    // Print person details
    printf("Name: %s\\n", person.name);
    printf("Age: %d\\n", person.age);
    printf("Height: %.2f\\n", person.height);
    
    // Use union
    data.i = 10;
    printf("data.i: %d\\n", data.i);
    
    data.f = 220.5;
    printf("data.f: %.2f\\n", data.f);
    
    strcpy(data.str, "C Programming");
    printf("data.str: %s\\n", data.str);
    
    return 0;
}

// Function definition
void print_person(Person_t *person) {
    printf("Name: %s\\n", person->name);
    printf("Age: %d\\n", person->age);
    printf("Height: %.2f\\n", person->height);
}
"""
    
    parse_c_code(sample_code)


if __name__ == "__main__":
    main() 