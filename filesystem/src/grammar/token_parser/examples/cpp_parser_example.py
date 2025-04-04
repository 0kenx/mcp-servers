#!/usr/bin/env python3
"""
Example demonstrating the usage of the C++ parser.

This script shows how to use the CppParser and ParserFactory
to parse C++ code and generate an abstract syntax tree.
"""

import sys
import json
from pathlib import Path

# Add the parent directory to the Python path
parent_dir = Path(__file__).resolve().parent.parent.parent.parent
sys.path.append(str(parent_dir))

from grammar.token_parser import ParserFactory


def parse_cpp_code(code: str) -> None:
    """
    Parse C++ code and print the AST.
    
    Args:
        code: C++ source code to parse
    """
    # Get a C++ parser from the factory
    parser = ParserFactory.create_parser('cpp')
    if not parser:
        print("C++ parser is not available")
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
    """Run the example with a sample C++ code snippet."""
    # Sample C++ code to parse
    sample_code = """
#include <iostream>
#include <vector>
#include <string>
#include <memory>

// Namespace for utility functions
namespace utils {
    // Template function for printing
    template <typename T>
    void print(const T& value) {
        std::cout << value << std::endl;
    }
    
    // Specialized version for std::string
    template <>
    void print<std::string>(const std::string& value) {
        std::cout << "String: " << value << std::endl;
    }
}

// Abstract base class
class Shape {
public:
    // Virtual destructor
    virtual ~Shape() = default;
    
    // Pure virtual function
    virtual double area() const = 0;
    
    // Virtual function with implementation
    virtual void display() const {
        std::cout << "This is a shape with area " << area() << std::endl;
    }
};

// Derived class
class Circle : public Shape {
private:
    double radius;

public:
    // Constructor
    explicit Circle(double r) : radius(r) {}
    
    // Override from base class
    double area() const override {
        return 3.14159 * radius * radius;
    }
};

// Template class
template <typename T>
class Container {
private:
    std::vector<T> elements;
    
public:
    // Add an element
    void add(const T& element) {
        elements.push_back(element);
    }
    
    // Get size
    size_t size() const {
        return elements.size();
    }
};

// Function with exception handling
void processValue(int value) {
    try {
        if (value < 0) {
            throw std::invalid_argument("Value cannot be negative");
        }
        if (value == 0) {
            throw std::runtime_error("Value cannot be zero");
        }
        std::cout << "Processing value: " << value << std::endl;
    } catch (const std::invalid_argument& e) {
        std::cerr << "Invalid argument: " << e.what() << std::endl;
    } catch (const std::exception& e) {
        std::cerr << "Exception: " << e.what() << std::endl;
    }
}

int main() {
    // Smart pointer
    std::unique_ptr<Shape> shape = std::make_unique<Circle>(5.0);
    shape->display();
    
    // Template function
    utils::print("Hello, C++!");
    utils::print(42);
    
    // Template class
    Container<int> intContainer;
    intContainer.add(1);
    intContainer.add(2);
    intContainer.add(3);
    
    // Exception handling
    processValue(10);
    processValue(0);
    processValue(-5);
    
    return 0;
}
"""
    
    parse_cpp_code(sample_code)


if __name__ == "__main__":
    main() 