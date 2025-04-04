"""
Parser factory for the grammar parser system.

This module provides a factory class for creating language-specific parsers.
"""

from typing import Dict, Type, Optional

from .token_parser import TokenParser
from .python_parser import PythonParser
from .javascript_parser import JavaScriptParser
from .typescript_parser import TypeScriptParser
from .c_parser import CParser
from .cpp_parser import CppParser
from .rust_parser import RustParser
from .html_parser import HTMLParser
from .css_parser import CSSParser
from .ts_react_parser import TSReactParser


class ParserFactory:
    """
    Factory class for creating language-specific parsers.
    
    This class maintains a registry of parser classes for different languages
    and provides methods to register and create parser instances.
    """
    
    _registry: Dict[str, Type[TokenParser]] = {}
    
    @classmethod
    def register(cls, language: str, parser_class: Type[TokenParser]) -> None:
        """
        Register a parser class for a specific language.
        
        Args:
            language: Language identifier (e.g., 'python', 'javascript')
            parser_class: The parser class to register
        """
        cls._registry[language.lower()] = parser_class
    
    @classmethod
    def create_parser(cls, language: str) -> Optional[TokenParser]:
        """
        Create a parser instance for the specified language.
        
        Args:
            language: Language identifier (e.g., 'python', 'javascript')
            
        Returns:
            An instance of the appropriate parser, or None if no parser is registered
            for the specified language
        """
        language = language.lower()
        if language in cls._registry:
            return cls._registry[language]()
        return None
    
    @classmethod
    def get_supported_languages(cls) -> list[str]:
        """
        Get a list of supported languages.
        
        Returns:
            List of language identifiers that have registered parsers
        """
        return list(cls._registry.keys())


# Register built-in parsers
ParserFactory.register('python', PythonParser)
ParserFactory.register('py', PythonParser)
ParserFactory.register('javascript', JavaScriptParser)
ParserFactory.register('js', JavaScriptParser)  # Alias for 'javascript'
ParserFactory.register('typescript', TypeScriptParser)
ParserFactory.register('ts', TypeScriptParser)  # Alias for 'typescript'
ParserFactory.register('c', CParser)
ParserFactory.register('cpp', CppParser)
ParserFactory.register('c++', CppParser)  # Alias for 'cpp'
ParserFactory.register('rust', RustParser)
ParserFactory.register('rs', RustParser)
ParserFactory.register('html', HTMLParser)
ParserFactory.register('htm', HTMLParser)
ParserFactory.register('css', CSSParser)
ParserFactory.register('tsx', TSReactParser)
ParserFactory.register('jsx', TSReactParser)  # Can also handle JSX 