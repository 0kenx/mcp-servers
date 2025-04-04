"""
Generic parsers for the grammar parser system.

This module provides generic parsers for common programming language constructs
like brace blocks, indentation blocks, and keyword-based blocks.
"""

from typing import List, Dict, Set, Optional, Any, Tuple, cast
from .token import Token, TokenType
from .token_parser import TokenParser
from .parser_state import ParserState, ContextInfo
from .symbol_table import SymbolTable
from .generic_brace_block_tokenizer import BraceBlockTokenizer


class BraceBlockParser(TokenParser):
    """
    Parser for brace-delimited blocks.
    
    This handles code blocks that are delimited by braces, which are common in
    languages like C, C++, Java, JavaScript, etc.
    """
    
    @staticmethod
    def parse_block(
        tokens: List[Token], 
        start_index: int, 
        state: ParserState,
        context_type: Optional[str] = None,
        context_metadata: Optional[Dict[str, Any]] = None
    ) -> Tuple[List[int], int]:
        """
        Parse a brace-delimited block.
        
        Args:
            tokens: List of tokens
            start_index: Index of the opening brace token
            state: Parser state
            context_type: Optional context type to push onto the stack
            context_metadata: Optional metadata for the context
            
        Returns:
            Tuple of (list of token indices in the block, index after the closing brace)
        """
        # Validate the start token
        if start_index >= len(tokens) or tokens[start_index].token_type != TokenType.OPEN_BRACE:
            return [], start_index
        
        # Push context if provided
        if context_type:
            state.enter_context(ContextInfo(context_type, context_metadata or {}))
        
        # Parse the block
        index = start_index + 1
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
        
        # Pop context if provided
        if context_type:
            state.exit_context()
        
        return block_tokens, index
        