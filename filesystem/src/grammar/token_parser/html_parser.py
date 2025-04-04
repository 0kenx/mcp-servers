"""
HTML parser for the grammar parser system.

This module provides a parser specific to HTML, handling elements, attributes,
comments, and document structure.
"""

from typing import List, Dict, Set, Optional, Any, Tuple, cast
import re

from .token import Token, TokenType
from .token_parser import TokenParser
from .parser_state import ParserState, ContextInfo
from .symbol_table import SymbolTable


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


class HTMLParser(TokenParser):
    """
    Parser for HTML code.
    
    This parser processes HTML syntax, handling elements, attributes,
    and document structure.
    """
    
    def __init__(self):
        """Initialize the HTML parser."""
        super().__init__()
        self.tokenizer = HTMLTokenizer()
        self.state = ParserState()
        self.symbol_table = SymbolTable()
        
        # Context types specific to HTML
        self.context_types = {
            "element": "element",
            "script": "script",
            "style": "style",
            "comment": "comment",
            "doctype": "doctype",
        }
    
    def parse(self, code: str) -> Dict[str, Any]:
        """
        Parse HTML code and build an abstract syntax tree.
        
        Args:
            code: HTML source code
            
        Returns:
            Dictionary representing the abstract syntax tree
        """
        # Reset state for a new parse
        self.state = ParserState()
        self.symbol_table = SymbolTable()
        
        # Tokenize the code
        tokens = self.tokenize(code)
        
        # Process the tokens to build the AST
        return self.build_ast(tokens)
    
    def build_ast(self, tokens: List[Token]) -> Dict[str, Any]:
        """
        Build an abstract syntax tree from a list of tokens.
        
        Args:
            tokens: List of tokens from the tokenizer
            
        Returns:
            Dictionary representing the abstract syntax tree
        """
        ast: Dict[str, Any] = {
            "type": "Document",
            "children": [],
            "tokens": tokens,
            "start": 0,
            "end": len(tokens) - 1 if tokens else 0,
        }
        
        # Stack for tracking parent nodes
        stack = [ast]
        
        i = 0
        while i < len(tokens):
            token = tokens[i]
            
            if token.token_type == TokenType.DOCTYPE:
                doctype_node = {
                    "type": "Doctype",
                    "value": token.value,
                    "start": i,
                    "end": i,
                    "parent": stack[-1],
                    "children": []
                }
                stack[-1]["children"].append(doctype_node)
                i += 1
            
            elif token.token_type == TokenType.OPEN_TAG:
                # Extract tag name
                tag_match = re.match(r'<\s*([a-zA-Z0-9_-]+)', token.value)
                tag_name = tag_match.group(1) if tag_match else "unknown"
                
                # Check if this is a special tag (script, style)
                is_special_tag = tag_name.lower() in ["script", "style"]
                
                # Create element node
                element_node = {
                    "type": "Element",
                    "tagName": tag_name,
                    "attributes": self._extract_attributes(token.value),
                    "start": i,
                    "end": None,  # Will be set when closing tag is found
                    "parent": stack[-1],
                    "children": []
                }
                
                # Add to symbol table
                self.symbol_table.add_symbol(
                    name=tag_name,
                    symbol_type="element",
                    position=token.position,
                    line=token.line,
                    column=token.column,
                    metadata={"attributes": element_node["attributes"]}
                )
                
                stack[-1]["children"].append(element_node)
                stack.append(element_node)
                
                # If it's a script or style tag, we need special handling for content
                if is_special_tag:
                    # Find the corresponding closing tag
                    j = i + 1
                    content_start = j
                    while j < len(tokens):
                        if (tokens[j].token_type == TokenType.CLOSE_TAG and 
                            f"</{tag_name}" in tokens[j].value.lower()):
                            break
                        j += 1
                    
                    # Extract content between tags
                    if j > content_start:
                        content = "".join(t.value for t in tokens[content_start:j])
                        content_node = {
                            "type": f"{tag_name.capitalize()}Content",
                            "value": content,
                            "start": content_start,
                            "end": j - 1,
                            "parent": element_node,
                            "children": []
                        }
                        element_node["children"].append(content_node)
                    
                    # Skip to the closing tag
                    i = j
                else:
                    i += 1
            
            elif token.token_type == TokenType.CLOSE_TAG:
                # Extract tag name
                tag_match = re.match(r'</\s*([a-zA-Z0-9_-]+)', token.value)
                tag_name = tag_match.group(1) if tag_match else "unknown"
                
                # Find matching opening tag in stack
                j = len(stack) - 1
                while j >= 0:
                    if (stack[j].get("type") == "Element" and 
                        stack[j].get("tagName", "").lower() == tag_name.lower()):
                        # Set end position
                        stack[j]["end"] = i
                        
                        # Pop elements up to and including the matched element
                        while len(stack) > j:
                            stack.pop()
                        
                        break
                    j -= 1
                
                i += 1
            
            elif token.token_type == TokenType.SELF_CLOSING_TAG:
                # Extract tag name
                tag_match = re.match(r'<\s*([a-zA-Z0-9_-]+)', token.value)
                tag_name = tag_match.group(1) if tag_match else "unknown"
                
                # Create element node
                element_node = {
                    "type": "Element",
                    "tagName": tag_name,
                    "attributes": self._extract_attributes(token.value),
                    "selfClosing": True,
                    "start": i,
                    "end": i,
                    "parent": stack[-1],
                    "children": []
                }
                
                # Add to symbol table
                self.symbol_table.add_symbol(
                    name=tag_name,
                    symbol_type="element",
                    position=token.position,
                    line=token.line,
                    column=token.column,
                    metadata={"attributes": element_node["attributes"]}
                )
                
                stack[-1]["children"].append(element_node)
                i += 1
            
            elif token.token_type == TokenType.COMMENT:
                comment_node = {
                    "type": "Comment",
                    "value": token.value,
                    "start": i,
                    "end": i,
                    "parent": stack[-1],
                    "children": []
                }
                stack[-1]["children"].append(comment_node)
                i += 1
            
            elif token.token_type == TokenType.TEXT:
                text_node = {
                    "type": "Text",
                    "value": token.value,
                    "start": i,
                    "end": i,
                    "parent": stack[-1],
                    "children": []
                }
                stack[-1]["children"].append(text_node)
                i += 1
            
            else:
                # Skip whitespace and other tokens
                i += 1
        
        # Validate and repair the AST
        self.validate_and_repair_ast()
        
        return ast
    
    def _extract_attributes(self, tag_content: str) -> List[Dict[str, Any]]:
        """
        Extract attributes from a tag string.
        
        Args:
            tag_content: Content of the tag including '<' and '>'
            
        Returns:
            List of attribute dictionaries with name and value
        """
        # Remove the tag name and brackets
        tag_name_match = re.match(r'<\s*([a-zA-Z0-9_-]+)', tag_content)
        if not tag_name_match:
            return []
        
        tag_name = tag_name_match.group(1)
        content = tag_content[tag_name_match.end():]
        
        # Remove closing part of tag
        content = re.sub(r'\s*\/?>$', '', content)
        
        # Match attributes
        # Format: name="value", name='value', or name
        attribute_pattern = r'([a-zA-Z0-9_-]+)(?:\s*=\s*(?:"([^"]*)"|\'([^\']*)\'|([^\s>]*)?))?'
        
        attributes = []
        for match in re.finditer(attribute_pattern, content):
            name = match.group(1)
            # Find the first non-None value in groups 2, 3, or 4
            value = next((g for g in (match.group(2), match.group(3), match.group(4)) if g is not None), "")
            
            attributes.append({
                "name": name,
                "value": value
            })
        
        return attributes 