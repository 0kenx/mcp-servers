"""
Grammar parsers for different programming languages.

These parsers extract structured information from source code to aid in function
identification, definition lookup, and global namespace exploration. They use
heuristic approaches rather than full parsing to balance accuracy with simplicity.
"""

from .python import PythonParser
from .c_cpp import CCppParser
from .javascript import JavaScriptParser
from .typescript import TypeScriptParser
from .rust import RustParser

from .base import CodeElement, ElementType, BaseParser

# Map of file extensions to appropriate parser classes
EXTENSION_TO_PARSER = {
    # Python
    '.py': PythonParser,
    '.pyx': PythonParser,
    '.pyw': PythonParser,
    # C/C++
    '.c': CCppParser,
    '.cpp': CCppParser,
    '.cc': CCppParser,
    '.cxx': CCppParser,
    '.h': CCppParser,
    '.hpp': CCppParser,
    '.hxx': CCppParser,
    # JavaScript
    '.js': JavaScriptParser,
    '.jsx': JavaScriptParser,
    '.mjs': JavaScriptParser,
    # TypeScript 
    '.ts': TypeScriptParser,
    '.tsx': TypeScriptParser,
    # Rust
    '.rs': RustParser,
}

def get_parser_for_file(file_path):
    """
    Returns the appropriate parser for a given file based on its extension.
    
    Args:
        file_path: Path to the file
        
    Returns:
        A parser instance or None if the file type is not supported
    """
    import os
    extension = os.path.splitext(file_path)[1].lower()
    parser_class = EXTENSION_TO_PARSER.get(extension)
    
    if parser_class:
        return parser_class()
    return None
