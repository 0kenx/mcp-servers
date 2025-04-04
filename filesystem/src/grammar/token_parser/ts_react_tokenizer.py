"""
TypeScript React tokenizer for the grammar parser system.

This module provides a tokenizer specific to TypeScript with JSX/TSX syntax.
Using regex-based rules for token identification.
"""

from typing import List, Dict, Set, Tuple, Optional, Any, Match
import re
from .token import Token, TokenType
from .tokenizer import TokenizerState, TokenRule
from .typescript_tokenizer import TypeScriptTokenizer


class TSReactTokenizer(TypeScriptTokenizer):
    """
    Tokenizer for TypeScript React (TSX) code.
    
    This extends the TypeScript tokenizer to handle JSX syntax.
    """
    
    def __init__(self):
        """Initialize the TypeScript React tokenizer."""
        super().__init__()
        self.language = "tsx"
        
        # Add JSX-specific rules
        self.setup_jsx_rules()
    
    def setup_jsx_rules(self):
        """Add JSX-specific tokenization rules to the existing TypeScript rules."""
        # JSX opening tags: <TagName or <TagName.SubComponent
        self.add_rule(TokenRule(
            r"<([A-Z][a-zA-Z0-9]*(?:\.[A-Z][a-zA-Z0-9]*)*|[a-z][a-zA-Z0-9]*-*[a-zA-Z0-9]*)(?=[\s/>])",
            TokenType.JSX_TAG
        ))
        
        # JSX closing tags: </TagName>
        self.add_rule(TokenRule(
            r"</([A-Z][a-zA-Z0-9]*(?:\.[A-Z][a-zA-Z0-9]*)*|[a-z][a-zA-Z0-9]*-*[a-zA-Z0-9]*)>",
            TokenType.JSX_TAG
        ))
        
        # JSX tag attributes: name="value" or name={value}
        self.add_rule(TokenRule(
            r"[a-zA-Z][a-zA-Z0-9]*(?:[-:][a-zA-Z][a-zA-Z0-9]*)*(?==)",
            TokenType.JSX_ATTRIBUTE
        ))
        
        # JSX self-closing tag end: />
        self.add_rule(TokenRule(
            r"/>",
            TokenType.JSX_TAG
        ))
        
        # JSX tag end: >
        self.add_rule(TokenRule(
            r">(?![a-zA-Z0-9])",
            TokenType.JSX_TAG
        ))
        
        # JSX expressions: {expression}
        self.add_rule(TokenRule(
            r"\{(?:[^{}]|\{[^{}]*\})*\}",
            TokenType.JSX_EXPRESSION,
            re.DOTALL
        ))
        
        # JSX text content
        self.add_rule(TokenRule(
            r"(?<=>)[^<{]+(?=<|\{|$)",
            TokenType.JSX_TEXT
        ))
        
        # JSX fragment opening: <>
        self.add_rule(TokenRule(
            r"<>",
            TokenType.JSX_TAG
        ))
        
        # JSX fragment closing: </>
        self.add_rule(TokenRule(
            r"</>",
            TokenType.JSX_TAG
        ))
    
    def tokenize(self, code: str) -> List[Token]:
        """
        Tokenize TSX code.
        
        Args:
            code: TypeScript React source code
        
        Returns:
            List of tokens
        """
        return super().tokenize(code)

