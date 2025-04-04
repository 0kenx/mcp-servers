"""
CSS tokenizer for the grammar parser system.

This module provides a tokenizer specific to the CSS programming language.
"""

from typing import List, Dict, Set, Tuple, Optional, Any
from .token import Token, TokenType
from .tokenizer import Tokenizer, TokenizerState


class CSSTokenizer(Tokenizer):
    """
    Tokenizer for CSS code.
    
    This tokenizer handles CSS-specific tokens such as selectors, properties,
    values, and special CSS syntax.
    """
    
    def tokenize(self, code: str) -> List[Token]:
        """
        Tokenize CSS code into a list of tokens.
        
        Args:
            code: CSS source code to tokenize
            
        Returns:
            List of tokens
        """
        tokens = []
        position = 0
        line = 1
        column = 1
        
        i = 0
        while i < len(code):
            char = code[i]
            
            # Handle whitespace
            if char.isspace():
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
                continue
            
            # Handle comments
            if i + 1 < len(code) and code[i:i+2] == '/*':
                start_position = position
                start_line = line
                start_column = column
                
                # Find end of comment
                comment_end = code.find('*/', i + 2)
                if comment_end == -1:
                    comment_end = len(code)
                else:
                    comment_end += 2  # Include the closing '*/'
                
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
            
            # Handle at-rules (@media, @import, etc.)
            if char == '@':
                start_position = position
                start_line = line
                start_column = column
                
                # Find the end of the at-rule name
                at_rule_end = i
                while at_rule_end < len(code) and not code[at_rule_end].isspace() and code[at_rule_end] != '{' and code[at_rule_end] != ';':
                    at_rule_end += 1
                
                at_rule_name = code[i:at_rule_end]
                tokens.append(Token(
                    TokenType.AT_RULE,
                    at_rule_name,
                    start_position,
                    start_line,
                    start_column
                ))
                
                # Update position and column
                for j in range(i, at_rule_end):
                    position += 1
                    column += 1
                
                i = at_rule_end
                continue
            
            # Handle selectors and property names (until we hit a '{' or ':')
            if char.isalnum() or char in '.#*[>,+~:':
                start_position = position
                start_line = line
                start_column = column
                
                # Determine if this is a selector or property
                is_property = False
                in_rule_block = False
                
                # Check if we're inside a rule block by looking back for most recent '{' and '}'
                last_open_brace = -1
                last_close_brace = -1
                for j in range(len(tokens) - 1, -1, -1):
                    if tokens[j].token_type == TokenType.OPEN_BRACE:
                        last_open_brace = j
                        break
                
                for j in range(len(tokens) - 1, -1, -1):
                    if tokens[j].token_type == TokenType.CLOSE_BRACE:
                        last_close_brace = j
                        break
                
                if last_open_brace > last_close_brace:
                    in_rule_block = True
                
                # Find the end of the selector or property
                identifier_end = i
                while identifier_end < len(code):
                    # For selectors, stop at '{' or ','
                    if not in_rule_block and (code[identifier_end] == '{' or code[identifier_end] == ','):
                        break
                    # For properties, stop at ':'
                    if in_rule_block and code[identifier_end] == ':':
                        is_property = True
                        break
                    # Always stop at whitespace, ';', '}', or '{'
                    if code[identifier_end].isspace() or code[identifier_end] in ';}{':
                        break
                    identifier_end += 1
                
                identifier = code[i:identifier_end]
                
                if is_property:
                    tokens.append(Token(
                        TokenType.PROPERTY,
                        identifier,
                        start_position,
                        start_line,
                        start_column
                    ))
                else:
                    tokens.append(Token(
                        TokenType.SELECTOR if not in_rule_block else TokenType.IDENTIFIER,
                        identifier,
                        start_position,
                        start_line,
                        start_column
                    ))
                
                # Update position and column
                for j in range(i, identifier_end):
                    position += 1
                    column += 1
                
                i = identifier_end
                continue
            
            # Handle property values (after ':' until ';')
            if char == ':':
                tokens.append(Token(
                    TokenType.COLON,
                    ':',
                    position,
                    line,
                    column
                ))
                position += 1
                column += 1
                i += 1
                
                # Skip whitespace
                while i < len(code) and code[i].isspace():
                    position += 1
                    column += 1
                    if code[i] == '\n':
                        line += 1
                        column = 1
                    i += 1
                
                if i < len(code):
                    start_position = position
                    start_line = line
                    start_column = column
                    
                    # Find the end of the value
                    value_end = i
                    while value_end < len(code) and code[value_end] != ';' and code[value_end] != '}' and code[value_end] != '\n':
                        value_end += 1
                    
                    value = code[i:value_end].strip()
                    if value:
                        tokens.append(Token(
                            TokenType.VALUE,
                            value,
                            start_position,
                            start_line,
                            start_column
                        ))
                    
                    # Update position and column
                    for j in range(i, value_end):
                        position += 1
                        column += 1
                        if code[j] == '\n':
                            line += 1
                            column = 1
                    
                    i = value_end
                    continue
            
            # Handle punctuation
            if char in '{};,':
                token_type = None
                if char == '{':
                    token_type = TokenType.OPEN_BRACE
                elif char == '}':
                    token_type = TokenType.CLOSE_BRACE
                elif char == ';':
                    token_type = TokenType.SEMICOLON
                elif char == ',':
                    token_type = TokenType.COMMA
                
                tokens.append(Token(
                    token_type,
                    char,
                    position,
                    line,
                    column
                ))
                position += 1
                column += 1
                i += 1
                continue
            
            # Handle anything else
            tokens.append(Token(
                TokenType.IDENTIFIER,
                char,
                position,
                line,
                column
            ))
            position += 1
            column += 1
            i += 1
        
        return tokens

