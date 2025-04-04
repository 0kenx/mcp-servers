"""
Python language parser for extracting structured information from Python code.

This module provides a comprehensive parser for Python code that can handle
incomplete or syntactically incorrect code, extract rich metadata, and
build a structured representation of the code elements.
"""

import re
from typing import List, Dict, Optional, Tuple, Any, Set
from .base import BaseParser, CodeElement, ElementType


class PythonParser(BaseParser):
    """
    Parser for Python code that extracts functions, classes, methods, variables, and imports.
    
    Includes built-in preprocessing for incomplete code and metadata extraction.
    """

    def __init__(self):
        """Initialize the Python parser."""
        super().__init__()
        self.language = "python"
        self.handle_incomplete_code = True
        
        # Patterns for identifying various Python elements
        self.function_pattern = re.compile(r"^\s*def\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*\(")
        self.class_pattern = re.compile(r"^\s*class\s+([a-zA-Z_][a-zA-Z0-9_]*)")
        self.decorator_pattern = re.compile(r"^\s*@([a-zA-Z_][a-zA-Z0-9_\.]*)")
        self.import_pattern = re.compile(
            r"^\s*(?:import|from)\s+([a-zA-Z_][a-zA-Z0-9_\.]*)"
        )
        self.variable_pattern = re.compile(r"^\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*=")
        self.docstring_pattern = re.compile(r'^(\s*)(?:\'\'\'|""")')
        self.return_type_pattern = re.compile(
            r"\)\s*->\s*([a-zA-Z_][a-zA-Z0-9_\[\],\s\.]*)"
        )
        self.type_annotation_pattern = re.compile(r':\s*([a-zA-Z_][a-zA-Z0-9_\[\],\s\.]*)')
        
        # Standard indentation for Python
        self.standard_indent = 4
        
        # Allowed nesting patterns
        self.allowed_nestings = [
            ('module', 'function'),
            ('module', 'class'),
            ('module', 'variable'),
            ('module', 'import'),
            ('class', 'method'),
            ('class', 'variable'),
            ('function', 'variable'),
            ('function', 'function'),  # Nested functions are allowed but uncommon
            # These are much less common:
            ('function', 'class'),     # Classes defined in functions are rare
            ('method', 'function'),    # Functions defined in methods are rare
            ('method', 'class'),       # Classes defined in methods are rare
        ]
        
        # Diagnostics container
        self._preprocessing_diagnostics = None
        self._was_code_modified = False

    def parse(self, code: str) -> List[CodeElement]:
        """
        Parse Python code and extract structured information.

        Args:
            code: Python source code

        Returns:
            List of identified code elements
        """
        # First, preprocess the code to handle incomplete syntax if enabled
        if self.handle_incomplete_code:
            code, was_modified, diagnostics = self.preprocess_incomplete_code(code)
            self._was_code_modified = was_modified
            self._preprocessing_diagnostics = diagnostics
            
        # Now parse the code
        self.elements = []
        lines = self._split_into_lines(code)
        line_count = len(lines)

        # Process all code at the current indentation level
        self._parse_block(lines, 0, line_count - 1, 0, None)

        return self.elements

    def _parse_block(
        self,
        lines: List[str],
        start_idx: int,
        end_idx: int,
        indent_level: int,
        parent: Optional[CodeElement] = None,
    ) -> None:
        """
        Parse a block of code at a specific indentation level.

        Args:
            lines: List of code lines
            start_idx: Starting line index
            end_idx: Ending line index
            indent_level: Indentation level of this block
            parent: Parent element if this is a nested block
        """
        line_idx = start_idx
        while line_idx <= end_idx:
            line = lines[line_idx]
            line_num = line_idx + 1  # Convert to 1-based indexing

            # Skip empty lines or lines with insufficient indentation
            if not line.strip() or self._count_indentation(line) < indent_level:
                line_idx += 1
                continue

            # Check for decorator
            decorators = []
            while line_idx <= end_idx and self.decorator_pattern.match(line):
                decorator_match = self.decorator_pattern.match(line)
                if decorator_match:
                    decorators.append(decorator_match.group(1))
                line_idx += 1
                if line_idx > end_idx:
                    break
                line = lines[line_idx]

            # Recalculate line number after processing decorators
            line_num = line_idx + 1

            # Check for classes
            class_match = self.class_pattern.match(line)
            if class_match and self._count_indentation(line) == indent_level:
                class_name = class_match.group(1)

                # Find the end of the class
                block_end = self._find_block_end(lines, line_idx, indent_level)

                # Extract class code
                class_code = "\n".join(lines[line_idx : block_end + 1])

                # Extract metadata for this class
                metadata = self.extract_metadata("\n".join(lines), line_idx)
                # Add decorators if they were collected earlier
                if decorators:
                    metadata["decorators"] = decorators

                # Create the class element
                class_element = CodeElement(
                    element_type=ElementType.CLASS,
                    name=class_name,
                    start_line=line_num,
                    end_line=block_end + 1,
                    code=class_code,
                    parent=parent,
                    metadata=metadata,
                )

                # Add to elements list
                self.elements.append(class_element)

                # Process class body (nested elements)
                class_indent = indent_level + self.standard_indent
                self._parse_block(
                    lines, line_idx + 1, block_end, class_indent, class_element
                )

                # Move past this class
                line_idx = block_end + 1
                continue

            # Check for functions
            function_match = self.function_pattern.match(line)
            if function_match and self._count_indentation(line) == indent_level:
                func_name = function_match.group(1)

                # Determine if method or function
                element_type = (
                    ElementType.METHOD
                    if parent and parent.element_type == ElementType.CLASS
                    else ElementType.FUNCTION
                )

                # Find the end of the function
                block_end = self._find_block_end(lines, line_idx, indent_level)

                # Extract function code
                func_code = "\n".join(lines[line_idx : block_end + 1])

                # Extract metadata for this function
                metadata = self.extract_metadata("\n".join(lines), line_idx)

                # Add decorators if they were collected earlier
                if decorators:
                    metadata["decorators"] = decorators

                # Extract return type if present and not already in metadata
                if "return_type" not in metadata:
                    return_match = self.return_type_pattern.search(line)
                    if return_match:
                        metadata["return_type"] = return_match.group(1).strip()

                # Create function element
                func_element = CodeElement(
                    element_type=element_type,
                    name=func_name,
                    start_line=line_num,
                    end_line=block_end + 1,
                    code=func_code,
                    parent=parent,
                    metadata=metadata,
                )

                # Add to elements list
                self.elements.append(func_element)

                # Process function body (nested elements)
                func_indent = indent_level + self.standard_indent
                self._parse_block(
                    lines, line_idx + 1, block_end, func_indent, func_element
                )

                # Move past this function
                line_idx = block_end + 1
                continue

            # Check for variables at current indentation level
            variable_match = self.variable_pattern.match(line)
            if variable_match and self._count_indentation(line) == indent_level:
                var_name = variable_match.group(1)

                # Create variable element
                var_element = CodeElement(
                    element_type=ElementType.VARIABLE,
                    name=var_name,
                    start_line=line_num,
                    end_line=line_num,
                    code=line.strip(),
                    parent=parent,
                )

                self.elements.append(var_element)
                line_idx += 1
                continue

            # Check for imports
            import_match = self.import_pattern.match(line)
            if import_match and self._count_indentation(line) == indent_level:
                import_name = import_match.group(1)

                # Create import element
                import_element = CodeElement(
                    element_type=ElementType.IMPORT,
                    name=import_name,
                    start_line=line_num,
                    end_line=line_num,
                    code=line.strip(),
                    parent=parent,
                )

                self.elements.append(import_element)
                line_idx += 1
                continue

            # Move to next line if no match
            line_idx += 1

    def check_syntax_validity(self, code: str) -> bool:
        """
        Check if the Python code has valid syntax.

        Args:
            code: Python source code

        Returns:
            True if syntax is valid, False otherwise
        """
        try:
            compile(code, "<string>", "exec")
            return True
        except SyntaxError:
            return False

    def _find_block_end(
        self, lines: List[str], start_idx: int, indent_level: int
    ) -> int:
        """
        Find the end of a block (function, class, etc.) by tracking indentation.

        Args:
            lines: List of code lines
            start_idx: Index of the block start line
            indent_level: Indentation level of the block start line

        Returns:
            Index of the last line in the block
        """
        line_count = len(lines)

        # First, find the indentation level of the block's body
        body_indent = None
        for i in range(start_idx + 1, line_count):
            line = lines[i].rstrip()
            if not line or line.lstrip().startswith("#"):
                continue

            current_indent = self._count_indentation(line)
            if current_indent > indent_level:
                body_indent = current_indent
                break

        # If no body found or indentation inconsistent, return the start line
        if body_indent is None:
            return start_idx

        # Now find where the block ends by looking for a line with indentation
        # less than or equal to the starting indent level
        for i in range(start_idx + 1, line_count):
            line = lines[i].rstrip()
            if not line:
                continue

            current_indent = self._count_indentation(line)
            if current_indent <= indent_level:
                return i - 1

        # If we reach here, the block extends to the end of the file
        return line_count - 1

    def get_all_globals(self, code: str) -> Dict[str, CodeElement]:
        """
        Get all global elements in the code.

        Args:
            code: Source code to search

        Returns:
            Dictionary mapping element names to CodeElement objects
        """
        elements = self.parse(code)
        globals_dict = {}

        for element in elements:
            # Only include top-level elements (no parent)
            if element.parent is None:
                globals_dict[element.name] = element

        return globals_dict
        
    def preprocess_incomplete_code(self, code: str) -> Tuple[str, bool, Dict[str, Any]]:
        """
        Python-specific preprocessing for incomplete code.
        
        This method applies Python-specific strategies to handle incomplete code, including:
        - Fixing missing colons in function/class definitions
        - Adding missing 'pass' statements in empty blocks
        - Correcting indentation issues
        - Balancing parentheses in function arguments
        - Fixing multi-line string termination
        
        Args:
            code: Source code that might be incomplete
            
        Returns:
            Tuple of (preprocessed code, was_modified flag, diagnostics dict)
        """
        diagnostics = {
            "fixes_applied": [],
            "nesting_analysis": {},
            "confidence_score": 1.0
        }
        
        modified = False
        
        # Apply python-specific fixes
        code, python_modified, python_diag = self._fix_python_specific(code)
        modified = modified or python_modified
        
        if python_modified:
            diagnostics["fixes_applied"].append("python_specific_fixes")
            
        # Add python-specific diagnostics
        if python_diag:
            diagnostics.update(python_diag)
        
        # Apply nesting and structural analysis
        code, struct_modified, struct_diag = self._fix_structural_issues(code)
        modified = modified or struct_modified
        
        if struct_modified:
            diagnostics["fixes_applied"].append("structural_fixes")
            
        # Update diagnostics
        if struct_diag:
            diagnostics.update(struct_diag)
            
        # Calculate confidence score
        if modified:
            # More fixes = less confidence
            num_fixes = len(diagnostics["fixes_applied"])
            diagnostics["confidence_score"] = max(0.3, 1.0 - (num_fixes * 0.2))
        
        return code, modified, diagnostics
    
    def _fix_python_specific(self, code: str) -> Tuple[str, bool, Dict[str, Any]]:
        """Apply Python-specific fixes."""
        lines = code.splitlines()
        modified = False
        diagnostics = {"python_fixes": []}
        
        # Check for missing colons in function/class definitions
        colon_fixed_lines = []
        for line in lines:
            # Look for function/class definitions without colons
            def_match = re.match(
                r"^\s*def\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*\([^)]*\)\s*$", line
            )
            class_match = re.match(r"^\s*class\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*$", line)
            
            if def_match or class_match:
                if not line.rstrip().endswith(':'):
                    line = line.rstrip() + ':'
                    modified = True
                    diagnostics["python_fixes"].append("added_missing_colon")
            
            colon_fixed_lines.append(line)
        
        if modified:
            code = '\n'.join(colon_fixed_lines)
            lines = colon_fixed_lines
        
        # Check for missing 'pass' in empty blocks
        pass_fixed_lines = []
        in_def_or_class = False
        current_indent = 0
        
        for i, line in enumerate(lines):
            pass_fixed_lines.append(line)
            
            stripped = line.strip()
            if not stripped:
                continue
                
            # Check if this is a definition
            if re.match(r"^\s*(?:def|class)\s+", line):
                current_indent = len(line) - len(line.lstrip())
                in_def_or_class = True
                
                # Check next line
                if i + 1 < len(lines):
                    next_line = lines[i + 1]
                    next_indent = len(next_line) - len(next_line.lstrip())
                    
                    # If next line isn't indented or is another definition, add 'pass'
                    if (not next_line.strip() or next_indent <= current_indent) and line.rstrip().endswith(':'):
                        pass_fixed_lines.append(' ' * (current_indent + self.standard_indent) + 'pass')
                        modified = True
                        diagnostics["python_fixes"].append("added_missing_pass")
                elif line.rstrip().endswith(':'):  # At end of file
                    pass_fixed_lines.append(' ' * (current_indent + self.standard_indent) + 'pass')
                    modified = True
                    diagnostics["python_fixes"].append("added_missing_pass")
        
        if modified and pass_fixed_lines != lines:
            code = '\n'.join(pass_fixed_lines)
            lines = pass_fixed_lines
            
        # Fix parentheses in function definitions
        paren_fixed_lines = []
        for i, line in enumerate(lines):
            # Check for function definitions with unbalanced parentheses
            if re.match(r"^\s*def\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*\(", line):
                # Count parentheses
                open_parens = line.count('(')
                close_parens = line.count(')')
                
                if open_parens > close_parens:
                    # Missing closing parentheses
                    line = line.rstrip() + ')' * (open_parens - close_parens)
                    if not line.rstrip().endswith(':'):
                        line = line.rstrip() + ':'
                    modified = True
                    diagnostics["python_fixes"].append("balanced_parentheses")
            
            paren_fixed_lines.append(line)
        
        if modified and paren_fixed_lines != lines:
            code = '\n'.join(paren_fixed_lines)
            lines = paren_fixed_lines
            
        # Fix unclosed multi-line strings
        string_fixed_lines = []
        in_multiline_string = False
        string_delimiter = None
        
        for i, line in enumerate(lines):
            string_fixed_lines.append(line)
            
            if not in_multiline_string:
                # Check for start of multi-line string
                if '"""' in line and line.count('"""') % 2 == 1:
                    in_multiline_string = True
                    string_delimiter = '"""'
                elif "'''" in line and line.count("'''") % 2 == 1:
                    in_multiline_string = True
                    string_delimiter = "'''"
            else:
                # Check for end of multi-line string
                if string_delimiter in line:
                    in_multiline_string = False
                    string_delimiter = None
        
        # If we're still in a multi-line string at the end, close it
        if in_multiline_string and string_delimiter:
            string_fixed_lines.append(string_delimiter)
            modified = True
            diagnostics["python_fixes"].append("closed_multiline_string")
        
        if modified and string_fixed_lines != lines:
            code = '\n'.join(string_fixed_lines)
        
        return code, modified, diagnostics
        
    def _fix_structural_issues(self, code: str) -> Tuple[str, bool, Dict[str, Any]]:
        """Apply fixes for structural issues based on language knowledge."""
        modified = False
        diagnostics = {"structural_fixes": []}
        
        # Analyze the nesting structure
        nesting_analysis = self._analyze_nesting(code)
        diagnostics["nesting_analysis"] = nesting_analysis
        
        # Fix indentation issues
        code, indent_modified = self._fix_indentation(code, nesting_analysis)
        modified = modified or indent_modified
        
        if indent_modified:
            diagnostics["structural_fixes"].append("fixed_indentation_issues")
            
        return code, modified, diagnostics
        
    def _analyze_nesting(self, code: str) -> Dict[str, Any]:
        """
        Analyze the code to understand its nesting structure.
        
        Args:
            code: The source code
            
        Returns:
            Dictionary with nesting analysis
        """
        lines = code.splitlines()
        analysis = {
            "nesting_levels": [],
            "nesting_stack": [],
            "unusual_nestings": [],
            "unclosed_blocks": [],
        }
        
        current_nesting = []
        indent_stack = [0]  # Start with 0 indentation
        
        for i, line in enumerate(lines):
            if not line.strip():
                continue
                
            current_indent = len(line) - len(line.lstrip())
            
            # Track nesting based on indentation changes
            if current_indent > indent_stack[-1]:
                # New nesting level
                indent_stack.append(current_indent)
                
                # Try to determine the type of the new block
                if i > 0:
                    prev_line = lines[i-1]
                    if re.match(self.function_pattern, prev_line):
                        current_nesting.append("function")
                    elif re.match(self.class_pattern, prev_line):
                        current_nesting.append("class")
                    else:
                        current_nesting.append("block")
                else:
                    current_nesting.append("module")
            elif current_indent < indent_stack[-1]:
                # Exiting one or more nesting levels
                while indent_stack and current_indent < indent_stack[-1]:
                    indent_stack.pop()
                    if current_nesting:
                        current_nesting.pop()
            
            # Record the current nesting level and stack for this line
            analysis["nesting_levels"].append({
                "line": i + 1,
                "depth": len(current_nesting),
                "stack": current_nesting.copy() if current_nesting else ["module"],
            })
            
        # Check for unusual nestings
        for level_info in analysis["nesting_levels"]:
            stack = level_info["stack"]
            if len(stack) >= 2:
                parent = stack[-2]
                child = stack[-1]
                
                # Check if nesting is allowed
                if not self._can_be_nested(parent, child):
                    analysis["unusual_nestings"].append({
                        "line": level_info["line"],
                        "parent": parent,
                        "child": child,
                        "likelihood": self._get_nesting_likelihood(child, level_info["depth"]),
                    })
        
        # Check for unclosed blocks at the end
        if current_nesting:
            analysis["unclosed_blocks"] = current_nesting.copy()
            
        return analysis
    
    def _can_be_nested(self, parent_type: str, child_type: str) -> bool:
        """Check if the child element can be nested inside the parent element."""
        return (parent_type, child_type) in self.allowed_nestings
        
    def _get_nesting_likelihood(self, element_type: str, nesting_level: int) -> float:
        """
        Get the likelihood score for an element at a specific nesting level.
        Returns a value between 0-1 where higher is more likely.
        """
        if nesting_level == 0:  # Module level
            if element_type in ('function', 'class', 'import', 'variable'):
                return 1.0
            return 0.2
        elif nesting_level == 1:  # Inside class or function
            if element_type == 'method' and element_type == 'class':
                return 0.9  # Methods inside classes are very common
            elif element_type == 'variable':
                return 0.8  # Variables can be anywhere
            elif element_type == 'function' and element_type == 'function':
                return 0.5  # Nested functions are somewhat common
            elif element_type == 'class' and element_type == 'function':
                return 0.3  # Classes in functions are uncommon
            return 0.2
        else:  # Deep nesting
            # Deep nesting gets progressively less likely
            return max(0.1, 1.0 - (nesting_level * 0.2))
            
    def _fix_indentation(self, code: str, nesting_analysis: Dict[str, Any]) -> Tuple[str, bool]:
        """Fix indentation issues based on Python's rules."""
        lines = code.splitlines()
        modified = False
        
        # Python relies on consistent indentation
        # Check for inconsistent indentation within blocks
        
        # First, identify the standard indentation unit (usually 4 spaces)
        indent_sizes = []
        prev_indent = 0
        
        for i, line in enumerate(lines):
            if not line.strip():  # Skip empty lines
                continue
                
            current_indent = len(line) - len(line.lstrip())
            if current_indent > prev_indent:
                indent_sizes.append(current_indent - prev_indent)
            
            prev_indent = current_indent
        
        # Determine most common indent unit
        if not indent_sizes:
            indent_unit = self.standard_indent  # Default to 4 spaces
        else:
            # Get the most common increment
            from collections import Counter
            indent_counter = Counter(indent_sizes)
            most_common = indent_counter.most_common(1)[0][0] if indent_counter else self.standard_indent
            indent_unit = most_common if most_common > 0 else self.standard_indent
        
        # Now check each line for indentation issues
        fixed_lines = lines.copy()
        prev_indent = 0
        expected_indent = None
        
        for i, line in enumerate(lines):
            if not line.strip():  # Skip empty lines
                continue
                
            current_indent = len(line) - len(line.lstrip())
            
            # Check if this looks like a continuation (inside a parenthesis or bracket)
            # or if it's a new block after a colon
            if i > 0:
                prev_line = lines[i-1].rstrip()
                
                # Check for a line ending with a colon (new block should start)
                if prev_line.endswith(':'):
                    # Next line should be indented by the standard amount
                    expected_indent = prev_indent + indent_unit
                    if current_indent != expected_indent and line.strip():
                        fixed_lines[i] = ' ' * expected_indent + line.lstrip()
                        modified = True
                # Or if in a continued expression, the indentation should be consistent
                elif '(' in prev_line and ')' not in prev_line.split('(', 1)[1]:
                    if current_indent <= prev_indent:
                        # Should be indented more than the previous line
                        expected_indent = prev_indent + indent_unit
                        fixed_lines[i] = ' ' * expected_indent + line.lstrip()
                        modified = True
            
            prev_indent = current_indent
        
        if modified:
            code = '\n'.join(fixed_lines)
            
        return code, modified

    def extract_metadata(self, code: str, line_idx: int) -> Dict[str, Any]:
        """
        Extract Python-specific metadata from code at the given line index.
        
        Args:
            code: The full source code
            line_idx: The line index where the symbol definition starts
            
        Returns:
            Dictionary of extracted metadata
        """
        lines = code.splitlines()
        metadata = {}
        
        # Extract docstrings
        docstring = self._extract_docstring(lines, line_idx + 1, self._count_indentation(lines[line_idx]))
        if docstring:
            metadata["docstring"] = docstring
            
        # Extract type information
        if line_idx < len(lines):
            line = lines[line_idx]
            
            # Look for return type annotation
            return_match = self.return_type_pattern.search(line)
            if return_match:
                metadata["return_type"] = return_match.group(1).strip()
                
            # Extract parameter type annotations if this is a function definition
            if re.match(self.function_pattern, line):
                param_types = self._extract_parameter_types(line)
                if param_types:
                    metadata["parameter_types"] = param_types
        
        return metadata
        
    def _extract_parameter_types(self, function_def: str) -> Dict[str, str]:
        """
        Extract parameter type annotations from a function definition.
        
        Args:
            function_def: The function definition line
            
        Returns:
            Dictionary mapping parameter names to their type annotations
        """
        param_types = {}
        
        # Extract the parameter section
        if '(' in function_def and ')' in function_def:
            param_section = function_def.split('(', 1)[1].split(')', 1)[0]
            
            # Parse each parameter
            for param in param_section.split(','):
                param = param.strip()
                if ':' in param:
                    # Has type annotation
                    name_part, type_part = param.split(':', 1)
                    param_name = name_part.strip()
                    param_type = type_part.strip()
                    
                    # Remove default value if present
                    if '=' in param_type:
                        param_type = param_type.split('=', 1)[0].strip()
                        
                    if param_name and param_type:
                        param_types[param_name] = param_type
        
        return param_types
        
    def _extract_docstring(self, lines: List[str], start_idx: int, indent_level: int) -> Optional[str]:
        """
        Extract a docstring from the code.
        
        Args:
            lines: List of code lines
            start_idx: Index to start looking from
            indent_level: Indentation level of the enclosing block
            
        Returns:
            Docstring if found, None otherwise
        """
        if start_idx >= len(lines):
            return None
            
        # Check if the line could be a docstring
        line = lines[start_idx]
        if not line.strip():
            # Skip blank lines
            if start_idx + 1 < len(lines):
                return self._extract_docstring(lines, start_idx + 1, indent_level)
            return None
            
        docstring_match = self.docstring_pattern.match(line)
        if not docstring_match:
            return None
            
        # Check if the indentation is correct (should match or exceed enclosing block)
        doc_indent = len(docstring_match.group(1))
        if doc_indent < indent_level:
            return None
            
        # Determine the docstring delimiter (''' or """)
        delimiter = '"""' if '"""' in line else "'''"
            
        # Check if the docstring is a single line
        if line.count(delimiter) == 2:
            # Single-line docstring
            return line.strip()
            
        # Multi-line docstring, find the end
        docstring_lines = [line]
        for idx in range(start_idx + 1, len(lines)):
            docstring_lines.append(lines[idx])
            if delimiter in lines[idx]:
                break
                
        return "\n".join(docstring_lines)
