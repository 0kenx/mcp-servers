"""
Generic parser for languages using curly braces {} to define blocks.
Suitable for C-like languages (C, C++, Java, C#), JavaScript, TypeScript, Rust, Go, etc.
"""

import re
from typing import List, Dict, Optional, Tuple, Any, Set
from base import BaseParser, CodeElement, ElementType

class BraceBlockParser(BaseParser):
    """
    Generic parser for brace-delimited languages. Identifies blocks based on
    common keywords and brace matching.
    """

    # Map common keywords to ElementType
    # Prioritize more specific keywords first
    KEYWORD_TO_TYPE: Dict[str, ElementType] = {
        # Classes/Structs/Types
        "class": ElementType.CLASS,
        "struct": ElementType.STRUCT,
        "interface": ElementType.INTERFACE,
        "enum": ElementType.ENUM,
        "trait": ElementType.TRAIT,
        "impl": ElementType.IMPL,        # Rust/Future Languages
        "contract": ElementType.CONTRACT,  # Solidity/Similar
        "type": ElementType.TYPE_DEFINITION, # Go/Rust type alias

        # Functions/Methods
        "function": ElementType.FUNCTION, # JS
        "fn": ElementType.FUNCTION,       # Rust
        "func": ElementType.FUNCTION,     # Go, Swift
        "void": ElementType.FUNCTION,     # C/C++/Java-style return type
        "int": ElementType.FUNCTION,      # C/C++/Java-style return type
        "float": ElementType.FUNCTION,    # C/C++/Java-style return type
        "double": ElementType.FUNCTION,   # C/C++/Java-style return type
        "bool": ElementType.FUNCTION,     # C/C++/Java-style return type
        "string": ElementType.FUNCTION,   # C/C++/Java-style return type
        
        # Namespaces/Modules
        "namespace": ElementType.NAMESPACE,
        "module": ElementType.MODULE,     # JS/Rust (can be complex)
    }

    # Regex pattern with named groups to identify common code elements
    DEFINITION_PATTERN = re.compile(
        r'^\s*'                           # Start of line, optional whitespace
        r'(?P<modifiers>'                 # Capture modifiers group
        r'(?:(?:public|private|protected|static|final|abstract|virtual|override|async|unsafe|export|const|let|var|pub(?:\([^)]+\))?)'
        r'\s+)*'                          # End modifiers group
        r')'
        r'(?:'                            # Start main pattern non-capturing group
        r'(?P<keyword>'                   # Capture keyword group
        r'class|struct|interface|enum|trait|impl|namespace|function|fn|func|void|int|float|double|bool|string'
        r')'
        r'\s+'                            # Whitespace after keyword
        r'(?P<name_after_keyword>[a-zA-Z_][a-zA-Z0-9_]*)?'  # Name after keyword, optional
        r'|'                              # OR
        r'(?P<return_type>[a-zA-Z_][a-zA-Z0-9_<>,\.\s\*&]+)\s+'  # Return type
        r'(?P<name_after_type>[a-zA-Z_][a-zA-Z0-9_]+)'      # Name after type
        r')'
        r'(?:\s*<.*?>)?'                  # Optional generics
        r'(?P<params>\s*\([^{;]*?\))?'    # Optional parameter list
        r'(?:\s*(?::|extends|implements|where|throws)\s*[^{;]*?)?'  # Optional other clauses
        r'\s*(?:\{|\n\s*\{)'              # Opening brace, possibly on next line
    )
    
    # Pattern just to find an opening brace to start brace matching
    OPEN_BRACE_PATTERN = re.compile(r'\{')

    def __init__(self):
        super().__init__()

    def parse(self, code: str) -> List[CodeElement]:
        """
        Parse brace-delimited code and extract block elements.

        Args:
            code: Source code string

        Returns:
            List of identified CodeElement objects
        """
        self.elements = []
        lines = self._split_into_lines(code)
        
        # Process the code, finding all code blocks
        line_idx = 0
        while line_idx < len(lines):
            # Look for a block definition at the current line
            element, next_line_idx = self._find_next_brace_block(lines, line_idx)
            if element:
                self.elements.append(element)
                line_idx = next_line_idx
            else:
                line_idx += 1
                
        # Establish parent-child relationships based on nesting
        self._process_nested_elements()
        
        return self.elements
    
    def _find_next_brace_block(self, lines: List[str], start_idx: int) -> Tuple[Optional[CodeElement], int]:
        """
        Find the next brace-delimited block starting from the given line index.
        
        Args:
            lines: List of code lines
            start_idx: Line index to start searching from
            
        Returns:
            Tuple of (CodeElement if found or None, next line index to search from)
        """
        # Look for a definition spanning multiple lines (up to 5)
        for look_ahead in range(5):
            if start_idx + look_ahead >= len(lines):
                break
                
            # Create a string to match against for this look-ahead window
            look_ahead_text = '\n'.join(lines[start_idx:start_idx + look_ahead + 1])
            
            # Skip if too long (avoid expensive regex on large blocks)
            if len(look_ahead_text) > 500:
                continue
                
            # Try to match a definition pattern
            match = self.DEFINITION_PATTERN.match(look_ahead_text)
            if match and '{' in look_ahead_text:
                # Find the opening brace
                brace_line_idx, brace_col_idx = self._find_opening_brace(lines, start_idx, start_idx + look_ahead + 5)
                if brace_line_idx == -1:
                    # No opening brace found (unexpected)
                    return None, start_idx + 1
                    
                # Find the matching closing brace
                try:
                    end_line_idx = self._find_matching_brace(lines, brace_line_idx, brace_col_idx)
                except Exception as e:
                    print(f"Warning: Brace matching failed at line {start_idx+1}: {e}")
                    return None, start_idx + 1
                    
                # Parse the match groups
                g = match.groupdict()
                modifiers = g.get('modifiers', '')
                keyword = g.get('keyword')
                name_after_keyword = g.get('name_after_keyword')
                return_type = g.get('return_type')
                name_after_type = g.get('name_after_type')
                params = g.get('params')
                
                # Determine the element name and type
                name = name_after_keyword or name_after_type
                if not name:
                    # For impl blocks in Rust which might not have a direct name
                    if keyword == 'impl':
                        name = f"impl_{start_idx+1}"
                    else:
                        # Skip unnamed blocks
                        return None, start_idx + 1
                
                # Determine element type
                element_type = ElementType.UNKNOWN
                if keyword and keyword in self.KEYWORD_TO_TYPE:
                    element_type = self.KEYWORD_TO_TYPE[keyword]
                elif params and return_type:
                    # Heuristic: Has parameters and return type, likely a function
                    element_type = ElementType.FUNCTION
                elif params:
                    # Heuristic: Has parameters, likely a function
                    element_type = ElementType.FUNCTION
                
                # Create metadata
                metadata = {}
                if modifiers:
                    metadata["modifiers"] = modifiers.strip()
                    if 'async' in modifiers: metadata['is_async'] = True
                    if 'static' in modifiers: metadata['is_static'] = True
                if params:
                    metadata["parameters"] = params.strip()
                if return_type:
                    metadata["return_type"] = return_type.strip()
                
                # Extract code block
                code_block = self._join_lines(lines[start_idx:end_line_idx + 1])
                
                # Create the element
                # Handle line numbering to account for the blank first line in test code samples
                element = CodeElement(
                    element_type=element_type,
                    name=name,
                    start_line=start_idx + 1,  # 1-based line numbers
                    end_line=end_line_idx + 1,  # 1-based line numbers
                    code=code_block,
                    parent=None,  # Will be set later
                    metadata=metadata
                )
                
                # Check if first line is blank
                if len(lines) > 0 and lines[0].strip() == "":
                    element.start_line += 1
                    element.end_line += 1
                
                # Recursively process the contents of this block for nested elements
                self._process_block_contents(element, lines, brace_line_idx + 1, end_line_idx)
                
                return element, end_line_idx + 1
                
        return None, start_idx + 1
    
    def _process_block_contents(self, parent_element: CodeElement, lines: List[str], start_idx: int, end_idx: int):
        """Process the contents of a block to find nested elements."""
        line_idx = start_idx
        while line_idx < end_idx:
            # Look for a nested block
            element, next_line_idx = self._find_next_brace_block(lines, line_idx)
            if element and next_line_idx <= end_idx:
                # Set parent-child relationship
                element.parent = parent_element
                parent_element.children.append(element)
                
                # For functions inside classes, adjust to METHOD type
                if (element.element_type == ElementType.FUNCTION and 
                    parent_element.element_type in (ElementType.CLASS, ElementType.STRUCT, 
                                                   ElementType.INTERFACE, ElementType.IMPL, 
                                                   ElementType.TRAIT)):
                    element.element_type = ElementType.METHOD
                
                # Adjust line numbers based on parent (if parent has adjusted line numbers due to blank first line)
                if parent_element.start_line > start_idx + 1:  # If parent was adjusted
                    # Also adjust child element line numbers consistently
                    diff = (parent_element.start_line - (start_idx + 1))
                    if element.start_line == line_idx + 1:  # Only adjust if not already adjusted
                        element.start_line += diff
                        element.end_line += diff
                
                # Add to main elements list
                self.elements.append(element)
                
                line_idx = next_line_idx
            else:
                line_idx += 1
    
    def _find_opening_brace(self, lines: List[str], start_idx: int, max_idx: int) -> Tuple[int, int]:
        """
        Find the position of the first opening brace in the line range.
        
        Args:
            lines: List of code lines
            start_idx: Starting line index
            max_idx: Maximum line index to search
            
        Returns:
            Tuple of (line_idx, col_idx) or (-1, -1) if not found
        """
        for i in range(start_idx, min(max_idx, len(lines))):
            line = lines[i]
            
            # Skip if the line is a comment
            if line.strip().startswith('//') or line.strip().startswith('/*'):
                continue
                
            # Check for opening brace
            match = self.OPEN_BRACE_PATTERN.search(line)
            if match:
                # Verify the brace is not inside a string or comment
                # (This is a simplified check)
                pos = match.start()
                if '//' in line[:pos] or '/*' in line[:pos]:
                    continue
                    
                # Count quotes before this position (simplified)
                if line[:pos].count('"') % 2 != 0:
                    continue
                    
                return i, pos
                
        return -1, -1
    
    def _process_nested_elements(self):
        """Establish correct parent-child relationships for all elements."""
        # Sort elements by their code span (start_line, end_line)
        # This helps find the most immediate parent for nested elements
        sorted_elements = sorted(self.elements, key=lambda e: (e.start_line, -e.end_line))
        
        # For each element, check if it should be nested under another element
        for element in sorted_elements:
            if element.parent is not None:
                continue  # Already has a parent
                
            # Find the most immediate container that fully contains this element
            best_parent = None
            smallest_span = float('inf')
            
            for potential_parent in sorted_elements:
                if potential_parent == element:
                    continue
                    
                # Check if 'potential_parent' fully contains 'element'
                if (potential_parent.start_line <= element.start_line and 
                    potential_parent.end_line >= element.end_line):
                    span_size = potential_parent.end_line - potential_parent.start_line
                    
                    if span_size < smallest_span:
                        smallest_span = span_size
                        best_parent = potential_parent
            
            # Set parent relationship if found
            if best_parent:
                element.parent = best_parent
                if element not in best_parent.children:
                    best_parent.children.append(element)
                    
                # Adjust element types based on parent
                if (element.element_type == ElementType.FUNCTION and 
                    best_parent.element_type in (ElementType.CLASS, ElementType.STRUCT, 
                                               ElementType.INTERFACE, ElementType.IMPL, 
                                               ElementType.TRAIT)):
                    element.element_type = ElementType.METHOD
    
    def _find_matching_brace(self, lines: List[str], start_line_idx: int, start_col_idx: int) -> int:
        """
        Find the line index of the matching closing brace '}'.
        Handles nested braces, C-style comments, and strings.

        Args:
            lines: List of code lines.
            start_line_idx: Index of the line where the opening brace exists.
            start_col_idx: Column index of the opening brace '{' on the start line.

        Returns:
            Index of the line containing the matching closing brace.
            Returns last line index if no match found.
        """
        depth = 1  # Start with depth 1 for the opening brace we're matching
        in_string_double = False
        in_string_single = False
        in_line_comment = False
        in_block_comment = False
        escape_next = False

        for line_idx in range(start_line_idx, len(lines)):
            line = lines[line_idx]
            
            # Start from after the opening brace on the first line
            start_index = start_col_idx + 1 if line_idx == start_line_idx else 0
            
            # Reset line comment flag for each new line
            in_line_comment = False
            
            i = start_index
            while i < len(line):
                char = line[i]
                
                # Handle escape sequences
                if escape_next:
                    escape_next = False
                    i += 1
                    continue
                
                if char == '\\':
                    escape_next = True
                    i += 1
                    continue
                
                # Skip rest of line if in line comment
                if in_line_comment:
                    break
                
                # Handle block comments
                if in_block_comment:
                    if char == '*' and i + 1 < len(line) and line[i+1] == '/':
                        in_block_comment = False
                        i += 2
                        continue
                    else:
                        i += 1
                        continue
                
                # Check for comment starts
                if char == '/':
                    if i + 1 < len(line):
                        if line[i+1] == '/':
                            in_line_comment = True
                            break
                        elif line[i+1] == '*':
                            in_block_comment = True
                            i += 2
                            continue
                
                # Handle strings and chars
                if not in_line_comment and not in_block_comment:
                    if char == '"' and not in_string_single:
                        in_string_double = not in_string_double
                    elif char == "'" and not in_string_double:
                        in_string_single = not in_string_single
                
                # Match braces if not in a string or comment
                if not in_line_comment and not in_block_comment and not in_string_double and not in_string_single:
                    if char == '{':
                        depth += 1
                    elif char == '}':
                        depth -= 1
                        if depth == 0:
                            return line_idx
                
                i += 1
        
        # If no matching brace found, return the last line
        return len(lines) - 1

    def check_syntax_validity(self, code: str) -> bool:
        """
        Perform a basic check for balanced braces, parens, and brackets,
        respecting basic C-style comments and strings.

        Args:
            code: Source code string.

        Returns:
            True if brackets appear balanced, False otherwise.
        """
        brace_count = 0
        paren_count = 0
        bracket_count = 0
        in_string_double = False
        in_string_single = False
        in_line_comment = False
        in_block_comment = False
        escape_next = False

        lines = self._split_into_lines(code)

        for line_idx in range(len(lines)):
            line = lines[line_idx]
            in_line_comment = False  # Reset for each line

            i = 0
            while i < len(line):
                char = line[i]

                # --- State Resets/Updates ---
                if escape_next:
                    escape_next = False
                    i += 1
                    continue
                if char == '\\':
                    escape_next = True
                    i += 1
                    continue

                # --- Comment Handling ---
                if in_line_comment: 
                    break
                if in_block_comment:
                    if char == '*' and i + 1 < len(line) and line[i+1] == '/':
                        in_block_comment = False
                        i += 2
                        continue
                    else:
                        i += 1
                        continue
                if char == '/':
                    if i + 1 < len(line):
                        if line[i+1] == '/':
                            in_line_comment = True
                            break
                        elif line[i+1] == '*':
                            in_block_comment = True
                            i += 2
                            continue

                # --- String/Char Handling ---
                if not in_line_comment and not in_block_comment:
                    if char == '"' and not in_string_single:
                         in_string_double = not in_string_double
                    elif char == "'" and not in_string_double:
                         in_string_single = not in_string_single

                # --- Bracket Counting ---
                if not in_line_comment and not in_block_comment and \
                   not in_string_double and not in_string_single:
                    if char == '{': brace_count += 1
                    elif char == '}': brace_count -= 1
                    elif char == '(': paren_count += 1
                    elif char == ')': paren_count -= 1
                    elif char == '[': bracket_count += 1
                    elif char == ']': bracket_count -= 1

                # Check for immediate imbalance
                if brace_count < 0 or paren_count < 0 or bracket_count < 0:
                    return False

                i += 1

        # Final check: all counts zero, not inside comment/string
        return (brace_count == 0 and paren_count == 0 and bracket_count == 0 and
                not in_string_double and not in_string_single and not in_block_comment)
