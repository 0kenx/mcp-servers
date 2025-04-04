"""
HTML tokenizer for the grammar parser system.

This module provides a tokenizer specific to the HTML language.
"""

from typing import List, Dict, Set, Tuple, Optional, Any
from .token import Token, TokenType
from .tokenizer import Tokenizer, TokenizerState


class HTMLTokenizer:
    """
    Tokenizer for HTML code.
    
    This tokenizer handles HTML-specific tokens such as tags, attributes,
    and text content.
    """
    
    def tokenize(self, code: str) -> List[Token]:
        """
        Tokenize HTML code into a list of tokens.
        
        Args:
            code: HTML source code to tokenize
            
        Returns:
            List of tokens
        """
        tokens = []
        position = 0
        line = 1
        column = 1
        
        i = 0
        while i < len(code):
            # Handle HTML tags
            if code[i] == '<':
                start_position = position
                start_line = line
                start_column = column
                
                # Check for comments
                if i + 4 <= len(code) and code[i:i+4] == '<!--':
                    # Find end of comment
                    comment_end = code.find('-->', i + 4)
                    if comment_end == -1:
                        comment_end = len(code)
                    else:
                        comment_end += 3  # Include the '-->'
                    
                    comment_content = code[i:comment_end]
                    tokens.append(Token(
                        TokenType.COMMENT,
                        comment_content,
                        start_position,
                        start_line,
                        start_column
                    ))
                    
                    # Update position and line/column counters
                    for char in comment_content:
                        position += 1
                        column += 1
                        if char == '\n':
                            line += 1
                            column = 1
                    
                    i = comment_end
                    continue
                
                # Check for doctype
                if i + 9 <= len(code) and code[i:i+9].lower() == '<!doctype':
                    doctype_end = code.find('>', i)
                    if doctype_end == -1:
                        doctype_end = len(code)
                    else:
                        doctype_end += 1  # Include the '>'
                    
                    doctype_content = code[i:doctype_end]
                    tokens.append(Token(
                        TokenType.DOCTYPE,
                        doctype_content,
                        start_position,
                        start_line,
                        start_column
                    ))
                    
                    # Update position and line/column counters
                    for char in doctype_content:
                        position += 1
                        column += 1
                        if char == '\n':
                            line += 1
                            column = 1
                    
                    i = doctype_end
                    continue
                
                # Regular tag
                # Find end of tag
                tag_end = code.find('>', i)
                if tag_end == -1:
                    tag_end = len(code)
                else:
                    tag_end += 1  # Include the '>'
                
                tag_content = code[i:tag_end]
                
                # Determine if it's an opening, closing, or self-closing tag
                if tag_content.startswith('</'):
                    token_type = TokenType.CLOSE_TAG
                elif tag_content.endswith('/>'):
                    token_type = TokenType.SELF_CLOSING_TAG
                else:
                    token_type = TokenType.OPEN_TAG
                
                tokens.append(Token(
                    token_type,
                    tag_content,
                    start_position,
                    start_line,
                    start_column
                ))
                
                # Update position and line/column counters
                for char in tag_content:
                    position += 1
                    column += 1
                    if char == '\n':
                        line += 1
                        column = 1
                
                i = tag_end
            
            # Handle whitespace
            elif code[i].isspace():
                start_position = position
                start_line = line
                start_column = column
                
                whitespace = ''
                while i < len(code) and code[i].isspace():
                    whitespace += code[i]
                    position += 1
                    column += 1
                    if code[i] == '\n':
                        line += 1
                        column = 1
                    i += 1
                
                tokens.append(Token(
                    TokenType.WHITESPACE,
                    whitespace,
                    start_position,
                    start_line,
                    start_column
                ))
            
            # Handle text content
            else:
                start_position = position
                start_line = line
                start_column = column
                
                text = ''
                while i < len(code) and code[i] != '<' and not code[i].isspace():
                    text += code[i]
                    position += 1
                    column += 1
                    if code[i] == '\n':
                        line += 1
                        column = 1
                    i += 1
                
                if text:
                    tokens.append(Token(
                        TokenType.TEXT,
                        text,
                        start_position,
                        start_line,
                        start_column
                    ))
                
            if i == 0 or (i < len(code) and not code[i].isspace() and code[i] != '<'):
                position += 1
                column += 1
                if i < len(code) and code[i] == '\n':
                    line += 1
                    column = 1
                i += 1
        
        return tokens

