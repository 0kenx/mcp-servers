"""
TypeScript React parser for the grammar parser system.

This module provides a parser specific to TypeScript with JSX/TSX syntax,
extending the TypeScript parser to handle React JSX components and expressions.
"""

from typing import List, Dict, Set, Optional, Any, Tuple, cast
import re

from .token import Token, TokenType
from .typescript_parser import TypeScriptParser
from .parser_state import ParserState, ContextInfo
from .symbol_table import SymbolTable


class TSReactTokenizer:
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


class TSReactParser(TypeScriptParser):
    """
    Parser for TypeScript React (TSX) code.
    
    This parser extends the TypeScript parser to handle JSX syntax used in React.
    """
    
    def __init__(self):
        """Initialize the TSX parser."""
        super().__init__()
        self.tokenizer = TSReactTokenizer()
        
        # Add JSX-specific context types
        self.context_types.update({
            "jsx_element": "jsx_element",
            "jsx_fragment": "jsx_fragment",
            "jsx_expression": "jsx_expression",
        })
    
    def build_ast(self, tokens: List[Token]) -> Dict[str, Any]:
        """
        Build an abstract syntax tree from a list of tokens.
        
        Extends the TypeScript AST building to handle JSX syntax.
        
        Args:
            tokens: List of tokens from the tokenizer
            
        Returns:
            Dictionary representing the abstract syntax tree
        """
        # Let TypeScript parser handle the base structure
        ast = super().build_ast(tokens)
        
        # Custom handling for JSX elements after TypeScript has built the AST
        self._process_jsx_elements(ast)
        
        return ast
    
    def _process_jsx_elements(self, node: Dict[str, Any]) -> None:
        """
        Process JSX elements in the AST.
        
        Walks the AST and identifies/processes JSX elements.
        
        Args:
            node: AST node to process
        """
        if not isinstance(node, dict):
            return
        
        # Check if this is a JSX tag
        if node.get("type") == "JSXElement":
            self._process_jsx_attributes(node)
        
        # Recursively process children
        if "children" in node and isinstance(node["children"], list):
            for child in node["children"]:
                self._process_jsx_elements(child)
    
    def _process_jsx_attributes(self, jsx_node: Dict[str, Any]) -> None:
        """
        Process attributes in a JSX element.
        
        Args:
            jsx_node: JSX element node
        """
        if "attributes" in jsx_node and isinstance(jsx_node["attributes"], list):
            for attr in jsx_node["attributes"]:
                # Handle spread attributes
                if attr.get("type") == "JSXSpreadAttribute":
                    continue
                
                # Add attribute to symbol table
                if "name" in attr and "value" in attr:
                    self.symbol_table.add_symbol(
                        name=attr["name"],
                        symbol_type="jsx_attribute",
                        position=attr.get("start", 0),
                        line=0,  # We don't have line info at this level
                        column=0,  # We don't have column info at this level
                        metadata={"element": jsx_node.get("tagName", ""), "value": attr["value"]}
                    )
    
    def _parse_keyword_statement(self, tokens: List[Token], index: int) -> Optional[Dict[str, Any]]:
        """
        Parse a statement that starts with a keyword.
        
        Extends the TypeScript parser to handle JSX-specific statements.
        
        Args:
            tokens: List of tokens
            index: Current index in the token list
            
        Returns:
            Dictionary with the parsed node and next index, or None if parsing failed
        """
        # If we encounter a JSX tag, parse it as a JSX element
        if index < len(tokens) and tokens[index].token_type == TokenType.JSX_TAG:
            return self._parse_jsx_element(tokens, index)
        
        # Otherwise, let TypeScript parser handle it
        return super()._parse_keyword_statement(tokens, index)
    
    def _parse_jsx_element(self, tokens: List[Token], index: int) -> Optional[Dict[str, Any]]:
        """
        Parse a JSX element.
        
        Args:
            tokens: List of tokens
            index: Current index in the token list
            
        Returns:
            Dictionary with the parsed node and next index, or None if parsing failed
        """
        if index >= len(tokens) or tokens[index].token_type != TokenType.JSX_TAG:
            return None
        
        start_index = index
        tag_content = tokens[index].value
        
        # Extract tag name
        tag_match = re.match(r'<\s*([a-zA-Z0-9_\.\-:]+)', tag_content)
        tag_name = tag_match.group(1) if tag_match else "unknown"
        
        # Check if this is a self-closing tag
        is_self_closing = tag_content.rstrip().endswith('/>')
        
        # Extract attributes
        attributes = self._extract_jsx_attributes(tag_content)
        
        # Create the element node
        jsx_element_node = {
            "type": "JSXElement",
            "tagName": tag_name,
            "attributes": attributes,
            "selfClosing": is_self_closing,
            "start": index,
            "end": None,  # Will be set when closing tag is found
            "parent": None,
            "children": []
        }
        
        # Add element to symbol table
        self.symbol_table.add_symbol(
            name=tag_name,
            symbol_type="jsx_element",
            position=tokens[index].position,
            line=tokens[index].line,
            column=tokens[index].column,
            metadata={"attributes": [attr["name"] for attr in attributes if "name" in attr]}
        )
        
        index += 1
        
        # If not self-closing, parse children until we find the closing tag
        if not is_self_closing:
            while index < len(tokens):
                # Check for closing tag
                if (tokens[index].token_type == TokenType.JSX_TAG and 
                    re.match(r'</\s*' + re.escape(tag_name) + r'\s*>', tokens[index].value)):
                    jsx_element_node["end"] = index
                    index += 1
                    break
                
                # Parse JSX child elements
                if tokens[index].token_type == TokenType.JSX_TAG:
                    child = self._parse_jsx_element(tokens, index)
                    if child:
                        child_node = child["node"]
                        child_node["parent"] = jsx_element_node
                        jsx_element_node["children"].append(child_node)
                        index = child["next_index"]
                        continue
                
                # Parse JSX expressions (in curly braces)
                if tokens[index].token_type == TokenType.JSX_EXPRESSION:
                    expr_node = {
                        "type": "JSXExpression",
                        "expression": tokens[index].value[1:-1],  # Remove { and }
                        "start": index,
                        "end": index,
                        "parent": jsx_element_node,
                        "children": []
                    }
                    jsx_element_node["children"].append(expr_node)
                    index += 1
                    continue
                
                # Parse text content
                if tokens[index].token_type == TokenType.JSX_TEXT:
                    text_node = {
                        "type": "JSXText",
                        "value": tokens[index].value,
                        "start": index,
                        "end": index,
                        "parent": jsx_element_node,
                        "children": []
                    }
                    jsx_element_node["children"].append(text_node)
                    index += 1
                    continue
                
                # Skip other tokens
                index += 1
            
            # If we didn't find a closing tag, set end to the last token
            if jsx_element_node["end"] is None:
                jsx_element_node["end"] = len(tokens) - 1
        else:
            # Self-closing tags end at their own position
            jsx_element_node["end"] = start_index
        
        return {
            "node": jsx_element_node,
            "next_index": index
        }
    
    def _extract_jsx_attributes(self, tag_content: str) -> List[Dict[str, Any]]:
        """
        Extract attributes from a JSX tag.
        
        Args:
            tag_content: Content of the JSX tag
            
        Returns:
            List of attribute objects with name and value
        """
        # Remove the tag name and brackets
        tag_name_match = re.match(r'<\s*([a-zA-Z0-9_\.\-:]+)', tag_content)
        if not tag_name_match:
            return []
        
        tag_name = tag_name_match.group(1)
        content = tag_content[tag_name_match.end():]
        
        # Remove closing part of tag
        content = re.sub(r'\s*\/?>$', '', content)
        
        attributes = []
        
        # Match regular attributes (name="value" or name={expr})
        attr_pattern = r'([a-zA-Z0-9_\-:]+)(?:\s*=\s*(?:"([^"]*)"|\'([^\']*)\'|(\{[^}]*\})))?'
        
        for match in re.finditer(attr_pattern, content):
            name = match.group(1)
            
            # Determine value type: string or expression
            value = None
            if match.group(2) is not None:  # Double quoted string
                value = {"type": "StringLiteral", "value": match.group(2)}
            elif match.group(3) is not None:  # Single quoted string
                value = {"type": "StringLiteral", "value": match.group(3)}
            elif match.group(4) is not None:  # Expression in curly braces
                expr = match.group(4)[1:-1]  # Remove { and }
                value = {"type": "JSXExpression", "value": expr}
            else:
                # Boolean attribute (no value specified)
                value = {"type": "BooleanLiteral", "value": True}
            
            attributes.append({
                "type": "JSXAttribute",
                "name": name,
                "value": value
            })
        
        # Match spread attributes ({...props})
        spread_pattern = r'(\{\.\.\.([^}]*)\})'
        
        for match in re.finditer(spread_pattern, content):
            attributes.append({
                "type": "JSXSpreadAttribute",
                "expression": match.group(2).strip()
            })
        
        return attributes 