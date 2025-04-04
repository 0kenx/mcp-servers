"""
C++ tokenizer for the grammar parser system.

This module provides a tokenizer specific to the C++ programming language.
Using regex-based rules for token identification.
"""

from typing import List, Dict, Set, Tuple, Optional, Any, Match
import re
from .token import Token, TokenType
from .c_tokenizer import CTokenizer
from .tokenizer import TokenRule


class CppTokenizer(CTokenizer):
    """
    Tokenizer for C++ code.
    
    This extends the C tokenizer to handle C++-specific token types.
    """
    
    def __init__(self):
        """Initialize the C++ tokenizer."""
        super().__init__()
        self.language = "c++"
        
        # Add C++-specific keywords
        self.keywords.update({
            "alignas", "alignof", "and", "and_eq", "asm", "bitand", "bitor", "bool",
            "catch", "class", "compl", "concept", "consteval", "constexpr", "constinit",
            "const_cast", "co_await", "co_return", "co_yield", "decltype", "delete",
            "dynamic_cast", "explicit", "export", "false", "friend", "inline", "mutable",
            "namespace", "new", "noexcept", "not", "not_eq", "nullptr", "operator", "or",
            "or_eq", "private", "protected", "public", "reinterpret_cast", "requires",
            "static_assert", "static_cast", "template", "this", "thread_local", "throw",
            "true", "try", "typeid", "typename", "using", "virtual", "wchar_t", "xor", "xor_eq"
        })
        
        # Add C++-specific operators
        self.operators.update({
            "::": TokenType.OPERATOR,    # Scope resolution
            "<=>": TokenType.OPERATOR,   # Three-way comparison (C++20)
            ".*": TokenType.OPERATOR,    # Pointer to member
            "->*": TokenType.OPERATOR    # Pointer to member
        })
        
        # Setup C++-specific rules
        self.setup_cpp_rules()
    
    def setup_cpp_rules(self):
        """Set up C++-specific tokenization rules."""
        # C++ raw string literals
        self.add_rule(TokenRule(
            r'R"(\w*)\((.*?)\)\w*"',
            TokenType.STRING,
            re.DOTALL
        ))
        
        # C++ namespaces
        self.add_rule(TokenRule(
            r'\b(namespace)\s+([a-zA-Z_][a-zA-Z0-9_]*)',
            TokenType.KEYWORD,
            0,
            lambda m: {"namespace_name": m.group(2)}
        ))
        
        # C++ class/struct definition
        self.add_rule(TokenRule(
            r'\b(class|struct)\s+([a-zA-Z_][a-zA-Z0-9_]*)',
            TokenType.KEYWORD,
            0,
            lambda m: {"class_name": m.group(2)}
        ))
        
        # C++ template parameters
        self.add_rule(TokenRule(
            r'<(?:[^<>]|<(?:[^<>]|<[^<>]*>)*>)*>',
            TokenType.OPERATOR
        ))
        
        # Update rules from parent
        self.rules = []  # Clear rules from parent initialization
        self.setup_c_rules()  # Re-setup C rules
        
        # Standard rules are added after our custom rules
        self.setup_default_rules()
    
    def tokenize(self, code: str) -> List[Token]:
        """
        Tokenize the C++ code.
        
        Args:
            code: C++ source code to tokenize
            
        Returns:
            List of tokens
        """
        return super().tokenize(code)
