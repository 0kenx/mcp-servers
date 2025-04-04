"""
Token-based parsers for the grammar parser system.

This package provides token-based parsers for various programming languages.
These parsers use a two-pass approach: first tokenizing the code, then
building an AST from the tokens.
"""

from .token import Token, TokenType
from .tokenizer import Tokenizer, TokenizerState
from .parser_state import ParserState, ContextInfo
from .symbol_table import SymbolTable, Symbol, Scope
from .token_parser import TokenParser
from .python_tokenizer import PythonTokenizer
from .python_parser import PythonParser
from .javascript_tokenizer import JavaScriptTokenizer
from .javascript_parser import JavaScriptParser
from .generic_brace_block_parser import BraceBlockParser
from .generic_indentation_block_parser import IndentationBlockParser
from .generic_keyword_pattern_parser import KeywordBlockParser
from .parser_factory import ParserFactory
from .context_tracker import ContextTracker, Context
from .ast_utils import remove_circular_refs, format_ast_for_output

__all__ = [
    'Token',
    'TokenType',
    'Tokenizer',
    'TokenizerState',
    'ParserState',
    'ContextInfo',
    'SymbolTable',
    'Symbol',
    'Scope',
    'TokenParser',
    'PythonTokenizer',
    'PythonParser',
    'JavaScriptTokenizer',
    'JavaScriptParser',
    'BraceBlockParser',
    'IndentationBlockParser',
    'KeywordBlockParser',
    'ParserFactory',
    'ContextTracker',
    'Context',
    'remove_circular_refs',
    'format_ast_for_output',
] 