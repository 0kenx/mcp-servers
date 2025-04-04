"""
TypeScript React  tokenizer for the grammar parser system.

This module provides a tokenizer specific to TypeScript with JSX/TSX syntax.
"""

from typing import List, Dict, Set, Tuple, Optional, Any
from .token import Token, TokenType
from .tokenizer import Tokenizer, TokenizerState
from .typescript_tokenizer import TypeScriptTokenizer


class TSReactTokenizer(TypeScriptTokenizer):
    """
    Tokenizer for TypeScript React (TSX) code.
    
    This extends the TypeScript tokenizer to handle JSX syntax.
    """
    
    def tokenize(self, code: str) -> List[Token]:
        """
        Tokenize TSX code.
        
        Args:
            code: TypeScript React source code to tokenize
            
        Returns:
            List of tokens
        """
        tokens = []
        position = 0
        line = 1
        column = 1
        
        i = 0
        in_jsx_context = False
        jsx_depth = 0
        
        while i < len(code):
            # Handle JSX opening tags
            if code[i:i+1] == '<' and i + 1 < len(code) and (code[i+1].isalpha() or code[i+1] == '_' or code[i+1] == '/'):
                # Check if we're entering JSX context
                if not in_jsx_context and code[i+1] != '/':
                    in_jsx_context = True
                
                start_position = position
                start_line = line
                start_column = column
                
                # Find the end of the tag
                tag_end = i
                if code[i+1] == '/':  # Closing tag
                    # Find the closing '>'
                    while tag_end < len(code) and code[tag_end] != '>':
                        tag_end += 1
                    if tag_end < len(code):
                        tag_end += 1  # Include the '>'
                    
                    jsx_depth -= 1
                    if jsx_depth <= 0:
                        in_jsx_context = False
                        jsx_depth = 0
                
                else:  # Opening tag
                    jsx_depth += 1
                    
                    # Find the end of the tag (either '>' or '/>')
                    brace_depth = 0
                    while tag_end < len(code):
                        if code[tag_end] == '{':
                            brace_depth += 1
                        elif code[tag_end] == '}':
                            brace_depth -= 1
                        elif code[tag_end] == '>' and brace_depth == 0:
                            tag_end += 1  # Include the '>'
                            break
                        elif code[tag_end:tag_end+2] == '/>' and brace_depth == 0:
                            tag_end += 2  # Include the '/>'
                            jsx_depth -= 1  # Self-closing tag reduces depth
                            if jsx_depth <= 0:
                                in_jsx_context = False
                                jsx_depth = 0
                            break
                        
                        tag_end += 1
                
                tag_content = code[i:tag_end]
                
                # Determine token type
                token_type = TokenType.JSX_TAG
                
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
                continue
            
            # Handle JSX expressions (inside curly braces)
            if in_jsx_context and code[i] == '{':
                start_position = position
                start_line = line
                start_column = column
                
                # Find the matching closing brace
                brace_count = 1
                expr_end = i + 1
                while expr_end < len(code) and brace_count > 0:
                    if code[expr_end] == '{':
                        brace_count += 1
                    elif code[expr_end] == '}':
                        brace_count -= 1
                    
                    expr_end += 1
                
                expr_content = code[i:expr_end]
                
                tokens.append(Token(
                    TokenType.JSX_EXPRESSION,
                    expr_content,
                    start_position,
                    start_line,
                    start_column
                ))
                
                # Update position and line/column counters
                for char in expr_content:
                    position += 1
                    column += 1
                    if char == '\n':
                        line += 1
                        column = 1
                
                i = expr_end
                continue
            
            # Handle JSX text content
            if in_jsx_context and code[i] != '<' and code[i] != '{':
                start_position = position
                start_line = line
                start_column = column
                
                text_end = i
                while text_end < len(code) and code[text_end] != '<' and code[text_end] != '{':
                    text_end += 1
                
                text_content = code[i:text_end]
                if text_content.strip():  # Only add non-empty text
                    tokens.append(Token(
                        TokenType.JSX_TEXT,
                        text_content,
                        start_position,
                        start_line,
                        start_column
                    ))
                
                # Update position and line/column counters
                for char in text_content:
                    position += 1
                    column += 1
                    if char == '\n':
                        line += 1
                        column = 1
                
                i = text_end
                continue
            
            # For non-JSX code, tokenize as TypeScript
            # Handle whitespace
            if code[i].isspace():
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
            if i + 1 < len(code):
                if code[i:i+2] == '//':
                    start_position = position
                    start_line = line
                    start_column = column
                    
                    comment_end = code.find('\n', i)
                    if comment_end == -1:
                        comment_end = len(code)
                    
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
                    
                    i = comment_end
                    continue
                
                if code[i:i+2] == '/*':
                    start_position = position
                    start_line = line
                    start_column = column
                    
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
            
            # Handle identifiers and keywords
            if code[i].isalpha() or code[i] == '_':
                start_position = position
                start_line = line
                start_column = column
                
                identifier_end = i
                while identifier_end < len(code) and (code[identifier_end].isalnum() or code[identifier_end] == '_'):
                    identifier_end += 1
                
                identifier = code[i:identifier_end]
                
                # Check if it's a keyword
                keywords = ['const', 'let', 'var', 'function', 'class', 'interface',
                           'export', 'import', 'from', 'return', 'if', 'else',
                           'for', 'while', 'do', 'switch', 'case', 'default',
                           'try', 'catch', 'finally', 'throw', 'extends', 'implements',
                           'type', 'namespace', 'enum', 'public', 'private', 'protected',
                           'static', 'readonly', 'as', 'instanceof', 'typeof',
                           'async', 'await', 'break', 'continue', 'new']
                
                if identifier in keywords:
                    token_type = TokenType.KEYWORD
                else:
                    token_type = TokenType.IDENTIFIER
                
                tokens.append(Token(
                    token_type,
                    identifier,
                    start_position,
                    start_line,
                    start_column
                ))
                
                # Update position and column
                position += len(identifier)
                column += len(identifier)
                
                i = identifier_end
                continue
            
            # Handle string literals
            if code[i] in ['"', "'"]:
                start_position = position
                start_line = line
                start_column = column
                
                quote = code[i]
                string_end = i + 1
                escaped = False
                
                while string_end < len(code):
                    if code[string_end] == '\\':
                        escaped = not escaped
                    elif code[string_end] == quote and not escaped:
                        string_end += 1  # Include the closing quote
                        break
                    else:
                        escaped = False
                    
                    string_end += 1
                
                string_content = code[i:string_end]
                
                tokens.append(Token(
                    TokenType.STRING,
                    string_content,
                    start_position,
                    start_line,
                    start_column
                ))
                
                # Update position and line/column counters
                for char in string_content:
                    position += 1
                    column += 1
                    if char == '\n':
                        line += 1
                        column = 1
                
                i = string_end
                continue
            
            # Handle template literals
            if code[i] == '`':
                start_position = position
                start_line = line
                start_column = column
                
                template_end = i + 1
                escaped = False
                
                while template_end < len(code):
                    if code[template_end] == '\\':
                        escaped = not escaped
                    elif code[template_end] == '`' and not escaped:
                        template_end += 1  # Include the closing backtick
                        break
                    else:
                        escaped = False
                    
                    template_end += 1
                
                template_content = code[i:template_end]
                
                tokens.append(Token(
                    TokenType.TEMPLATE_LITERAL,
                    template_content,
                    start_position,
                    start_line,
                    start_column
                ))
                
                # Update position and line/column counters
                for char in template_content:
                    position += 1
                    column += 1
                    if char == '\n':
                        line += 1
                        column = 1
                
                i = template_end
                continue
            
            # Handle operators and punctuation
            operators = ['++', '--', '+=', '-=', '*=', '/=', '%=', '**=', '&&', '||',
                        '==', '===', '!=', '!==', '>=', '<=', '=>', '...', '??']
            
            # Try to match multi-character operators first
            matched_operator = None
            for op in operators:
                if i + len(op) <= len(code) and code[i:i+len(op)] == op:
                    matched_operator = op
                    break
            
            if matched_operator:
                tokens.append(Token(
                    TokenType.OPERATOR,
                    matched_operator,
                    position,
                    line,
                    column
                ))
                
                position += len(matched_operator)
                column += len(matched_operator)
                i += len(matched_operator)
                continue
            
            # Handle single-character operators and punctuation
            if code[i] in '+-*/%=&|!<>^~?:.,;()[]{}':
                tokens.append(Token(
                    TokenType.OPERATOR if code[i] in '+-*/%=&|!<>^~?:' else
                    TokenType.COMMA if code[i] == ',' else
                    TokenType.SEMICOLON if code[i] == ';' else
                    TokenType.DOT if code[i] == '.' else
                    TokenType.OPEN_PAREN if code[i] == '(' else
                    TokenType.CLOSE_PAREN if code[i] == ')' else
                    TokenType.OPEN_BRACKET if code[i] == '[' else
                    TokenType.CLOSE_BRACKET if code[i] == ']' else
                    TokenType.OPEN_BRACE if code[i] == '{' else
                    TokenType.CLOSE_BRACE,
                    code[i],
                    position,
                    line,
                    column
                ))
                
                position += 1
                column += 1
                i += 1
                continue
            
            # Handle numeric literals
            if code[i].isdigit() or (code[i] == '.' and i + 1 < len(code) and code[i+1].isdigit()):
                start_position = position
                start_line = line
                start_column = column
                
                number_end = i
                has_decimal = False
                
                if code[i] == '.':
                    has_decimal = True
                
                while number_end < len(code):
                    if code[number_end] == '.' and not has_decimal:
                        has_decimal = True
                    elif not code[number_end].isdigit() and not (code[number_end].lower() in 'xboe' and number_end == i + 1 and code[i] == '0'):
                        break
                    
                    number_end += 1
                
                number = code[i:number_end]
                
                tokens.append(Token(
                    TokenType.NUMBER,
                    number,
                    start_position,
                    start_line,
                    start_column
                ))
                
                position += len(number)
                column += len(number)
                i = number_end
                continue
            
            # Handle anything else character by character
            tokens.append(Token(
                TokenType.IDENTIFIER,
                code[i],
                position,
                line,
                column
            ))
            
            position += 1
            column += 1
            i += 1
        
        return tokens

