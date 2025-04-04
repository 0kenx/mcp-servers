"""
Generic tokenizers for the grammar parser system.

"""

from typing import List, Dict, Set, Tuple, Optional, Any
from .token import Token, TokenType
from .tokenizer import Tokenizer, TokenizerState


class KeywordPatternTokenizer(Tokenizer):
    """
    Tokenizer for keyword-pattern-based blocks.
    
    This handles code blocks that are defined by a keyword pattern.
    """

    def __init__(self):
        """Initialize the keyword pattern tokenizer."""
        super().__init__()
        self.language = "keyword_pattern"

        # Keyword pattern rules
        self.keyword_rules = [
            TokenRule(r"^(\s+)", TokenType.INDENT),
            TokenRule(r"^(\s+)", TokenType.DEDENT),
        ]

