"""
Token class for the grammar parser system.
Represents a single token in the code.
"""

from enum import Enum
from typing import Optional, Dict, Any


class TokenType(Enum):
    """Types of tokens that can be identified by the tokenizer."""
    KEYWORD = "keyword"
    IDENTIFIER = "identifier"
    STRING = "string"
    NUMBER = "number"
    OPERATOR = "operator"
    DELIMITER = "delimiter"
    COMMENT = "comment"
    WHITESPACE = "whitespace"
    NEWLINE = "newline"
    
    # Specific delimiter tokens
    OPEN_BRACE = "open_brace"          # {
    CLOSE_BRACE = "close_brace"        # }
    OPEN_PAREN = "open_paren"          # (
    CLOSE_PAREN = "close_paren"        # )
    OPEN_BRACKET = "open_bracket"      # [
    CLOSE_BRACKET = "close_bracket"    # ]
    
    # Context transition markers
    STRING_START = "string_start"
    STRING_END = "string_end"
    COMMENT_START = "comment_start"
    COMMENT_END = "comment_end"
    
    # Operators
    EQUALS = "equals"                  # =
    ARROW = "arrow"                    # ->
    FAT_ARROW = "fat_arrow"            # =>
    COLON = "colon"                    # :
    SEMICOLON = "semicolon"            # ;
    COMMA = "comma"                    # ,
    DOT = "dot"                        # .
    
    UNKNOWN = "unknown"


class Token:
    """
    Represents a token in the source code.
    
    A token is a lexical unit recognized by the parser, such as a keyword,
    identifier, delimiter, operator, etc.
    """
    
    def __init__(
        self, 
        token_type: TokenType, 
        value: str, 
        position: int,
        line: int,
        column: int,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """
        Initialize a token.
        
        Args:
            token_type: Type of the token
            value: Text value of the token
            position: Position in the source code (character index)
            line: Line number (1-based)
            column: Column number (1-based)
            metadata: Additional information about the token
        """
        self.token_type = token_type
        self.value = value
        self.position = position
        self.line = line
        self.column = column
        self.metadata = metadata or {}
    
    def __repr__(self):
        return f"Token({self.token_type.value}, '{self.value}', line {self.line}, col {self.column})"
    
    def __str__(self):
        return f"{self.token_type.value}('{self.value}')"
    
    def is_type(self, *token_types: TokenType) -> bool:
        """Check if the token is of any of the specified types."""
        return self.token_type in token_types
    
    def is_keyword(self, *keywords: str) -> bool:
        """Check if the token is a keyword with one of the specified values."""
        return self.token_type == TokenType.KEYWORD and self.value in keywords
    
    def is_identifier(self, *names: str) -> bool:
        """Check if the token is an identifier with one of the specified names."""
        return self.token_type == TokenType.IDENTIFIER and (not names or self.value in names) 