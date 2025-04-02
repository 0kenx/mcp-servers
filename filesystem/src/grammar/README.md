# Grammar Parsers

Code parsers for extracting structured information (functions, classes, variables) from source code in various programming languages. These parsers can analyze code and build a structured representation of its elements, even when dealing with incomplete or syntactically imperfect code.

## Features

### Language-Aware Handling of Incomplete Code

The parsers include intelligent, language-aware handling for incomplete code, making them useful even during active development when code might be in-progress or have syntax issues:

- **Language-specific preprocessing**: Uses knowledge of language features to make smart decisions
- **Balance unmatched braces**: Automatically adds missing closing braces
- **Fix indentation issues**: Corrects common indentation errors
- **Structural analysis**: Understands code structure to fix nesting issues
- **Nesting validation**: Identifies and corrects unlikely nesting patterns (like classes inside functions)
- **Recover incomplete blocks**: Adds minimal bodies to incomplete function/class definitions
- **Contextual fixes**: Applies fixes based on surrounding context

### Rich Metadata Extraction

The parsers extract comprehensive metadata from code symbols, enhancing the usefulness of the parsed results:

- **Docstrings**: Documentation comments preceding functions/classes
- **Decorators**: Function/class decorators in languages that support them
- **Type information**: Return types, parameter types, and type annotations
- **Visibility**: Public/private/protected modifiers
- **Other attributes**: Language-specific attributes like C++ attributes

## Implementation

### Incomplete Code Handling

The `IncompleteCodeHandler` class provides utilities to preprocess code before parsing:

```python
# Example: Preprocessing code before parsing
code, was_modified = self.preprocess_incomplete_code(code)
if was_modified:
    # Code was fixed to handle syntax issues
    print("Code was modified to handle incomplete syntax")
```

Strategies include:
- Brace balancing
- Indentation correction
- Block recovery

### Metadata Extraction

The `MetadataExtractor` classes provide language-specific metadata extraction:

```python
# Example: Getting metadata for a function
metadata = parser.extract_metadata(code, line_idx)
# metadata contains docstrings, decorators, type info, etc.
```

Supported metadata types:
- Python: docstrings, decorators, type annotations, return types
- JavaScript: JSDoc comments, TypeScript decorators/types
- C/C++: Doxygen comments, attributes, visibility modifiers

## Usage

Example of parsing Python code with incomplete syntax:

```python
from grammar.python import PythonParser

code = """
def calculate_total(items: List[Item]) -> float:
    """Calculate the total price of all items."""
    return sum(item.price for item in items)
    
class ShoppingCart:
    """Shopping cart containing items."""
    
    def __init__(self):
        self.items = []
        
    def add_item(self, item):
        self.items.append(item)
        
    def get_total(self):
        return calculate_total(self.items)
"""

parser = PythonParser()
elements = parser.parse(code)

# Check if code was modified during parsing
if parser.was_code_modified():
    print("Code was corrected for syntax issues")

# Access metadata
for element in elements:
    if "docstring" in element.metadata:
        print(f"{element.name} has docstring: {element.metadata['docstring']}")
    if "return_type" in element.metadata:
        print(f"{element.name} returns: {element.metadata['return_type']}")
```

## Supported Languages

- Python
- JavaScript/TypeScript
- C/C++
- Rust
- Generic block-based languages

## Architecture

```
+-----------------+        +-------------------------------+
|   BaseParser    |------->| Language-Aware Preprocessor   |
+-----------------+        +-------------------------------+
        |                            |
        | Uses                        | Uses as fallback
        |                            v
        |                  +---------------------------+
        |                  |   IncompleteCodeHandler  |
        |                  +---------------------------+
        |
        |  Uses
        v
+------------------+       +---------------------------+
| MetadataExtractor|<----->|   Language-Specific       |
+------------------+       |   Metadata Extractors     |
                           +---------------------------+
        ^
        |  Inherits
        |
+-------+----------+
|                  |
|  Language        |
|  Specific        |
|  Parsers         |
|                  |
+------------------+
```

The system is designed with a modular architecture:

1. **BaseParser**: Provides common utilities and functionality for all parsers
2. **LanguageAwarePreprocessor**: Intelligent preprocessing using language knowledge
3. **IncompleteCodeHandler**: Basic module for handling generic syntax issues
4. **MetadataExtractor**: Base class for extracting metadata from code
5. **Language-Specific Parsers**: Implement parsing logic for each language

## Extension

To add support for a new language:
1. Create a new parser class inheriting from `BaseParser`
2. Set the `language` attribute to select the appropriate metadata extractor
3. Implement the `parse` method with language-specific parsing logic

## Error Handling & Diagnostics

The parsers provide comprehensive error handling and detailed diagnostics:

```python
# Check if the parser modified the code to handle syntax issues
was_modified = parser.was_code_modified()

# Get detailed diagnostics about the preprocessing
diagnostics = parser.get_preprocessing_diagnostics()
if diagnostics:
    # Get confidence score for the fixes
    confidence = diagnostics["confidence_score"]  # 0.0-1.0 where higher is better
    
    # See what fixes were applied
    fixes = diagnostics["fixes_applied"]  # List of fix types
    
    # Get structural analysis
    nesting = diagnostics["nesting_analysis"]  # Detailed nesting info

# Check if the code has valid syntax (without preprocessing)
is_valid = parser.check_syntax_validity(code)

# Get parsing results even with syntax errors
elements = parser.parse(code)  # Will use preprocessing if enabled
```

When a parser encounters incomplete code:

1. It analyzes the code structure to understand nesting patterns
2. It applies language-specific knowledge to make smart decisions
3. It fixes common issues with intelligent preprocessing
4. It provides confidence scores and detailed diagnostics
5. It extracts as much information as possible from the valid parts
6. It returns a structured representation of what it could successfully parse

This approach allows the parsers to be useful even during active development or when analyzing code snippets, with the added benefit of understanding why and how the code was fixed.
