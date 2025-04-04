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
from .generic_brace_block import BraceBlockParser
from .generic_indentation_block import IndentationBlockParser
from .generic_keyword_pattern import KeywordPatternParser  # Import the new parser

from .base import CodeElement, ElementType, BaseParser

# Map of file extensions to *specific* parser classes
EXTENSION_TO_PARSER = {
    # Python
    ".py": PythonParser,
    ".pyx": PythonParser,
    ".pyw": PythonParser,
    # C/C++
    ".c": CCppParser,
    ".cpp": CCppParser,
    ".cc": CCppParser,
    ".cxx": CCppParser,
    ".h": CCppParser,
    ".hpp": CCppParser,
    ".hxx": CCppParser,
    # JavaScript
    ".js": JavaScriptParser,
    ".jsx": JavaScriptParser,
    ".mjs": JavaScriptParser,
    # TypeScript
    ".ts": TypeScriptParser,
    ".tsx": TypeScriptParser,
    # Rust
    ".rs": RustParser,
    # Add other specific parsers here
}

# Common extensions for brace-based languages (heuristic)
BRACE_EXTENSIONS = {".java", ".cs", ".go", ".php", ".swift", ".kt", ".kts", ".scala"}
# Common extensions for indentation-based languages (heuristic)
INDENT_EXTENSIONS = {".yaml", ".yml", ".sass", ".styl", ".coffee", ".fs"}  # F# is .fs


def get_parser_for_file(file_path):
    """
    Returns the appropriate parser for a given file based on its extension.
    Falls back to generic parsers based on extension heuristics if specific parser not found.

    Args:
        file_path: Path to the file

    Returns:
        A parser instance or None if the file type is not recognized by any strategy.
    """
    import os

    extension = os.path.splitext(file_path)[1].lower()

    # 1. Try specific parser first
    parser_class = EXTENSION_TO_PARSER.get(extension)
    if parser_class:
        # print(f"Using specific parser {parser_class.__name__} for {extension}")
        return parser_class()

    # 2. Try generic parsers based on extension heuristics
    if extension in BRACE_EXTENSIONS:
        # print(f"Using generic BraceBlockParser for {extension}")
        return BraceBlockParser()
    elif extension in INDENT_EXTENSIONS:
        # print(f"Using generic IndentationBlockParser for {extension}")
        return IndentationBlockParser()

    # 3. As a last resort, use the KeywordPatternParser for any other unknown text-based file?
    #    Or return None? Let's try KeywordPatternParser as a broad fallback.
    #    Could add checks here, e.g., ensure it's likely a text file.
    # print(f"Warning: No specific or heuristic parser for '{extension}'. Falling back to KeywordPatternParser.")
    return KeywordPatternParser()

    # Alternatively, return None if no parser is suitable
    # return None
