"""
Rust parser for the grammar parser system.

This module provides a parser specific to the Rust programming language,
building on the base token parser framework.
"""

from typing import List, Dict, Optional, Any

from .token import Token, TokenType
from .token_parser import TokenParser
from .parser_state import ParserState
from .symbol_table import SymbolTable
from .rust_tokenizer import RustTokenizer
from .generic_brace_block_parser import BraceBlockParser
from .base import CodeElement, ElementType


class RustParser(TokenParser):
    """
    Parser for Rust code.

    This parser processes Rust-specific syntax, handling constructs like structs,
    enums, traits, modules, and more.
    """

    def __init__(self):
        """Initialize the Rust parser."""
        super().__init__()
        self.tokenizer = RustTokenizer()
        self.state = ParserState()
        self.symbol_table = SymbolTable()

        # Context types specific to Rust
        self.context_types = {
            "function": "function",
            "struct": "struct",
            "enum": "enum",
            "trait": "trait",
            "impl": "impl",
            "module": "module",
            "match": "match",
            "loop": "loop",
            "if": "if",
            "else": "else",
            "macro": "macro",
            "attribute": "attribute",
        }

        # Track blocks
        self.brace_stack = []
        self.paren_stack = []

    def parse(self, code: str) -> List[CodeElement]:
        """
        Parse Rust code and return a list of code elements.

        Args:
            code: Rust source code

        Returns:
            List of code elements
        """
        # Reset state for a new parse
        self.elements = []
        self.state = ParserState()
        self.symbol_table = SymbolTable()
        self.brace_stack = []
        self.paren_stack = []

        # Tokenize the code
        tokens = self.tokenize(code)

        # Process the tokens and build elements directly
        self._build_elements_from_tokens(tokens)

        # Validate and repair AST
        self.validate_and_repair_ast()

        return self.elements

    def _build_elements_from_tokens(self, tokens: List[Token]) -> None:
        """
        Build CodeElement objects directly from tokens.

        This method processes tokens and builds a list of CodeElement objects
        representing functions, structs, traits, etc. found in the code.

        Args:
            tokens: List of tokens from the tokenizer
        """
        i = 0
        line_map = {}
        current_line = 1

        # First pass: build a mapping of token indices to line numbers
        for i, token in enumerate(tokens):
            if token.token_type == TokenType.NEWLINE:
                current_line += 1
            line_map[i] = current_line

        i = 0
        while i < len(tokens):
            # Skip whitespace and newlines
            if tokens[i].token_type in [TokenType.WHITESPACE, TokenType.NEWLINE]:
                i += 1
                continue

            # Handle attributes
            if tokens[i].token_type == TokenType.ATTRIBUTE:
                attr = self._parse_attribute(tokens, i)
                if attr:
                    i = attr["next_index"]
                    continue

            # Check for function or struct definitions
            if tokens[i].token_type == TokenType.KEYWORD:
                stmt = self._parse_keyword_statement(tokens, i)
                if stmt:
                    node = stmt["node"]
                    # Create CodeElement from AST node
                    element = self._convert_node_to_element(node, line_map)
                    if element:
                        self.elements.append(element)
                    i = stmt["next_index"]
                    continue

            # Check for declarations or definitions starting with identifiers
            if tokens[i].token_type == TokenType.IDENTIFIER:
                stmt = self._parse_declaration_or_definition(tokens, i)
                if stmt:
                    node = stmt["node"]
                    # Create CodeElement from AST node
                    element = self._convert_node_to_element(node, line_map)
                    if element:
                        self.elements.append(element)
                    i = stmt["next_index"]
                    continue

            # Move to next token if no pattern matched
            i += 1

    def _convert_node_to_element(
        self, node: Dict[str, Any], line_map: Dict[int, int]
    ) -> Optional[CodeElement]:
        """
        Convert an AST node to a CodeElement.

        Args:
            node: The AST node to convert
            line_map: Mapping from token indices to line numbers

        Returns:
            A CodeElement or None if the node cannot be converted
        """
        element_type = None
        name = ""
        start_line = 1
        end_line = 1
        parameters = []

        # Get name and type based on node type
        if "type" in node:
            if node["type"] == "FunctionDefinition":
                element_type = ElementType.FUNCTION
                if "name" in node:
                    name = node["name"]
                # Extract parameters if available
                if "parameters" in node:
                    parameters = node["parameters"]
            elif node["type"] == "StructDefinition":
                element_type = ElementType.STRUCT
                if "name" in node:
                    name = node["name"]
            elif node["type"] == "EnumDefinition":
                element_type = ElementType.ENUM
                if "name" in node:
                    name = node["name"]
            elif node["type"] == "TraitDefinition":
                element_type = ElementType.TRAIT
                if "name" in node:
                    name = node["name"]
            elif node["type"] == "ImplBlock":
                element_type = ElementType.IMPL
                if "name" in node:
                    name = node["name"]
            elif node["type"] == "ModuleDefinition":
                element_type = ElementType.MODULE
                if "name" in node:
                    name = node["name"]

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
        if parameters:
            element.parameters = parameters

        # Add Rust-specific attributes
        if "is_pub" in node and node["is_pub"]:
            element.is_pub = True
        if "is_unsafe" in node and node["is_unsafe"]:
            element.is_unsafe = True
        if "return_type" in node and node["return_type"]:
            element.return_type = node["return_type"]

        # Add children
        if "children" in node:
            for child_node in node["children"]:
                child_element = self._convert_node_to_element(child_node, line_map)
                if child_element:
                    child_element.parent = element
                    element.children.append(child_element)

        return element

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
            "children": [],
        }

        i = 0
        while i < len(tokens):
            # Skip whitespace and newlines for AST building
            if tokens[i].token_type in [TokenType.WHITESPACE, TokenType.NEWLINE]:
                i += 1
                continue

            # Handle attributes
            if tokens[i].token_type == TokenType.ATTRIBUTE:
                attr = self._parse_attribute(tokens, i)
                if attr:
                    ast["body"].append(attr["node"])
                    ast["children"].append(attr["node"])
                    i = attr["next_index"]
                    continue

            # Parse statements based on token type
            if tokens[i].token_type == TokenType.KEYWORD:
                stmt = self._parse_keyword_statement(tokens, i)
                if stmt:
                    ast["body"].append(stmt["node"])
                    ast["children"].append(stmt["node"])
                    i = stmt["next_index"]
                else:
                    i += 1
            elif tokens[i].token_type == TokenType.IDENTIFIER:
                stmt = self._parse_declaration_or_definition(tokens, i)
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

    def _parse_attribute(
        self, tokens: List[Token], index: int
    ) -> Optional[Dict[str, Any]]:
        """
        Parse an attribute declaration.

        Args:
            tokens: List of tokens
            index: Current index in the token list

        Returns:
            Dictionary with the parsed node and next index, or None if parsing failed
        """
        start_index = index
        index += 1  # Skip '#'

        # Skip '[' if present
        if index < len(tokens) and tokens[index].token_type == TokenType.OPEN_BRACKET:
            index += 1

        # Parse the attribute content (simplified)
        attribute_tokens = []
        while (
            index < len(tokens) and tokens[index].token_type != TokenType.CLOSE_BRACKET
        ):
            attribute_tokens.append(index)
            index += 1

        # Skip ']' if present
        if index < len(tokens) and tokens[index].token_type == TokenType.CLOSE_BRACKET:
            index += 1

        # Create attribute node
        attribute_node = {
            "type": "Attribute",
            "tokens": attribute_tokens,
            "start": start_index,
            "end": index - 1,
            "parent": None,
            "children": [],
        }

        return {"node": attribute_node, "next_index": index}

    def _parse_keyword_statement(
        self, tokens: List[Token], index: int
    ) -> Optional[Dict[str, Any]]:
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

        if keyword == "fn":
            return self._parse_function_definition(tokens, index)
        elif keyword == "struct":
            return self._parse_struct_definition(tokens, index)
        elif keyword == "enum":
            return self._parse_enum_definition(tokens, index)
        elif keyword == "trait":
            return self._parse_trait_definition(tokens, index)
        elif keyword == "impl":
            return self._parse_impl_block(tokens, index)
        elif keyword == "mod":
            return self._parse_module_definition(tokens, index)
        elif keyword == "match":
            return self._parse_match_statement(tokens, index)
        elif keyword == "if":
            return self._parse_if_statement(tokens, index)
        elif keyword == "for" or keyword == "while" or keyword == "loop":
            return self._parse_loop_statement(tokens, index)
        elif keyword == "let":
            return self._parse_let_statement(tokens, index)
        elif keyword == "return":
            return self._parse_return_statement(tokens, index)

        # Default simple statement
        return self._parse_expression_statement(tokens, index)

    def _parse_function_definition(
        self, tokens: List[Token], index: int
    ) -> Optional[Dict[str, Any]]:
        """
        Parse a function definition.

        Args:
            tokens: List of tokens
            index: Current index in the token list

        Returns:
            Dictionary with the parsed node and next index, or None if parsing failed
        """
        start_index = index
        index += 1  # Skip 'fn' keyword

        # Skip whitespace
        while index < len(tokens) and tokens[index].token_type == TokenType.WHITESPACE:
            index += 1

        # Get function name
        if index >= len(tokens) or tokens[index].token_type != TokenType.IDENTIFIER:
            return None

        function_name = tokens[index].value
        name_index = index
        index += 1

        # Simplified implementation that just extracts the name and looks for the body
        # Skipping details like parameters, return type, and generics

        # Find opening brace for function body
        while index < len(tokens) and tokens[index].token_type != TokenType.OPEN_BRACE:
            index += 1

        if index >= len(tokens):
            return None

        # Parse function body
        body_indices, next_index = BraceBlockParser.parse_block(
            tokens,
            index,
            self.state,
            self.context_types["function"],
            {"name": function_name},
        )

        # Create function node
        function_node = {
            "type": "FunctionDefinition",
            "name": function_name,
            "body": body_indices,
            "start": start_index,
            "end": next_index - 1,
            "is_pub": False,  # Simplified, would be determined by checking for 'pub' keyword
            "is_unsafe": False,  # Simplified
            "parameters": [],  # Simplified
            "return_type": None,  # Simplified
            "parent": None,
            "children": [],
        }

        # Add function to symbol table
        self.symbol_table.add_symbol(
            name=function_name,
            symbol_type="function",
            position=tokens[name_index].position,
            line=tokens[name_index].line,
            column=tokens[name_index].column,
            metadata={},
        )

        return {"node": function_node, "next_index": next_index}

    def _parse_struct_definition(
        self, tokens: List[Token], index: int
    ) -> Optional[Dict[str, Any]]:
        """
        Parse a struct definition.

        Args:
            tokens: List of tokens
            index: Current index in the token list

        Returns:
            Dictionary with the parsed node and next index, or None if parsing failed
        """
        # Simplified implementation
        start_index = index
        index += 1  # Skip 'struct' keyword

        # Skip whitespace
        while index < len(tokens) and tokens[index].token_type == TokenType.WHITESPACE:
            index += 1

        # Get struct name
        if index >= len(tokens) or tokens[index].token_type != TokenType.IDENTIFIER:
            return None

        struct_name = tokens[index].value
        name_index = index
        index += 1

        # Simplified parsing that skips details like generic parameters

        # Find opening brace for struct body (if any)
        while index < len(tokens) and tokens[index].token_type not in [
            TokenType.OPEN_BRACE,
            TokenType.SEMICOLON,
        ]:
            index += 1

        # Check if this is a unit struct or a struct with fields
        if index < len(tokens) and tokens[index].token_type == TokenType.OPEN_BRACE:
            # Parse struct body
            body_indices, next_index = BraceBlockParser.parse_block(
                tokens,
                index,
                self.state,
                self.context_types["struct"],
                {"name": struct_name},
            )

            # Create struct node
            struct_node = {
                "type": "StructDefinition",
                "name": struct_name,
                "body": body_indices,
                "start": start_index,
                "end": next_index - 1,
                "is_pub": False,  # Simplified
                "fields": [],  # Simplified
                "parent": None,
                "children": [],
            }

            index = next_index
        else:
            # Unit struct or tuple struct without a body
            # Skip semicolon if present
            if index < len(tokens) and tokens[index].token_type == TokenType.SEMICOLON:
                index += 1

            # Create struct node
            struct_node = {
                "type": "StructDefinition",
                "name": struct_name,
                "body": [],
                "start": start_index,
                "end": index - 1,
                "is_pub": False,  # Simplified
                "fields": [],  # Simplified
                "parent": None,
                "children": [],
            }

        # Add struct to symbol table
        self.symbol_table.add_symbol(
            name=struct_name,
            symbol_type="struct",
            position=tokens[name_index].position,
            line=tokens[name_index].line,
            column=tokens[name_index].column,
            metadata={},
        )

        return {"node": struct_node, "next_index": index}

    def _parse_enum_definition(
        self, tokens: List[Token], index: int
    ) -> Optional[Dict[str, Any]]:
        """Placeholder for enum parsing."""
        # Implement similarly to struct parsing
        return None

    def _parse_trait_definition(
        self, tokens: List[Token], index: int
    ) -> Optional[Dict[str, Any]]:
        """Placeholder for trait parsing."""
        return None

    def _parse_impl_block(
        self, tokens: List[Token], index: int
    ) -> Optional[Dict[str, Any]]:
        """Placeholder for impl block parsing."""
        return None

    def _parse_module_definition(
        self, tokens: List[Token], index: int
    ) -> Optional[Dict[str, Any]]:
        """Placeholder for module parsing."""
        return None

    def _parse_match_statement(
        self, tokens: List[Token], index: int
    ) -> Optional[Dict[str, Any]]:
        """Placeholder for match statement parsing."""
        return None

    def _parse_if_statement(
        self, tokens: List[Token], index: int
    ) -> Optional[Dict[str, Any]]:
        """Placeholder for if statement parsing."""
        return None

    def _parse_loop_statement(
        self, tokens: List[Token], index: int
    ) -> Optional[Dict[str, Any]]:
        """Placeholder for loop statement parsing."""
        return None

    def _parse_let_statement(
        self, tokens: List[Token], index: int
    ) -> Optional[Dict[str, Any]]:
        """Placeholder for let statement parsing."""
        return None

    def _parse_return_statement(
        self, tokens: List[Token], index: int
    ) -> Optional[Dict[str, Any]]:
        """Placeholder for return statement parsing."""
        return None

    def _parse_expression_statement(
        self, tokens: List[Token], index: int
    ) -> Optional[Dict[str, Any]]:
        """
        Parse a generic expression statement.

        Args:
            tokens: List of tokens
            index: Current index in the token list

        Returns:
            Dictionary with the parsed node and next index, or None if parsing failed
        """
        # Simplified implementation
        start_index = index

        # Parse to the end of the statement
        statement_tokens = []
        while index < len(tokens) and tokens[index].token_type != TokenType.SEMICOLON:
            statement_tokens.append(index)
            index += 1

        # Skip semicolon
        if index < len(tokens) and tokens[index].token_type == TokenType.SEMICOLON:
            index += 1

        # Create statement node
        statement_node = {
            "type": "ExpressionStatement",
            "tokens": statement_tokens,
            "start": start_index,
            "end": index - 1,
            "parent": None,
            "children": [],
        }

        return {"node": statement_node, "next_index": index}

    def _parse_declaration_or_definition(
        self, tokens: List[Token], index: int
    ) -> Optional[Dict[str, Any]]:
        """
        Parse a declaration or definition starting with an identifier.

        Args:
            tokens: List of tokens
            index: Current index in the token list

        Returns:
            Dictionary with the parsed node and next index, or None if parsing failed
        """
        # Simplified implementation
        start_index = index
        identifier = tokens[index].value
        index += 1

        # Parse to the end of the statement or block
        while index < len(tokens) and tokens[index].token_type not in [
            TokenType.SEMICOLON,
            TokenType.OPEN_BRACE,
        ]:
            index += 1

        # Check for a block or just a statement
        if index < len(tokens) and tokens[index].token_type == TokenType.OPEN_BRACE:
            # Parse block
            body_indices, next_index = BraceBlockParser.parse_block(
                tokens, index, self.state, "block", {}
            )

            # Create declaration node
            declaration_node = {
                "type": "DeclarationWithBlock",
                "name": identifier,
                "body": body_indices,
                "start": start_index,
                "end": next_index - 1,
                "parent": None,
                "children": [],
            }

            index = next_index
        else:
            # Skip semicolon if present
            if index < len(tokens) and tokens[index].token_type == TokenType.SEMICOLON:
                index += 1

            # Create declaration node
            declaration_node = {
                "type": "Declaration",
                "name": identifier,
                "start": start_index,
                "end": index - 1,
                "parent": None,
                "children": [],
            }

        return {"node": declaration_node, "next_index": index}

    def _fix_parent_child_relationships(self, ast: Dict[str, Any]) -> None:
        """
        Fix parent-child relationships in the AST.

        Args:
            ast: The abstract syntax tree to fix
        """
        # This would walk the AST and ensure all nodes have correct parent and children references
        pass
