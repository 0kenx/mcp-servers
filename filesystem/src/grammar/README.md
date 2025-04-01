# Language Grammar Parsers

This directory contains robust parsers for various programming languages to support code analysis in the MCP editor. These parsers use heuristic approaches to extract structured information from source code without requiring a full compiler frontend.

## Parsers

The following language parsers are implemented:

- **Python** - Parses Python functions, classes, decorators, and docstrings
- **C/C++** - Parses C and C++ functions, classes, structs, namespaces, and includes
- **JavaScript** - Parses JavaScript functions, arrow functions, classes, and modules
- **TypeScript** - Extends JavaScript parser with TypeScript-specific elements like interfaces and type declarations

## Features

Each parser can:

1. Identify the implementation of functions (including decorators and docstrings)
2. Identify all globals (function names, variables, type definitions)
3. Find specific elements by name or position
4. Report on parent-child relationships between code elements
5. Validate basic syntax correctness

## Usage

```python
from src.grammar.python import PythonParser
from src.grammar.base import ElementType

# Create a parser
parser = PythonParser()

# Parse some code
code = """
def hello_world():
    \"\"\"Say hello to the world!\"\"\"
    return "Hello, World!"

class Person:
    def __init__(self, name):
        self.name = name
        
    def greet(self):
        return f"Hello, {self.name}!"
"""

# Get all code elements
elements = parser.parse(code)

# Find a specific function
hello_func = parser.find_function(code, "hello_world")
if hello_func:
    print(f"Found function: {hello_func.name}")
    print(f"Docstring: {hello_func.metadata.get('docstring')}")
    
# Get all globals
globals_dict = parser.get_all_globals(code)
print(f"Global elements: {list(globals_dict.keys())}")
```

## Extending

To add a new language parser:

1. Create a new file `your_language.py` in the `src/grammar` directory
2. Implement a parser class that extends `BaseParser`
3. Define regex patterns for identifying language elements
4. Implement the `parse` method to extract code elements
5. Add your parser to the `EXTENSION_TO_PARSER` dictionary in `__init__.py`
6. Create tests in the `tests` directory

## Running Tests

Tests for all parsers can be run using the test runner:

```bash
cd /path/to/project
python -m src.grammar.tests.run_tests
```

To run tests for a specific parser:

```bash
python -m src.grammar.tests.run_tests test_python_parser
```

## Structure of Code Elements

Code elements are represented by the `CodeElement` class with the following attributes:

- `element_type`: Type of element (function, class, variable, etc.)
- `name`: Name of the element
- `start_line`: Starting line number (1-based)
- `end_line`: Ending line number (1-based)
- `code`: Full code of the element
- `parent`: Parent element if nested
- `metadata`: Additional information specific to the element type
- `children`: List of child elements

## Limitations

These parsers use regex and heuristics, not a full grammar-based parser. They may not handle:

- Highly complex code with unusual formatting
- All language features, especially newer or less common ones
- Preprocessor directives in C/C++ beyond basic includes
- Macro expansions that change code structure
