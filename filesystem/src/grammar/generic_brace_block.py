"""
Generic parser for languages using curly braces {} to define blocks.
Suitable for C-like languages (C, C++, Java, C#), JavaScript, TypeScript, Rust, Go, etc.
"""

import re
from typing import List, Dict, Optional, Tuple, Any
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

    # Regex to find potential definitions preceding a block or parenthesis
    # Group 1: Optional keywords/modifiers (public, static, etc.)
    # Group 2: Primary keyword (class, function, void, int, etc.) OR potential type
    # Group 3: Element name
    # Group 4: Optional parameter list in parens ()
    # It looks for EITHER `keyword name` OR `potential_type name (...)`
    DEFINITION_PATTERN = re.compile(
        r'^\s*'                                      # Start of line, optional whitespace
        r'((?:(?:public|private|protected|static|final|abstract|virtual|override|async|unsafe|export|const|let|var|pub(?:\([^)]+\))?)\s+)*)?' # Modifiers (Group 1)
        r'(?:'                                       # Non-capturing group for keyword OR type
            r'(' + '|'.join(KEYWORD_TO_TYPE.keys()) + r')\s+' # Keyword (Group 2)
            r'([a-zA-Z_][a-zA-Z0-9_:]*)?'            # Optional Name following keyword (Group 3) - name might be optional for impl etc.
        r'|'                                         # OR
            r'([a-zA-Z_][a-zA-Z0-9_<>,\s:]*)?\s+'    # Potential Type (Group 2 - reused index, but only one branch matches)
            r'([a-zA-Z_][a-zA-Z0-9_:]+)'             # Name following type (Group 3 - reused index)
        r')'
        r'(?:<.*?>)?'                                # Optional generics
        r'(\s*\(.*?\))?'                             # Optional parameter list (Group 4)
        r'(?:\s*:.*?)?'                              # Optional inheritance/supertraits/return type hint before {
        r'(?:\s*where\s*.*?)?'                       # Optional where clause before {
        r'(?:\s*throws\s*.*?)?'                      # Optional throws clause before {
        r'\s*\{'                                     # Must have opening brace eventually on the line or subsequent lines
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
        stack: List[CodeElement] = [] # Track parent elements

        line_idx = 0
        while line_idx < line_count:
            line = lines[line_idx]
            line_num = line_idx + 1 # 1-based

            # --- Simple Comment Skipping ---
            # Basic check, doesn't handle comments after code on same line well
            stripped_line = line.strip()
            if not stripped_line or stripped_line.startswith("//") or stripped_line.startswith("#"): # Common single-line comments
                 line_idx += 1
                 continue
            # Basic block comment start check (doesn't skip the whole block here)
            if stripped_line.startswith("/*"):
                 # We rely on the brace matcher to navigate block comments
                 pass # Don't skip the line, let brace matcher handle it

            # --- Check for Closing Brace ---
            # If a line *primarily* consists of a closing brace, try to pop stack
            # This handles dedenting/closing blocks
            if stripped_line == '}' and stack:
                closed_element = stack.pop()
                # Update end line only if it's later than the current end_line
                closed_element.end_line = max(line_num, closed_element.end_line)
                line_idx += 1
                continue

            # --- Check for Potential Definitions ---
            # Try matching definition pattern over potentially multiple lines
            # in case the opening brace is not on the same line.
            potential_def_lines = []
            potential_def_match = None
            brace_line_idx = -1
            for i in range(line_idx, min(line_idx + 5, line_count)): # Check current and next few lines
                 potential_def_lines.append(lines[i])
                 current_scan_text = "\n".join(potential_def_lines)
                 match = self.DEFINITION_PATTERN.match(current_scan_text)
                 if match:
                      # Found a potential keyword/name pattern, now ensure there's an opening brace
                      brace_match = self.OPEN_BRACE_PATTERN.search(current_scan_text, match.end())
                      if brace_match:
                           potential_def_match = match
                           brace_line_idx = i # The line index where the brace was found
                           break # Found a match with a brace
                 # If the combined lines get too long or complex, stop scanning
                 if len(current_scan_text) > 500: break


            if potential_def_match and brace_line_idx != -1:
                match = potential_def_match
                # Determine keyword, name, element type
                keyword = match.group(2) or match.group(5) # Group 2 from 1st OR, Group 5 from 2nd OR
                name = match.group(3) or match.group(6) # Group 3 from 1st OR, Group 6 from 2nd OR
                params = match.group(4) # Parameter list

                element_type = ElementType.UNKNOWN
                if keyword and keyword in self.KEYWORD_TO_TYPE:
                    element_type = self.KEYWORD_TO_TYPE[keyword]
                elif params is not None: # If it looks like name(...) {, assume FUNCTION
                     element_type = ElementType.FUNCTION
                elif name and name[0].isupper() and not keyword: # Heuristic: Uppercase name often means Type/Class
                     element_type = ElementType.CLASS # Could be struct etc. but CLASS is common

                # If no name extracted but it's an 'impl', generate a placeholder
                if not name and element_type == ElementType.IMPL:
                    name = f"impl_{line_num}" # Placeholder name

                if not name: # Still no name? Skip, likely not a main definition
                    line_idx += 1
                    continue

                # Find the matching closing brace
                # Start searching for the brace from the original line_idx
                # The actual opening brace might be on brace_line_idx
                try:
                    start_brace_line_idx = -1
                    start_brace_col_idx = -1
                    # Find the actual start of the brace
                    temp_scan_idx = line_idx
                    while temp_scan_idx <= brace_line_idx:
                        brace_search = self.OPEN_BRACE_PATTERN.search(lines[temp_scan_idx])
                        if brace_search:
                            start_brace_line_idx = temp_scan_idx
                            start_brace_col_idx = brace_search.start()
                            break
                        temp_scan_idx += 1

                    if start_brace_line_idx == -1: # Should not happen if brace_line_idx was set
                        line_idx += 1
                        continue

                    end_line_idx = self._find_matching_brace(lines, start_brace_line_idx, start_brace_col_idx)

                except Exception as e: # Broad catch during brace finding failure
                     print(f"Warning: Brace matching failed at line {line_num}: {e}")
                     line_idx += 1 # Skip this potential element
                     continue


                # Extract code block
                start_extract_idx = line_idx # Start code from the definition line
                end_extract_idx = end_line_idx
                code_block = self._join_lines(lines[start_extract_idx : end_extract_idx + 1])

                # Determine parent
                parent = stack[-1] if stack else None

                # Adjust element type if nested (e.g., Function inside Class -> Method)
                if element_type == ElementType.FUNCTION and parent and parent.element_type in (ElementType.CLASS, ElementType.INTERFACE, ElementType.STRUCT, ElementType.IMPL, ElementType.TRAIT):
                    element_type = ElementType.METHOD

                # Create metadata
                metadata = {}
                if params:
                    metadata["parameters"] = params.strip()
                # Add modifiers? Group 1 match. Needs parsing.
                modifiers = match.group(1)
                if modifiers:
                    metadata["modifiers"] = modifiers.strip()
                    if 'async' in modifiers: metadata['is_async'] = True
                    if 'static' in modifiers: metadata['is_static'] = True


                # Create element
                element = CodeElement(
                    element_type=element_type,
                    name=name,
                    start_line=line_num, # Definition line
                    end_line=end_line_idx + 1, # Closing brace line
                    code=code_block,
                    parent=parent,
                    metadata=metadata
                )
                self.elements.append(element)

                # Push onto stack as it defines a new scope
                stack.append(element)

                # Advance past the definition line(s), ready to parse inside or after
                line_idx = brace_line_idx + 1 # Start parsing after the line containing the opening brace
                continue # Restart loop for the next line


            # If no definition or closing brace handled, just move to the next line
            line_idx += 1


        # Final check for elements left on stack (unclosed blocks at EOF)
        final_line_num = line_count
        while stack:
            element = stack.pop()
            element.end_line = max(final_line_num, element.end_line)

        return self.elements


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
        depth = 0
        in_string_double = False
        in_string_single = False
        in_char = False # Less common, basic check
        in_line_comment = False
        in_block_comment = False
        escape_next = False

        for line_idx in range(start_line_idx, len(lines)):
            line = lines[line_idx]
            start_index = start_col_idx if line_idx == start_line_idx else 0

            # Reset line comment flag for each new line
            in_line_comment = False

            i = start_index
            while i < len(line):
                char = line[i]
                prev_char = line[i-1] if i > 0 else None

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
                if in_line_comment: # Already in line comment, skip rest of line
                    break # Go to next line

                if in_block_comment:
                    if char == '*' and i + 1 < len(line) and line[i+1] == '/':
                        in_block_comment = False
                        i += 2 # Skip */
                        continue
                    else:
                        i += 1
                        continue # Still inside block comment

                # Check for comment starts
                if char == '/':
                    if i + 1 < len(line):
                        if line[i+1] == '/':
                            in_line_comment = True
                            break # Skip rest of line
                        elif line[i+1] == '*':
                            in_block_comment = True
                            i += 2 # Skip /*
                            continue

                # --- String/Char Handling ---
                # Only toggle if not in a comment
                if not in_line_comment and not in_block_comment:
                    if char == '"' and not in_string_single and not in_char:
                         in_string_double = not in_string_double
                    elif char == "'" and not in_string_double: # Allow single quotes unless in double quotes
                         # Basic char literal toggle (imperfect for multi-char ' ' etc.)
                         in_char = not in_char # Simplistic toggle
                         # Could also be single-quoted string in some languages (JS)
                         in_string_single = not in_string_single

                # --- Brace Matching ---
                # Only match if not in comment or string/char
                if not in_line_comment and not in_block_comment and \
                   not in_string_double and not in_string_single and not in_char:
                    if char == '{':
                        # Need to increment depth even for the starting brace if we re-scan it
                        if line_idx > start_line_idx or i >= start_col_idx:
                            depth += 1
                    elif char == '}':
                        if depth == 0:
                            # Found the matching closing brace
                            return line_idx
                        depth -= 1
                        if depth < 0:
                             # More closing than opening, indicates likely syntax error before this point
                             # print(f"Warning: Unmatched closing brace at line {line_idx+1}, col {i+1}")
                             return line_idx # Return current line as best guess

                i += 1 # Move to next char

            # Reset start col restriction after processing the first line fully
            start_col_idx = 0


        # If loop finishes, matching brace not found (likely EOF)
        # print(f"Warning: No matching closing brace found for opening brace at line {start_line_idx+1}")
        return len(lines) - 1 # Return last line index


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
