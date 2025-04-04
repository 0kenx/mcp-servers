"""
Generic tokenizers for the grammar parser system.
This module provides a tokenizer for languages that use indentation to define blocks.
Using regex-based rules for token identification.
"""

from typing import List, Dict, Set, Tuple, Optional, Any, Match
import re
from .token import Token, TokenType
from .tokenizer import Tokenizer, TokenizerState, TokenRule


class IndentationBlockTokenizer(Tokenizer):
    """
    Tokenizer for indentation-based blocks.
    
    This handles code blocks that are defined by their indentation level,
    which are common in languages like Python, YAML, etc.
    """

    def __init__(self):
        """Initialize the indentation block tokenizer."""
        super().__init__()
        self.language = "indentation"
        
        # Set up basic indentation block rules
        self.setup_indentation_block_rules()
    
    def setup_indentation_block_rules(self):
        """Set up tokenization rules for indentation-based blocks."""
        # Leading whitespace at the beginning of a line
        self.add_rule(TokenRule(
            r"^[ \t]+",
            TokenType.WHITESPACE,
            re.MULTILINE,
            lambda m: {"indent_level": len(m.group(0))}
        ))
        
        # Colon (often used to start blocks in indentation-based languages)
        self.add_rule(TokenRule(
            r":",
            TokenType.COLON
        ))
        
        # Generic identifiers
        self.add_rule(TokenRule(
            r"[a-zA-Z_][a-zA-Z0-9_]*",
            TokenType.IDENTIFIER
        ))
        
        # Newlines (important for indentation-based languages)
        self.add_rule(TokenRule(
            r"\n",
            TokenType.NEWLINE
        ))
        
        # Add basic rules like whitespace, numbers, etc.
        self.setup_default_rules()
    
    def tokenize(self, code: str) -> List[Token]:
        """
        Tokenize code with indentation-based blocks.
        
        Args:
            code: Source code to tokenize
            
        Returns:
            List of tokens
        """
        tokens = super().tokenize(code)
        
        # For indentation-based languages, we need to process the tokens
        # to detect INDENT and DEDENT tokens based on whitespace at line starts
        # This is a simplified version - a real implementation would track the stack
        # of indentation levels and generate INDENT/DEDENT tokens accordingly
        
        return tokens

