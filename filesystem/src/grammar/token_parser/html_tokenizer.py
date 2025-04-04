"""
HTML tokenizer for the grammar parser system.

This module provides a tokenizer specific to the HTML language.
Using regex-based rules for token identification.
"""

from typing import List, Dict, Set, Tuple, Optional, Any, Match
import re
from .token import Token, TokenType
from .tokenizer import Tokenizer, TokenizerState, TokenRule


class HTMLTokenizer(Tokenizer):
    """
    Tokenizer for HTML code.
    
    This tokenizer handles HTML-specific tokens such as tags, attributes,
    and text content.
    """
    
    def __init__(self):
        """Initialize the HTML tokenizer."""
        super().__init__()
        self.language = "html"
        
        # Set up HTML-specific rules
        self.setup_html_rules()
    
    def setup_html_rules(self):
        """Set up HTML-specific tokenization rules."""
        # HTML comments
        self.add_rule(TokenRule(
            r"<!--(?:.|\n)*?-->",
            TokenType.COMMENT,
            re.DOTALL
        ))
        
        # Doctype declaration
        self.add_rule(TokenRule(
            r"<!DOCTYPE(?:.|\n)*?>",
            TokenType.DOCTYPE,
            re.DOTALL | re.IGNORECASE
        ))
        
        # Self-closing tags
        self.add_rule(TokenRule(
            r"<[a-zA-Z][a-zA-Z0-9_:.-]*(?:\s+[a-zA-Z_:][a-zA-Z0-9_:.-]*(?:\s*=\s*(?:\"[^\"]*\"|'[^']*'|[^'\"\s>]*))?)*\s*/\s*>",
            TokenType.SELF_CLOSING_TAG
        ))
        
        # Opening tags with attributes
        self.add_rule(TokenRule(
            r"<[a-zA-Z][a-zA-Z0-9_:.-]*(?:\s+[a-zA-Z_:][a-zA-Z0-9_:.-]*(?:\s*=\s*(?:\"[^\"]*\"|'[^']*'|[^'\"\s>]*))?)*\s*>",
            TokenType.OPEN_TAG
        ))
        
        # Closing tags
        self.add_rule(TokenRule(
            r"</[a-zA-Z][a-zA-Z0-9_:.-]*\s*>",
            TokenType.CLOSE_TAG
        ))
        
        # Tag attributes (extracted from tag)
        self.add_rule(TokenRule(
            r"[a-zA-Z_:][a-zA-Z0-9_:.-]*\s*=\s*(?:\"[^\"]*\"|'[^']*'|[^'\"\s>]*)",
            TokenType.ATTRIBUTE
        ))
        
        # Script tags with content
        self.add_rule(TokenRule(
            r"<script(?:\s+[a-zA-Z_:][a-zA-Z0-9_:.-]*(?:\s*=\s*(?:\"[^\"]*\"|'[^']*'|[^'\"\s>]*))?)*\s*>(?:.|\n)*?</script\s*>",
            TokenType.SCRIPT,
            re.DOTALL | re.IGNORECASE
        ))
        
        # Style tags with content
        self.add_rule(TokenRule(
            r"<style(?:\s+[a-zA-Z_:][a-zA-Z0-9_:.-]*(?:\s*=\s*(?:\"[^\"]*\"|'[^']*'|[^'\"\s>]*))?)*\s*>(?:.|\n)*?</style\s*>",
            TokenType.STYLE,
            re.DOTALL | re.IGNORECASE
        ))
        
        # HTML entities
        self.add_rule(TokenRule(
            r"&[a-zA-Z0-9#]+;",
            TokenType.ENTITY
        ))
        
        # Text content (anything that's not a tag, comment, etc.)
        self.add_rule(TokenRule(
            r"[^<&\s]+",
            TokenType.TEXT
        ))
        
        # Whitespace
        self.add_rule(TokenRule(
            r"\s+",
            TokenType.WHITESPACE
        ))
    
    def tokenize(self, code: str) -> List[Token]:
        """
        Tokenize HTML code into a list of tokens.
        
        Args:
            code: HTML source code to tokenize
            
        Returns:
            List of tokens
        """
        return super().tokenize(code)

