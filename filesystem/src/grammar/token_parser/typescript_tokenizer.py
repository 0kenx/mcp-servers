"""
TypeScript tokenizer for the grammar parser system.

This module provides a tokenizer specific to the TypeScript programming language.
Using regex-based rules for token identification.
"""

from typing import List, Dict, Set, Tuple, Optional, Any, Match
import re
from .token import Token, TokenType
from .tokenizer import Tokenizer, TokenizerState, TokenRule


class TypeScriptTokenizer(Tokenizer):
    """
    Tokenizer for TypeScript code.
    
    This tokenizer handles TypeScript-specific syntax, including type annotations,
    generics, interfaces, and more.
    """
    
    def __init__(self):
        """Initialize the TypeScript tokenizer."""
        super().__init__()
        self.language = "typescript"
        
        # TypeScript keywords
        self.keywords = {
            "abstract", "any", "as", "async", "await", "boolean", "break", "case",
            "catch", "class", "const", "constructor", "continue", "debugger", "declare",
            "default", "delete", "do", "else", "enum", "export", "extends", "false",
            "finally", "for", "from", "function", "get", "if", "implements", "import",
            "in", "infer", "instanceof", "interface", "is", "keyof", "let", "module", 
            "namespace", "never", "new", "null", "number", "object", "package", "private",
            "protected", "public", "readonly", "require", "return", "set", "static",
            "string", "super", "switch", "symbol", "this", "throw", "true", "try", 
            "type", "typeof", "undefined", "unique", "unknown", "var", "void", "while",
            "with", "yield"
        }
        
        # TypeScript operators
        self.operators = {
            "+": TokenType.OPERATOR,
            "-": TokenType.OPERATOR,
            "*": TokenType.OPERATOR,
            "**": TokenType.OPERATOR,
            "/": TokenType.OPERATOR,
            "%": TokenType.OPERATOR,
            "++": TokenType.OPERATOR,
            "--": TokenType.OPERATOR,
            "<<": TokenType.OPERATOR,
            ">>": TokenType.OPERATOR,
            ">>>": TokenType.OPERATOR,
            "&": TokenType.OPERATOR,
            "|": TokenType.OPERATOR,
            "^": TokenType.OPERATOR,
            "~": TokenType.OPERATOR,
            "!": TokenType.OPERATOR,
            "<": TokenType.OPERATOR,
            ">": TokenType.OPERATOR,
            "<=": TokenType.OPERATOR,
            ">=": TokenType.OPERATOR,
            "==": TokenType.OPERATOR,
            "===": TokenType.OPERATOR,
            "!=": TokenType.OPERATOR,
            "!==": TokenType.OPERATOR,
            "=": TokenType.EQUALS,
            "+=": TokenType.OPERATOR,
            "-=": TokenType.OPERATOR,
            "*=": TokenType.OPERATOR,
            "/=": TokenType.OPERATOR,
            "%=": TokenType.OPERATOR,
            "&=": TokenType.OPERATOR,
            "|=": TokenType.OPERATOR,
            "^=": TokenType.OPERATOR,
            ">>=": TokenType.OPERATOR,
            "<<=": TokenType.OPERATOR,
            ">>>=": TokenType.OPERATOR,
            "**=": TokenType.OPERATOR,
            "&&": TokenType.OPERATOR,
            "||": TokenType.OPERATOR,
            "??": TokenType.OPERATOR,
            "?.": TokenType.OPERATOR,
            "=>": TokenType.FAT_ARROW,
            "?:": TokenType.OPERATOR,
            "?": TokenType.OPERATOR,
            ".": TokenType.DOT,
            ":": TokenType.COLON,
            ";": TokenType.SEMICOLON,
            ",": TokenType.COMMA,
        }
        
        # Set up TypeScript-specific rules
        self.setup_typescript_rules()
    
    def setup_typescript_rules(self):
        """Set up TypeScript-specific tokenization rules."""
        # String patterns for TypeScript
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
        
        # Template literals (backtick strings)
        self.add_rule(TokenRule(
            r'`(?:[^`\\]|\\.|\\${|\\\\)*(?:`|$)',
            TokenType.STRING
        ))
        
        # Template literal expressions ${...}
        self.add_rule(TokenRule(
            r'\${(?:[^}]|\\})*}',
            TokenType.STRING
        ))
        
        # Line comments
        self.add_rule(TokenRule(
            r"//[^\n]*",
            TokenType.COMMENT
        ))
        
        # Block comments
        self.add_rule(TokenRule(
            r"/\*(?:.|\n)*?\*/",
            TokenType.COMMENT,
            re.DOTALL
        ))
        
        # Regular expressions
        self.add_rule(TokenRule(
            r"/(?!\*|/)(?:[^/\\\n]|\\.)+/[gimyus]*",
            TokenType.OPERATOR
        ))
        
        # Numbers (decimal, hex, octal, binary, scientific notation)
        self.add_rule(TokenRule(
            r"\b(?:0[xX][0-9a-fA-F]+|0[oO][0-7]+|0[bB][01]+|\d+(?:\.\d+)?(?:[eE][+-]?\d+)?n?)\b",
            TokenType.NUMBER
        ))
        
        # Type annotations
        # Generic type parameters
        self.add_rule(TokenRule(
            r"<(?:[a-zA-Z_$][\w$]*(?:\s+extends\s+[^>]+)?(?:,\s*)?)+>",
            TokenType.OPERATOR
        ))
        
        # Standard rules are added after our custom rules
        self.setup_default_rules()
    
    def tokenize(self, code: str) -> List[Token]:
        """
        Tokenize TypeScript code.
        
        Args:
            code: TypeScript source code
        
        Returns:
            List of tokens
        """
        return super().tokenize(code)
