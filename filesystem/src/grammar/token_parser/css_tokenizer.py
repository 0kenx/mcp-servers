"""
CSS tokenizer for the grammar parser system.

This module provides a tokenizer specific to the CSS language.
Using regex-based rules for token identification.
"""

from typing import List, Dict, Set, Tuple, Optional, Any, Match
import re
from .token import Token, TokenType
from .tokenizer import Tokenizer, TokenizerState, TokenRule


class CSSTokenizer(Tokenizer):
    """
    Tokenizer for CSS code.
    
    This tokenizer handles CSS-specific tokens such as selectors, properties,
    values, and special CSS syntax.
    """
    
    def __init__(self):
        """Initialize the CSS tokenizer."""
        super().__init__()
        self.language = "css"
        
        # Set up CSS-specific rules
        self.setup_css_rules()
    
    def setup_css_rules(self):
        """Set up CSS-specific tokenization rules."""
        # Comments
        self.add_rule(TokenRule(
            r"/\*(?:.|\n)*?\*/", 
            TokenType.COMMENT,
            re.DOTALL
        ))
        
        # At-rules (@media, @import, etc.)
        self.add_rule(TokenRule(
            r"@[a-zA-Z-]+", 
            TokenType.AT_RULE
        ))
        
        # Property names (inside rules)
        self.add_rule(TokenRule(
            r"[a-zA-Z-]+(?=\s*:)", 
            TokenType.PROPERTY
        ))
        
        # Property values (after colons)
        self.add_rule(TokenRule(
            r":\s*([^;}{]+)",
            TokenType.VALUE,
            0,
            lambda m: {"value": m.group(1).strip()}
        ))
        
        # Selectors (ID, class, element, pseudo-class, pseudo-element)
        # ID selectors
        self.add_rule(TokenRule(
            r"#[a-zA-Z][a-zA-Z0-9_-]*",
            TokenType.SELECTOR
        ))
        
        # Class selectors
        self.add_rule(TokenRule(
            r"\.[a-zA-Z][a-zA-Z0-9_-]*",
            TokenType.SELECTOR
        ))
        
        # Element selectors
        self.add_rule(TokenRule(
            r"[a-zA-Z][a-zA-Z0-9_-]*(?=[\s{:+~>\[,]|$)",
            TokenType.SELECTOR
        ))
        
        # Pseudo-classes and pseudo-elements
        self.add_rule(TokenRule(
            r":{1,2}[a-zA-Z][a-zA-Z0-9_-]*(?:\([^)]*\))?",
            TokenType.SELECTOR
        ))
        
        # Attribute selectors
        self.add_rule(TokenRule(
            r"\[[^\]]+\]",
            TokenType.SELECTOR
        ))
        
        # Combinators
        self.add_rule(TokenRule(
            r"[>+~]",
            TokenType.OPERATOR
        ))
        
        # Important declaration
        self.add_rule(TokenRule(
            r"!important",
            TokenType.IDENTIFIER
        ))
        
        # Units (px, em, rem, vh, etc.)
        self.add_rule(TokenRule(
            r"[0-9]+(?:\.[0-9]+)?(?:px|em|rem|%|vh|vw|vmin|vmax|ch|ex|cm|mm|in|pt|pc|fr|deg|rad|turn|s|ms|Hz|kHz|dpi|dpcm|dppx)?",
            TokenType.NUMBER
        ))
        
        # Color values
        self.add_rule(TokenRule(
            r"#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})",
            TokenType.NUMBER
        ))
        
        # Functions like rgb(), calc(), url(), etc.
        self.add_rule(TokenRule(
            r"[a-zA-Z-]+\([^)]*\)",
            TokenType.IDENTIFIER
        ))
        
        # Strings
        self.add_rule(TokenRule(
            r'"(?:[^"\\]|\\.)*"',
            TokenType.STRING
        ))
        
        self.add_rule(TokenRule(
            r"'(?:[^'\\]|\\.)*'",
            TokenType.STRING
        ))
        
        # Standard rules are added after our custom rules
        self.setup_default_rules()
    
    def tokenize(self, code: str) -> List[Token]:
        """
        Tokenize CSS code into a list of tokens.
        
        Args:
            code: CSS source code to tokenize
            
        Returns:
            List of tokens
        """
        return super().tokenize(code)

