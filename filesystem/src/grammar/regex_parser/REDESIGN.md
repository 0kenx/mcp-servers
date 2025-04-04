# Grammar Parser System Redesign Proposal

This document outlines a comprehensive redesign plan for the grammar parser system, focusing on two key aspects:
1. How parent-child relationships are established
2. How context is tracked during parsing

## Current Issues

The current implementation has several limitations:

1. **Parent-Child Relationship Issues**: The system struggles to correctly establish relationships between nested elements.
2. **Brace Matching Limitations**: The matching algorithm has trouble with complex nested structures and unbalanced braces.
3. **Over/Under Detection**: Pattern matching can be too aggressive, detecting too many elements or missing important ones.
4. **Context Awareness**: Limited awareness of non-code elements (comments, strings) causes false positives.
5. **Language-Specific Features**: Advanced language features are not properly handled.

## Redesign Plan

### 1. Parser State Machine Architecture

Replace the current post-processing approach with a state machine that tracks context during parsing:

```python
class ParserState:
    def __init__(self):
        self.current_scope = None  # Current parent element
        self.scope_stack = []      # Stack of scopes for nested elements
        self.context_type = "code" # Current context: "code", "string", "comment", etc.
        self.brace_depth = 0       # Current nesting level
        self.last_token = None     # Previous significant token 
        self.in_string = False     # Whether currently in a string
        self.string_delimiter = None  # Current string delimiter (', ", or `)
        self.in_comment = False    # Whether currently in a comment
        self.language_context = {} # Language-specific state data
```

### 2. Two-Pass Token-Based Parsing

Replace regex-heavy pattern matching with token-based parsing:

#### First Pass: Tokenization
```python
def tokenize(self, code):
    tokens = []
    state = TokenizerState()
    
    for i, char in enumerate(code):
        # Track context transitions (string/comment/code)
        if not state.in_comment and not state.in_string:
            if char == '"' or char == "'" or char == '`':
                state.in_string = True
                state.string_delimiter = char
                tokens.append(Token("STRING_START", char, i))
            elif char == '/' and i+1 < len(code):
                if code[i+1] == '/':
                    state.in_comment = True
                    state.comment_type = "line"
                    tokens.append(Token("COMMENT_START", "//", i))
                elif code[i+1] == '*':
                    state.in_comment = True
                    state.comment_type = "block"
                    tokens.append(Token("COMMENT_START", "/*", i))
            elif char in "{[(":
                tokens.append(Token("OPEN_DELIM", char, i))
            elif char in "}])":
                tokens.append(Token("CLOSE_DELIM", char, i))
            # ...more token types
    
    return tokens
```

#### Second Pass: AST Construction
```python
def build_ast(self, tokens):
    state = ParserState()
    elements = []
    
    i = 0
    while i < len(tokens):
        # Process tokens in context-aware chunks
        if state.context_type == "code":
            if self._is_start_of_definition(tokens, i):
                element = self._parse_definition(tokens, i, state)
                
                # Establish parent-child relationship during parsing
                if state.current_scope:
                    element.parent = state.current_scope
                    state.current_scope.children.append(element)
                
                elements.append(element)
                
                # Update state for nested elements
                state.scope_stack.append(state.current_scope)
                state.current_scope = element
                
            # Handle end of scope
            elif tokens[i].type == "CLOSE_DELIM" and tokens[i].value == "}":
                if state.scope_stack:
                    state.current_scope = state.scope_stack.pop()
        
        # Handle context transitions
        if tokens[i].type == "STRING_START":
            state.context_type = "string"
        elif tokens[i].type == "COMMENT_START":
            state.context_type = "comment"
        # ...
        
        i += 1
    
    return elements
```

### 3. Context-Sensitive Symbol Detection

Enhance detection of definitions with immediate context:

```python
def _is_start_of_definition(self, tokens, index):
    """Check if tokens at index represent start of function/class/etc. with context awareness"""
    context = self._get_token_context(tokens, index, 5)  # Look at 5 tokens of context
    
    # Check for function pattern with language-specific context
    if self.language == "javascript":
        # JS function patterns
        if context.has_keyword("function") and context.has_identifier():
            return True
        # Arrow function
        if context.has_identifier() and context.has_sequence("=>"):
            return True
    elif self.language == "python":
        # Python function/class patterns
        if context.has_keyword("def", "class") and context.has_identifier():
            return True
    
    return False
```

### 4. Hierarchical Context Tracking

Track nested context information more precisely:

```python
class ContextTracker:
    def __init__(self):
        self.contexts = []  # Stack of contexts
        
    def enter_context(self, context_type, metadata=None):
        self.contexts.append({"type": context_type, "metadata": metadata or {}})
        
    def exit_context(self):
        if self.contexts:
            return self.contexts.pop()
        return None
        
    def current_context(self):
        return self.contexts[-1] if self.contexts else {"type": "code", "metadata": {}}
    
    def is_in_context(self, context_type):
        return any(ctx["type"] == context_type for ctx in self.contexts)
```

### 5. Language-Specific Symbol Tables

Maintain language-specific symbol tables during parsing:

```python
class SymbolTable:
    def __init__(self):
        self.scopes = [{}]  # Stack of symbol tables
        self.current_scope_index = 0
        
    def enter_scope(self):
        self.scopes.append({})
        self.current_scope_index += 1
        
    def exit_scope(self):
        if len(self.scopes) > 1:
            self.scopes.pop()
            self.current_scope_index -= 1
    
    def add_symbol(self, name, symbol_type, metadata=None):
        self.scopes[self.current_scope_index][name] = {
            "type": symbol_type,
            "metadata": metadata or {}
        }
    
    def lookup_symbol(self, name):
        # Search from innermost to outermost scope
        for i in range(self.current_scope_index, -1, -1):
            if name in self.scopes[i]:
                return self.scopes[i][name]
        return None
```

### 6. AST Validation and Repair

Add an AST validation phase to catch and fix structural issues:

```python
def validate_and_repair_ast(self, elements):
    """Validate and repair the AST structure"""
    # Check for overlap - elements shouldn't have overlapping ranges
    self._check_for_overlapping_elements(elements)
    
    # Validate parent-child relationships
    self._validate_parent_child_relationships(elements)
    
    # Fix orphaned elements
    orphans = [e for e in elements if e.parent is None and e.start_line > 1]
    for orphan in orphans:
        potential_parent = self._find_most_likely_parent(orphan, elements)
        if potential_parent:
            orphan.parent = potential_parent
            potential_parent.children.append(orphan)
    
    # Fix element types based on context
    for element in elements:
        if element.element_type == ElementType.FUNCTION and element.parent:
            if element.parent.element_type in (ElementType.CLASS, ElementType.STRUCT):
                element.element_type = ElementType.METHOD
```

## Implementation Strategy

### 1. Incremental Development
- First implement the core state machine and context tracking
- Then enhance token-based parsing for one language (Python as a starting point)
- Gradually extend to other languages

### 2. Better Test Coverage
- Add unit tests specifically for parser state transitions
- Add tests for nested structures and context tracking
- Create tests for edge cases in each language

### 3. Language-Specific Extensions
- Ensure all languages have dedicated context recognition rules
- Create language-specific token patterns with inheritance hierarchy
- Implement language-specific symbol table handlers

## Benefits Over Current Implementation

1. **Context-Aware Parsing**: By tracking context during parsing, we avoid misinterpreting strings and comments as code.

2. **Better Parent-Child Relationships**: Relationships are established during parsing rather than retrofitted afterward.

3. **Improved Handling of Complex Structures**: Token-based parsing provides better understanding of nested structures.

4. **Language-Specific Features**: The design is extensible for language-specific features.

5. **More Accurate Element Detection**: Context-sensitive detection reduces both false positives and negatives.

## Limitations and Tradeoffs

1. **Complexity**: This design is more complex than the current regex-based approach.

2. **Performance**: A two-pass approach may be slower than the current implementation.

3. **Development Time**: Implementing this design will require significant effort.

However, these tradeoffs are justified by the improved robustness and accuracy of the parsing results. 