"""
Generic tokenizers for the grammar parser system.
This module provides a tokenizer for languages that use keyword patterns.
Using regex-based rules for token identification.
"""

from typing import List
from .token import Token, TokenType
from .tokenizer import Tokenizer, TokenRule


class KeywordPatternTokenizer(Tokenizer):
    """
    Tokenizer for keyword-pattern-based blocks.

    This handles code blocks that are defined by a keyword pattern,
    such as if-then-else, begin-end, etc.
    """

    def __init__(self):
        """Initialize the keyword pattern tokenizer."""
        super().__init__()
        self.language = "keyword_pattern"

        # Set up basic keyword pattern rules
        self.setup_keyword_pattern_rules()

    def setup_keyword_pattern_rules(self):
        """Set up tokenization rules for keyword-pattern-based blocks."""
        # Common block start keywords
        self.add_rule(TokenRule(r"\b(if|while|for|begin)\b", TokenType.KEYWORD))

        # Common block end keywords
        self.add_rule(TokenRule(r"\b(endif|endwhile|endfor|end)\b", TokenType.KEYWORD))

        # Common conditional keywords
        self.add_rule(TokenRule(r"\b(then|else|elsif|elif)\b", TokenType.KEYWORD))

        # Generic identifiers
        self.add_rule(TokenRule(r"[a-zA-Z_][a-zA-Z0-9_]*", TokenType.IDENTIFIER))

        # Add basic rules like whitespace, numbers, etc.
        self.setup_default_rules()

    def tokenize(self, code: str) -> List[Token]:
        """
        Tokenize code with keyword-pattern-based blocks.

        Args:
            code: Source code to tokenize

        Returns:
            List of tokens
        """
        return super().tokenize(code)
