#!/usr/bin/env python3
"""
Example demonstrating the BraceBlockParser.

This script shows how to use the BraceBlockParser to parse brace-delimited blocks
that are common in C-like languages such as C, C++, Java, and JavaScript.
"""

import sys
from pathlib import Path
from typing import List

# Add the parent directory to the Python path
parent_dir = Path(__file__).resolve().parent.parent.parent.parent
sys.path.append(str(parent_dir))

from grammar.token_parser.token import Token, TokenType
from grammar.token_parser.parser_state import ParserState
from grammar.token_parser.generic_parsers import BraceBlockParser


def create_tokens_from_code(code: str) -> List[Token]:
    """
    Create a simple list of tokens from the code.

    This is a very simplified tokenizer that only identifies braces and text.
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

    for char in code:
        if char == "{":
            tokens.append(Token(TokenType.OPEN_BRACE, "{", position, line, column))
        elif char == "}":
            tokens.append(Token(TokenType.CLOSE_BRACE, "}", position, line, column))
        elif char == "\n":
            tokens.append(Token(TokenType.NEWLINE, "\n", position, line, column))
            line += 1
            column = 0
        elif char.isspace():
            tokens.append(Token(TokenType.WHITESPACE, char, position, line, column))
        else:
            # For simplicity, we'll treat any other character as "text"
            tokens.append(Token(TokenType.IDENTIFIER, char, position, line, column))

        position += 1
        column += 1

    return tokens


def parse_brace_block(code: str) -> None:
    """
    Parse a brace-delimited block and print the contents.

    Args:
        code: Source code to parse
    """
    # Create tokens from the code
    tokens = create_tokens_from_code(code)

    # Find the opening brace
    brace_index = -1
    for i, token in enumerate(tokens):
        if token.token_type == TokenType.OPEN_BRACE:
            brace_index = i
            break

    if brace_index == -1:
        print("No opening brace found in the code.")
        return

    # Create a parser state
    state = ParserState()

    # Parse the brace block
    block_indices, next_index = BraceBlockParser.parse_block(
        tokens,
        brace_index,
        state,
        "function",  # Example context type
        {"name": "example_function"},  # Example context metadata
    )

    # Print the block tokens
    print("Brace Block Contents:")
    for idx in block_indices:
        token = tokens[idx]
        print(
            f"  {token.token_type.name}: '{token.value}' at line {token.line}, column {token.column}"
        )

    print(
        f"\nBlock ended at index {next_index}, token: {tokens[next_index - 1].value if next_index - 1 < len(tokens) else 'END'}"
    )
    print(f"Context type during parsing: {state.get_current_context_type()}")


def main() -> None:
    """Run the example with a sample brace-delimited code block."""
    # Sample code with a brace block
    sample_code = """function example() {
    // This is a function body
    if (x > 0) {
        // Nested block
        return x;
    }
    return 0;
}"""

    parse_brace_block(sample_code)


if __name__ == "__main__":
    main()
