"""
C++ parser for the grammar parser system.

This module provides a parser specific to the C++ programming language,
extending the C parser to handle C++-specific features.
"""

from typing import List, Dict, Optional, Any

from .token import Token, TokenType
from .c_parser import CParser
from .cpp_tokenizer import CppTokenizer
from .generic_brace_block_parser import BraceBlockParser
from .base import CodeElement, ElementType


class CppParser(CParser):
    """
    Parser for C++ code.

    This parser extends the C parser to handle C++-specific syntax, such as
    classes, templates, namespaces, and other C++ features.
    """

    def __init__(self):
        """Initialize the C++ parser."""
        super().__init__()
        self.tokenizer = CppTokenizer()

        # Add C++-specific context types
        self.context_types.update(
            {
                "class": "class",
                "namespace": "namespace",
                "template": "template",
                "template_specialization": "template_specialization",
                "try_catch": "try_catch",
                "exception": "exception",
            }
        )

    def _parse_keyword_statement(
        self, tokens: List[Token], index: int
    ) -> Optional[Dict[str, Any]]:
        """
        Parse a statement that starts with a keyword.

        Extends the C parser to handle C++-specific keywords.

        Args:
            tokens: List of tokens
            index: Current index in the token list

        Returns:
            Dictionary with the parsed node and next index, or None if parsing failed
        """
        if index >= len(tokens):
            return None

        keyword = tokens[index].value

        # Handle C++-specific keywords
        if keyword == "class":
            return self._parse_class_declaration(tokens, index)
        elif keyword == "namespace":
            return self._parse_namespace_declaration(tokens, index)
        elif keyword == "template":
            return self._parse_template_declaration(tokens, index)
        elif keyword == "try":
            return self._parse_try_catch_block(tokens, index)
        elif keyword == "throw":
            return self._parse_throw_statement(tokens, index)
        elif keyword == "public" or keyword == "private" or keyword == "protected":
            return self._parse_access_specifier(tokens, index)

        # Fall back to C keyword parsing
        return super()._parse_keyword_statement(tokens, index)

    def _parse_class_declaration(
        self, tokens: List[Token], index: int
    ) -> Optional[Dict[str, Any]]:
        """
        Parse a class declaration.

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
        base_classes = []
        if index < len(tokens) and tokens[index].token_type == TokenType.COLON:
            index += 1

            # Skip whitespace
            while (
                index < len(tokens) and tokens[index].token_type == TokenType.WHITESPACE
            ):
                index += 1

            # Parse inheritance list (simplified)
            while (
                index < len(tokens) and tokens[index].token_type != TokenType.OPEN_BRACE
            ):
                if tokens[index].token_type == TokenType.IDENTIFIER:
                    # Check for access specifier
                    access_specifier = "default"
                    if tokens[index].value in ["public", "private", "protected"]:
                        access_specifier = tokens[index].value
                        index += 1

                        # Skip whitespace
                        while (
                            index < len(tokens)
                            and tokens[index].token_type == TokenType.WHITESPACE
                        ):
                            index += 1

                    # Get base class name
                    if (
                        index < len(tokens)
                        and tokens[index].token_type == TokenType.IDENTIFIER
                    ):
                        base_name = tokens[index].value
                        base_classes.append(
                            {
                                "type": "BaseClass",
                                "name": base_name,
                                "access": access_specifier,
                                "start": index,
                                "end": index,
                                "parent": None,
                                "children": [],
                            }
                        )
                        index += 1
                else:
                    # Skip other tokens
                    index += 1

                # Skip whitespace and commas
                while index < len(tokens) and tokens[index].token_type in [
                    TokenType.WHITESPACE,
                    TokenType.COMMA,
                ]:
                    index += 1

        # Check for body (open brace)
        has_body = False
        body_tokens = []
        if index < len(tokens) and tokens[index].token_type == TokenType.OPEN_BRACE:
            has_body = True

            # Context metadata
            context_metadata = {"name": class_name}

            # Add class to symbol table
            self.symbol_table.add_symbol(
                name=class_name,
                symbol_type="class",
                position=tokens[name_index].position,
                line=tokens[name_index].line,
                column=tokens[name_index].column,
                metadata={"base_classes": [b["name"] for b in base_classes]},
            )

            # Parse class body
            body_indices, next_index = BraceBlockParser.parse_block(
                tokens, index, self.state, self.context_types["class"], context_metadata
            )

            body_tokens = body_indices
            index = next_index

        # Skip semicolon if present
        if index < len(tokens) and tokens[index].token_type == TokenType.SEMICOLON:
            index += 1

        # Create class node
        class_node = {
            "type": "ClassDeclaration",
            "name": class_name,
            "base_classes": base_classes,
            "has_body": has_body,
            "body": body_tokens,
            "start": start_index,
            "end": index - 1,
            "parent": None,
            "children": [],
        }

        # Set parent-child relationships
        for base in base_classes:
            base["parent"] = class_node
            class_node["children"].append(base)

        return {"node": class_node, "next_index": index}

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

        # Get namespace name (optional)
        name = None
        name_index = None
        if index < len(tokens) and tokens[index].token_type == TokenType.IDENTIFIER:
            name = tokens[index].value
            name_index = index
            index += 1

            # Skip whitespace
            while (
                index < len(tokens) and tokens[index].token_type == TokenType.WHITESPACE
            ):
                index += 1

        # Check for body (open brace)
        has_body = False
        body_tokens = []
        if index < len(tokens) and tokens[index].token_type == TokenType.OPEN_BRACE:
            has_body = True

            # Context metadata
            context_metadata = (
                {"name": name} if name else {"name": "anonymous_namespace"}
            )

            # Add namespace to symbol table if it has a name
            if name and name_index is not None:
                self.symbol_table.add_symbol(
                    name=name,
                    symbol_type="namespace",
                    position=tokens[name_index].position,
                    line=tokens[name_index].line,
                    column=tokens[name_index].column,
                    metadata={},
                )

            # Parse namespace body
            body_indices, next_index = BraceBlockParser.parse_block(
                tokens,
                index,
                self.state,
                self.context_types["namespace"],
                context_metadata,
            )

            body_tokens = body_indices
            index = next_index

        # Create namespace node
        namespace_node = {
            "type": "NamespaceDeclaration",
            "name": name,
            "has_body": has_body,
            "body": body_tokens,
            "start": start_index,
            "end": index - 1,
            "parent": None,
            "children": [],
        }

        return {"node": namespace_node, "next_index": index}

    def _parse_template_declaration(
        self, tokens: List[Token], index: int
    ) -> Optional[Dict[str, Any]]:
        """
        Parse a template declaration.

        Args:
            tokens: List of tokens
            index: Current index in the token list

        Returns:
            Dictionary with the parsed node and next index, or None if parsing failed
        """
        start_index = index
        index += 1  # Skip 'template' keyword

        # Skip whitespace
        while index < len(tokens) and tokens[index].token_type == TokenType.WHITESPACE:
            index += 1

        # Check for template parameters (less than)
        if (
            index >= len(tokens)
            or tokens[index].token_type != TokenType.OPERATOR
            or tokens[index].value != "<"
        ):
            return None

        index += 1

        # Parse template parameters (simplified)
        template_parameters = []
        while index < len(tokens) and (
            tokens[index].token_type != TokenType.OPERATOR or tokens[index].value != ">"
        ):
            # This is a very simplified template parameter parsing
            if tokens[index].token_type == TokenType.IDENTIFIER:
                template_parameters.append(
                    {
                        "type": "TemplateParameter",
                        "value": tokens[index].value,
                        "start": index,
                        "end": index,
                        "parent": None,
                        "children": [],
                    }
                )

            index += 1

        # Skip greater than
        if (
            index < len(tokens)
            and tokens[index].token_type == TokenType.OPERATOR
            and tokens[index].value == ">"
        ):
            index += 1
        else:
            return None  # Malformed template declaration

        # Skip whitespace
        while index < len(tokens) and tokens[index].token_type == TokenType.WHITESPACE:
            index += 1

        # Parse the templated declaration
        templated_decl = None
        if index < len(tokens):
            if tokens[index].token_type == TokenType.KEYWORD:
                if tokens[index].value == "class" or tokens[index].value == "struct":
                    templated_decl = self._parse_class_declaration(tokens, index)
                elif tokens[index].value == "typename":
                    templated_decl = self._parse_typename_declaration(tokens, index)

            if not templated_decl:
                # Parse as a function or other declaration
                templated_decl = self._parse_declaration_or_definition(tokens, index)

        if not templated_decl:
            return None

        # Create template node
        template_node = {
            "type": "TemplateDeclaration",
            "parameters": template_parameters,
            "declaration": templated_decl["node"],
            "start": start_index,
            "end": templated_decl["next_index"] - 1,
            "parent": None,
            "children": [],
        }

        # Set parent-child relationships
        for param in template_parameters:
            param["parent"] = template_node
            template_node["children"].append(param)

        templated_decl["node"]["parent"] = template_node
        template_node["children"].append(templated_decl["node"])

        return {"node": template_node, "next_index": templated_decl["next_index"]}

    def _parse_typename_declaration(
        self, tokens: List[Token], index: int
    ) -> Optional[Dict[str, Any]]:
        """
        Parse a typename declaration.

        Args:
            tokens: List of tokens
            index: Current index in the token list

        Returns:
            Dictionary with the parsed node and next index, or None if parsing failed
        """
        # Simplified implementation
        start_index = index
        index += 1  # Skip 'typename' keyword

        # Parse to the end of the statement
        declaration_tokens = []
        while index < len(tokens) and tokens[index].token_type != TokenType.SEMICOLON:
            declaration_tokens.append(index)
            index += 1

        # Skip semicolon
        if index < len(tokens) and tokens[index].token_type == TokenType.SEMICOLON:
            index += 1

        # Create typename node
        typename_node = {
            "type": "TypenameDeclaration",
            "tokens": declaration_tokens,
            "start": start_index,
            "end": index - 1,
            "parent": None,
            "children": [],
        }

        return {"node": typename_node, "next_index": index}

    def _parse_try_catch_block(
        self, tokens: List[Token], index: int
    ) -> Optional[Dict[str, Any]]:
        """
        Parse a try-catch block.

        Args:
            tokens: List of tokens
            index: Current index in the token list

        Returns:
            Dictionary with the parsed node and next index, or None if parsing failed
        """
        start_index = index
        index += 1  # Skip 'try' keyword

        # Skip whitespace
        while index < len(tokens) and tokens[index].token_type == TokenType.WHITESPACE:
            index += 1

        # Expect open brace for try block
        if index >= len(tokens) or tokens[index].token_type != TokenType.OPEN_BRACE:
            return None

        # Parse try block
        try_block, next_index = BraceBlockParser.parse_block(
            tokens,
            index,
            self.state,
            self.context_types["try_catch"],
            {"name": "try_block"},
        )

        index = next_index

        # Skip whitespace
        while index < len(tokens) and tokens[index].token_type == TokenType.WHITESPACE:
            index += 1

        # Parse catch clauses
        catch_clauses = []
        while (
            index < len(tokens)
            and tokens[index].token_type == TokenType.KEYWORD
            and tokens[index].value == "catch"
        ):
            catch_start = index
            index += 1

            # Skip whitespace
            while (
                index < len(tokens) and tokens[index].token_type == TokenType.WHITESPACE
            ):
                index += 1

            # Expect open parenthesis
            if index >= len(tokens) or tokens[index].token_type != TokenType.OPEN_PAREN:
                break

            # Parse catch parameter (simplified)
            index += 1
            catch_parameter = []
            while (
                index < len(tokens)
                and tokens[index].token_type != TokenType.CLOSE_PAREN
            ):
                catch_parameter.append(index)
                index += 1

            # Skip close parenthesis
            if (
                index < len(tokens)
                and tokens[index].token_type == TokenType.CLOSE_PAREN
            ):
                index += 1
            else:
                break

            # Skip whitespace
            while (
                index < len(tokens) and tokens[index].token_type == TokenType.WHITESPACE
            ):
                index += 1

            # Expect open brace for catch block
            if index >= len(tokens) or tokens[index].token_type != TokenType.OPEN_BRACE:
                break

            # Parse catch block
            catch_block, next_index = BraceBlockParser.parse_block(
                tokens,
                index,
                self.state,
                self.context_types["exception"],
                {"name": "catch_block"},
            )

            # Add catch clause
            catch_clauses.append(
                {
                    "type": "CatchClause",
                    "parameter": catch_parameter,
                    "body": catch_block,
                    "start": catch_start,
                    "end": next_index - 1,
                    "parent": None,
                    "children": [],
                }
            )

            index = next_index

            # Skip whitespace
            while (
                index < len(tokens) and tokens[index].token_type == TokenType.WHITESPACE
            ):
                index += 1

        # Create try-catch node
        try_catch_node = {
            "type": "TryCatchStatement",
            "try_block": try_block,
            "catch_clauses": catch_clauses,
            "start": start_index,
            "end": index - 1,
            "parent": None,
            "children": [],
        }

        # Set parent-child relationships
        for catch_clause in catch_clauses:
            catch_clause["parent"] = try_catch_node
            try_catch_node["children"].append(catch_clause)

        return {"node": try_catch_node, "next_index": index}

    def _parse_throw_statement(
        self, tokens: List[Token], index: int
    ) -> Optional[Dict[str, Any]]:
        """
        Parse a throw statement.

        Args:
            tokens: List of tokens
            index: Current index in the token list

        Returns:
            Dictionary with the parsed node and next index, or None if parsing failed
        """
        start_index = index
        index += 1  # Skip 'throw' keyword

        # Parse to the end of the statement
        throw_expression = []
        while index < len(tokens) and tokens[index].token_type != TokenType.SEMICOLON:
            throw_expression.append(index)
            index += 1

        # Skip semicolon
        if index < len(tokens) and tokens[index].token_type == TokenType.SEMICOLON:
            index += 1

        # Create throw node
        throw_node = {
            "type": "ThrowStatement",
            "expression": throw_expression,
            "start": start_index,
            "end": index - 1,
            "parent": None,
            "children": [],
        }

        return {"node": throw_node, "next_index": index}

    def _parse_access_specifier(
        self, tokens: List[Token], index: int
    ) -> Optional[Dict[str, Any]]:
        """
        Parse an access specifier (public, private, protected).

        Args:
            tokens: List of tokens
            index: Current index in the token list

        Returns:
            Dictionary with the parsed node and next index, or None if parsing failed
        """
        start_index = index
        access_specifier = tokens[index].value
        index += 1

        # Skip whitespace
        while index < len(tokens) and tokens[index].token_type == TokenType.WHITESPACE:
            index += 1

        # Expect colon
        if index < len(tokens) and tokens[index].token_type == TokenType.COLON:
            index += 1
        else:
            return None

        # Create access specifier node
        access_node = {
            "type": "AccessSpecifier",
            "access": access_specifier,
            "start": start_index,
            "end": index - 1,
            "parent": None,
            "children": [],
        }

        return {"node": access_node, "next_index": index}

    def _convert_node_to_element(
        self, node: Dict[str, Any], line_map: Dict[int, int]
    ) -> Optional[CodeElement]:
        """
        Convert an AST node to a CodeElement, with support for C++ specific nodes.

        Args:
            node: The AST node to convert
            line_map: Mapping from token indices to line numbers

        Returns:
            A CodeElement or None if the node cannot be converted
        """
        # First, try the C parser's converter
        element = super()._convert_node_to_element(node, line_map)
        if element:
            return element

        # Handle C++-specific nodes
        element_type = None
        name = ""
        start_line = 1
        end_line = 1
        parameters = []

        # Get name and type based on node type
        if "type" in node:
            if node["type"] == "ClassDeclaration":
                element_type = ElementType.CLASS
                if "name" in node:
                    name = node["name"]
            elif node["type"] == "NamespaceDeclaration":
                element_type = ElementType.NAMESPACE
                if "name" in node:
                    name = node["name"]
                elif "name" == None:
                    name = "anonymous_namespace"
            elif node["type"] == "TemplateDeclaration":
                # For template declarations, we want to extract the actual templated entity
                if "declaration" in node and isinstance(node["declaration"], dict):
                    # Call recursively on the inner declaration
                    return self._convert_node_to_element(node["declaration"], line_map)
                else:
                    element_type = ElementType.TEMPLATE
                    name = "template"

        # Get start and end lines
        if "start" in node and node["start"] in line_map:
            start_line = line_map[node["start"]]
        if "end" in node and node["end"] in line_map:
            end_line = line_map[node["end"]]

        # Skip if we couldn't determine the element type
        if not element_type:
            return None

        # Create the element
        element = CodeElement(
            name=name,
            element_type=element_type,
            start_line=start_line,
            end_line=end_line,
        )

        # Set parameters if available
        if "parameters" in node and node["parameters"]:
            element.parameters = node["parameters"]

        # Add children
        if "children" in node:
            for child_node in node["children"]:
                child_element = self._convert_node_to_element(child_node, line_map)
                if child_element:
                    child_element.parent = element
                    element.children.append(child_element)

        return element
