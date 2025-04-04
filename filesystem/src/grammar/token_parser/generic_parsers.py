"""
Generic parsers for the grammar parser system.

This module provides generic parsers for common programming language constructs
like brace blocks, indentation blocks, and keyword-based blocks.
"""

from typing import List, Dict, Set, Optional, Any, Tuple, cast
from .token import Token, TokenType
from .parser_state import ParserState, ContextInfo


class BraceBlockParser:
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


class IndentationBlockParser:
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


class KeywordBlockParser:
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
        nested: bool = True
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
        if (start_index >= len(tokens) or 
            tokens[start_index].token_type != TokenType.KEYWORD or 
            tokens[start_index].value != start_keyword):
            return [], start_index
        
        # Push context if provided
        if context_type:
            state.enter_context(ContextInfo(context_type, context_metadata or {}))
        
        # Parse the block
        index = start_index + 1
        nesting_level = 1
        block_tokens = []
        
        while index < len(tokens) and nesting_level > 0:
            if (tokens[index].token_type == TokenType.KEYWORD and 
                tokens[index].value == start_keyword and nested):
                nesting_level += 1
            elif (tokens[index].token_type == TokenType.KEYWORD and 
                  tokens[index].value == end_keyword):
                nesting_level -= 1
                if nesting_level == 0:
                    # Don't include the end keyword in the block
                    break
            
            # Add this token to the block
            block_tokens.append(index)
            index += 1
        
        # Skip the end keyword if found
        if index < len(tokens) and tokens[index].token_type == TokenType.KEYWORD and tokens[index].value == end_keyword:
            index += 1
        
        # Pop context if provided
        if context_type:
            state.exit_context()
        
        return block_tokens, index 