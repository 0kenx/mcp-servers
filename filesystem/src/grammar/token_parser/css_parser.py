"""
CSS parser for the grammar parser system.

This module provides a parser specific to CSS, handling selectors, properties,
at-rules, media queries, and CSS structure.
"""

from typing import List, Dict, Optional, Any

from .token import Token, TokenType
from .token_parser import TokenParser
from .parser_state import ParserState
from .symbol_table import SymbolTable
from .css_tokenizer import CSSTokenizer
from .generic_brace_block_parser import BraceBlockParser


class CSSParser(TokenParser):
    """
    Parser for CSS code.

    This parser processes CSS syntax, handling rules, properties, values,
    and at-rules like media queries.
    """

    def __init__(self):
        """Initialize the CSS parser."""
        super().__init__()
        self.tokenizer = CSSTokenizer()
        self.state = ParserState()
        self.symbol_table = SymbolTable()

        # Context types specific to CSS
        self.context_types = {
            "rule": "rule",
            "at_rule": "at_rule",
            "media_query": "media_query",
            "keyframes": "keyframes",
            "import": "import",
            "font_face": "font_face",
        }

    def parse(self, code: str) -> Dict[str, Any]:
        """
        Parse CSS code and build an abstract syntax tree.

        Args:
            code: CSS source code

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
            "type": "Stylesheet",
            "rules": [],
            "tokens": tokens,
            "start": 0,
            "end": len(tokens) - 1 if tokens else 0,
            "parent": None,
            "children": [],
        }

        i = 0
        while i < len(tokens):
            # Skip whitespace and comments
            if tokens[i].token_type in [TokenType.WHITESPACE, TokenType.COMMENT]:
                i += 1
                continue

            # Handle at-rules
            if tokens[i].token_type == TokenType.AT_RULE:
                at_rule = self._parse_at_rule(tokens, i)
                if at_rule:
                    ast["rules"].append(at_rule["node"])
                    ast["children"].append(at_rule["node"])
                    i = at_rule["next_index"]
                else:
                    i += 1

            # Handle style rules
            elif tokens[i].token_type == TokenType.SELECTOR:
                style_rule = self._parse_style_rule(tokens, i)
                if style_rule:
                    ast["rules"].append(style_rule["node"])
                    ast["children"].append(style_rule["node"])
                    i = style_rule["next_index"]
                else:
                    i += 1

            else:
                i += 1

        # Fix parent-child relationships
        for child in ast["children"]:
            child["parent"] = ast

        return ast

    def _parse_at_rule(
        self, tokens: List[Token], index: int
    ) -> Optional[Dict[str, Any]]:
        """
        Parse an at-rule (e.g., @media, @import, @keyframes).

        Args:
            tokens: List of tokens
            index: Current token index

        Returns:
            Dictionary with parsed node and next index, or None if parsing failed
        """
        if index >= len(tokens) or tokens[index].token_type != TokenType.AT_RULE:
            return None

        start_index = index
        at_rule_name = tokens[index].value[1:]  # Remove '@'
        index += 1

        # Skip whitespace
        while index < len(tokens) and tokens[index].token_type == TokenType.WHITESPACE:
            index += 1

        # Parse parameters until '{' or ';'
        parameters = []
        while index < len(tokens) and tokens[index].token_type not in [
            TokenType.OPEN_BRACE,
            TokenType.SEMICOLON,
        ]:
            if tokens[index].token_type != TokenType.WHITESPACE:
                parameters.append(tokens[index].value)
            index += 1

        # Add at-rule to symbol table
        self.symbol_table.add_symbol(
            name=at_rule_name,
            symbol_type="at_rule",
            position=tokens[start_index].position,
            line=tokens[start_index].line,
            column=tokens[start_index].column,
            metadata={"parameters": " ".join(parameters)},
        )

        # Check if this at-rule has a block
        has_block = (
            index < len(tokens) and tokens[index].token_type == TokenType.OPEN_BRACE
        )

        block_content = []
        if has_block:
            # Enter appropriate context based on at-rule type
            context_type = self.context_types.get(
                at_rule_name.lower(), self.context_types["at_rule"]
            )
            context_metadata = {"name": at_rule_name}

            # Parse the block
            block_indices, next_index = BraceBlockParser.parse_block(
                tokens, index, self.state, context_type, context_metadata
            )

            # For @media and similar rules, parse the nested rules in the block
            if at_rule_name.lower() in ["media", "supports", "document"]:
                nested_ast = self._parse_nested_rules(tokens, block_indices)
                block_content = nested_ast["rules"] if "rules" in nested_ast else []
            else:
                # For other at-rules like @keyframes, preserve token indices
                block_content = block_indices

            index = next_index
        else:
            # Simple at-rule like @import
            if index < len(tokens) and tokens[index].token_type == TokenType.SEMICOLON:
                index += 1

        # Create at-rule node
        at_rule_node = {
            "type": "AtRule",
            "name": at_rule_name,
            "parameters": " ".join(parameters),
            "hasBlock": has_block,
            "block": block_content,
            "start": start_index,
            "end": index - 1,
            "parent": None,
            "children": [],
        }

        return {"node": at_rule_node, "next_index": index}

    def _parse_style_rule(
        self, tokens: List[Token], index: int
    ) -> Optional[Dict[str, Any]]:
        """
        Parse a style rule (selector and declaration block).

        Args:
            tokens: List of tokens
            index: Current token index

        Returns:
            Dictionary with parsed node and next index, or None if parsing failed
        """
        if index >= len(tokens) or tokens[index].token_type != TokenType.SELECTOR:
            return None

        start_index = index
        selectors = []
        current_selector = tokens[index].value
        index += 1

        # Collect all parts of the selector (handling multiple comma-separated selectors)
        while index < len(tokens) and tokens[index].token_type != TokenType.OPEN_BRACE:
            if tokens[index].token_type == TokenType.COMMA:
                selectors.append(current_selector.strip())
                current_selector = ""
            elif tokens[index].token_type != TokenType.WHITESPACE:
                current_selector += tokens[index].value
            else:
                current_selector += " "
            index += 1

        if current_selector.strip():
            selectors.append(current_selector.strip())

        # Add selectors to symbol table
        for selector in selectors:
            self.symbol_table.add_symbol(
                name=selector,
                symbol_type="selector",
                position=tokens[start_index].position,
                line=tokens[start_index].line,
                column=tokens[start_index].column,
                metadata={},
            )

        # Check for open brace
        if index >= len(tokens) or tokens[index].token_type != TokenType.OPEN_BRACE:
            return None

        # Parse declaration block
        context_metadata = {"selectors": selectors}
        block_indices, next_index = BraceBlockParser.parse_block(
            tokens, index, self.state, self.context_types["rule"], context_metadata
        )

        # Parse declarations within the block
        declarations = self._parse_declarations(tokens, block_indices)

        index = next_index

        # Create style rule node
        style_rule_node = {
            "type": "StyleRule",
            "selectors": selectors,
            "declarations": declarations,
            "start": start_index,
            "end": index - 1,
            "parent": None,
            "children": [],
        }

        return {"node": style_rule_node, "next_index": index}

    def _parse_declarations(
        self, tokens: List[Token], indices: List[int]
    ) -> List[Dict[str, Any]]:
        """
        Parse CSS declarations (property-value pairs).

        Args:
            tokens: List of tokens
            indices: Indices of tokens in the declaration block

        Returns:
            List of declaration nodes
        """
        declarations = []

        i = 0
        while i < len(indices):
            idx = indices[i]

            # Skip whitespace and comments
            if tokens[idx].token_type in [TokenType.WHITESPACE, TokenType.COMMENT]:
                i += 1
                continue

            # Look for property
            if (
                tokens[idx].token_type == TokenType.PROPERTY
                or tokens[idx].token_type == TokenType.IDENTIFIER
            ):
                property_name = tokens[idx].value
                property_index = i
                i += 1

                # Skip to colon
                while (
                    i < len(indices)
                    and tokens[indices[i]].token_type != TokenType.COLON
                ):
                    i += 1

                if i >= len(indices):
                    break

                # Skip colon
                i += 1

                # Skip whitespace
                while (
                    i < len(indices)
                    and tokens[indices[i]].token_type == TokenType.WHITESPACE
                ):
                    i += 1

                # Get value
                value = ""
                if (
                    i < len(indices)
                    and tokens[indices[i]].token_type == TokenType.VALUE
                ):
                    value = tokens[indices[i]].value
                    i += 1

                # Skip to semicolon or end of block
                while (
                    i < len(indices)
                    and tokens[indices[i]].token_type != TokenType.SEMICOLON
                ):
                    i += 1

                # Skip semicolon
                if (
                    i < len(indices)
                    and tokens[indices[i]].token_type == TokenType.SEMICOLON
                ):
                    i += 1

                # Add property to symbol table
                self.symbol_table.add_symbol(
                    name=property_name,
                    symbol_type="property",
                    position=tokens[idx].position,
                    line=tokens[idx].line,
                    column=tokens[idx].column,
                    metadata={"value": value},
                )

                # Create declaration node
                declaration_node = {
                    "type": "Declaration",
                    "property": property_name,
                    "value": value,
                    "start": property_index,
                    "end": i - 1,
                    "parent": None,
                    "children": [],
                }

                declarations.append(declaration_node)
            else:
                i += 1

        return declarations

    def _parse_nested_rules(
        self, tokens: List[Token], indices: List[int]
    ) -> Dict[str, Any]:
        """
        Parse nested rules inside a block (e.g., inside @media).

        Args:
            tokens: List of tokens
            indices: Indices of tokens in the block

        Returns:
            AST for the nested rules
        """
        # Create a sub-parser to parse the block content
        sub_tokens = [tokens[idx] for idx in indices]

        # Create a mini-AST for the nested content
        mini_ast = {"type": "Stylesheet", "rules": [], "parent": None, "children": []}

        i = 0
        while i < len(sub_tokens):
            # Skip whitespace and comments
            if sub_tokens[i].token_type in [TokenType.WHITESPACE, TokenType.COMMENT]:
                i += 1
                continue

            # Handle nested at-rules
            if sub_tokens[i].token_type == TokenType.AT_RULE:
                # Find corresponding indices in original token list
                original_index = indices[i]
                at_rule = self._parse_at_rule(tokens, original_index)
                if at_rule:
                    mini_ast["rules"].append(at_rule["node"])
                    mini_ast["children"].append(at_rule["node"])

                    # Skip ahead in sub_tokens based on the next_index in original tokens
                    next_original_index = at_rule["next_index"]
                    while i < len(indices) and indices[i] < next_original_index:
                        i += 1
                else:
                    i += 1

            # Handle nested style rules
            elif sub_tokens[i].token_type == TokenType.SELECTOR:
                original_index = indices[i]
                style_rule = self._parse_style_rule(tokens, original_index)
                if style_rule:
                    mini_ast["rules"].append(style_rule["node"])
                    mini_ast["children"].append(style_rule["node"])

                    # Skip ahead in sub_tokens based on the next_index in original tokens
                    next_original_index = style_rule["next_index"]
                    while i < len(indices) and indices[i] < next_original_index:
                        i += 1
                else:
                    i += 1

            else:
                i += 1

        # Fix parent-child relationships
        for child in mini_ast["children"]:
            child["parent"] = mini_ast

        return mini_ast
