"""
Python language parser for extracting structured information from Python code.
"""

import re
from typing import List, Dict, Optional, Tuple, Set
from .base import BaseParser, CodeElement, ElementType


class PythonParser(BaseParser):
    """
    Parser for Python code that extracts functions, classes, methods, variables, and imports.
    """

    def __init__(self):
        """Initialize the Python parser."""
        super().__init__()
        # Patterns for identifying various Python elements
        self.function_pattern = re.compile(r'^\s*def\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*\(')
        self.class_pattern = re.compile(r'^\s*class\s+([a-zA-Z_][a-zA-Z0-9_]*)')
        self.decorator_pattern = re.compile(r'^\s*@([a-zA-Z_][a-zA-Z0-9_\.]*)')
        self.import_pattern = re.compile(r'^\s*(?:import|from)\s+([a-zA-Z_][a-zA-Z0-9_\.]*)')
        self.variable_pattern = re.compile(r'^\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*=')
        self.docstring_pattern = re.compile(r'^(\s*)(?:\'\'\'|""")')
        self.return_type_pattern = re.compile(r'\)\s*->\s*([a-zA-Z_][a-zA-Z0-9_\[\],\s]*)')

    def parse(self, code: str) -> List[CodeElement]:
        """
        Parse Python code and extract structured information.

        Args:
            code: Python source code

        Returns:
            List of identified code elements
        """
        self.elements = []
        lines = self._split_into_lines(code)
        line_count = len(lines)

        # Process all code at the current indentation level
        self._parse_block(lines, 0, line_count - 1, 0, None)
        
        return self.elements

    def _parse_block(self, lines: List[str], start_idx: int, end_idx: int, 
                    indent_level: int, parent: Optional[CodeElement] = None) -> None:
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
                class_code = "\n".join(lines[line_idx:block_end+1])
                
                # Create the class element
                class_element = CodeElement(
                    element_type=ElementType.CLASS,
                    name=class_name,
                    start_line=line_num,
                    end_line=block_end + 1,
                    code=class_code,
                    parent=parent,
                    metadata={"decorators": decorators}
                )
                
                # Check for docstring
                doc_idx = line_idx + 1
                if doc_idx <= end_idx:
                    docstring = self._extract_docstring(lines, doc_idx, indent_level)
                    if docstring:
                        class_element.metadata["docstring"] = docstring
                
                # Add to elements list
                self.elements.append(class_element)
                
                # Process class body (nested elements)
                class_indent = indent_level + 4  # Assuming standard 4-space indentation
                self._parse_block(lines, line_idx + 1, block_end, class_indent, class_element)
                
                # Move past this class
                line_idx = block_end + 1
                continue
            
            # Check for functions
            function_match = self.function_pattern.match(line)
            if function_match and self._count_indentation(line) == indent_level:
                func_name = function_match.group(1)
                
                # Determine if method or function
                element_type = ElementType.METHOD if parent and parent.element_type == ElementType.CLASS else ElementType.FUNCTION
                
                # Find the end of the function
                block_end = self._find_block_end(lines, line_idx, indent_level)
                
                # Extract function code
                func_code = "\n".join(lines[line_idx:block_end+1])
                
                # Extract return type if present
                return_type = None
                return_match = self.return_type_pattern.search(line)
                if return_match:
                    return_type = return_match.group(1).strip()
                
                # Create function element
                func_element = CodeElement(
                    element_type=element_type,
                    name=func_name,
                    start_line=line_num,
                    end_line=block_end + 1,
                    code=func_code,
                    parent=parent,
                    metadata={
                        "decorators": decorators,
                        "return_type": return_type
                    }
                )
                
                # Check for docstring
                doc_idx = line_idx + 1
                if doc_idx <= end_idx:
                    docstring = self._extract_docstring(lines, doc_idx, indent_level + 4)
                    if docstring:
                        func_element.metadata["docstring"] = docstring
                
                # Add to elements list
                self.elements.append(func_element)
                
                # Process function body (nested elements)
                func_indent = indent_level + 4  # Assuming standard 4-space indentation
                self._parse_block(lines, line_idx + 1, block_end, func_indent, func_element)
                
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
                    parent=parent
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
                    parent=parent
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
            compile(code, '<string>', 'exec')
            return True
        except SyntaxError:
            return False

    def _find_block_end(self, lines: List[str], start_idx: int, indent_level: int) -> int:
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
            if not line or line.lstrip().startswith('#'):
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
            docstring = line.strip()
            return docstring

        # Multi-line docstring, find the end
        docstring_lines = [line]
        for idx in range(start_idx + 1, len(lines)):
            docstring_lines.append(lines[idx])
            if delimiter in lines[idx]:
                break

        return "\n".join(docstring_lines)

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
