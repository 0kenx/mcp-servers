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
from .generic_indentation_block_tokenizer import IndentationBlockTokenizer

class IndentationBlockParser(TokenParser):
    """
    Parser for indentation-based blocks.
    
    This handles code blocks that are defined by their indentation level,
    which are common in languages like Python, YAML, etc.
    """
    
    @staticmethod
    def parse_block(
        tokens: List[Token], 
        start_index: int,
        base_indentation: int,
        state: ParserState,
        context_type: Optional[str] = None,
        context_metadata: Optional[Dict[str, Any]] = None,
        whitespace_token_type: TokenType = TokenType.WHITESPACE
    ) -> Tuple[List[int], int]:
        """
        Parse an indentation-based block.
        
        Args:
            tokens: List of tokens
            start_index: Index to start parsing from (should be after a colon or equivalent)
            base_indentation: Indentation level of the parent block
            state: Parser state
            context_type: Optional context type to push onto the stack
            context_metadata: Optional metadata for the context
            whitespace_token_type: Token type for whitespace
            
        Returns:
            Tuple of (list of token indices in the block, index after the block)
        """
        # Skip to the next line to start the indented block
        index = start_index
        while index < len(tokens) and tokens[index].token_type != TokenType.NEWLINE:
            index += 1
        
        if index < len(tokens):
            index += 1  # Skip the newline
        
        # Push context if provided
        if context_type:
            state.enter_context(ContextInfo(context_type, context_metadata or {}))
        
        # Parse the indented block
        block_tokens = []
        block_indentation = None
        
        while index < len(tokens):
            # Check for indentation at the start of a line
            if index < len(tokens) and tokens[index].token_type == whitespace_token_type:
                # Get indentation level
                indent_size = len(tokens[index].value)
                if "indent_size" in tokens[index].metadata:
                    indent_size = tokens[index].metadata["indent_size"]
                
                # Set the block indentation level on the first line
                if block_indentation is None:
                    block_indentation = indent_size
                    
                    # If block indentation is less than or equal to base, this isn't a proper block
                    if block_indentation <= base_indentation:
                        # Pop context if provided
                        if context_type:
                            state.exit_context()
                        return [], start_index
                
                # Check if we've dedented back to or beyond the base level
                if indent_size <= base_indentation:
                    break
                
                # Check if this line is part of the block (at the same or deeper indentation)
                if indent_size >= block_indentation:
                    block_tokens.append(index)
                    index += 1
                    continue
            
            # Add non-whitespace tokens to the block
            if index < len(tokens) and tokens[index].token_type != TokenType.NEWLINE:
                block_tokens.append(index)
            
            index += 1
            
            # If we hit a newline, reset to check indentation on the next line
            if index < len(tokens) and tokens[index].token_type == TokenType.NEWLINE:
                block_tokens.append(index)
                index += 1
        
        # Pop context if provided
        if context_type:
            state.exit_context()
        
        return block_tokens, index
