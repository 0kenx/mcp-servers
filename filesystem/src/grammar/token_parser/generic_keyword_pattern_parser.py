"""
Generic parsers for the grammar parser system.

This module provides generic parsers for common programming language constructs
like brace blocks, indentation blocks, and keyword-based blocks.
"""

from typing import List, Dict, Optional, Any, Tuple
from .token import Token, TokenType
from .token_parser import TokenParser
from .parser_state import ParserState, ContextInfo


class KeywordBlockParser(TokenParser):
    """
    Parser for keyword-delimited blocks.

    This handles blocks that are started by a specific keyword and ended by
    another keyword, common in languages with keywords like if/endif,
    case/end, begin/end, etc.
    """

    @staticmethod
    def parse_block(
        tokens: List[Token],
        start_index: int,
        start_keyword: str,
        end_keyword: str,
        state: ParserState,
        context_type: Optional[str] = None,
        context_metadata: Optional[Dict[str, Any]] = None,
        nested: bool = True,
    ) -> Tuple[List[int], int]:
        """
        Parse a keyword-delimited block.

        Args:
            tokens: List of tokens
            start_index: Index of the start keyword token
            start_keyword: Keyword that starts the block
            end_keyword: Keyword that ends the block
            state: Parser state
            context_type: Optional context type to push onto the stack
            context_metadata: Optional metadata for the context
            nested: Whether blocks of this type can be nested

        Returns:
            Tuple of (list of token indices in the block, index after the end keyword)
        """
        # Validate the start token
        if (
            start_index >= len(tokens)
            or tokens[start_index].token_type != TokenType.KEYWORD
            or tokens[start_index].value != start_keyword
        ):
            return [], start_index

        # Push context if provided
        if context_type:
            state.enter_context(ContextInfo(context_type, context_metadata or {}))

        # Parse the block
        index = start_index + 1
        nesting_level = 1
        block_tokens = []

        while index < len(tokens) and nesting_level > 0:
            if (
                tokens[index].token_type == TokenType.KEYWORD
                and tokens[index].value == start_keyword
                and nested
            ):
                nesting_level += 1
            elif (
                tokens[index].token_type == TokenType.KEYWORD
                and tokens[index].value == end_keyword
            ):
                nesting_level -= 1
                if nesting_level == 0:
                    # Don't include the end keyword in the block
                    break

            # Add this token to the block
            block_tokens.append(index)
            index += 1

        # Skip the end keyword if found
        if (
            index < len(tokens)
            and tokens[index].token_type == TokenType.KEYWORD
            and tokens[index].value == end_keyword
        ):
            index += 1

        # Pop context if provided
        if context_type:
            state.exit_context()

        return block_tokens, index
