"""
Generic tokenizers for the grammar parser system.

"""

from typing import List, Dict, Set, Tuple, Optional, Any
from .token import Token, TokenType
from .tokenizer import Tokenizer, TokenizerState


class BraceBlockTokenizer(Tokenizer):
    """
    Tokenizer for brace-delimited blocks.
    
    This handles code blocks that are delimited by braces, which are common in

    languages like C, C++, Java, JavaScript, etc.
    """

    def __init__(self):
        """Initialize the brace block tokenizer."""
        super().__init__()
        self.language = "brace"
        
        # Brace rules
        self.brace_rules = [
            TokenRule(r"^(\s+)", TokenType.INDENT),
            TokenRule(r"^(\s+)", TokenType.DEDENT),
        ]
        