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
from .ts_react_tokenizer import TSReactTokenizer


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