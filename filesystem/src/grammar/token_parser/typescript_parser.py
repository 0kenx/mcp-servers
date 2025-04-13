"""
TypeScript parser for the grammar parser system.

This module provides a parser specific to the TypeScript programming language,
extending the JavaScript parser to handle TypeScript-specific features.
"""

from typing import List, Dict, Optional, Any, Tuple

from .token import Token, TokenType
from .javascript_parser import JavaScriptParser
from .base import CodeElement, ElementType


class TypeScriptParser(JavaScriptParser):
    """
    Parser for TypeScript code.

    This parser extends the JavaScript parser to handle TypeScript-specific syntax,
    such as type annotations, interfaces, and other TypeScript features.
    """

    def __init__(self):
        """Initialize the TypeScript parser."""
        super().__init__()

        # Add TypeScript-specific context types
        self.context_types.update(
            {
                "interface": "interface",
                "type": "type",
                "namespace": "namespace",
                "enum": "enum",
                "generic": "generic",
            }
        )
        
    def _build_elements_from_tokens(self, tokens: List[Token]) -> None:
        """
        Build code elements directly from the tokens.

        Extends the JavaScript parser to handle TypeScript-specific elements like interfaces and type aliases.

        Args:
            tokens: List of tokens from the tokenizer
        """
        i = 0
        while i < len(tokens):
            # Skip whitespace and newlines for element building
            if tokens[i].token_type in [TokenType.WHITESPACE, TokenType.NEWLINE]:
                i += 1
                continue

            # Parse statements based on token type
            if i < len(tokens):
                if tokens[i].token_type == TokenType.KEYWORD:
                    # Process TypeScript-specific keywords
                    if tokens[i].value == "interface":
                        # Parse interface declaration
                        interface, next_index = self._parse_interface_direct(tokens, i)
                        if interface:
                            self.elements.append(interface)
                            i = next_index
                        else:
                            i += 1
                    elif tokens[i].value == "type":
                        # Parse type alias
                        type_alias, next_index = self._parse_type_alias_direct(tokens, i)
                        if type_alias:
                            self.elements.append(type_alias)
                            i = next_index
                        else:
                            i += 1
                    elif tokens[i].value == "enum":
                        # TODO: Implement enum parsing
                        i += 1
                    elif tokens[i].value == "namespace":
                        # TODO: Implement namespace parsing
                        i += 1
                    else:
                        # Fall back to JavaScript keyword processing
                        super()._build_elements_from_tokens(tokens[i:])
                        return
                else:
                    # Fall back to JavaScript token processing
                    super()._build_elements_from_tokens(tokens[i:])
                    return
    def _parse_interface_direct(self, tokens: List[Token], index: int) -> Tuple[Optional[CodeElement], int]:
        """
        Parse a TypeScript interface declaration into a CodeElement.
        
        Args:
            tokens: List of tokens
            index: Current index in the token list
            
        Returns:
            Tuple of (parsed interface element or None, new index)
        """
        start_index = index
        start_line = tokens[index].line
        
        # Skip 'interface' keyword
        index += 1
        
        # Skip whitespace
        while index < len(tokens) and tokens[index].token_type == TokenType.WHITESPACE:
            index += 1
            
        # Get interface name
        interface_name = ""
        if index < len(tokens) and tokens[index].token_type == TokenType.IDENTIFIER:
            interface_name = tokens[index].value
            index += 1
        else:
            # Interface must have a name
            return None, index
        
        # Skip whitespace
        while index < len(tokens) and tokens[index].token_type == TokenType.WHITESPACE:
            index += 1
            
        # Check for type parameters (generic interfaces)
        type_parameters = []
        if index < len(tokens) and tokens[index].token_type == TokenType.OPERATOR and tokens[index].value == "<":
            # Parse type parameters
            index += 1  # Skip '<'
            angle_depth = 1
            param_name = ""
            
            while index < len(tokens) and angle_depth > 0:
                token = tokens[index]
                
                # Type parameter name
                if token.token_type == TokenType.IDENTIFIER and not param_name:
                    param_name = token.value
                
                # Type parameter separator (comma)
                elif token.token_type == TokenType.COMMA:
                    if param_name:
                        type_parameters.append(param_name)
                        param_name = ""
                
                # Update angle bracket depth
                if token.token_type == TokenType.OPERATOR and token.value == "<":
                    angle_depth += 1
                elif token.token_type == TokenType.OPERATOR and token.value == ">":
                    angle_depth -= 1
                    
                    # If we're at the end of type parameters, add the last one
                    if angle_depth == 0 and param_name:
                        type_parameters.append(param_name)
                
                index += 1
            
            # Skip whitespace after closing angle bracket
            while index < len(tokens) and tokens[index].token_type == TokenType.WHITESPACE:
                index += 1
        
        # Check for extends clause
        extends = []
        if index < len(tokens) and tokens[index].token_type == TokenType.KEYWORD and tokens[index].value == "extends":
            index += 1  # Skip 'extends' keyword
            
            # Parse extended interfaces (comma-separated list)
            while index < len(tokens) and tokens[index].token_type != TokenType.OPEN_BRACE:
                if tokens[index].token_type == TokenType.IDENTIFIER:
                    extends.append(tokens[index].value)
                    
                    # Skip to comma or opening brace
                    index += 1
                    while index < len(tokens) and tokens[index].token_type != TokenType.COMMA and tokens[index].token_type != TokenType.OPEN_BRACE:
                        index += 1
                        
                    # Check if we found a comma
                    if index < len(tokens) and tokens[index].token_type == TokenType.COMMA:
                        index += 1  # Skip comma
                        # Skip whitespace
                        while index < len(tokens) and tokens[index].token_type == TokenType.WHITESPACE:
                            index += 1
                else:
                    index += 1
        
        # Skip to opening brace
        while index < len(tokens) and tokens[index].token_type != TokenType.OPEN_BRACE:
            index += 1
            
        if index >= len(tokens):
            return None, index  # Not a valid interface definition
            
        # Found opening brace, now match closing brace
        index += 1
        brace_depth = 1
        end_line = start_line
        
        # Parse interface body (find matching closing brace)
        while index < len(tokens) and brace_depth > 0:
            if tokens[index].token_type == TokenType.OPEN_BRACE:
                brace_depth += 1
            elif tokens[index].token_type == TokenType.CLOSE_BRACE:
                brace_depth -= 1
                
            if tokens[index].line > end_line:
                end_line = tokens[index].line
                
            index += 1
        
        # Create the CodeElement for the interface
        # Extract the actual code
        code_fragment = ''
        for i in range(start_index, index):
            if i < len(tokens):
                code_fragment += tokens[i].value
        
        interface_element = CodeElement(
            name=interface_name,
            element_type=ElementType.INTERFACE,
            start_line=start_line,
            end_line=end_line,
            code=code_fragment
        )
        
        # Add type parameters if available
        if type_parameters:
            interface_element.type_parameters = type_parameters
            
        # Add extends information if available
        if extends:
            interface_element.extends = extends
        
        return interface_element, index
        
    def _parse_type_alias_direct(self, tokens: List[Token], index: int) -> Tuple[Optional[CodeElement], int]:
        """
        Parse a TypeScript type alias into a CodeElement.
        
        Args:
            tokens: List of tokens
            index: Current index in the token list
            
        Returns:
            Tuple of (parsed type alias element or None, new index)
        """
        start_index = index
        start_line = tokens[index].line
        
        # Skip 'type' keyword
        index += 1
        
        # Skip whitespace
        while index < len(tokens) and tokens[index].token_type == TokenType.WHITESPACE:
            index += 1
            
        # Get type alias name
        type_name = ""
        if index < len(tokens) and tokens[index].token_type == TokenType.IDENTIFIER:
            type_name = tokens[index].value
            index += 1
        else:
            # Type alias must have a name
            return None, index
        
        # Skip whitespace
        while index < len(tokens) and tokens[index].token_type == TokenType.WHITESPACE:
            index += 1
            
        # Check for type parameters (generic type aliases)
        type_parameters = []
        if index < len(tokens) and tokens[index].token_type == TokenType.OPERATOR and tokens[index].value == "<":
            # Parse type parameters (similar to interface)
            index += 1  # Skip '<'
            angle_depth = 1
            param_name = ""
            
            while index < len(tokens) and angle_depth > 0:
                token = tokens[index]
                
                # Type parameter name
                if token.token_type == TokenType.IDENTIFIER and not param_name:
                    param_name = token.value
                
                # Type parameter separator (comma)
                elif token.token_type == TokenType.COMMA:
                    if param_name:
                        type_parameters.append(param_name)
                        param_name = ""
                
                # Update angle bracket depth
                if token.token_type == TokenType.OPERATOR and token.value == "<":
                    angle_depth += 1
                elif token.token_type == TokenType.OPERATOR and token.value == ">":
                    angle_depth -= 1
                    
                    # If we're at the end of type parameters, add the last one
                    if angle_depth == 0 and param_name:
                        type_parameters.append(param_name)
                
                index += 1
            
            # Skip whitespace after closing angle bracket
            while index < len(tokens) and tokens[index].token_type == TokenType.WHITESPACE:
                index += 1
        
        # Skip to equals sign
        while index < len(tokens) and tokens[index].token_type != TokenType.EQUALS:
            index += 1
            
        if index >= len(tokens):
            return None, index  # Not a valid type alias
            
        # Skip equals sign
        index += 1
        
        # Find the end of the type alias (could be complex with braces, etc.)
        # We'll just look for a semicolon at the top level
        brace_depth = 0
        angle_depth = 0
        paren_depth = 0
        end_line = start_line
        
        while index < len(tokens):
            if tokens[index].token_type == TokenType.OPEN_BRACE:
                brace_depth += 1
            elif tokens[index].token_type == TokenType.CLOSE_BRACE:
                brace_depth -= 1
            elif tokens[index].token_type == TokenType.OPEN_PAREN:
                paren_depth += 1
            elif tokens[index].token_type == TokenType.CLOSE_PAREN:
                paren_depth -= 1
            elif tokens[index].token_type == TokenType.OPERATOR and tokens[index].value == "<":
                angle_depth += 1
            elif tokens[index].token_type == TokenType.OPERATOR and tokens[index].value == ">":
                angle_depth -= 1
            elif tokens[index].token_type == TokenType.SEMICOLON and brace_depth == 0 and angle_depth == 0 and paren_depth == 0:
                # End of type alias
                break
                
            if tokens[index].line > end_line:
                end_line = tokens[index].line
                
            index += 1
        
        # Skip past the semicolon if found
        if index < len(tokens) and tokens[index].token_type == TokenType.SEMICOLON:
            index += 1
        
        # Create the CodeElement for the type alias
        # Extract the actual code
        code_fragment = ''
        for i in range(start_index, index):
            if i < len(tokens):
                code_fragment += tokens[i].value
        
        type_alias = CodeElement(
            name=type_name,
            element_type=ElementType.TYPE_DEFINITION,
            start_line=start_line,
            end_line=end_line,
            code=code_fragment
        )
        
        # Add type parameters if available
        if type_parameters:
            type_alias.type_parameters = type_parameters
        
        return type_alias, index

    """
    Parser for TypeScript code.

    This parser extends the JavaScript parser to handle TypeScript-specific syntax,
    such as type annotations, interfaces, and other TypeScript features.
    """

    def __init__(self):
        """Initialize the TypeScript parser."""
        super().__init__()

        # Add TypeScript-specific context types
        self.context_types.update(
            {
                "interface": "interface",
                "type": "type",
                "namespace": "namespace",
                "enum": "enum",
                "generic": "generic",
            }
        )

    def _parse_keyword_statement(
        self, tokens: List[Token], index: int
    ) -> Optional[Dict[str, Any]]:
        """
        Parse a statement that starts with a keyword.

        Extends the JavaScript parser to handle TypeScript-specific keywords.

        Args:
            tokens: List of tokens
            index: Current index in the token list

        Returns:
            Dictionary with the parsed node and next index, or None if parsing failed
        """
        if index >= len(tokens):
            return None

        keyword = tokens[index].value

        # Handle TypeScript-specific keywords
        if keyword == "interface":
            return self._parse_interface_declaration(tokens, index)
        elif keyword == "type":
            return self._parse_type_alias(tokens, index)
        elif keyword == "namespace":
            return self._parse_namespace_declaration(tokens, index)
        elif keyword == "enum":
            return self._parse_enum_declaration(tokens, index)

        # Fall back to JavaScript keyword parsing
        return super()._parse_keyword_statement(tokens, index)

    def _parse_interface_declaration(
        self, tokens: List[Token], index: int
    ) -> Optional[Dict[str, Any]]:
        """
        Parse an interface declaration.

        Args:
            tokens: List of tokens
            index: Current index in the token list

        Returns:
            Dictionary with the parsed node and next index, or None if parsing failed
        """
        start_index = index
        index += 1  # Skip 'interface' keyword

        # Skip whitespace
        while index < len(tokens) and tokens[index].token_type == TokenType.WHITESPACE:
            index += 1

        # Get interface name
        if index >= len(tokens) or tokens[index].token_type != TokenType.IDENTIFIER:
            return None

        interface_name = tokens[index].value
        name_index = index
        index += 1

        # Skip whitespace
        while index < len(tokens) and tokens[index].token_type == TokenType.WHITESPACE:
            index += 1

        # Check for extends clause
        extends_interfaces = []
        if (
            index < len(tokens)
            and tokens[index].token_type == TokenType.KEYWORD
            and tokens[index].value == "extends"
        ):
            index += 1

            # Skip whitespace
            while (
                index < len(tokens) and tokens[index].token_type == TokenType.WHITESPACE
            ):
                index += 1

            # Parse extended interfaces
            while (
                index < len(tokens) and tokens[index].token_type != TokenType.OPEN_BRACE
            ):
                if tokens[index].token_type == TokenType.IDENTIFIER:
                    extends_interfaces.append(
                        {
                            "type": "Identifier",
                            "name": tokens[index].value,
                            "start": index,
                            "end": index,
                            "parent": None,
                            "children": [],
                        }
                    )
                    index += 1
                elif tokens[index].token_type == TokenType.COMMA:
                    index += 1
                else:
                    index += 1

                # Skip whitespace
                while (
                    index < len(tokens)
                    and tokens[index].token_type == TokenType.WHITESPACE
                ):
                    index += 1

        # Expect open brace
        if index >= len(tokens) or tokens[index].token_type != TokenType.OPEN_BRACE:
            return None

        # Add interface to symbol table
        self.symbol_table.add_symbol(
            name=interface_name,
            symbol_type="interface",
            position=tokens[name_index].position,
            line=tokens[name_index].line,
            column=tokens[name_index].column,
            metadata={"extends": [ext["name"] for ext in extends_interfaces]},
        )

        # Parse interface body
        body_tokens, next_index = self._parse_brace_block(tokens, index)

        # Create interface node
        interface_node = {
            "type": "InterfaceDeclaration",
            "name": interface_name,
            "extends": extends_interfaces,
            "body": body_tokens,
            "start": start_index,
            "end": next_index - 1,
            "parent": None,
            "children": [],
        }

        # Set parent-child relationships
        for ext in extends_interfaces:
            ext["parent"] = interface_node
            interface_node["children"].append(ext)

        return {"node": interface_node, "next_index": next_index}

    def _parse_type_alias(
        self, tokens: List[Token], index: int
    ) -> Optional[Dict[str, Any]]:
        """
        Parse a type alias declaration.

        Args:
            tokens: List of tokens
            index: Current index in the token list

        Returns:
            Dictionary with the parsed node and next index, or None if parsing failed
        """
        start_index = index
        index += 1  # Skip 'type' keyword

        # Skip whitespace
        while index < len(tokens) and tokens[index].token_type == TokenType.WHITESPACE:
            index += 1

        # Get type name
        if index >= len(tokens) or tokens[index].token_type != TokenType.IDENTIFIER:
            return None

        type_name = tokens[index].value
        name_index = index
        index += 1

        # Skip whitespace
        while index < len(tokens) and tokens[index].token_type == TokenType.WHITESPACE:
            index += 1

        # Expect equals
        if index >= len(tokens) or tokens[index].token_type != TokenType.EQUALS:
            return None

        index += 1

        # Skip whitespace
        while index < len(tokens) and tokens[index].token_type == TokenType.WHITESPACE:
            index += 1

        # Add type alias to symbol table
        self.symbol_table.add_symbol(
            name=type_name,
            symbol_type="type",
            position=tokens[name_index].position,
            line=tokens[name_index].line,
            column=tokens[name_index].column,
            metadata={},
        )

        # Parse to the end of the statement (simplified)
        start_of_type = index
        while index < len(tokens) and tokens[index].token_type != TokenType.SEMICOLON:
            index += 1

        # Skip semicolon
        if index < len(tokens) and tokens[index].token_type == TokenType.SEMICOLON:
            index += 1

        # Create type alias node
        type_alias_node = {
            "type": "TypeAliasDeclaration",
            "name": type_name,
            "value": {
                "type": "TypeValue",
                "tokens": list(
                    range(
                        start_of_type,
                        index - 1
                        if tokens[index - 1].token_type == TokenType.SEMICOLON
                        else index,
                    )
                ),
                "start": start_of_type,
                "end": index - 1,
                "parent": None,
                "children": [],
            },
            "start": start_index,
            "end": index - 1,
            "parent": None,
            "children": [],
        }

        # Set parent-child relationships
        type_alias_node["value"]["parent"] = type_alias_node
        type_alias_node["children"].append(type_alias_node["value"])

        return {"node": type_alias_node, "next_index": index}

    def _parse_namespace_declaration(
        self, tokens: List[Token], index: int
    ) -> Optional[Dict[str, Any]]:
        """
        Parse a namespace declaration.

        Args:
            tokens: List of tokens
            index: Current index in the token list

        Returns:
            Dictionary with the parsed node and next index, or None if parsing failed
        """
        start_index = index
        index += 1  # Skip 'namespace' keyword

        # Skip whitespace
        while index < len(tokens) and tokens[index].token_type == TokenType.WHITESPACE:
            index += 1

        # Get namespace name
        if index >= len(tokens) or tokens[index].token_type != TokenType.IDENTIFIER:
            return None

        namespace_name = tokens[index].value
        name_index = index
        index += 1

        # Skip whitespace
        while index < len(tokens) and tokens[index].token_type == TokenType.WHITESPACE:
            index += 1

        # Expect open brace
        if index >= len(tokens) or tokens[index].token_type != TokenType.OPEN_BRACE:
            return None

        # Add namespace to symbol table
        self.symbol_table.add_symbol(
            name=namespace_name,
            symbol_type="namespace",
            position=tokens[name_index].position,
            line=tokens[name_index].line,
            column=tokens[name_index].column,
            metadata={},
        )

        # Parse namespace body
        body_tokens, next_index = self._parse_brace_block(tokens, index)

        # Create namespace node
        namespace_node = {
            "type": "NamespaceDeclaration",
            "name": namespace_name,
            "body": body_tokens,
            "start": start_index,
            "end": next_index - 1,
            "parent": None,
            "children": [],
        }

        return {"node": namespace_node, "next_index": next_index}

    def _parse_enum_declaration(
        self, tokens: List[Token], index: int
    ) -> Optional[Dict[str, Any]]:
        """
        Parse an enum declaration.

        Args:
            tokens: List of tokens
            index: Current index in the token list

        Returns:
            Dictionary with the parsed node and next index, or None if parsing failed
        """
        start_index = index
        index += 1  # Skip 'enum' keyword

        # Skip whitespace
        while index < len(tokens) and tokens[index].token_type == TokenType.WHITESPACE:
            index += 1

        # Get enum name
        if index >= len(tokens) or tokens[index].token_type != TokenType.IDENTIFIER:
            return None

        enum_name = tokens[index].value
        name_index = index
        index += 1

        # Skip whitespace
        while index < len(tokens) and tokens[index].token_type == TokenType.WHITESPACE:
            index += 1

        # Expect open brace
        if index >= len(tokens) or tokens[index].token_type != TokenType.OPEN_BRACE:
            return None

        # Add enum to symbol table
        self.symbol_table.add_symbol(
            name=enum_name,
            symbol_type="enum",
            position=tokens[name_index].position,
            line=tokens[name_index].line,
            column=tokens[name_index].column,
            metadata={},
        )

        # Parse enum body
        body_tokens, next_index = self._parse_brace_block(tokens, index)

        # Create enum node
        enum_node = {
            "type": "EnumDeclaration",
            "name": enum_name,
            "body": body_tokens,
            "start": start_index,
            "end": next_index - 1,
            "parent": None,
            "children": [],
        }

        return {"node": enum_node, "next_index": next_index}

    def _parse_function_declaration(
        self, tokens: List[Token], index: int
    ) -> Optional[Dict[str, Any]]:
        """
        Parse a function declaration, including TypeScript-specific type annotations.

        Args:
            tokens: List of tokens
            index: Current index in the token list

        Returns:
            Dictionary with the parsed node and next index, or None if parsing failed
        """
        # First parse using the JavaScript parser
        result = super()._parse_function_declaration(tokens, index)
        if not result:
            return None

        # The JavaScript parser has handled the basic function structure
        # Here we would add TypeScript-specific parsing for type annotations,
        # generic type parameters, etc.

        # For simplicity, we'll just return the JavaScript parser's result
        return result

    def _parse_brace_block(
        self, tokens: List[Token], index: int
    ) -> Tuple[List[int], int]:
        """
        Parse a brace-delimited block, similar to what BraceBlockParser does,
        but inline for convenience.

        Args:
            tokens: List of tokens
            index: Index of the opening brace token

        Returns:
            Tuple of (list of token indices in the block, index after the closing brace)
        """
        # Validate the start token
        if index >= len(tokens) or tokens[index].token_type != TokenType.OPEN_BRACE:
            return [], index

        # Parse the block
        index += 1
        brace_count = 1
        block_tokens = []

        while index < len(tokens) and brace_count > 0:
            if tokens[index].token_type == TokenType.OPEN_BRACE:
                brace_count += 1
            elif tokens[index].token_type == TokenType.CLOSE_BRACE:
                brace_count -= 1
                if brace_count == 0:
                    # Don't include the closing brace in the block
                    break

            # Add this token to the block
            block_tokens.append(index)
            index += 1

        # Skip the closing brace if found
        if index < len(tokens) and tokens[index].token_type == TokenType.CLOSE_BRACE:
            index += 1

        return block_tokens, index
