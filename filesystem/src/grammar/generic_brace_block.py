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

        # Namespaces/Modules
        "namespace": ElementType.NAMESPACE,
        "module": ElementType.MODULE,     # JS/Rust (can be complex)

        # Others (Less common block starters, maybe treat as UNKNOWN or skip)
        # "if": ElementType.UNKNOWN,
        # "for": ElementType.UNKNOWN,
        # "while": ElementType.UNKNOWN,
        # "switch": ElementType.UNKNOWN,
    }

    # Regex to find potential definitions preceding a block
    DEFINITION_PATTERN = re.compile(
        r'^\s*'                                      # Start of line, optional whitespace
        r'((?:(?:public|private|protected|static|final|abstract|virtual|override|async|unsafe|export|const|let|var|pub(?:\([^)]+\))?)\s+)*)?' # Modifiers (Group 1)
        r'(?:'                                       # Non-capturing group for keyword OR type
            r'(' + '|'.join(KEYWORD_TO_TYPE.keys()) + r')\s+' # Keyword (Group 2)
            r'([a-zA-Z_][a-zA-Z0-9_:]*)?'            # Optional Name following keyword (Group 3)
        r'|'                                         # OR
            r'([a-zA-Z_][a-zA-Z0-9_<>,\s:\.]*)\s+'   # Potential Type (Group 4)
            r'([a-zA-Z_][a-zA-Z0-9_:]+)'             # Name following type (Group 5)
        r')'
        r'(?:<.*?>)?'                                # Optional generics
        r'(\s*\([^{;]*?\))?'                         # Optional parameter list (Group 6) - matches until { or ;
        r'(?:\s*:.*?)?'                              # Optional inheritance/supertraits/return type hint before {
        r'(?:\s*where\s*.*?)?'                       # Optional where clause before {
        r'(?:\s*throws\s*.*?)?'                      # Optional throws clause before {
        r'\s*\{'                                     # Must have opening brace eventually on the line or subsequent lines
    )

    # Function pattern - more specific than the general definition pattern
    FUNCTION_PATTERN = re.compile(
        r'^\s*'                                          # Start of line, optional whitespace
        r'((?:(?:public|private|protected|static|final|abstract|virtual|override|async|unsafe|export)\s+)*)?' # Modifiers
        r'(?:(?:function|fn|func)\s+)?'                  # Optional function keyword
        r'([a-zA-Z_][a-zA-Z0-9_:]*)'                     # Function name
        r'\s*\(([^)]*)\)'                                # Params in parentheses
        r'(?:\s*(?:->|:)\s*[a-zA-Z_][a-zA-Z0-9_<>,\s:\.]*)?'  # Optional return type
        r'\s*\{'                                          # Opening brace
    )

    # Pattern just to find an opening brace to start brace matching
    OPEN_BRACE_PATTERN = re.compile(r'\{')

    def __init__(self):
        super().__init__()
        # We won't perform full language-specific comment/string stripping
        # The brace matching logic will have basic handling for them.

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
        line_count = len(lines)
        
        # Parse the code for brace blocks
        self._parse_code_blocks(lines, line_count)
        
        # Process elements to establish proper parent-child relationships
        self._establish_parent_child_relationships()
        
        return self.elements

    def _parse_code_blocks(self, lines: List[str], line_count: int):
        """Parse the lines of code to identify code blocks based on braces."""
        line_idx = 0
        while line_idx < line_count:
            line = lines[line_idx]
            line_num = line_idx + 1 # 1-based
            
            # Skip empty lines and comments
            stripped_line = line.strip()
            if not stripped_line or stripped_line.startswith("//") or stripped_line.startswith("#"):
                line_idx += 1
                continue
            
            # Try to match a function definition first (most common)
            func_element = self._try_match_function(lines, line_idx, line_count)
            if func_element:
                self.elements.append(func_element)
                line_idx = func_element.end_line  # Move past the function
                continue
            
            # Try to match other block definitions like class, struct, etc.
            element = self._try_match_definition(lines, line_idx, line_count)
            if element:
                self.elements.append(element)
                line_idx = element.end_line  # Move past the element
                continue
                
            # No match found, move to next line
            line_idx += 1

    def _try_match_function(self, lines: List[str], start_idx: int, line_count: int) -> Optional[CodeElement]:
        """
        Try to match a function definition at the given line index.
        
        Args:
            lines: The lines of code
            start_idx: Starting line index to check
            line_count: Total number of lines
            
        Returns:
            A CodeElement for the function if found, None otherwise
        """
        for i in range(min(3, line_count - start_idx)):  # Look ahead up to 3 lines
            look_ahead = '\n'.join(lines[start_idx:start_idx+i+1])
            match = self.FUNCTION_PATTERN.match(look_ahead)
            if match and '{' in look_ahead:
                modifiers, name, params = match.groups()
                
                # Find the opening brace and its matching closing brace
                brace_line_idx, brace_col_idx = self._find_opening_brace(lines, start_idx, min(start_idx+i+5, line_count))
                if brace_line_idx == -1:
                    return None
                    
                try:
                    end_line_idx = self._find_matching_brace(lines, brace_line_idx, brace_col_idx)
                except Exception as e:
                    print(f"Warning: Brace matching failed at line {start_idx+1}: {e}")
                    return None
                
                code_block = self._join_lines(lines[start_idx:end_line_idx+1])
                
                metadata = {}
                if params:
                    metadata["parameters"] = params.strip()
                if modifiers:
                    metadata["modifiers"] = modifiers.strip()
                    if 'async' in modifiers: metadata['is_async'] = True
                    if 'static' in modifiers: metadata['is_static'] = True
                
                element_type = ElementType.FUNCTION
                element = CodeElement(
                    element_type=element_type,
                    name=name,
                    start_line=start_idx+1,
                    end_line=end_line_idx+1,
                    code=code_block,
                    parent=None,  # Will be set in post-processing
                    metadata=metadata
                )
                
                return element
        
        return None

    def _try_match_definition(self, lines: List[str], start_idx: int, line_count: int) -> Optional[CodeElement]:
        """
        Try to match a class, struct, or other block definition.
        
        Args:
            lines: The lines of code
            start_idx: Starting line index to check
            line_count: Total number of lines
            
        Returns:
            A CodeElement for the definition if found, None otherwise
        """
        for i in range(min(5, line_count - start_idx)):  # Look ahead up to 5 lines
            look_ahead = '\n'.join(lines[start_idx:start_idx+i+1])
            if len(look_ahead) > 500:  # Skip if too long (to avoid expensive regex on large blocks)
                continue
                
            match = self.DEFINITION_PATTERN.match(look_ahead)
            if match and '{' in look_ahead:
                # Parse the match groups
                modifiers = match.group(1) or ""
                keyword = match.group(2)  # From first branch
                name_after_keyword = match.group(3)  # From first branch
                type_name = match.group(4)  # From second branch
                name_after_type = match.group(5)  # From second branch
                params = match.group(6)  # Parameter list
                
                # Determine element name and type
                name = name_after_keyword or name_after_type
                element_type = ElementType.UNKNOWN
                
                if keyword and keyword in self.KEYWORD_TO_TYPE:
                    element_type = self.KEYWORD_TO_TYPE[keyword]
                elif params is not None:  # If it has parameters, likely a function
                    element_type = ElementType.FUNCTION
                elif name and name[0].isupper() and not keyword:
                    # Heuristic: Uppercase name without keyword often means Type/Class
                    element_type = ElementType.CLASS
                
                # Special case for impl blocks in Rust
                if element_type == ElementType.IMPL and not name:
                    name = f"impl_{start_idx+1}"
                
                if not name:  # Skip if no name found
                    return None
                
                # Find the opening brace and its matching closing brace
                brace_line_idx, brace_col_idx = self._find_opening_brace(lines, start_idx, min(start_idx+i+5, line_count))
                if brace_line_idx == -1:
                    return None
                    
                try:
                    end_line_idx = self._find_matching_brace(lines, brace_line_idx, brace_col_idx)
                except Exception as e:
                    print(f"Warning: Brace matching failed at line {start_idx+1}: {e}")
                    return None
                
                code_block = self._join_lines(lines[start_idx:end_line_idx+1])
                
                metadata = {}
                if params:
                    metadata["parameters"] = params.strip()
                if modifiers:
                    metadata["modifiers"] = modifiers.strip()
                    if 'async' in modifiers: metadata['is_async'] = True
                    if 'static' in modifiers: metadata['is_static'] = True
                
                element = CodeElement(
                    element_type=element_type,
                    name=name,
                    start_line=start_idx+1,
                    end_line=end_line_idx+1,
                    code=code_block,
                    parent=None,  # Will be set in post-processing
                    metadata=metadata
                )
                
                return element
        
        return None

    def _find_opening_brace(self, lines: List[str], start_idx: int, end_idx: int) -> Tuple[int, int]:
        """
        Find the position of the opening brace in the given line range.
        
        Args:
            lines: The lines of code
            start_idx: Starting line index to check
            end_idx: Ending line index (exclusive)
            
        Returns:
            A tuple of (line_idx, col_idx) for the first opening brace found,
            or (-1, -1) if no brace is found.
        """
        for i in range(start_idx, min(end_idx, len(lines))):
            line = lines[i]
            if '{' in line:
                # Skip if the line is a comment
                if line.strip().startswith(('//','/*','*/')):
                    continue
                
                # Find the opening brace position
                match = self.OPEN_BRACE_PATTERN.search(line)
                if match:
                    return i, match.start()
        
        return -1, -1

    def _establish_parent_child_relationships(self):
        """Establish parent-child relationships between elements based on code spans."""
        # Sort elements by start line, then by end line (larger spans first)
        sorted_elements = sorted(self.elements, key=lambda e: (e.start_line, -e.end_line))
        
        # Process method elements
        for child in sorted_elements:
            # Skip elements that already have a parent assigned
            if child.parent:
                continue
                
            # Find the most immediate parent that contains this element
            best_parent = None
            min_container_size = float('inf')
            
            for potential_parent in sorted_elements:
                if potential_parent == child:
                    continue
                    
                # Check if potential_parent contains child
                if (potential_parent.start_line <= child.start_line and 
                    potential_parent.end_line >= child.end_line):
                    # Calculate container size (smaller is better for immediate parent)
                    container_size = (potential_parent.end_line - potential_parent.start_line)
                    
                    if container_size < min_container_size:
                        min_container_size = container_size
                        best_parent = potential_parent
            
            # Set parent and adjust element type if needed
            if best_parent:
                child.parent = best_parent
                
                # Add to parent's children list
                if child not in best_parent.children:
                    best_parent.children.append(child)
                
                # Adjust element type for functions inside class-like containers
                if (child.element_type == ElementType.FUNCTION and 
                    best_parent.element_type in (ElementType.CLASS, ElementType.INTERFACE, 
                                               ElementType.STRUCT, ElementType.IMPL, 
                                               ElementType.TRAIT)):
                    child.element_type = ElementType.METHOD

    def _find_matching_brace(self, lines: List[str], start_line_idx: int, start_col_idx: int) -> int:
        """
        Find the line index of the matching closing brace '}'.
        Handles basic nested braces, C-style comments, and simple strings.

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
        in_char = False
        in_line_comment = False
        in_block_comment = False
        escape_next = False

        for line_idx in range(start_line_idx, len(lines)):
            line = lines[line_idx]
            start_index = (start_col_idx + 1) if line_idx == start_line_idx else 0  # Start after the opening brace on first line
            
            # Reset line comment flag for each new line
            in_line_comment = False
            
            i = start_index
            while i < len(line):
                char = line[i]
                prev_char = line[i-1] if i > 0 else None
                
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
                    if char == '"' and not in_string_single and not in_char:
                        in_string_double = not in_string_double
                    elif char == "'" and not in_string_double:
                        # Toggle string/char markers
                        in_char = not in_char
                        in_string_single = not in_string_single
                
                # Match braces if not in a string or comment
                if not in_line_comment and not in_block_comment and not in_string_double and not in_string_single and not in_char:
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
        in_char = False
        in_line_comment = False
        in_block_comment = False
        escape_next = False

        lines = self._split_into_lines(code)

        for line_idx in range(len(lines)):
            line = lines[line_idx]
            in_line_comment = False # Reset for each line

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
                if in_line_comment: break
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
                    if char == '"' and not in_string_single and not in_char:
                         in_string_double = not in_string_double
                    elif char == "'" and not in_string_double:
                         in_char = not in_char
                         in_string_single = not in_string_single

                # --- Bracket Counting ---
                if not in_line_comment and not in_block_comment and \
                   not in_string_double and not in_string_single and not in_char:
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
                not in_string_double and not in_string_single and not in_char and
                not in_block_comment)
