"""
Generic tokenizers for the grammar parser system.
This module provides a tokenizer for languages that use braces to define blocks.
Using regex-based rules for token identification.
"""

from typing import List
from .token import Token, TokenType
from .tokenizer import Tokenizer, TokenRule


class BraceBlockTokenizer(Tokenizer):
    """
    Tokenizer for brace-delimited blocks.

    This handles code blocks that are delimited by braces, which are common in
    languages like C, C++, Java, JavaScript, etc.
    """

    def __init__(self):
        """Initialize the brace block tokenizer."""
        super().__init__()
        self.language = "brace"

        # Set up basic brace block rules
        self.setup_brace_block_rules()

    def setup_brace_block_rules(self):
        """Set up tokenization rules for brace-delimited blocks."""
        # Opening brace
        self.add_rule(TokenRule(r"\{", TokenType.OPEN_BRACE))

        # Closing brace
        self.add_rule(TokenRule(r"\}", TokenType.CLOSE_BRACE))

        # Semicolon statement terminators
        self.add_rule(TokenRule(r";", TokenType.SEMICOLON))

        # Generic identifiers
        self.add_rule(TokenRule(r"[a-zA-Z_][a-zA-Z0-9_]*", TokenType.IDENTIFIER))

        # Add basic rules like whitespace, numbers, etc.
        self.setup_default_rules()

    def tokenize(self, code: str) -> List[Token]:
        """
        Tokenize code with brace-delimited blocks.

        Args:
            code: Source code to tokenize

        Returns:
            List of tokens
        """
        return super().tokenize(code)
