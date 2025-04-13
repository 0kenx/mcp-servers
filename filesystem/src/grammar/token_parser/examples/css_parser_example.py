#!/usr/bin/env python3
"""
Example demonstrating the usage of the CSS parser.

This script shows how to use the CSSParser to parse CSS code and generate
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


def parse_css_code(code: str) -> None:
    """
    Parse CSS code and print the AST.

    Args:
        code: CSS source code to parse
    """
    # Get a CSS parser from the factory
    parser = ParserFactory.create_parser("css")
    if not parser:
        print("CSS parser is not available")
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
            metadata_str = ""
            if symbol.metadata:
                if "value" in symbol.metadata:
                    metadata_str = f", Value: {symbol.metadata['value']}"
                elif "parameters" in symbol.metadata:
                    metadata_str = f", Parameters: {symbol.metadata['parameters']}"

            print(
                f"  {symbol.name} (Type: {symbol.symbol_type}, Line: {symbol.line}, Column: {symbol.column}{metadata_str})"
            )


def main() -> None:
    """Run the example with a sample CSS code snippet."""
    # Sample CSS code to parse
    sample_code = """
/* Main CSS Styles */
@charset "UTF-8";
@import url('https://fonts.googleapis.com/css2?family=Roboto:wght@400;700&display=swap');

:root {
    --primary-color: #3498db;
    --secondary-color: #2ecc71;
    --text-color: #333;
    --background-color: #f4f4f4;
    --spacing-unit: 20px;
    --border-radius: 5px;
    --box-shadow: 0 2px 5px rgba(0, 0, 0, 0.1);
}

/* Reset styles */
* {
    margin: 0;
    padding: 0;
    box-sizing: border-box;
}

html, body {
    font-family: 'Roboto', Arial, sans-serif;
    font-size: 16px;
    line-height: 1.6;
    color: var(--text-color);
    background-color: var(--background-color);
}

/* Container styles */
.container {
    max-width: 1200px;
    margin: 0 auto;
    padding: var(--spacing-unit);
}

/* Header styles */
header {
    background-color: var(--primary-color);
    color: white;
    padding: var(--spacing-unit);
    margin-bottom: var(--spacing-unit);
}

header h1 {
    font-size: 2rem;
    margin-bottom: 10px;
}

/* Navigation styles */
nav ul {
    display: flex;
    list-style-type: none;
}

nav li {
    margin-right: 15px;
}

nav a {
    color: white;
    text-decoration: none;
    transition: color 0.3s ease;
}

nav a:hover {
    color: var(--secondary-color);
}

/* Section styles */
section {
    background-color: white;
    border-radius: var(--border-radius);
    box-shadow: var(--box-shadow);
    padding: var(--spacing-unit);
    margin-bottom: var(--spacing-unit);
}

section h2 {
    color: var(--primary-color);
    margin-bottom: 15px;
    border-bottom: 1px solid #eee;
    padding-bottom: 10px;
}

/* Form styles */
.form-group {
    margin-bottom: 15px;
}

label {
    display: block;
    margin-bottom: 5px;
    font-weight: 700;
}

input, textarea {
    width: 100%;
    padding: 10px;
    border: 1px solid #ddd;
    border-radius: var(--border-radius);
}

button {
    background-color: var(--primary-color);
    color: white;
    border: none;
    padding: 10px 20px;
    border-radius: var(--border-radius);
    cursor: pointer;
    transition: background-color 0.3s ease;
}

button:hover {
    background-color: var(--secondary-color);
}

/* Footer styles */
footer {
    text-align: center;
    margin-top: var(--spacing-unit);
    padding: var(--spacing-unit) 0;
    border-top: 1px solid #eee;
}

/* Media queries */
@media (max-width: 768px) {
    .container {
        padding: 10px;
    }
    
    header {
        padding: 15px;
    }
    
    nav ul {
        flex-direction: column;
    }
    
    nav li {
        margin-right: 0;
        margin-bottom: 10px;
    }
}

/* Animation keyframes */
@keyframes fadeIn {
    from {
        opacity: 0;
    }
    to {
        opacity: 1;
    }
}

.fade-in {
    animation: fadeIn 0.5s ease forwards;
}
"""

    parse_css_code(sample_code)


if __name__ == "__main__":
    main()
