"""
Generic tokenizers for the grammar parser system.

"""

from typing import List, Dict, Set, Tuple, Optional, Any
from .token import Token, TokenType
from .tokenizer import Tokenizer, TokenizerState


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
        
        # Indentation rules
        self.indent_rules = [
            TokenRule(r"^(\s+)", TokenType.INDENT),
            TokenRule(r"^(\s+)", TokenType.DEDENT),
        ]
        
