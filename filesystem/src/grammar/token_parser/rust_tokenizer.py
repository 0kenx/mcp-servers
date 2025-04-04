"""
Rust tokenizer for the grammar parser system.

This module provides a tokenizer specific to the Rust programming language.
Using regex-based rules for token identification.
"""

from typing import List, Dict, Set, Tuple, Optional, Any, Match
import re
from .token import Token, TokenType
from .tokenizer import Tokenizer, TokenizerState, TokenRule


class RustTokenizer(Tokenizer):
    """
    Tokenizer for Rust code.
    
    This tokenizer handles Rust-specific syntax including attributes, lifetimes,
    and other Rust-specific features.
    """
    
    def __init__(self):
        """Initialize the Rust tokenizer."""
        super().__init__()
        self.language = "rust"
        
        # Rust keywords
        self.keywords = {
            "as", "async", "await", "break", "const", "continue", "crate", "dyn",
            "else", "enum", "extern", "false", "fn", "for", "if", "impl", "in",
            "let", "loop", "match", "mod", "move", "mut", "pub", "ref", "return",
            "self", "Self", "static", "struct", "super", "trait", "true", "type",
            "unsafe", "use", "where", "while", "abstract", "become", "box", "do",
            "final", "macro", "override", "priv", "try", "typeof", "unsized", "virtual",
            "yield"
        }
        
        # Rust operators
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
            "::": TokenType.OPERATOR,
            "->": TokenType.ARROW,
            "=>": TokenType.FAT_ARROW,
            "..": TokenType.OPERATOR,
            "...": TokenType.OPERATOR,
            ".": TokenType.DOT,
            ",": TokenType.COMMA,
            ":": TokenType.COLON,
            ";": TokenType.SEMICOLON,
            "@": TokenType.OPERATOR,
            "#": TokenType.OPERATOR,
            "?": TokenType.OPERATOR
        }
        
        # Set up Rust-specific rules
        self.setup_rust_rules()
    
    def setup_rust_rules(self):
        """Set up Rust-specific tokenization rules."""
        # Attributes
        self.add_rule(TokenRule(
            r"#\s*!\s*\[[^\]]*\]|#\s*\[[^\]]*\]",
            TokenType.ATTRIBUTE
        ))
        
        # Lifetimes
        self.add_rule(TokenRule(
            r"'[a-zA-Z_][a-zA-Z0-9_]*",
            TokenType.IDENTIFIER,
            0,
            lambda m: {"is_lifetime": True}
        ))
        
        # Raw string literals r"..." or r#"..."#
        self.add_rule(TokenRule(
            r'r#*"(?:\\.|[^\\"])*"#*',
            TokenType.STRING
        ))
        
        # Byte string literals b"..." or br#"..."#
        self.add_rule(TokenRule(
            r'b"(?:\\.|[^\\"])*"|br#*"(?:\\.|[^\\"])*"#*',
            TokenType.STRING
        ))
        
        # Regular string literals
        self.add_rule(TokenRule(
            r'"(?:\\.|[^\\"])*"',
            TokenType.STRING
        ))
        
        # Character literals
        self.add_rule(TokenRule(
            r"'(?:\\.|[^\\'])+'",
            TokenType.STRING
        ))
        
        # Line comments
        self.add_rule(TokenRule(
            r"//[^\n]*",
            TokenType.COMMENT
        ))
        
        # Block comments (non-recursive)
        self.add_rule(TokenRule(
            r"/\*(?:.|\n)*?\*/",
            TokenType.COMMENT,
            re.DOTALL
        ))
        
        # Integer literals with suffixes
        self.add_rule(TokenRule(
            r"\b\d[\d_]*(?:u8|u16|u32|u64|u128|usize|i8|i16|i32|i64|i128|isize)?\b",
            TokenType.NUMBER
        ))
        
        # Hexadecimal literals
        self.add_rule(TokenRule(
            r"\b0x[0-9a-fA-F_]+(?:u8|u16|u32|u64|u128|usize|i8|i16|i32|i64|i128|isize)?\b",
            TokenType.NUMBER
        ))
        
        # Octal literals
        self.add_rule(TokenRule(
            r"\b0o[0-7_]+(?:u8|u16|u32|u64|u128|usize|i8|i16|i32|i64|i128|isize)?\b",
            TokenType.NUMBER
        ))
        
        # Binary literals
        self.add_rule(TokenRule(
            r"\b0b[01_]+(?:u8|u16|u32|u64|u128|usize|i8|i16|i32|i64|i128|isize)?\b",
            TokenType.NUMBER
        ))
        
        # Floating point literals
        self.add_rule(TokenRule(
            r"\b\d[\d_]*\.\d[\d_]*(?:[eE][+-]?[\d_]+)?(?:f32|f64)?\b",
            TokenType.NUMBER
        ))
        
        # Function definitions
        self.add_rule(TokenRule(
            r"\bfn\s+([a-zA-Z_][a-zA-Z0-9_]*)",
            TokenType.KEYWORD,
            0,
            lambda m: {"function_name": m.group(1)}
        ))
        
        # Struct definitions
        self.add_rule(TokenRule(
            r"\bstruct\s+([a-zA-Z_][a-zA-Z0-9_]*)",
            TokenType.KEYWORD,
            0,
            lambda m: {"struct_name": m.group(1)}
        ))
        
        # Enum definitions
        self.add_rule(TokenRule(
            r"\benum\s+([a-zA-Z_][a-zA-Z0-9_]*)",
            TokenType.KEYWORD,
            0,
            lambda m: {"enum_name": m.group(1)}
        ))
        
        # Trait definitions
        self.add_rule(TokenRule(
            r"\btrait\s+([a-zA-Z_][a-zA-Z0-9_]*)",
            TokenType.KEYWORD,
            0,
            lambda m: {"trait_name": m.group(1)}
        ))
        
        # Module definitions
        self.add_rule(TokenRule(
            r"\bmod\s+([a-zA-Z_][a-zA-Z0-9_]*)",
            TokenType.KEYWORD,
            0,
            lambda m: {"module_name": m.group(1)}
        ))
        
        # Standard rules are added after our custom rules
        self.setup_default_rules()
    
    def tokenize(self, code: str) -> List[Token]:
        """
        Tokenize the Rust code.
        
        Args:
            code: Rust source code to tokenize
            
        Returns:
            List of tokens
        """
        return super().tokenize(code)
