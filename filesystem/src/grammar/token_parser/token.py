"""
Token class for the grammar parser system.
Represents a single token in the code.
"""

from enum import Enum
from typing import Optional, Dict, Any
from dataclasses import dataclass, field


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

    # Indentation tokens
    INDENT = "indent"  # Increase in indentation level
    DEDENT = "dedent"  # Decrease in indentation level

    # Specific delimiter tokens
    OPEN_BRACE = "open_brace"  # {
    CLOSE_BRACE = "close_brace"  # }
    OPEN_PAREN = "open_paren"  # (
    CLOSE_PAREN = "close_paren"  # )
    OPEN_BRACKET = "open_bracket"  # [
    CLOSE_BRACKET = "close_bracket"  # ]

    # Context transition markers
    STRING_START = "string_start"
    STRING_END = "string_end"
    COMMENT_START = "comment_start"
    COMMENT_END = "comment_end"

    # Operators
    EQUALS = "equals"  # =
    ARROW = "arrow"  # ->
    FAT_ARROW = "fat_arrow"  # =>
    COLON = "colon"  # :
    SEMICOLON = "semicolon"  # ;
    COMMA = "comma"  # ,
    DOT = "dot"  # .

    # Preprocessor directive (C/C++/etc.)
    PREPROCESSOR = "preprocessor"  # #include, #define, etc.

    # Rust specific tokens
    ATTRIBUTE = "attribute"  # #[derive(Debug)]

    # CSS specific tokens
    AT_RULE = "at_rule"  # @media, @import, etc.
    PROPERTY = "property"  # CSS property name
    VALUE = "value"  # CSS property value
    SELECTOR = "selector"  # CSS selector

    # HTML specific tokens
    DOCTYPE = "doctype"  # <!DOCTYPE html>
    OPEN_TAG = "open_tag"  # <tag>
    CLOSE_TAG = "close_tag"  # </tag>
    SELF_CLOSING_TAG = "self_closing_tag"  # <tag/>
    SCRIPT = "script"  # <script>...</script>
    STYLE = "style"  # <style>...</style>
    ENTITY = "entity"  # &nbsp;
    TEXT = "text"  # Text content

    # JSX specific tokens
    JSX_TAG = "jsx_tag"  # <tag>, </tag>, <tag/>, etc.
    JSX_ATTRIBUTE = "jsx_attribute"  # attribute names in JSX tags
    JSX_EXPRESSION = "jsx_expression"  # {expression} in JSX
    JSX_TEXT = "jsx_text"  # Text content between JSX tags

    UNKNOWN = "unknown"


@dataclass
class Token:
    """
    Represents a token in the source code.

    A token is a lexical unit recognized by the parser, such as a keyword,
    identifier, delimiter, operator, etc.
    """

    token_type: TokenType
    value: str
    position: int
    line: int
    column: int
    metadata: Optional[Dict[str, Any]] = field(default_factory=dict)

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
        return self.token_type == TokenType.IDENTIFIER and (
            not names or self.value in names
        )
