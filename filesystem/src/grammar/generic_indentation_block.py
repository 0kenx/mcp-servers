"""
Generic parser for languages using indentation to define blocks.
Primarily suitable for Python, potentially F#, YAML, CoffeeScript.
"""

import re
from typing import List, Dict, Optional, Tuple, Set, Any
from .base import BaseParser, CodeElement, ElementType

class IndentationBlockParser(BaseParser):
    """
    Generic parser for indentation-delimited languages. Identifies blocks based on
    indentation changes following common keywords. Assumes consistent indentation.
    """

    # Keywords that typically define a named block in indentation-based languages
    DEFINITION_KEYWORDS: Dict[str, ElementType] = {
        "def": ElementType.FUNCTION,
        "class": ElementType.CLASS,
        # Add other potential keywords if needed for broader (but less precise) use
        # "module": ElementType.MODULE, # Example for hypothetical language
    }

    # Regex to capture the name after a definition keyword
    # Group 1: Keyword
    # Group 2: Name
    DEFINITION_PATTERN = re.compile(
        r'^\s*(' + '|'.join(DEFINITION_KEYWORDS.keys()) + r')\s+' # Keyword (Group 1)
        r'([a-zA-Z_][a-zA-Z0-9_]*)'                       # Name (Group 2)
        r'\s*[:\(]?.*' # Match parameters or colon, etc., don't strictly parse
    )

    # Docstring pattern (similar to Python)
    DOCSTRING_PATTERN = re.compile(r'^(\s*)(?:\'\'\'|""")')

    # --- Configuration ---
    # Assume a standard indentation width (e.g., 4 spaces).
    # Handling mixed tabs/spaces or variable widths is beyond this generic parser.
    INDENT_WIDTH = 4

    def __init__(self):
        super().__init__()

    def parse(self, code: str) -> List[CodeElement]:
        """
        Parse indentation-based code and extract structured information.

        Args:
            code: Source code string

        Returns:
            List of identified CodeElement objects
        """
        self.elements = []
        lines = self._split_into_lines(code)
        line_count = len(lines)

        # Process the top-level block (indent level 0)
        self._parse_block(lines, 0, line_count - 1, 0, None)

        return self.elements

    def _parse_block(self, lines: List[str], start_idx: int, end_idx: int,
                    expected_indent: int, parent: Optional[CodeElement] = None) -> None:
        """
        Recursively parse a block of code expected at a specific indentation level.

        Args:
            lines: List of all code lines.
            start_idx: Starting line index for this block scan.
            end_idx: Ending line index for this block scan.
            expected_indent: The indentation level expected for elements in this block.
            parent: The parent CodeElement for elements found in this block.
        """
        line_idx = start_idx
        while line_idx <= end_idx:
            line = lines[line_idx]
            line_num = line_idx + 1 # 1-based

            # Skip empty lines and comments (basic '#' support)
            stripped_line = line.strip()
            if not stripped_line or stripped_line.startswith('#'):
                line_idx += 1
                continue

            current_indent = self._count_indentation(line)

            # If indentation decreases, we've exited the current block/scope
            if current_indent < expected_indent:
                break # Let the caller handle the decreased indent

            # If indentation matches, look for definitions at this level
            if current_indent == expected_indent:
                match = self.DEFINITION_PATTERN.match(line)
                if match:
                    keyword = match.group(1)
                    name = match.group(2)
                    element_type = self.DEFINITION_KEYWORDS[keyword]

                    # Determine if it's a method (if parent is class)
                    if element_type == ElementType.FUNCTION and parent and parent.element_type == ElementType.CLASS:
                         element_type = ElementType.METHOD

                    # Find the end of this element's block
                    block_end_idx = self._find_block_end(lines, line_idx, current_indent)

                    # Extract code
                    element_code = self._join_lines(lines[line_idx : block_end_idx + 1])

                    # Create element
                    element = CodeElement(
                        element_type=element_type,
                        name=name,
                        start_line=line_num,
                        end_line=block_end_idx + 1,
                        code=element_code,
                        parent=parent,
                        metadata={}
                    )

                    # Check for docstring (simple check on next line)
                    docstring = self._extract_docstring(lines, line_idx + 1, expected_indent + self.INDENT_WIDTH)
                    if docstring:
                        element.metadata["docstring"] = docstring

                    self.elements.append(element)

                    # Recursively parse the inner block
                    self._parse_block(lines, line_idx + 1, block_end_idx,
                                      expected_indent + self.INDENT_WIDTH, element)

                    # Skip past the parsed block
                    line_idx = block_end_idx + 1
                    continue # Continue loop from the line after the block

                # TODO: Could add handling for simple variable assignments at this level
                # variable_match = self.variable_pattern.match(line) ...

            # If indentation increases unexpectedly or line doesn't match, just advance
            line_idx += 1


    def _find_block_end(self, lines: List[str], start_idx: int, block_indent: int) -> int:
        """
        Find the end of an indented block.

        Args:
            lines: List of all code lines.
            start_idx: The line index where the block definition starts.
            block_indent: The indentation level of the block definition line.

        Returns:
            The line index of the last line belonging to this block.
        """
        line_count = len(lines)
        # Find the expected indentation of the block's body
        body_indent = -1
        for i in range(start_idx + 1, line_count):
            line = lines[i]
            stripped = line.strip()
            if not stripped or stripped.startswith('#'):
                continue
            current_indent = self._count_indentation(line)
            if current_indent > block_indent:
                body_indent = current_indent
                break
            elif current_indent <= block_indent: # No body found, or dedent immediately
                return start_idx

        if body_indent == -1: # No indented body found after the definition line
            return start_idx

        # Find the last line that has at least the body_indent level
        last_line_idx = start_idx # Default to start line if only definition exists
        for i in range(start_idx + 1, line_count):
            line = lines[i]
            current_indent = self._count_indentation(line)
            stripped = line.strip()

            # Skip blanks/comments *unless* they might be inside the block
            if not stripped or stripped.startswith('#'):
                 # Keep track if the previous line was part of the block
                 if i > 0 and self._count_indentation(lines[i-1]) >= body_indent:
                      # Assume blank/comment line is part of block if previous was
                      last_line_idx = i
                 continue

            # If indentation is sufficient, it's part of the block
            if current_indent >= body_indent:
                last_line_idx = i
            # If indentation drops below the block's body level, the block ended *before* this line
            elif current_indent <= block_indent:
                return last_line_idx # The previous line was the end

        # If we reach the end of the file, the block ended on the last line found
        return last_line_idx


    def _extract_docstring(self, lines: List[str], start_idx: int, expected_indent: int) -> Optional[str]:
        """
        Extract a potential docstring starting at start_idx. Very basic version.

        Args:
            lines: List of code lines.
            start_idx: Index to start looking from.
            expected_indent: Expected indentation level for the docstring.

        Returns:
            Docstring text if found, None otherwise.
        """
        # First, let's check a few lines ahead for a docstring
        for i in range(start_idx, min(start_idx + 5, len(lines))):
            if i >= len(lines):
                continue
                
            line = lines[i]
            stripped = line.strip()
            
            # Skip empty lines and comments
            if not stripped or stripped.startswith('#'):
                continue
                
            # Check if line starts with a docstring delimiter
            if stripped.startswith("'''") or stripped.startswith('"""'):
                delimiter = "'''" if "'''" in stripped else '"""'
                
                # Single line docstring
                if stripped.endswith(delimiter) and len(stripped) > 6:  # At least '''x'''
                    return stripped
                    
                # Multi-line docstring
                doc_lines = [line]
                for j in range(i + 1, len(lines)):
                    current_line = lines[j]
                    doc_lines.append(current_line)
                    if delimiter in current_line:
                        # Found the end delimiter
                        return self._join_lines(doc_lines).strip()
                break
                
        return None # No docstring found


    def check_syntax_validity(self, code: str) -> bool:
        """
        Basic check for indentation consistency. Returns True if indentation
        only increases or decreases relative to parent blocks, False on
        unexpected indentation changes. Also checks for mixed tabs and spaces.

        Args:
            code: Source code string.

        Returns:
            True if indentation seems consistent, False otherwise.
        """
        lines = self._split_into_lines(code)
        indent_stack = [0] # Stack of expected indentation levels
        
        # Check for mixed tabs and spaces
        uses_tabs = False
        uses_spaces = False
        
        for line in lines:
            stripped = line.strip()
            if not stripped or stripped.startswith('#'):
                continue
                
            # Check for mixed indentation
            leading_whitespace = line[:len(line) - len(line.lstrip())]
            if '\t' in leading_whitespace:
                uses_tabs = True
            if ' ' in leading_whitespace:
                uses_spaces = True
                
            # If both tabs and spaces are used for indentation, it's inconsistent
            if uses_tabs and uses_spaces:
                return False

            current_indent = self._count_indentation(line)
            last_indent = indent_stack[-1]

            if current_indent > last_indent:
                # Indentation increased, push new level
                indent_stack.append(current_indent)
            elif current_indent < last_indent:
                # Indentation decreased, pop until we find matching level
                while indent_stack and indent_stack[-1] > current_indent:
                    indent_stack.pop()
                # After popping, current indent must match the new top level
                if not indent_stack or indent_stack[-1] != current_indent:
                    return False # Indentation decreased to unexpected level
            # else: current_indent == last_indent, which is fine

        return True # If we reach the end without errors
