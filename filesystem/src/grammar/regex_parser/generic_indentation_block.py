"""
Generic parser for languages using indentation to define blocks.
Primarily suitable for Python, potentially F#, YAML, CoffeeScript.
"""

import re
from typing import List, Dict, Optional, Tuple, Any
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
        r"^\s*(" + "|".join(DEFINITION_KEYWORDS.keys()) + r")\s+"  # Keyword (Group 1)
        r"([a-zA-Z_][a-zA-Z0-9_]*)"  # Name (Group 2)
        r"\s*[:\(]?.*"  # Match parameters or colon, etc., don't strictly parse
    )

    # Docstring pattern (similar to Python)
    DOCSTRING_PATTERN = re.compile(r'^(\s*)(?:\'\'\'|""")')

    # --- Configuration ---
    # Assume a standard indentation width (e.g., 4 spaces).
    # Handling mixed tabs/spaces or variable widths is beyond this generic parser.
    INDENT_WIDTH = 4

    def __init__(self):
        """Initialize the indentation block parser."""
        super().__init__()
        self.language = "indentation_block"
        self.handle_incomplete_code = True
        self._preprocessing_diagnostics = None
        self._was_code_modified = False

    def parse(self, code: str) -> List[CodeElement]:
        """
        Parse indentation-based code and extract structured information.

        Args:
            code: Source code string

        Returns:
            List of identified CodeElement objects
        """
        # First, preprocess the code to handle incomplete syntax if enabled
        if self.handle_incomplete_code:
            code, was_modified, diagnostics = self.preprocess_incomplete_code(code)
            self._was_code_modified = was_modified
            self._preprocessing_diagnostics = diagnostics
            
        self.elements = []
        lines = self._split_into_lines(code)
        line_count = len(lines)

        # Process the top-level block (indent level 0)
        self._parse_block(lines, 0, line_count - 1, 0, None)

        return self.elements

    def _parse_block(
        self,
        lines: List[str],
        start_idx: int,
        end_idx: int,
        expected_indent: int,
        parent: Optional[CodeElement] = None,
    ) -> None:
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
            line_num = line_idx + 1  # 1-based

            # Skip empty lines and comments (basic '#' support)
            stripped_line = line.strip()
            if not stripped_line or stripped_line.startswith("#"):
                line_idx += 1
                continue

            current_indent = self._count_indentation(line)

            # If indentation decreases, we've exited the current block/scope
            if current_indent < expected_indent:
                break  # Let the caller handle the decreased indent

            # If indentation matches, look for definitions at this level
            if current_indent == expected_indent:
                match = self.DEFINITION_PATTERN.match(line)
                if match:
                    keyword = match.group(1)
                    name = match.group(2)
                    element_type = self.DEFINITION_KEYWORDS[keyword]

                    # Determine if it's a method (if parent is class)
                    if (
                        element_type == ElementType.FUNCTION
                        and parent
                        and parent.element_type == ElementType.CLASS
                    ):
                        element_type = ElementType.METHOD

                    # Find the end of this element's block
                    block_end_idx = self._find_block_end(
                        lines, line_idx, current_indent
                    )

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
                        metadata={},
                    )

                    # Check for docstring (simple check on next line)
                    docstring = self._extract_docstring(
                        lines, line_idx + 1, expected_indent + self.INDENT_WIDTH
                    )
                    if docstring:
                        element.metadata["docstring"] = docstring

                    self.elements.append(element)

                    # Recursively parse the inner block
                    self._parse_block(
                        lines,
                        line_idx + 1,
                        block_end_idx,
                        expected_indent + self.INDENT_WIDTH,
                        element,
                    )

                    # Skip past the parsed block
                    line_idx = block_end_idx + 1
                    continue  # Continue loop from the line after the block

                # TODO: Could add handling for simple variable assignments at this level
                # variable_match = self.variable_pattern.match(line) ...

            # If indentation increases unexpectedly or line doesn't match, just advance
            line_idx += 1

    def _find_block_end(
        self, lines: List[str], start_idx: int, block_indent: int
    ) -> int:
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
            if not stripped or stripped.startswith("#"):
                continue
            current_indent = self._count_indentation(line)
            if current_indent > block_indent:
                body_indent = current_indent
                break
            elif current_indent <= block_indent:  # No body found, or dedent immediately
                return start_idx

        if body_indent == -1:  # No indented body found after the definition line
            return start_idx

        # Find the last line that has at least the body_indent level
        last_line_idx = start_idx  # Default to start line if only definition exists
        for i in range(start_idx + 1, line_count):
            line = lines[i]
            current_indent = self._count_indentation(line)
            stripped = line.strip()

            # Skip blanks/comments *unless* they might be inside the block
            if not stripped or stripped.startswith("#"):
                # Keep track if the previous line was part of the block
                if i > 0 and self._count_indentation(lines[i - 1]) >= body_indent:
                    # Assume blank/comment line is part of block if previous was
                    last_line_idx = i
                continue

            # If indentation is sufficient, it's part of the block
            if current_indent >= body_indent:
                last_line_idx = i
            # If indentation drops below the block's body level, the block ended *before* this line
            elif current_indent <= block_indent:
                return last_line_idx  # The previous line was the end

        # If we reach the end of the file, the block ended on the last line found
        return last_line_idx

    def _extract_docstring(
        self, lines: List[str], start_idx: int, expected_indent: int
    ) -> Optional[str]:
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
            if not stripped or stripped.startswith("#"):
                continue

            # Check if line starts with a docstring delimiter
            if stripped.startswith("'''") or stripped.startswith('"""'):
                delimiter = "'''" if "'''" in stripped else '"""'

                # Single line docstring
                if (
                    stripped.endswith(delimiter) and len(stripped) > 6
                ):  # At least '''x'''
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

        return None  # No docstring found

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
        indent_stack = [0]  # Stack of expected indentation levels

        # Check for mixed tabs and spaces
        uses_tabs = False
        uses_spaces = False

        for line in lines:
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue

            # Check for mixed indentation
            leading_whitespace = line[: len(line) - len(line.lstrip())]
            if "\t" in leading_whitespace:
                uses_tabs = True
            if " " in leading_whitespace:
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
                    return False  # Indentation decreased to unexpected level
            # else: current_indent == last_indent, which is fine

        return True  # If we reach the end without errors

    def preprocess_incomplete_code(self, code: str) -> Tuple[str, bool, Dict[str, Any]]:
        """
        Preprocess indentation-based code that might be incomplete or have syntax errors.
        
        Args:
            code: The original code that might have issues
            
        Returns:
            Tuple of (preprocessed code, was_modified flag, diagnostics)
        """
        diagnostics = {
            "fixes_applied": [],
            "confidence_score": 1.0,
        }
        
        modified = False
        
        # Apply basic fixes
        code, basic_modified = self._apply_basic_fixes(code)
        if basic_modified:
            modified = True
            diagnostics["fixes_applied"].append("basic_syntax_fixes")
        
        # Apply indentation-specific fixes
        code, indent_modified, indent_diagnostics = self._fix_indentation_specific(code)
        if indent_modified:
            modified = True
            diagnostics["fixes_applied"].append("indentation_specific_fixes")
            diagnostics.update(indent_diagnostics)
        
        # Apply structural fixes
        code, struct_modified, struct_diagnostics = self._fix_structural_issues(code)
        if struct_modified:
            modified = True
            diagnostics["fixes_applied"].append("structural_fixes")
            diagnostics.update(struct_diagnostics)
        
        # Calculate overall confidence
        if modified:
            # More fixes = less confidence
            num_fixes = len(diagnostics["fixes_applied"])
            diagnostics["confidence_score"] = max(0.3, 1.0 - (num_fixes * 0.2))
        
        return code, modified, diagnostics
    
    def _apply_basic_fixes(self, code: str) -> Tuple[str, bool]:
        """Apply basic syntax fixes for indentation-based languages."""
        modified = False
        
        # Fix indentation consistency
        lines, indent_modified = self._fix_indentation_consistency(code.splitlines())
        if indent_modified:
            code = '\n'.join(lines)
            modified = True
        
        # Recover incomplete blocks
        code, blocks_modified = self._recover_incomplete_blocks(code)
        modified = modified or blocks_modified
        
        return code, modified
    
    def _fix_indentation_consistency(self, lines: List[str]) -> Tuple[List[str], bool]:
        """
        Ensure consistent indentation throughout the code.
        
        Args:
            lines: Source code lines that may have inconsistent indentation
            
        Returns:
            Tuple of (fixed lines, was_modified flag)
        """
        if not lines:
            return lines, False
            
        modified = False
        fixed_lines = lines.copy()
        
        # Determine most common indentation unit (2, 4, or 8 spaces)
        indent_differences = []
        current_indent = 0
        
        for i, line in enumerate(lines):
            if not line.strip():  # Skip empty lines
                continue
                
            line_indent = len(line) - len(line.lstrip())
            if line_indent > current_indent:
                diff = line_indent - current_indent
                if diff > 0:  # Only consider positive differences
                    indent_differences.append(diff)
            current_indent = line_indent
        
        # Determine most common indent unit
        if not indent_differences:
            indent_unit = self.INDENT_WIDTH  # Default
        else:
            # Find the most common value among 2, 4, and 8
            counts = {2: 0, 4: 0, 8: 0}
            for diff in indent_differences:
                closest = min(counts.keys(), key=lambda x: abs(x - diff))
                counts[closest] += 1
            indent_unit = max(counts, key=counts.get)
        
        # Now fix lines with inconsistent indentation
        for i in range(1, len(lines)):
            if not lines[i].strip():  # Skip empty lines
                continue
                
            current_indent = len(lines[i]) - len(lines[i].lstrip())
            prev_indent = len(lines[i-1]) - len(lines[i-1].lstrip())
            
            # Check if this line should be indented relative to previous
            prev_line_ends_with_colon = lines[i-1].rstrip().endswith(':')
            
            if prev_line_ends_with_colon and current_indent <= prev_indent:
                # Line after a colon should be indented
                fixed_lines[i] = ' ' * (prev_indent + indent_unit) + lines[i].lstrip()
                modified = True
            elif current_indent > prev_indent and (current_indent - prev_indent) % indent_unit != 0:
                # Indentation increase should be a multiple of indent_unit
                new_indent = prev_indent + indent_unit * ((current_indent - prev_indent) // indent_unit + 1)
                fixed_lines[i] = ' ' * new_indent + lines[i].lstrip()
                modified = True
        
        return fixed_lines, modified
    
    def _recover_incomplete_blocks(self, code: str) -> Tuple[str, bool]:
        """
        Fix code with incomplete blocks, particularly focusing on indentation-based languages.
        
        Args:
            code: Source code that may have incomplete blocks
            
        Returns:
            Tuple of (recovered code, was_modified flag)
        """
        lines = code.splitlines()
        modified = False
        
        # Check for definition at the end of the file without content
        if lines and len(lines) > 0:
            last_line = lines[-1].strip()
            
            # In Python-like languages, a line ending with a colon should have content after it
            if last_line.endswith(':'):
                # Add a minimal block content (e.g., 'pass' for Python)
                indent = len(lines[-1]) - len(lines[-1].lstrip())
                lines.append(' ' * (indent + self.INDENT_WIDTH) + 'pass')
                modified = True
        
        return '\n'.join(lines), modified
    
    def _fix_indentation_specific(self, code: str) -> Tuple[str, bool, Dict[str, Any]]:
        """
        Apply fixes specific to indentation-based languages.
        
        Args:
            code: Source code to fix
            
        Returns:
            Tuple of (fixed code, was_modified flag, diagnostics)
        """
        lines = code.splitlines()
        modified = False
        diagnostics = {"indentation_fixes": []}
        
        # Check for incorrect dedents
        stack = [0]  # Stack of indentation levels, starting with 0
        fixed_lines = []
        
        for i, line in enumerate(lines):
            if not line.strip():  # Skip empty lines
                fixed_lines.append(line)
                continue
                
            current_indent = len(line) - len(line.lstrip())
            
            # If indentation decreases, it should match one of the previous levels
            if current_indent < stack[-1]:
                # Find the closest matching indent level in the stack
                while stack and current_indent < stack[-1]:
                    stack.pop()
                
                if not stack or current_indent != stack[-1]:
                    # Indentation doesn't match any previous level - fix it
                    if not stack:
                        # If stack is empty, default to 0
                        proper_indent = 0
                    else:
                        # Use the most recent matching level
                        proper_indent = stack[-1]
                    
                    fixed_lines.append(' ' * proper_indent + line.lstrip())
                    modified = True
                    diagnostics["indentation_fixes"].append(f"fixed_dedent_at_line_{i+1}")
                    continue
            
            # If indentation increases, add the new level to the stack
            elif current_indent > stack[-1]:
                stack.append(current_indent)
            
            fixed_lines.append(line)
        
        if modified:
            code = '\n'.join(fixed_lines)
        
        return code, modified, diagnostics
    
    def _fix_structural_issues(self, code: str) -> Tuple[str, bool, Dict[str, Any]]:
        """
        Fix structural issues in the code based on indentation patterns.
        
        Args:
            code: Source code to fix
            
        Returns:
            Tuple of (fixed code, was_modified flag, diagnostics)
        """
        # Analyze code structure
        structure_analysis = self._analyze_structure(code)
        diagnostics = {"structure_analysis": structure_analysis}
        
        # Define blocks that might be incomplete
        lines = code.splitlines()
        modified = False
        fixed_lines = lines.copy()
        
        # Process block structures
        for block_info in structure_analysis.get("blocks", []):
            if block_info.get("is_incomplete", False):
                # Add missing content to incomplete blocks
                block_end = block_info.get("end_line", 0)
                if block_end < len(lines):
                    indent_level = block_info.get("indent_level", 0)
                    # Add a 'pass' statement if the block is empty
                    fixed_lines.insert(block_end + 1, ' ' * (indent_level + self.INDENT_WIDTH) + 'pass')
                    modified = True
        
        if modified:
            code = '\n'.join(fixed_lines)
        
        return code, modified, diagnostics
    
    def _analyze_structure(self, code: str) -> Dict[str, Any]:
        """
        Analyze the structural elements of indentation-based code.
        
        Args:
            code: Source code to analyze
            
        Returns:
            Dictionary with structural analysis
        """
        lines = code.splitlines()
        result = {
            "blocks": [],
            "max_indent_level": 0,
            "inconsistent_indents": []
        }
        
        # Track blocks based on indentation changes
        current_indent = 0
        block_stack = []  # Stack of (line_idx, indent_level) tuples
        
        for i, line in enumerate(lines):
            if not line.strip():
                continue
                
            line_indent = len(line) - len(line.lstrip())
            
            # Track maximum indent level
            if line_indent > result["max_indent_level"]:
                result["max_indent_level"] = line_indent
            
            # Check for new block (indentation increase)
            if line_indent > current_indent:
                # Previous line started a new block
                if i > 0 and lines[i-1].strip().endswith(':'):
                    block_stack.append((i-1, current_indent))
                    
            # Check for end of block(s) (indentation decrease)
            elif line_indent < current_indent:
                # Close all blocks that end with this dedent
                while block_stack and block_stack[-1][1] >= line_indent:
                    start_idx, indent = block_stack.pop()
                    # Record the block
                    block_info = {
                        "start_line": start_idx + 1,  # 1-indexed line number
                        "end_line": i,  # End line (exclusive)
                        "indent_level": indent,
                        "is_incomplete": (i - start_idx) <= 1  # Block has no content
                    }
                    result["blocks"].append(block_info)
            
            # Check for inconsistent indentation
            if block_stack and line_indent > current_indent:
                expected_indent = current_indent + self.INDENT_WIDTH
                if line_indent != expected_indent:
                    result["inconsistent_indents"].append({
                        "line": i + 1,  # 1-indexed line number
                        "actual": line_indent,
                        "expected": expected_indent
                    })
            
            current_indent = line_indent
        
        # Close any remaining open blocks
        end_line = len(lines)
        while block_stack:
            start_idx, indent = block_stack.pop()
            block_info = {
                "start_line": start_idx + 1,
                "end_line": end_line,
                "indent_level": indent,
                "is_incomplete": (end_line - start_idx) <= 1
            }
            result["blocks"].append(block_info)
        
        return result
    
    def extract_metadata(self, code: str, line_idx: int) -> Dict[str, Any]:
        """
        Extract metadata from indentation-based code at the given line index.
        
        Args:
            code: The full source code
            line_idx: The line index where the symbol definition starts
            
        Returns:
            Dictionary containing extracted metadata
        """
        lines = code.splitlines()
        if line_idx >= len(lines):
            return {}
        
        metadata = {}
        
        # Extract docstring by checking the first non-empty line after definition
        docstring = self._extract_docstring(lines, line_idx + 1, self._count_indentation(lines[line_idx]) + self.INDENT_WIDTH)
        if docstring:
            metadata["docstring"] = docstring
        
        # Extract decorators (for Python-like languages)
        decorators = []
        current_idx = line_idx - 1
        while current_idx >= 0:
            line = lines[current_idx].strip()
            if line.startswith('@'):
                # Simple decorator detection
                decorators.insert(0, line[1:])  # Remove the @ symbol
                current_idx -= 1
            else:
                break
        
        if decorators:
            metadata["decorators"] = decorators
        
        # Extract function parameters for Python-like definitions
        definition_line = lines[line_idx]
        if '(' in definition_line and ')' in definition_line:
            params_match = re.search(r'\(([^)]*)\)', definition_line)
            if params_match:
                metadata["parameters"] = params_match.group(1).strip()
        
        # Extract return type annotation (Python 3 style)
        if '->' in definition_line:
            return_match = re.search(r'->([^:]+)', definition_line)
            if return_match:
                metadata["return_type"] = return_match.group(1).strip()
        
        # Extract type annotations for parameters (Python 3 style)
        type_annotations = {}
        
        if '(' in definition_line and ':' in definition_line:
            # Extract parameter section
            param_section = definition_line.split('(', 1)[1].split(')', 1)[0]
            
            # Find parameters with type annotations
            for param in param_section.split(','):
                param = param.strip()
                if ':' in param:
                    name, type_ann = param.split(':', 1)
                    type_annotations[name.strip()] = type_ann.strip()
        
        if type_annotations:
            metadata["type_annotations"] = type_annotations
        
        return metadata
