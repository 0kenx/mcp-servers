"""
TypeScript parser for the grammar parser system.

This module provides a parser specific to the TypeScript programming language,
extending the JavaScript parser to handle TypeScript-specific features.
"""

from typing import List, Dict, Optional, Any, Tuple

from .token import Token, TokenType
from .javascript_parser import JavaScriptParser


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
