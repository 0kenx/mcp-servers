"""
JavaScript tokenizer for the grammar parser system.

This module provides a tokenizer specific to the JavaScript programming language.
"""

from typing import List, Dict, Set, Tuple, Optional, Any
from .token import Token, TokenType
from .tokenizer import Tokenizer, TokenizerState


class JavaScriptTokenizer(Tokenizer):
    """
    Tokenizer for JavaScript code.
    
    This tokenizer handles JavaScript-specific syntax, including regular expressions,
    template literals, and more.
    """
    
    def __init__(self):
        """Initialize the JavaScript tokenizer."""
        super().__init__()
        self.language = "javascript"
        
        # JavaScript keywords
        self.keywords = {
            "await", "break", "case", "catch", "class", "const", "continue", "debugger",
            "default", "delete", "do", "else", "enum", "export", "extends", "false",
            "finally", "for", "function", "if", "implements", "import", "in", "instanceof",
            "interface", "let", "new", "null", "package", "private", "protected", "public",
            "return", "super", "switch", "static", "this", "throw", "try", "true",
            "typeof", "var", "void", "while", "with", "yield"
        }
        
        # JavaScript operators
        self.operators = {
            "+": TokenType.OPERATOR,
            "-": TokenType.OPERATOR,
            "*": TokenType.OPERATOR,
            "**": TokenType.OPERATOR,
            "/": TokenType.OPERATOR,
            "%": TokenType.OPERATOR,
            "++": TokenType.OPERATOR,
            "--": TokenType.OPERATOR,
            "=": TokenType.EQUALS,
            "+=": TokenType.OPERATOR,
            "-=": TokenType.OPERATOR,
            "*=": TokenType.OPERATOR,
            "/=": TokenType.OPERATOR,
            "%=": TokenType.OPERATOR,
            "**=": TokenType.OPERATOR,
            "&=": TokenType.OPERATOR,
            "|=": TokenType.OPERATOR,
            "^=": TokenType.OPERATOR,
            ">>=": TokenType.OPERATOR,
            "<<=": TokenType.OPERATOR,
            ">>>=": TokenType.OPERATOR,
            "&&": TokenType.OPERATOR,
            "||": TokenType.OPERATOR,
            "??": TokenType.OPERATOR,
            "?.": TokenType.OPERATOR,
            "&": TokenType.OPERATOR,
            "|": TokenType.OPERATOR,
            "^": TokenType.OPERATOR,
            "~": TokenType.OPERATOR,
            "<<": TokenType.OPERATOR,
            ">>": TokenType.OPERATOR,
            ">>>": TokenType.OPERATOR,
            "==": TokenType.OPERATOR,
            "===": TokenType.OPERATOR,
            "!=": TokenType.OPERATOR,
            "!==": TokenType.OPERATOR,
            "<": TokenType.OPERATOR,
            ">": TokenType.OPERATOR,
            "<=": TokenType.OPERATOR,
            ">=": TokenType.OPERATOR,
            "!": TokenType.OPERATOR,
            "?": TokenType.OPERATOR,
            ":": TokenType.COLON,
            ".": TokenType.DOT,
            "...": TokenType.OPERATOR,
            "=>": TokenType.FAT_ARROW,
            ",": TokenType.COMMA,
            ";": TokenType.SEMICOLON,
        }
    
    def tokenize(self, code: str) -> List[Token]:
        """
        Tokenize JavaScript code.
        
        Args:
            code: JavaScript source code
        
        Returns:
            List of tokens
        """
        tokens: List[Token] = []
        state = TokenizerState()
        
        i = 0
        while i < len(code):
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
                # Handle template literal interpolation
                if state.string_delimiter == '`' and char == '$' and i + 1 < len(code) and code[i + 1] == '{':
                    # Template literal interpolation start
                    tokens.append(self._create_token(
                        TokenType.OPERATOR,
                        "${",
                        state.position,
                        state.line,
                        state.column
                    ))
                    i += 2
                    state.position += 2
                    state.column += 2
                    
                    # Push the string context and enter code context
                    state.context_stack.append(("string", state.string_delimiter))
                    state.in_string = False
                    state.string_delimiter = None
                    continue
                
                # Check for end of string
                if char == state.string_delimiter:
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
                    continue
                
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
                if state.comment_type == "line" and char == '\n':
                    # End of line comment
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
                    continue
                elif state.comment_type == "block" and char == '*' and i + 1 < len(code) and code[i + 1] == '/':
                    # End of block comment
                    tokens.append(self._create_token(
                        TokenType.COMMENT_END,
                        "*/",
                        state.position,
                        state.line,
                        state.column
                    ))
                    i += 2
                    state.position += 2
                    state.column += 2
                    state.in_comment = False
                    state.comment_type = None
                    continue
                
                # Just a character inside a comment
                i += 1
                state.position += 1
                if char == '\n':
                    state.line += 1
                    state.column = 1
                else:
                    state.column += 1
                continue
            
            # Check for template literal
            if char == '`':
                tokens.append(self._create_token(
                    TokenType.STRING_START,
                    "`",
                    state.position,
                    state.line,
                    state.column,
                    {"template_literal": True}
                ))
                state.in_string = True
                state.string_delimiter = '`'
                i += 1
                state.position += 1
                state.column += 1
                continue
            
            # Check for closing template literal interpolation
            if not state.in_string and char == '}' and state.context_stack and state.context_stack[-1][0] == "string":
                # Pop the context
                context = state.context_stack.pop()
                
                # Add the closing brace
                tokens.append(self._create_token(
                    TokenType.CLOSE_BRACE,
                    "}",
                    state.position,
                    state.line,
                    state.column
                ))
                i += 1
                state.position += 1
                state.column += 1
                
                # Re-enter string context
                state.in_string = True
                state.string_delimiter = context[1]
                continue
            
            # Check for start of string
            if char in ["'", '"']:
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
            if char == '/' and i + 1 < len(code):
                if code[i + 1] == '/':
                    # Line comment
                    tokens.append(self._create_token(
                        TokenType.COMMENT_START,
                        "//",
                        state.position,
                        state.line,
                        state.column
                    ))
                    state.in_comment = True
                    state.comment_type = "line"
                    i += 2
                    state.position += 2
                    state.column += 2
                    continue
                elif code[i + 1] == '*':
                    # Block comment
                    tokens.append(self._create_token(
                        TokenType.COMMENT_START,
                        "/*",
                        state.position,
                        state.line,
                        state.column
                    ))
                    state.in_comment = True
                    state.comment_type = "block"
                    i += 2
                    state.position += 2
                    state.column += 2
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
            
            # Check for numbers
            if char.isdigit() or (char == '.' and i + 1 < len(code) and code[i + 1].isdigit()):
                num_val = ""
                num_start = i
                
                # Integer part
                if char.isdigit():
                    # Check for hexadecimal, octal, or binary
                    if char == '0' and i + 1 < len(code) and code[i + 1].lower() in ['x', 'o', 'b']:
                        num_val += code[i:i+2]
                        i += 2
                        
                        # Parse hex, octal, or binary digits
                        valid_chars = '0123456789abcdefABCDEF' if code[i-1].lower() == 'x' else \
                                      '01234567' if code[i-1].lower() == 'o' else '01'
                        
                        while i < len(code) and code[i] in valid_chars:
                            num_val += code[i]
                            i += 1
                    else:
                        # Regular decimal number
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