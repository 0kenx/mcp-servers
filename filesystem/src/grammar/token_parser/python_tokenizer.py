"""
Python tokenizer for the grammar parser system.

This module provides a tokenizer specific to the Python programming language.
"""

from typing import List, Dict, Set, Tuple, Optional, Any
from .token import Token, TokenType
from .tokenizer import Tokenizer, TokenizerState


class PythonTokenizer(Tokenizer):
    """
    Tokenizer for Python code.
    
    This tokenizer handles Python-specific syntax, including indentation-based blocks,
    triple-quoted strings, and more.
    """
    
    def __init__(self):
        """Initialize the Python tokenizer."""
        super().__init__()
        self.language = "python"
        
        # Python keywords
        self.keywords = {
            "and", "as", "assert", "async", "await", "break", "class", "continue",
            "def", "del", "elif", "else", "except", "finally", "for", "from",
            "global", "if", "import", "in", "is", "lambda", "nonlocal", "not",
            "or", "pass", "raise", "return", "try", "while", "with", "yield",
            "True", "False", "None"
        }
        
        # Python operators
        self.operators = {
            "+": TokenType.OPERATOR,
            "-": TokenType.OPERATOR,
            "*": TokenType.OPERATOR,
            "**": TokenType.OPERATOR,
            "/": TokenType.OPERATOR,
            "//": TokenType.OPERATOR,
            "%": TokenType.OPERATOR,
            "@": TokenType.OPERATOR,
            "<<": TokenType.OPERATOR,
            ">>": TokenType.OPERATOR,
            "&": TokenType.OPERATOR,
            "|": TokenType.OPERATOR,
            "^": TokenType.OPERATOR,
            "~": TokenType.OPERATOR,
            "<": TokenType.OPERATOR,
            ">": TokenType.OPERATOR,
            "<=": TokenType.OPERATOR,
            ">=": TokenType.OPERATOR,
            "==": TokenType.OPERATOR,
            "!=": TokenType.OPERATOR,
            "=": TokenType.EQUALS,
            "+=": TokenType.OPERATOR,
            "-=": TokenType.OPERATOR,
            "*=": TokenType.OPERATOR,
            "/=": TokenType.OPERATOR,
            "//=": TokenType.OPERATOR,
            "%=": TokenType.OPERATOR,
            "@=": TokenType.OPERATOR,
            "&=": TokenType.OPERATOR,
            "|=": TokenType.OPERATOR,
            "^=": TokenType.OPERATOR,
            ">>=": TokenType.OPERATOR,
            "<<=": TokenType.OPERATOR,
            "**=": TokenType.OPERATOR,
            "->": TokenType.ARROW,
            ":": TokenType.COLON,
        }
    
    def tokenize(self, code: str) -> List[Token]:
        """
        Tokenize Python code.
        
        Args:
            code: Python source code
        
        Returns:
            List of tokens
        """
        tokens: List[Token] = []
        state = TokenizerState()
        
        # Add newline at the end if there isn't one
        if not code.endswith('\n'):
            code += '\n'
        
        i = 0
        while i < len(code):
            char = code[i]
            
            # Track indentation at the start of a line
            if state.column == 1 and not state.in_string and not state.in_comment:
                # Count leading spaces
                indent_size = 0
                while i < len(code) and code[i].isspace() and code[i] != '\n':
                    indent_size += 1
                    i += 1
                
                # Add indent token if there are spaces
                if indent_size > 0:
                    tokens.append(self._create_token(
                        TokenType.WHITESPACE, 
                        " " * indent_size,
                        state.position,
                        state.line,
                        state.column,
                        {"indent_size": indent_size}
                    ))
                    # Update state
                    state.position += indent_size
                    state.column += indent_size
                
                # Continue with next character
                if i >= len(code):
                    break
                char = code[i]
            
            # Skip character if we're supposed to escape it
            if state.escape_next:
                state.escape_next = False
                state.position += 1
                state.column += 1
                i += 1
                continue
            
            # Handle escape sequences
            if char == '\\':
                state.escape_next = True
                state.position += 1
                state.column += 1
                i += 1
                continue
            
            # Handle strings
            if state.in_string:
                # Check for end of string
                if char == state.string_delimiter:
                    # Check for triple-quoted string
                    if (state.string_delimiter in ["'", '"'] and 
                        i + 2 < len(code) and 
                        code[i:i+3] == state.string_delimiter * 3 and
                        "triple_quoted" in state.metadata):
                        # End of triple-quoted string
                        tokens.append(self._create_token(
                            TokenType.STRING_END,
                            state.string_delimiter * 3,
                            state.position,
                            state.line,
                            state.column
                        ))
                        i += 3
                        state.position += 3
                        state.column += 3
                        state.in_string = False
                        state.string_delimiter = None
                        if "triple_quoted" in state.metadata:
                            del state.metadata["triple_quoted"]
                    elif "triple_quoted" not in state.metadata:
                        # End of regular string
                        tokens.append(self._create_token(
                            TokenType.STRING_END,
                            char,
                            state.position,
                            state.line,
                            state.column
                        ))
                        i += 1
                        state.position += 1
                        state.column += 1
                        state.in_string = False
                        state.string_delimiter = None
                    else:
                        # Just a quote inside a triple-quoted string
                        i += 1
                        state.position += 1
                        state.column += 1
                else:
                    # Just a character inside a string
                    i += 1
                    state.position += 1
                    if char == '\n':
                        state.line += 1
                        state.column = 1
                    else:
                        state.column += 1
                continue
            
            # Handle comments
            if state.in_comment:
                if char == '\n':
                    # End of line comment
                    if state.comment_type == "line":
                        tokens.append(self._create_token(
                            TokenType.COMMENT_END,
                            "",
                            state.position,
                            state.line,
                            state.column
                        ))
                        state.in_comment = False
                        state.comment_type = None
                    
                    # Newline token
                    tokens.append(self._create_token(
                        TokenType.NEWLINE,
                        "\n",
                        state.position,
                        state.line,
                        state.column
                    ))
                    
                    i += 1
                    state.position += 1
                    state.line += 1
                    state.column = 1
                else:
                    i += 1
                    state.position += 1
                    state.column += 1
                continue
            
            # Check for start of string
            if char in ["'", '"']:
                # Check for triple-quoted string
                if i + 2 < len(code) and code[i:i+3] == char * 3:
                    tokens.append(self._create_token(
                        TokenType.STRING_START,
                        char * 3,
                        state.position,
                        state.line,
                        state.column,
                        {"triple_quoted": True}
                    ))
                    state.in_string = True
                    state.string_delimiter = char
                    state.metadata["triple_quoted"] = True
                    i += 3
                    state.position += 3
                    state.column += 3
                else:
                    tokens.append(self._create_token(
                        TokenType.STRING_START,
                        char,
                        state.position,
                        state.line,
                        state.column
                    ))
                    state.in_string = True
                    state.string_delimiter = char
                    i += 1
                    state.position += 1
                    state.column += 1
                continue
            
            # Check for comments
            if char == '#':
                tokens.append(self._create_token(
                    TokenType.COMMENT_START,
                    "#",
                    state.position,
                    state.line,
                    state.column
                ))
                state.in_comment = True
                state.comment_type = "line"
                i += 1
                state.position += 1
                state.column += 1
                continue
            
            # Check for operators (including multi-character ones)
            if self._is_operator_char(char):
                # Try to match the longest operator
                operator = char
                j = i + 1
                while j < len(code) and operator + code[j] in self.operators:
                    operator += code[j]
                    j += 1
                
                # Add the operator token
                token_type = self.operators.get(operator, TokenType.OPERATOR)
                tokens.append(self._create_token(
                    token_type,
                    operator,
                    state.position,
                    state.line,
                    state.column
                ))
                
                i += len(operator)
                state.position += len(operator)
                state.column += len(operator)
                continue
            
            # Check for delimiters
            if char == '(':
                tokens.append(self._create_token(
                    TokenType.OPEN_PAREN,
                    char,
                    state.position,
                    state.line,
                    state.column
                ))
                i += 1
                state.position += 1
                state.column += 1
                continue
            
            if char == ')':
                tokens.append(self._create_token(
                    TokenType.CLOSE_PAREN,
                    char,
                    state.position,
                    state.line,
                    state.column
                ))
                i += 1
                state.position += 1
                state.column += 1
                continue
            
            if char == '[':
                tokens.append(self._create_token(
                    TokenType.OPEN_BRACKET,
                    char,
                    state.position,
                    state.line,
                    state.column
                ))
                i += 1
                state.position += 1
                state.column += 1
                continue
            
            if char == ']':
                tokens.append(self._create_token(
                    TokenType.CLOSE_BRACKET,
                    char,
                    state.position,
                    state.line,
                    state.column
                ))
                i += 1
                state.position += 1
                state.column += 1
                continue
            
            if char == '{':
                tokens.append(self._create_token(
                    TokenType.OPEN_BRACE,
                    char,
                    state.position,
                    state.line,
                    state.column
                ))
                i += 1
                state.position += 1
                state.column += 1
                continue
            
            if char == '}':
                tokens.append(self._create_token(
                    TokenType.CLOSE_BRACE,
                    char,
                    state.position,
                    state.line,
                    state.column
                ))
                i += 1
                state.position += 1
                state.column += 1
                continue
            
            if char == ',':
                tokens.append(self._create_token(
                    TokenType.COMMA,
                    char,
                    state.position,
                    state.line,
                    state.column
                ))
                i += 1
                state.position += 1
                state.column += 1
                continue
            
            if char == '.':
                tokens.append(self._create_token(
                    TokenType.DOT,
                    char,
                    state.position,
                    state.line,
                    state.column
                ))
                i += 1
                state.position += 1
                state.column += 1
                continue
            
            # Check for numbers
            if char.isdigit():
                num_val = ""
                num_start = i
                
                # Integer part
                while i < len(code) and code[i].isdigit():
                    num_val += code[i]
                    i += 1
                
                # Decimal part
                if i < len(code) and code[i] == '.':
                    num_val += code[i]
                    i += 1
                    while i < len(code) and code[i].isdigit():
                        num_val += code[i]
                        i += 1
                
                # Exponent part
                if i < len(code) and code[i].lower() == 'e':
                    num_val += code[i]
                    i += 1
                    if i < len(code) and (code[i] == '+' or code[i] == '-'):
                        num_val += code[i]
                        i += 1
                    while i < len(code) and code[i].isdigit():
                        num_val += code[i]
                        i += 1
                
                tokens.append(self._create_token(
                    TokenType.NUMBER,
                    num_val,
                    state.position,
                    state.line,
                    state.column
                ))
                
                state.position += (i - num_start)
                state.column += (i - num_start)
                continue
            
            # Check for identifiers and keywords
            if self._is_identifier_start(char):
                ident = ""
                ident_start = i
                
                while i < len(code) and self._is_identifier_part(code[i]):
                    ident += code[i]
                    i += 1
                
                # Check if it's a keyword
                if ident in self.keywords:
                    tokens.append(self._create_token(
                        TokenType.KEYWORD,
                        ident,
                        state.position,
                        state.line,
                        state.column
                    ))
                else:
                    tokens.append(self._create_token(
                        TokenType.IDENTIFIER,
                        ident,
                        state.position,
                        state.line,
                        state.column
                    ))
                
                state.position += (i - ident_start)
                state.column += (i - ident_start)
                continue
            
            # Handle newlines
            if char == '\n':
                tokens.append(self._create_token(
                    TokenType.NEWLINE,
                    char,
                    state.position,
                    state.line,
                    state.column
                ))
                i += 1
                state.position += 1
                state.line += 1
                state.column = 1
                continue
            
            # Handle whitespace
            if self._is_whitespace(char):
                whitespace = ""
                whitespace_start = i
                
                while i < len(code) and self._is_whitespace(code[i]):
                    whitespace += code[i]
                    i += 1
                
                tokens.append(self._create_token(
                    TokenType.WHITESPACE,
                    whitespace,
                    state.position,
                    state.line,
                    state.column
                ))
                
                state.position += (i - whitespace_start)
                state.column += (i - whitespace_start)
                continue
            
            # Handle any other character
            tokens.append(self._create_token(
                TokenType.UNKNOWN,
                char,
                state.position,
                state.line,
                state.column
            ))
            i += 1
            state.position += 1
            state.column += 1
        
        return tokens 