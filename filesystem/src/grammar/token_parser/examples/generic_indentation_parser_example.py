#!/usr/bin/env python3
"""
Example demonstrating the IndentationBlockParser.

This script shows how to use the IndentationBlockParser to parse indentation-based blocks
that are common in languages such as Python and YAML.
"""

import sys
import json
from pathlib import Path
from typing import List, Dict, Any

# Add the parent directory to the Python path
parent_dir = Path(__file__).resolve().parent.parent.parent.parent
sys.path.append(str(parent_dir))

from grammar.token_parser.token import Token, TokenType
from grammar.token_parser.parser_state import ParserState
from grammar.token_parser.generic_parsers import IndentationBlockParser


def create_tokens_from_code(code: str) -> List[Token]:
    """
    Create a simple list of tokens from the code.
    
    This is a very simplified tokenizer that mainly tracks indentation.
    A real parser would use a proper tokenizer.
    
    Args:
        code: Source code to tokenize
        
    Returns:
        List of tokens
    """
    tokens = []
    position = 0
    line = 1
    column = 1
    
    lines = code.split('\n')
    
    for line_num, line_content in enumerate(lines):
        # Calculate indentation at the start of the line
        indent_count = len(line_content) - len(line_content.lstrip())
        if indent_count > 0:
            indent = line_content[:indent_count]
            tokens.append(Token(
                TokenType.WHITESPACE, 
                indent, 
                position, 
                line_num + 1, 
                1, 
                metadata={"indent_size": indent_count}
            ))
            position += indent_count
            column = indent_count + 1
        
        # Process the rest of the line
        rest_of_line = line_content.lstrip()
        if rest_of_line:
            # For simplicity, we'll treat any non-whitespace content as "text"
            tokens.append(Token(
                TokenType.IDENTIFIER, 
                rest_of_line, 
                position, 
                line_num + 1, 
                column
            ))
            position += len(rest_of_line)
            column += len(rest_of_line)
        
        # Add a newline token except for the last line
        if line_num < len(lines) - 1:
            tokens.append(Token(
                TokenType.NEWLINE, 
                '\n', 
                position, 
                line_num + 1, 
                column
            ))
            position += 1
            line += 1
            column = 1
    
    return tokens


def parse_indentation_block(code: str) -> None:
    """
    Parse an indentation-based block and print the contents.
    
    Args:
        code: Source code to parse
    """
    # Create tokens from the code
    tokens = create_tokens_from_code(code)
    
    # Find the ":" token that would start a block (simplified for this example)
    start_index = 0
    base_indentation = 0
    
    for i, token in enumerate(tokens):
        if token.token_type == TokenType.IDENTIFIER and ":" in token.value:
            start_index = i
            # Check if there's a previous whitespace token to determine base indentation
            if i > 0 and tokens[i-1].token_type == TokenType.WHITESPACE:
                base_indentation = tokens[i-1].metadata.get("indent_size", 0)
            break
    
    # Create a parser state
    state = ParserState()
    
    # Parse the indentation block
    block_indices, next_index = IndentationBlockParser.parse_block(
        tokens, 
        start_index, 
        base_indentation,
        state,
        "function",  # Example context type
        {"name": "example_function"}  # Example context metadata
    )
    
    # Print the tokens
    print("All Tokens:")
    for i, token in enumerate(tokens):
        indent_info = f", indent={token.metadata.get('indent_size')}" if token.token_type == TokenType.WHITESPACE and 'indent_size' in token.metadata else ""
        print(f"  {i}: {token.token_type.name}: '{token.value}' at line {token.line}, column {token.column}{indent_info}")
    
    # Print the block tokens
    print("\nIndentation Block Contents:")
    for idx in block_indices:
        token = tokens[idx]
        indent_info = f", indent={token.metadata.get('indent_size')}" if token.token_type == TokenType.WHITESPACE and 'indent_size' in token.metadata else ""
        print(f"  {idx}: {token.token_type.name}: '{token.value}' at line {token.line}, column {token.column}{indent_info}")
    
    print(f"\nBlock ended at index {next_index}, token: {tokens[next_index].value if next_index < len(tokens) else 'END'}")
    print(f"Context type during parsing: {state.get_current_context_type()}")


def main() -> None:
    """Run the example with a sample indentation-based code block."""
    # Sample code with an indentation block
    sample_code = """def example_function():
    # This is a function body
    if x > 0:
        # Nested block
        return x
    return 0"""
    
    parse_indentation_block(sample_code)


if __name__ == "__main__":
    main() 