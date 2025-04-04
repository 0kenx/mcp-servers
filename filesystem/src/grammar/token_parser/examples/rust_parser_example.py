#!/usr/bin/env python3
"""
Example script for the Rust parser.

This script demonstrates how to use the Rust parser to parse Rust code
and generate an abstract syntax tree (AST).
"""

import sys
import json
from pathlib import Path

# Add the parent directory to the Python path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from src.grammar.token_parser import ParserFactory
from src.grammar.token_parser.token import Token


def parse_rust_code(rust_code: str) -> None:
    """
    Parse Rust code using the RustParser and print the AST.
    
    Args:
        rust_code: Rust source code to parse
    """
    # Create a parser instance
    parser_factory = ParserFactory()
    parser = parser_factory.create_parser("rust")
    
    if not parser:
        print("Failed to create Rust parser.")
        return
    
    # Parse the code
    ast = parser.parse(rust_code)
    
    # Helper function to remove circular references for JSON serialization
    def remove_circular_refs(node):
        if isinstance(node, dict):
            node.pop("parent", None)
            for child in node.get("children", []):
                remove_circular_refs(child)
            # Convert Token objects to string representations
            if "tokens" in node and node["tokens"] and isinstance(node["tokens"][0], Token):
                node["tokens"] = [str(token) for token in node["tokens"]]
            return node
        return node
    
    # Print the AST
    print("\nAST Structure:")
    ast_serializable = remove_circular_refs(ast.copy())
    print(json.dumps(ast_serializable, indent=2))
    
    # Print symbols found
    print("\nSymbol Table:")
    symbol_table = parser.symbol_table
    all_symbols = symbol_table.get_all_symbols()
    
    for scope, symbols in all_symbols.items():
        print(f"\nScope: {scope}")
        for symbol in symbols:
            print(f"  {symbol.name} (Type: {symbol.symbol_type}, Line: {symbol.line}, Column: {symbol.column})")


def main():
    """
    Main function that demonstrates Rust parsing with a sample Rust code snippet.
    """
    rust_code = """
// Example Rust code with various language constructs

// Attribute examples
#[derive(Debug, Clone)]
#[cfg(feature = "serde")]

// Module declaration
mod utils {
    pub fn helper() -> i32 {
        42
    }
}

// Use statement
use std::collections::HashMap;

// Trait declaration
pub trait Shape {
    fn area(&self) -> f64;
    fn name() -> &'static str;
}

// Struct with generics
pub struct Rectangle<T> {
    width: T,
    height: T,
}

// Impl block
impl<T: std::ops::Mul<Output = T> + Copy> Rectangle<T> {
    pub fn new(width: T, height: T) -> Self {
        Rectangle { width, height }
    }
    
    pub fn area(&self) -> T {
        self.width * self.height
    }
}

// Trait implementation
impl<T: std::ops::Mul<Output = T> + Copy> Shape for Rectangle<T> 
where T: Into<f64> {
    fn area(&self) -> f64 {
        (self.width * self.height).into()
    }
    
    fn name() -> &'static str {
        "Rectangle"
    }
}

// Enum with variants
pub enum Result<T, E> {
    Ok(T),
    Err(E),
}

// Function with pattern matching
fn process_result<T, E>(result: Result<T, E>) -> Option<T> {
    match result {
        Result::Ok(value) => Some(value),
        Result::Err(_) => None,
    }
}

// Main function
fn main() {
    let rect = Rectangle::new(5, 10);
    let area = rect.area();
    
    println!("Rectangle area: {}", area);
    
    // Using a HashMap
    let mut map = HashMap::new();
    map.insert("key1", "value1");
    map.insert("key2", "value2");
    
    // Conditional expression
    let condition = true;
    let value = if condition { 
        "condition is true" 
    } else { 
        "condition is false" 
    };
    
    // Using a loop
    let mut counter = 0;
    loop {
        counter += 1;
        if counter > 10 {
            break;
        }
    }
}
"""
    
    print("=== Parsing Rust Code ===")
    parse_rust_code(rust_code)


if __name__ == "__main__":
    main() 