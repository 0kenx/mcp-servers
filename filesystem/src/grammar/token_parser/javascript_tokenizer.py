"""
JavaScript tokenizer for the grammar parser system.

This module provides a tokenizer specific to the JavaScript programming language.
Using regex-based rules for token identification.
"""

from typing import List
import re
from .token import Token, TokenType
from .tokenizer import Tokenizer, TokenRule


class JavaScriptTokenizer(Tokenizer):
    """
    Tokenizer for JavaScript code.

    This tokenizer handles JavaScript-specific syntax, including regular expressions,
    template literals, and more.
    """

    def __init__(self):
        """Initialize the JavaScript tokenizer."""
        super().__init__()
        self.language = "javascript"

        # JavaScript keywords
        self.keywords = {
            "await",
            "break",
            "case",
            "catch",
            "class",
            "const",
            "continue",
            "debugger",
            "default",
            "delete",
            "do",
            "else",
            "enum",
            "export",
            "extends",
            "false",
            "finally",
            "for",
            "function",
            "if",
            "implements",
            "import",
            "in",
            "instanceof",
            "interface",
            "let",
            "new",
            "null",
            "package",
            "private",
            "protected",
            "public",
            "return",
            "super",
            "switch",
            "static",
            "this",
            "throw",
            "try",
            "true",
            "typeof",
            "var",
            "void",
            "while",
            "with",
            "yield",
        }

        # JavaScript operators
        self.operators = {
            "+": TokenType.OPERATOR,
            "-": TokenType.OPERATOR,
            "*": TokenType.OPERATOR,
            "**": TokenType.OPERATOR,
            "/": TokenType.OPERATOR,
            "%": TokenType.OPERATOR,
            "++": TokenType.OPERATOR,
            "--": TokenType.OPERATOR,
            "=": TokenType.EQUALS,
            "+=": TokenType.OPERATOR,
            "-=": TokenType.OPERATOR,
            "*=": TokenType.OPERATOR,
            "/=": TokenType.OPERATOR,
            "%=": TokenType.OPERATOR,
            "**=": TokenType.OPERATOR,
            "&=": TokenType.OPERATOR,
            "|=": TokenType.OPERATOR,
            "^=": TokenType.OPERATOR,
            ">>=": TokenType.OPERATOR,
            "<<=": TokenType.OPERATOR,
            ">>>=": TokenType.OPERATOR,
            "&&": TokenType.OPERATOR,
            "||": TokenType.OPERATOR,
            "??": TokenType.OPERATOR,
            "?.": TokenType.OPERATOR,
            "&": TokenType.OPERATOR,
            "|": TokenType.OPERATOR,
            "^": TokenType.OPERATOR,
            "~": TokenType.OPERATOR,
            "<<": TokenType.OPERATOR,
            ">>": TokenType.OPERATOR,
            ">>>": TokenType.OPERATOR,
            "==": TokenType.OPERATOR,
            "===": TokenType.OPERATOR,
            "!=": TokenType.OPERATOR,
            "!==": TokenType.OPERATOR,
            "<": TokenType.OPERATOR,
            ">": TokenType.OPERATOR,
            "<=": TokenType.OPERATOR,
            ">=": TokenType.OPERATOR,
            "!": TokenType.OPERATOR,
            "?": TokenType.OPERATOR,
            ":": TokenType.COLON,
            ".": TokenType.DOT,
            "...": TokenType.OPERATOR,
            "=>": TokenType.FAT_ARROW,
            ",": TokenType.COMMA,
            ";": TokenType.SEMICOLON,
        }

        # Set up JavaScript-specific rules
        self.setup_javascript_rules()

    def setup_javascript_rules(self):
        """Set up JavaScript-specific tokenization rules."""
        # String literals - single quoted
        self.add_rule(TokenRule(r"'(?:[^'\\]|\\.)*'", TokenType.STRING))

        # String literals - double quoted
        self.add_rule(TokenRule(r'"(?:[^"\\]|\\.)*"', TokenType.STRING))

        # Template literals (backtick strings)
        # Simple template literals without interpolation
        self.add_rule(TokenRule(r"`(?:[^`\\$]|\\.|\\$)*`", TokenType.STRING))

        # Template literals with interpolation - more complex and requires special handling
        # This is a simplified version - in a real implementation, these would need to be
        # processed in multiple steps
        self.add_rule(
            TokenRule(
                r"`(?:[^`\\$]|\\.|\\$)*\${",
                TokenType.STRING,
                0,
                lambda m: {"template_start": True},
            )
        )

        self.add_rule(
            TokenRule(
                r"}\s*(?:[^`\\$]|\\.|\\$)*`",
                TokenType.STRING,
                0,
                lambda m: {"template_end": True},
            )
        )

        self.add_rule(
            TokenRule(
                r"}\s*(?:[^`\\$]|\\.|\\$)*\${",
                TokenType.STRING,
                0,
                lambda m: {"template_middle": True},
            )
        )

        # Regular expressions
        # This regex tries to capture regex literals, but it's simplified
        # In practice, distinguishing regex literals from division operators
        # requires context-sensitive parsing
        self.add_rule(
            TokenRule(r"/(?!\*|/)(?:[^/\\\n]|\\.)+/[gimyus]*", TokenType.OPERATOR)
        )

        # Line comments
        self.add_rule(TokenRule(r"//[^\n]*", TokenType.COMMENT))

        # Block comments
        self.add_rule(TokenRule(r"/\*(?:.|\n)*?\*/", TokenType.COMMENT, re.DOTALL))

        # Numbers - decimal, hex, octal, binary, scientific notation
        self.add_rule(
            TokenRule(
                r"\b(?:0[xX][0-9a-fA-F]+|0[oO][0-7]+|0[bB][01]+|\d+(?:\.\d+)?(?:[eE][+-]?\d+)?)\b",
                TokenType.NUMBER,
            )
        )

        # BigInt literals
        self.add_rule(TokenRule(r"\b\d+n\b", TokenType.NUMBER))

        # Function declaration
        self.add_rule(
            TokenRule(
                r"\bfunction\s+([a-zA-Z_$][a-zA-Z0-9_$]*)",
                TokenType.KEYWORD,
                0,
                lambda m: {"function_name": m.group(1)},
            )
        )

        # Arrow function
        self.add_rule(
            TokenRule(
                r"(?:(?:\([^()]*\))|(?:[a-zA-Z_$][a-zA-Z0-9_$]*))\s*=>",
                TokenType.FAT_ARROW,
            )
        )

        # Class declaration
        self.add_rule(
            TokenRule(
                r"\bclass\s+([a-zA-Z_$][a-zA-Z0-9_$]*)",
                TokenType.KEYWORD,
                0,
                lambda m: {"class_name": m.group(1)},
            )
        )

        # Standard rules are added after our custom rules
        self.setup_default_rules()

    def tokenize(self, code: str) -> List[Token]:
        """
        Tokenize JavaScript code.

        Args:
            code: JavaScript source code

        Returns:
            List of tokens
        """
        return super().tokenize(code)
