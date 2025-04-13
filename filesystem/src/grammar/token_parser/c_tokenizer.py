"""
C tokenizer for the grammar parser system.

This module provides a tokenizer specific to the C programming language.
Using regex-based rules for token identification.
"""

from typing import List
import re
from .token import Token, TokenType
from .tokenizer import Tokenizer, TokenRule


class CTokenizer(Tokenizer):
    """
    Tokenizer for C code.

    This tokenizer handles C-specific syntax such as preprocessor directives,
    structs, pointers, and C-specific operators.
    """

    def __init__(self):
        """Initialize the C tokenizer."""
        super().__init__()
        self.language = "c"

        # C keywords
        self.keywords = {
            "auto",
            "break",
            "case",
            "char",
            "const",
            "continue",
            "default",
            "do",
            "double",
            "else",
            "enum",
            "extern",
            "float",
            "for",
            "goto",
            "if",
            "int",
            "long",
            "register",
            "return",
            "short",
            "signed",
            "sizeof",
            "static",
            "struct",
            "switch",
            "typedef",
            "union",
            "unsigned",
            "void",
            "volatile",
            "while",
        }

        # C operators
        self.operators = {
            "+": TokenType.OPERATOR,
            "-": TokenType.OPERATOR,
            "*": TokenType.OPERATOR,
            "/": TokenType.OPERATOR,
            "%": TokenType.OPERATOR,
            "=": TokenType.EQUALS,
            "+=": TokenType.OPERATOR,
            "-=": TokenType.OPERATOR,
            "*=": TokenType.OPERATOR,
            "/=": TokenType.OPERATOR,
            "%=": TokenType.OPERATOR,
            "==": TokenType.OPERATOR,
            "!=": TokenType.OPERATOR,
            ">": TokenType.OPERATOR,
            "<": TokenType.OPERATOR,
            ">=": TokenType.OPERATOR,
            "<=": TokenType.OPERATOR,
            "&&": TokenType.OPERATOR,
            "||": TokenType.OPERATOR,
            "!": TokenType.OPERATOR,
            "&": TokenType.OPERATOR,
            "|": TokenType.OPERATOR,
            "^": TokenType.OPERATOR,
            "~": TokenType.OPERATOR,
            "<<": TokenType.OPERATOR,
            ">>": TokenType.OPERATOR,
            "<<=": TokenType.OPERATOR,
            ">>=": TokenType.OPERATOR,
            "&=": TokenType.OPERATOR,
            "|=": TokenType.OPERATOR,
            "^=": TokenType.OPERATOR,
            "++": TokenType.OPERATOR,
            "--": TokenType.OPERATOR,
            "->": TokenType.OPERATOR,
            ".": TokenType.DOT,
            ",": TokenType.COMMA,
            ":": TokenType.COLON,
            ";": TokenType.SEMICOLON,
        }

        # Set up C-specific rules
        self.setup_c_rules()

    def setup_c_rules(self):
        """Set up C-specific tokenization rules."""
        # Preprocessor directives
        self.add_rule(
            TokenRule(
                r"^[ \t]*#[ \t]*(include|define|ifdef|ifndef|if|else|elif|endif|undef|pragma|error|line).*?(?=\n|$)",
                TokenType.PREPROCESSOR,
                re.MULTILINE,
            )
        )

        # String literals
        self.add_rule(TokenRule(r'"(?:[^"\\]|\\.)*"', TokenType.STRING))

        # Character literals
        self.add_rule(TokenRule(r"'(?:[^'\\]|\\.)'", TokenType.STRING))

        # Line comments
        self.add_rule(TokenRule(r"//[^\n]*", TokenType.COMMENT))

        # Block comments
        self.add_rule(TokenRule(r"/\*(?:.|\n)*?\*/", TokenType.COMMENT, re.DOTALL))

        # Hexadecimal numbers
        self.add_rule(TokenRule(r"\b0[xX][0-9a-fA-F]+[uUlL]*\b", TokenType.NUMBER))

        # Octal numbers
        self.add_rule(TokenRule(r"\b0[0-7]+[uUlL]*\b", TokenType.NUMBER))

        # Decimal numbers
        self.add_rule(TokenRule(r"\b\d+[uUlL]*\b", TokenType.NUMBER))

        # Floating point numbers
        self.add_rule(
            TokenRule(r"\b\d+\.\d+([eE][-+]?\d+)?[fFlL]?\b", TokenType.NUMBER)
        )

        # Add standard rules
        self.setup_default_rules()

    def tokenize(self, code: str) -> List[Token]:
        """
        Tokenize the C code.

        Args:
            code: C source code to tokenize

        Returns:
            List of tokens
        """
        return super().tokenize(code)
