"""
Base tokenizer for the grammar parser system.

This module provides the base Tokenizer class that all language-specific
tokenizers inherit from.
"""

from typing import List, Dict, Set, Tuple, Optional, Any
from .token import Token, TokenType


class TokenizerState:
    """
    Tracks the state of the tokenizer during the tokenization process.
    """
    
    def __init__(self):
        """Initialize the tokenizer state."""
        self.position = 0
        self.line = 1
        self.column = 1
        self.in_string = False
        self.string_delimiter = None
        self.in_comment = False
        self.comment_type = None  # "line" or "block"
        self.escape_next = False
        self.context_stack = []  # Stack of contexts (code, string, comment, etc.)
        self.metadata = {}  # Additional state metadata


class Tokenizer:
    """
    Base tokenizer class that converts source code into a list of tokens.
    
    This is an abstract base class. Language-specific tokenizers should
    inherit from this class and implement the tokenize method.
    """
    
    def __init__(self):
        """Initialize the tokenizer."""
        self.language = "generic"
        self.keywords = set()  # Language-specific keywords
        self.operators = {}    # Mapping from operator string to TokenType
    
    def tokenize(self, code: str) -> List[Token]:
        """
        Tokenize the source code.
        
        Args:
            code: Source code string
        
        Returns:
            List of tokens
        """
        raise NotImplementedError("Subclasses must implement tokenize method")
    
    def _is_identifier_start(self, char: str) -> bool:
        """
        Check if a character can start an identifier.
        
        Args:
            char: Character to check
        
        Returns:
            True if the character can start an identifier
        """
        return char.isalpha() or char == '_'
    
    def _is_identifier_part(self, char: str) -> bool:
        """
        Check if a character can be part of an identifier.
        
        Args:
            char: Character to check
        
        Returns:
            True if the character can be part of an identifier
        """
        return char.isalnum() or char == '_'
    
    def _is_whitespace(self, char: str) -> bool:
        """
        Check if a character is whitespace.
        
        Args:
            char: Character to check
        
        Returns:
            True if the character is whitespace
        """
        return char.isspace() and char != '\n'
    
    def _is_digit(self, char: str) -> bool:
        """
        Check if a character is a digit.
        
        Args:
            char: Character to check
        
        Returns:
            True if the character is a digit
        """
        return char.isdigit()
    
    def _is_operator_char(self, char: str) -> bool:
        """
        Check if a character can be part of an operator.
        
        Args:
            char: Character to check
        
        Returns:
            True if the character can be part of an operator
        """
        return char in '+-*/%=&|^~<>!?:'
    
    def _create_token(
        self, 
        token_type: TokenType, 
        value: str, 
        position: int, 
        line: int, 
        column: int,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Token:
        """
        Create a token.
        
        Args:
            token_type: Type of token
            value: Token value
            position: Position in source code
            line: Line number (1-based)
            column: Column number (1-based)
            metadata: Additional metadata
        
        Returns:
            The created token
        """
        return Token(token_type, value, position, line, column, metadata)
    
    def _update_position(self, state: TokenizerState, char: str) -> None:
        """
        Update the position state after processing a character.
        
        Args:
            state: Current tokenizer state
            char: Character that was processed
        """
        state.position += 1
        if char == '\n':
            state.line += 1
            state.column = 1
        else:
            state.column += 1 