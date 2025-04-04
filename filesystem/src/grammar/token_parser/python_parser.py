"""
Python parser for the grammar parser system.

This module provides a parser specific to the Python programming language,
building on the base token parser framework.
"""

from typing import List, Dict, Set, Optional, Any, Tuple, cast
import re

from .token import Token, TokenType
from .token_parser import TokenParser
from .parser_state import ParserState, ContextInfo
from .symbol_table import SymbolTable, Symbol
from .python_tokenizer import PythonTokenizer
from .generic_parsers import IndentationBlockParser


class PythonParser(TokenParser):
    """
    Parser for Python code.
    
    This parser processes Python-specific syntax, handling indentation-based blocks,
    function and class definitions, and produces an abstract syntax tree.
    """
    
    def __init__(self):
        """Initialize the Python parser."""
        super().__init__()
        self.tokenizer = PythonTokenizer()
        self.state = ParserState()
        self.symbol_table = SymbolTable()
        
        # Context types specific to Python
        self.context_types = {
            "function": "function",
            "class": "class",
            "method": "method",
            "if": "if",
            "else": "else",
            "elif": "elif",
            "for": "for",
            "while": "while",
            "try": "try",
            "except": "except",
            "finally": "finally",
            "with": "with",
            "comprehension": "comprehension",
            "lambda": "lambda",
            "decorator": "decorator",
        }
        
        # Mapping of indentation levels to their line numbers
        self.indent_levels: Dict[int, int] = {}
        self.current_indent_level = 0
    
    def parse(self, code: str) -> Dict[str, Any]:
        """
        Parse Python code and build an abstract syntax tree.
        
        Args:
            code: Python source code
            
        Returns:
            Dictionary representing the abstract syntax tree
        """
        # Reset state for a new parse
        self.state = ParserState()
        self.symbol_table = SymbolTable()
        self.indent_levels = {}
        self.current_indent_level = 0
        
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
            "type": "Program",
            "body": [],
            "tokens": tokens,
            "start": 0,
            "end": len(tokens) - 1 if tokens else 0,
            "children": []
        }
        
        i = 0
        while i < len(tokens):
            # Track indentation changes
            if tokens[i].token_type == TokenType.WHITESPACE and tokens[i].line == 1:
                indent_size = len(tokens[i].value)
                if "indent_size" in tokens[i].metadata:
                    indent_size = tokens[i].metadata["indent_size"]
                    
                if indent_size > self.current_indent_level:
                    # Indentation increased - start a new block
                    self.indent_levels[indent_size] = tokens[i].line
                    self.current_indent_level = indent_size
                elif indent_size < self.current_indent_level:
                    # Indentation decreased - end blocks
                    for level in sorted(self.indent_levels.keys(), reverse=True):
                        if level > indent_size:
                            # End this block
                            del self.indent_levels[level]
                    self.current_indent_level = indent_size
            
            # Skip whitespace and newlines for AST building
            if tokens[i].token_type in [TokenType.WHITESPACE, TokenType.NEWLINE]:
                i += 1
                continue
            
            # Parse statements based on token type
            if i < len(tokens):
                if tokens[i].token_type == TokenType.KEYWORD:
                    stmt = self._parse_keyword_statement(tokens, i)
                    if stmt:
                        ast["body"].append(stmt["node"])
                        ast["children"].append(stmt["node"])
                        i = stmt["next_index"]
                    else:
                        i += 1
                elif tokens[i].token_type == TokenType.IDENTIFIER:
                    stmt = self._parse_expression_statement(tokens, i)
                    if stmt:
                        ast["body"].append(stmt["node"])
                        ast["children"].append(stmt["node"])
                        i = stmt["next_index"]
                    else:
                        i += 1
                else:
                    # Other token types
                    i += 1
        
        # Post-process the AST to fix parent-child relationships
        self._fix_parent_child_relationships(ast)
        
        # Validate and repair the AST
        self.validate_and_repair_ast()
        
        return ast
    
    def _parse_keyword_statement(self, tokens: List[Token], index: int) -> Optional[Dict[str, Any]]:
        """
        Parse a statement that starts with a keyword.
        
        Args:
            tokens: List of tokens
            index: Current index in the token list
            
        Returns:
            Dictionary with the parsed node and next index, or None if parsing failed
        """
        if index >= len(tokens):
            return None
            
        keyword = tokens[index].value
        
        if keyword == "def":
            return self._parse_function_definition(tokens, index)
        elif keyword == "class":
            return self._parse_class_definition(tokens, index)
        elif keyword == "if":
            return self._parse_if_statement(tokens, index)
        elif keyword == "for":
            return self._parse_for_statement(tokens, index)
        elif keyword == "while":
            return self._parse_while_statement(tokens, index)
        elif keyword == "return":
            return self._parse_return_statement(tokens, index)
        elif keyword in ["import", "from"]:
            return self._parse_import_statement(tokens, index)
        elif keyword in ["try", "except", "finally"]:
            return self._parse_try_statement(tokens, index)
        elif keyword == "with":
            return self._parse_with_statement(tokens, index)
        
        # Default simple statement
        return self._parse_expression_statement(tokens, index)
    
    def _parse_function_definition(self, tokens: List[Token], index: int) -> Optional[Dict[str, Any]]:
        """
        Parse a function definition.
        
        Args:
            tokens: List of tokens
            index: Current index in the token list
            
        Returns:
            Dictionary with the parsed node and next index, or None if parsing failed
        """
        start_index = index
        index += 1  # Skip 'def' keyword
        
        # Skip whitespace
        while index < len(tokens) and tokens[index].token_type == TokenType.WHITESPACE:
            index += 1
        
        # Get function name
        if index >= len(tokens) or tokens[index].token_type != TokenType.IDENTIFIER:
            return None
        
        function_name = tokens[index].value
        name_index = index
        index += 1
        
        # Skip whitespace
        while index < len(tokens) and tokens[index].token_type == TokenType.WHITESPACE:
            index += 1
        
        # Expect open parenthesis
        if index >= len(tokens) or tokens[index].token_type != TokenType.OPEN_PAREN:
            return None
        
        index += 1
        
        # Parse parameters
        parameters = []
        while index < len(tokens) and tokens[index].token_type != TokenType.CLOSE_PAREN:
            # Skip whitespace
            if tokens[index].token_type == TokenType.WHITESPACE:
                index += 1
                continue
                
            # Parameter name
            if tokens[index].token_type == TokenType.IDENTIFIER:
                param_name = tokens[index].value
                param_index = index
                index += 1
                
                # Check for type annotation
                param_type = None
                if index < len(tokens) and tokens[index].token_type == TokenType.COLON:
                    index += 1
                    
                    # Skip whitespace
                    while index < len(tokens) and tokens[index].token_type == TokenType.WHITESPACE:
                        index += 1
                    
                    # Get type annotation
                    if index < len(tokens) and tokens[index].token_type == TokenType.IDENTIFIER:
                        param_type = tokens[index].value
                        index += 1
                
                # Check for default value
                default_value = None
                if index < len(tokens) and tokens[index].token_type == TokenType.EQUALS:
                    index += 1
                    
                    # Skip whitespace
                    while index < len(tokens) and tokens[index].token_type == TokenType.WHITESPACE:
                        index += 1
                    
                    # Parse default value expression
                    default_value_expr = self._parse_expression(tokens, index)
                    if default_value_expr:
                        default_value = default_value_expr["node"]
                        index = default_value_expr["next_index"]
                
                parameters.append({
                    "type": "Parameter",
                    "name": param_name,
                    "annotation": param_type,
                    "default": default_value,
                    "start": param_index,
                    "end": index - 1,
                    "parent": None,
                    "children": []
                })
            
            # Skip comma
            if index < len(tokens) and tokens[index].token_type == TokenType.COMMA:
                index += 1
                continue
        
        # Skip closing parenthesis
        if index < len(tokens) and tokens[index].token_type == TokenType.CLOSE_PAREN:
            index += 1
        
        # Check for return type annotation
        return_type = None
        if index < len(tokens) and tokens[index].token_type == TokenType.ARROW:
            index += 1
            
            # Skip whitespace
            while index < len(tokens) and tokens[index].token_type == TokenType.WHITESPACE:
                index += 1
            
            # Get return type annotation
            if index < len(tokens) and tokens[index].token_type == TokenType.IDENTIFIER:
                return_type = tokens[index].value
                index += 1
        
        # Skip whitespace and colon
        while index < len(tokens) and tokens[index].token_type == TokenType.WHITESPACE:
            index += 1
            
        if index < len(tokens) and tokens[index].token_type == TokenType.COLON:
            index += 1
        else:
            return None  # Malformed function definition
        
        # Calculate the current indentation level
        current_indent_level = 0
        for i in range(start_index - 1, -1, -1):
            if tokens[i].token_type == TokenType.NEWLINE:
                # Found the start of the current line
                if i + 1 < len(tokens) and tokens[i + 1].token_type == TokenType.WHITESPACE:
                    # Get indentation level
                    indent_token = tokens[i + 1]
                    current_indent_level = len(indent_token.value)
                    if "indent_size" in indent_token.metadata:
                        current_indent_level = indent_token.metadata["indent_size"]
                break
        
        # Context metadata
        context_metadata = {"name": function_name}
        
        # Add function to symbol table
        self.symbol_table.add_symbol(
            name=function_name,
            symbol_type="function",
            position=tokens[name_index].position,
            line=tokens[name_index].line,
            column=tokens[name_index].column,
            metadata={"parameters": [p["name"] for p in parameters]}
        )
        
        # Parse function body using generic indentation block parser
        body_tokens, next_index = IndentationBlockParser.parse_block(
            tokens,
            index,
            current_indent_level,
            self.state,
            self.context_types["function"],
            context_metadata
        )
        
        # Create function node
        function_node = {
            "type": "FunctionDefinition",
            "name": function_name,
            "parameters": parameters,
            "return_type": return_type,
            "body": body_tokens,
            "start": start_index,
            "end": next_index - 1,
            "parent": None,
            "children": []
        }
        
        # Set parent-child relationships for parameters
        for param in parameters:
            param["parent"] = function_node
            function_node["children"].append(param)
        
        return {
            "node": function_node,
            "next_index": next_index
        }
    
    def _parse_class_definition(self, tokens: List[Token], index: int) -> Optional[Dict[str, Any]]:
        """
        Parse a class definition.
        
        Args:
            tokens: List of tokens
            index: Current index in the token list
            
        Returns:
            Dictionary with the parsed node and next index, or None if parsing failed
        """
        start_index = index
        index += 1  # Skip 'class' keyword
        
        # Skip whitespace
        while index < len(tokens) and tokens[index].token_type == TokenType.WHITESPACE:
            index += 1
        
        # Get class name
        if index >= len(tokens) or tokens[index].token_type != TokenType.IDENTIFIER:
            return None
        
        class_name = tokens[index].value
        name_index = index
        index += 1
        
        # Skip whitespace
        while index < len(tokens) and tokens[index].token_type == TokenType.WHITESPACE:
            index += 1
        
        # Check for inheritance
        bases = []
        if index < len(tokens) and tokens[index].token_type == TokenType.OPEN_PAREN:
            index += 1
            
            while index < len(tokens) and tokens[index].token_type != TokenType.CLOSE_PAREN:
                # Skip whitespace
                if tokens[index].token_type == TokenType.WHITESPACE:
                    index += 1
                    continue
                    
                # Base class name
                if tokens[index].token_type == TokenType.IDENTIFIER:
                    base_name = tokens[index].value
                    base_index = index
                    index += 1
                    
                    bases.append({
                        "type": "Identifier",
                        "name": base_name,
                        "start": base_index,
                        "end": base_index,
                        "parent": None,
                        "children": []
                    })
                
                # Skip comma
                if index < len(tokens) and tokens[index].token_type == TokenType.COMMA:
                    index += 1
                    continue
            
            # Skip closing parenthesis
            if index < len(tokens) and tokens[index].token_type == TokenType.CLOSE_PAREN:
                index += 1
        
        # Skip whitespace and colon
        while index < len(tokens) and tokens[index].token_type == TokenType.WHITESPACE:
            index += 1
            
        if index < len(tokens) and tokens[index].token_type == TokenType.COLON:
            index += 1
        else:
            return None  # Malformed class definition
        
        # Calculate the current indentation level
        current_indent_level = 0
        for i in range(start_index - 1, -1, -1):
            if tokens[i].token_type == TokenType.NEWLINE:
                # Found the start of the current line
                if i + 1 < len(tokens) and tokens[i + 1].token_type == TokenType.WHITESPACE:
                    # Get indentation level
                    indent_token = tokens[i + 1]
                    current_indent_level = len(indent_token.value)
                    if "indent_size" in indent_token.metadata:
                        current_indent_level = indent_token.metadata["indent_size"]
                break
        
        # Context metadata
        context_metadata = {
            "name": class_name,
            "bases": [b["name"] for b in bases]
        }
        
        # Add class to symbol table
        self.symbol_table.add_symbol(
            name=class_name,
            symbol_type="class",
            position=tokens[name_index].position,
            line=tokens[name_index].line,
            column=tokens[name_index].column,
            metadata={"bases": [b["name"] for b in bases]}
        )
        
        # Parse class body using generic indentation block parser
        body_tokens, next_index = IndentationBlockParser.parse_block(
            tokens,
            index,
            current_indent_level,
            self.state,
            self.context_types["class"],
            context_metadata
        )
        
        # Create class node
        class_node = {
            "type": "ClassDefinition",
            "name": class_name,
            "bases": bases,
            "body": body_tokens,
            "start": start_index,
            "end": next_index - 1,
            "parent": None,
            "children": []
        }
        
        # Set parent-child relationships for bases
        for base in bases:
            base["parent"] = class_node
            class_node["children"].append(base)
        
        return {
            "node": class_node,
            "next_index": next_index
        }
    
    def _parse_expression_statement(self, tokens: List[Token], index: int) -> Optional[Dict[str, Any]]:
        """
        Parse an expression statement.
        
        Args:
            tokens: List of tokens
            index: Current index in the token list
            
        Returns:
            Dictionary with the parsed node and next index, or None if parsing failed
        """
        expr = self._parse_expression(tokens, index)
        if not expr:
            return None
        
        stmt = {
            "type": "ExpressionStatement",
            "expression": expr["node"],
            "start": expr["node"]["start"],
            "end": expr["node"]["end"],
            "parent": None,
            "children": [expr["node"]]
        }
        
        expr["node"]["parent"] = stmt
        
        return {
            "node": stmt,
            "next_index": expr["next_index"]
        }
    
    def _parse_expression(self, tokens: List[Token], index: int) -> Optional[Dict[str, Any]]:
        """
        Parse an expression.
        
        Args:
            tokens: List of tokens
            index: Current index in the token list
            
        Returns:
            Dictionary with the parsed node and next index, or None if parsing failed
        """
        # For simplicity, we'll just parse basic expressions
        if index >= len(tokens):
            return None
        
        if tokens[index].token_type == TokenType.IDENTIFIER:
            # Variable reference or function call
            identifier = tokens[index].value
            start_index = index
            index += 1
            
            # Check if it's a function call
            if index < len(tokens) and tokens[index].token_type == TokenType.OPEN_PAREN:
                index += 1
                
                # Parse arguments
                arguments = []
                while index < len(tokens) and tokens[index].token_type != TokenType.CLOSE_PAREN:
                    # Skip whitespace
                    if tokens[index].token_type == TokenType.WHITESPACE:
                        index += 1
                        continue
                    
                    # Parse argument expression
                    arg_expr = self._parse_expression(tokens, index)
                    if arg_expr:
                        arguments.append(arg_expr["node"])
                        index = arg_expr["next_index"]
                    else:
                        # Skip this token if we couldn't parse an expression
                        index += 1
                    
                    # Skip comma
                    if index < len(tokens) and tokens[index].token_type == TokenType.COMMA:
                        index += 1
                
                # Skip closing parenthesis
                if index < len(tokens) and tokens[index].token_type == TokenType.CLOSE_PAREN:
                    index += 1
                
                # Create call expression node
                call_node = {
                    "type": "CallExpression",
                    "callee": {
                        "type": "Identifier",
                        "name": identifier,
                        "start": start_index,
                        "end": start_index,
                        "parent": None,
                        "children": []
                    },
                    "arguments": arguments,
                    "start": start_index,
                    "end": index - 1,
                    "parent": None,
                    "children": []
                }
                
                # Set parent-child relationships
                call_node["callee"]["parent"] = call_node
                call_node["children"].append(call_node["callee"])
                
                for arg in arguments:
                    arg["parent"] = call_node
                    call_node["children"].append(arg)
                
                return {
                    "node": call_node,
                    "next_index": index
                }
            else:
                # Simple identifier
                return {
                    "node": {
                        "type": "Identifier",
                        "name": identifier,
                        "start": start_index,
                        "end": start_index,
                        "parent": None,
                        "children": []
                    },
                    "next_index": index
                }
        elif tokens[index].token_type == TokenType.NUMBER:
            # Numeric literal
            return {
                "node": {
                    "type": "NumericLiteral",
                    "value": tokens[index].value,
                    "start": index,
                    "end": index,
                    "parent": None,
                    "children": []
                },
                "next_index": index + 1
            }
        elif tokens[index].token_type == TokenType.STRING_START:
            # String literal
            start_index = index
            string_value = ""
            index += 1
            
            # Collect string content
            while index < len(tokens):
                if tokens[index].token_type == TokenType.STRING_END:
                    index += 1
                    break
                
                string_value += tokens[index].value
                index += 1
            
            return {
                "node": {
                    "type": "StringLiteral",
                    "value": string_value,
                    "start": start_index,
                    "end": index - 1,
                    "parent": None,
                    "children": []
                },
                "next_index": index
            }
        
        # Default case
        return None
    
    def _parse_if_statement(self, tokens: List[Token], index: int) -> Optional[Dict[str, Any]]:
        """Placeholder for parsing if statements."""
        # This would be implemented similarly to the function and class parsers
        return None
    
    def _parse_for_statement(self, tokens: List[Token], index: int) -> Optional[Dict[str, Any]]:
        """Placeholder for parsing for statements."""
        return None
    
    def _parse_while_statement(self, tokens: List[Token], index: int) -> Optional[Dict[str, Any]]:
        """Placeholder for parsing while statements."""
        return None
    
    def _parse_return_statement(self, tokens: List[Token], index: int) -> Optional[Dict[str, Any]]:
        """Placeholder for parsing return statements."""
        return None
    
    def _parse_import_statement(self, tokens: List[Token], index: int) -> Optional[Dict[str, Any]]:
        """Placeholder for parsing import statements."""
        return None
    
    def _parse_try_statement(self, tokens: List[Token], index: int) -> Optional[Dict[str, Any]]:
        """Placeholder for parsing try-except statements."""
        return None
    
    def _parse_with_statement(self, tokens: List[Token], index: int) -> Optional[Dict[str, Any]]:
        """Placeholder for parsing with statements."""
        return None
    
    def _fix_parent_child_relationships(self, ast: Dict[str, Any]) -> None:
        """
        Fix parent-child relationships in the AST.
        
        Args:
            ast: The abstract syntax tree to fix
        """
        # Implement parent-child relationship fixing logic here
        # This would walk the AST and ensure all nodes have correct parent and children references
        pass 