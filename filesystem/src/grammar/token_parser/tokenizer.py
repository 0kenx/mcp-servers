"""
Base tokenizer for the grammar parser system.

This module provides the base Tokenizer class that all language-specific
tokenizers inherit from.
"""

from typing import List, Dict, Set, Tuple, Optional, Any, Pattern, Match, Callable
import re
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


class TokenRule:
    """
    Defines a regex rule for token matching.
    """
    
    def __init__(
        self, 
        pattern: str, 
        token_type: TokenType, 
        flags: int = 0,
        transform: Optional[Callable[[Match], Dict[str, Any]]] = None
    ):
        """
        Initialize a token rule.
        
        Args:
            pattern: Regex pattern string
            token_type: Type of token to create when pattern matches
            flags: Regex compilation flags (e.g., re.MULTILINE)
            transform: Optional function to transform match into extra token attributes
        """
        self.pattern = re.compile(pattern, flags)
        self.token_type = token_type
        self.transform = transform or (lambda m: {})
    
    def match(self, code: str, pos: int) -> Optional[Tuple[Token, int]]:
        """
        Try to match the rule at the given position.
        
        Args:
            code: Source code string
            pos: Current position in the code
            
        Returns:
            Tuple of (Token, new position) if match succeeded, None otherwise
        """
        match = self.pattern.match(code, pos)
        if not match:
            return None
        
        value = match.group(0)
        end_pos = match.end()
        
        # Calculate line and column info
        line = code.count('\n', 0, pos) + 1
        last_nl = code.rfind('\n', 0, pos)
        column = pos - last_nl if last_nl >= 0 else pos + 1
        
        # Apply transform to get extra metadata
        metadata = self.transform(match)
        
        token = Token(self.token_type, value, pos, line, column, metadata)
        return token, end_pos


class Tokenizer:
    """
    Base tokenizer class that converts source code into a list of tokens.
    
    This is an abstract base class. Language-specific tokenizers should
    inherit from this class and implement their own token rules.
    """
    
    def __init__(self):
        """Initialize the tokenizer."""
        self.language = "generic"
        self.keywords = set()  # Language-specific keywords
        self.operators = {}    # Mapping from operator string to TokenType
        self.rules: List[TokenRule] = []  # List of token rules
    
    def add_rule(self, rule: TokenRule) -> None:
        """
        Add a token rule to the tokenizer.
        
        Args:
            rule: TokenRule to add
        """
        self.rules.append(rule)
    
    def add_keyword_rule(self) -> None:
        """Add a rule for matching language keywords."""
        if not self.keywords:
            return
        
        # Escape any regex special chars in keywords
        keyword_pattern = '|'.join(re.escape(kw) for kw in self.keywords)
        # Ensure keywords are matched as whole words
        pattern = f"\\b({keyword_pattern})\\b"
        
        self.add_rule(TokenRule(pattern, TokenType.KEYWORD))
    
    def add_operator_rules(self) -> None:
        """Add rules for matching language operators."""
        if not self.operators:
            return
        
        # Sort operators by length (longest first) to avoid partial matches
        sorted_operators = sorted(self.operators.keys(), key=len, reverse=True)
        for op in sorted_operators:
            pattern = re.escape(op)
            token_type = self.operators[op]
            self.add_rule(TokenRule(pattern, token_type))
    
    def setup_default_rules(self) -> None:
        """
        Set up default tokenization rules.
        
        This method should be called by subclasses after they've defined
        their keywords and operators.
        """
        # Add keyword rule
        self.add_keyword_rule()
        
        # Add operator rules
        self.add_operator_rules()
        
        # Common rules for many languages
        # Identifiers: start with letter or underscore, can contain alphanumeric chars and underscores
        self.add_rule(TokenRule(r"[a-zA-Z_]\w*", TokenType.IDENTIFIER))
        
        # Numbers: integer or floating point
        self.add_rule(TokenRule(r"\d+(\.\d+)?([eE][+-]?\d+)?", TokenType.NUMBER))
        
        # Whitespace: spaces, tabs
        self.add_rule(TokenRule(r"[ \t]+", TokenType.WHITESPACE))
        
        # Newlines
        self.add_rule(TokenRule(r"\n", TokenType.NEWLINE))
        
        # Delimiters
        self.add_rule(TokenRule(r"\{", TokenType.OPEN_BRACE))
        self.add_rule(TokenRule(r"\}", TokenType.CLOSE_BRACE))
        self.add_rule(TokenRule(r"\(", TokenType.OPEN_PAREN))
        self.add_rule(TokenRule(r"\)", TokenType.CLOSE_PAREN))
        self.add_rule(TokenRule(r"\[", TokenType.OPEN_BRACKET))
        self.add_rule(TokenRule(r"\]", TokenType.CLOSE_BRACKET))
        self.add_rule(TokenRule(r";", TokenType.SEMICOLON))
        self.add_rule(TokenRule(r",", TokenType.COMMA))
        self.add_rule(TokenRule(r"\.", TokenType.DOT))
    
    def tokenize(self, code: str) -> List[Token]:
        """
        Tokenize the source code.
        
        Args:
            code: Source code string
        
        Returns:
            List of tokens
        """
        if not self.rules:
            self.setup_default_rules()
        
        tokens: List[Token] = []
        pos = 0
        
        while pos < len(code):
            matched = False
            
            # Try each rule in order
            for rule in self.rules:
                result = rule.match(code, pos)
                if result:
                    token, new_pos = result
                    tokens.append(token)
                    pos = new_pos
                    matched = True
                    break
            
            # If no rule matched, create an UNKNOWN token for the character
            if not matched:
                line = code.count('\n', 0, pos) + 1
                last_nl = code.rfind('\n', 0, pos)
                column = pos - last_nl if last_nl >= 0 else pos + 1
                
                tokens.append(Token(
                    TokenType.UNKNOWN,
                    code[pos],
                    pos,
                    line,
                    column
                ))
                pos += 1
        
        return tokens
    
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
    
    # Keep these methods for backward compatibility
    def _is_identifier_start(self, char: str) -> bool:
        """Check if a character can start an identifier."""
        return char.isalpha() or char == '_'
    
    def _is_identifier_part(self, char: str) -> bool:
        """Check if a character can be part of an identifier."""
        return char.isalnum() or char == '_'
    
    def _is_whitespace(self, char: str) -> bool:
        """Check if a character is whitespace."""
        return char.isspace() and char != '\n'
    
    def _is_digit(self, char: str) -> bool:
        """Check if a character is a digit."""
        return char.isdigit()
    
    def _is_operator_char(self, char: str) -> bool:
        """Check if a character can be part of an operator."""
        return char in '+-*/%=&|^~<>!?:' 