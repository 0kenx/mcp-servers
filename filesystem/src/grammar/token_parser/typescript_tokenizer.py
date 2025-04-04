"""
TypeScript tokenizer for the grammar parser system.

This module provides a tokenizer specific to the TypeScript programming language.
"""

from typing import List, Dict, Set, Tuple, Optional, Any
from .token import Token, TokenType
from .tokenizer import Tokenizer, TokenizerState
from .javascript_tokenizer import JavaScriptTokenizer

class TypeScriptTokenizer(JavaScriptTokenizer):
    """
    Tokenizer for TypeScript code.
    
    This extends the JavaScript tokenizer to handle TypeScript-specific tokens.
    """ 
    
    def tokenize(self, code: str) -> List[Token]:
        """
        Tokenize TypeScript code.
        
        Args:
            code: TypeScript source code to tokenize

        Returns:
            List of tokens
        """
        tokens = super().tokenize(code)

        # Add TypeScript-specific tokens
        return tokens
