"""
Python tokenizer for the grammar parser system.

This module provides a tokenizer specific to the Python programming language.
Using regex-based rules for token identification.
"""

from typing import List, Dict, Set, Tuple, Optional, Any, Match
import re
from .token import Token, TokenType
from .tokenizer import Tokenizer, TokenizerState, TokenRule


class PythonTokenizer(Tokenizer):
    """
    Tokenizer for Python code.
    
    This tokenizer handles Python-specific syntax, including indentation-based blocks,
    triple-quoted strings, and more.
    """
    
    def __init__(self):
        """Initialize the Python tokenizer."""
        super().__init__()
        self.language = "python"
        
        # Python keywords
        self.keywords = {
            "and", "as", "assert", "async", "await", "break", "class", "continue",
            "def", "del", "elif", "else", "except", "finally", "for", "from",
            "global", "if", "import", "in", "is", "lambda", "nonlocal", "not",
            "or", "pass", "raise", "return", "try", "while", "with", "yield",
            "True", "False", "None"
        }
        
        # Python operators
        self.operators = {
            "+": TokenType.OPERATOR,
            "-": TokenType.OPERATOR,
            "*": TokenType.OPERATOR,
            "**": TokenType.OPERATOR,
            "/": TokenType.OPERATOR,
            "//": TokenType.OPERATOR,
            "%": TokenType.OPERATOR,
            "@": TokenType.OPERATOR,
            "<<": TokenType.OPERATOR,
            ">>": TokenType.OPERATOR,
            "&": TokenType.OPERATOR,
            "|": TokenType.OPERATOR,
            "^": TokenType.OPERATOR,
            "~": TokenType.OPERATOR,
            "<": TokenType.OPERATOR,
            ">": TokenType.OPERATOR,
            "<=": TokenType.OPERATOR,
            ">=": TokenType.OPERATOR,
            "==": TokenType.OPERATOR,
            "!=": TokenType.OPERATOR,
            "=": TokenType.EQUALS,
            "+=": TokenType.OPERATOR,
            "-=": TokenType.OPERATOR,
            "*=": TokenType.OPERATOR,
            "/=": TokenType.OPERATOR,
            "//=": TokenType.OPERATOR,
            "%=": TokenType.OPERATOR,
            "@=": TokenType.OPERATOR,
            "&=": TokenType.OPERATOR,
            "|=": TokenType.OPERATOR,
            "^=": TokenType.OPERATOR,
            ">>=": TokenType.OPERATOR,
            "<<=": TokenType.OPERATOR,
            "**=": TokenType.OPERATOR,
            "->": TokenType.ARROW,
            ":": TokenType.COLON,
        }
        
        # Set up Python-specific rules
        self.setup_python_rules()
    
    def setup_python_rules(self):
        """Set up Python-specific tokenization rules."""
        # String patterns for Python
        # Single-quoted strings
        self.add_rule(TokenRule(
            r"'(?:[^'\\]|\\.|\\\\)*'",
            TokenType.STRING
        ))
        
        # Double-quoted strings
        self.add_rule(TokenRule(
            r'"(?:[^"\\]|\\.|\\\\)*"',
            TokenType.STRING
        ))
        
        # Triple single-quoted strings (multiline)
        self.add_rule(TokenRule(
            r"'''(?:.|\n)*?'''",
            TokenType.STRING,
            re.DOTALL
        ))
        
        # Triple double-quoted strings (multiline)
        self.add_rule(TokenRule(
            r'"""(?:.|\n)*?"""',
            TokenType.STRING,
            re.DOTALL
        ))
        
        # Comments
        self.add_rule(TokenRule(
            r"#[^\n]*",
            TokenType.COMMENT
        ))
        
        # Python decimal and hex numbers
        self.add_rule(TokenRule(
            r"\b(?:0[xX][0-9a-fA-F]+|0[bB][01]+|0[oO][0-7]+|\d+(?:\.\d+)?(?:[eE][+-]?\d+)?)\b",
            TokenType.NUMBER
        ))
        
        # Leading indentation (spaces or tabs at start of line)
        self.add_rule(TokenRule(
            r"^[ \t]+",
            TokenType.WHITESPACE,
            re.MULTILINE,
            lambda m: {"indent_size": len(m.group(0))}
        ))
        
        # Standard rules are added after our custom rules
        self.setup_default_rules()
    
    def tokenize(self, code: str) -> List[Token]:
        """
        Tokenize Python code.
        
        Args:
            code: Python source code
        
        Returns:
            List of tokens
        """
        # Add newline at the end if there isn't one to simplify tokenization
        if not code.endswith('\n'):
            code += '\n'
            
        return super().tokenize(code) 