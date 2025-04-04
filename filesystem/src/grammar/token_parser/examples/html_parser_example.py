#!/usr/bin/env python3
"""
Example demonstrating the usage of the HTML parser.

This script shows how to use the HTMLParser to parse HTML code and generate
an abstract syntax tree.
"""

import sys
import json
from pathlib import Path

# Add the parent directory to the Python path
parent_dir = Path(__file__).resolve().parent.parent.parent.parent
sys.path.append(str(parent_dir))

from grammar.token_parser import ParserFactory


def parse_html_code(code: str) -> None:
    """
    Parse HTML code and print the AST.
    
    Args:
        code: HTML source code to parse
    """
    # Get an HTML parser from the factory
    parser = ParserFactory.create_parser('html')
    if not parser:
        print("HTML parser is not available")
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
    all_symbols = parser.symbol_table.get_all_symbols()
    
    for scope, symbols in all_symbols.items():
        print(f"\nScope: {scope}")
        for symbol in symbols:
            print(f"  {symbol.name} (Type: {symbol.symbol_type}, Line: {symbol.line}, Column: {symbol.column})")


def main() -> None:
    """Run the example with a sample HTML code snippet."""
    # Sample HTML code to parse
    sample_code = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>HTML Parser Example</title>
    <link rel="stylesheet" href="styles.css">
    <style>
        body {
            font-family: Arial, sans-serif;
            margin: 0;
            padding: 20px;
            background-color: #f4f4f4;
            color: #333;
        }
        .container {
            max-width: 1200px;
            margin: 0 auto;
            background-color: white;
            padding: 20px;
            border-radius: 5px;
            box-shadow: 0 2px 5px rgba(0,0,0,0.1);
        }
    </style>
</head>
<body>
    <!-- Main content container -->
    <div class="container">
        <header>
            <h1>HTML Parser Demo</h1>
            <nav>
                <ul>
                    <li><a href="#section1">Section 1</a></li>
                    <li><a href="#section2">Section 2</a></li>
                    <li><a href="#section3">Section 3</a></li>
                </ul>
            </nav>
        </header>
        
        <main>
            <section id="section1">
                <h2>Section 1: Introduction</h2>
                <p>This is a demonstration of the HTML parser capabilities.</p>
                <p>It handles various HTML elements, attributes, and nested structures.</p>
            </section>
            
            <section id="section2">
                <h2>Section 2: Features</h2>
                <ul>
                    <li>Parses HTML elements</li>
                    <li>Handles attributes</li>
                    <li>Processes nested elements</li>
                    <li>Supports self-closing tags like <img src="example.jpg" alt="Example image" /></li>
                    <li>Handles comments</li>
                </ul>
            </section>
            
            <section id="section3">
                <h2>Section 3: Form Example</h2>
                <form action="/submit" method="post">
                    <div class="form-group">
                        <label for="name">Name:</label>
                        <input type="text" id="name" name="name" required>
                    </div>
                    <div class="form-group">
                        <label for="email">Email:</label>
                        <input type="email" id="email" name="email" required>
                    </div>
                    <div class="form-group">
                        <label for="message">Message:</label>
                        <textarea id="message" name="message" rows="4"></textarea>
                    </div>
                    <button type="submit">Submit</button>
                </form>
            </section>
        </main>
        
        <footer>
            <p>&copy; 2023 HTML Parser Example</p>
        </footer>
    </div>

    <script>
        document.addEventListener('DOMContentLoaded', function() {
            console.log('Page loaded successfully!');
            
            // Add event listener to the form
            const form = document.querySelector('form');
            form.addEventListener('submit', function(e) {
                e.preventDefault();
                alert('Form submitted!');
            });
        });
    </script>
</body>
</html>
"""
    
    parse_html_code(sample_code)


if __name__ == "__main__":
    main() 