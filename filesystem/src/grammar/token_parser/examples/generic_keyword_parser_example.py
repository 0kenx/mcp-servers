#!/usr/bin/env python3
"""
Example demonstrating the KeywordBlockParser.

This script shows how to use the KeywordBlockParser to parse keyword-delimited blocks
that are common in languages such as Pascal, SQL, and Ada.
"""

import sys
from pathlib import Path
from typing import List

# Add the parent directory to the Python path
parent_dir = Path(__file__).resolve().parent.parent.parent.parent
sys.path.append(str(parent_dir))

from grammar.token_parser.token import Token, TokenType
from grammar.token_parser.parser_state import ParserState
from grammar.token_parser.generic_parsers import KeywordBlockParser


def create_tokens_from_code(code: str) -> List[Token]:
    """
    Create a simple list of tokens from the code.

    This is a very simplified tokenizer that identifies keywords.
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

    # Split the code into words
    words = []
    current_word = ""
    for char in code:
        if char.isalnum() or char == "_":
            current_word += char
        else:
            if current_word:
                words.append(current_word)
                current_word = ""
            if not char.isspace():
                words.append(char)
            elif char == "\n":
                words.append("\n")

    if current_word:
        words.append(current_word)

    # Convert words to tokens
    keywords = ["begin", "end", "if", "then", "else", "case", "for", "while", "do"]

    for word in words:
        if word == "\n":
            tokens.append(Token(TokenType.NEWLINE, "\n", position, line, column))
            line += 1
            column = 1
        elif word.lower() in keywords:
            tokens.append(
                Token(TokenType.KEYWORD, word.lower(), position, line, column)
            )
            column += len(word)
        elif word.isalnum() or word == "_":
            tokens.append(Token(TokenType.IDENTIFIER, word, position, line, column))
            column += len(word)
        elif word.isspace():
            tokens.append(Token(TokenType.WHITESPACE, word, position, line, column))
            column += len(word)
        else:
            # For simplicity, other characters are treated as operators
            tokens.append(Token(TokenType.OPERATOR, word, position, line, column))
            column += len(word)

        position += len(word)

    return tokens


def parse_keyword_block(code: str) -> None:
    """
    Parse a keyword-delimited block and print the contents.

    Args:
        code: Source code to parse
    """
    # Create tokens from the code
    tokens = create_tokens_from_code(code)

    # Find the "begin" keyword
    begin_index = -1
    for i, token in enumerate(tokens):
        if token.token_type == TokenType.KEYWORD and token.value == "begin":
            begin_index = i
            break

    if begin_index == -1:
        print("No 'begin' keyword found in the code.")
        return

    # Create a parser state
    state = ParserState()

    # Parse the keyword block
    block_indices, next_index = KeywordBlockParser.parse_block(
        tokens,
        begin_index,
        "begin",  # Start keyword
        "end",  # End keyword
        state,
        "procedure",  # Example context type
        {"name": "example_procedure"},  # Example context metadata
    )

    # Print the tokens
    print("All Tokens:")
    for i, token in enumerate(tokens):
        print(
            f"  {i}: {token.token_type.name}: '{token.value}' at line {token.line}, column {token.column}"
        )

    # Print the block tokens
    print("\nKeyword Block Contents:")
    for idx in block_indices:
        token = tokens[idx]
        print(
            f"  {idx}: {token.token_type.name}: '{token.value}' at line {token.line}, column {token.column}"
        )

    print(
        f"\nBlock ended at index {next_index}, token: {tokens[next_index - 1].value if next_index - 1 < len(tokens) else 'END'}"
    )
    print(f"Context type during parsing: {state.get_current_context_type()}")


def main() -> None:
    """Run the example with a sample keyword-delimited code block."""
    # Sample code with a begin/end block (Pascal-like)
    sample_code = """procedure ExampleProcedure;
var
    x: integer;
begin
    x := 10;
    if x > 0 then
    begin
        writeln('Positive');
    end
    else
    begin
        writeln('Non-positive');
    end;
end;"""

    parse_keyword_block(sample_code)


if __name__ == "__main__":
    main()
