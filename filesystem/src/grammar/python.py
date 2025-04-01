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
        
        # Stack to keep track of the current parent element
        stack = []
        # Current active element being processed
        current_element = None
        
        line_idx = 0
        while line_idx < line_count:
            line = lines[line_idx]
            line_num = line_idx + 1  # Convert to 1-based indexing
            
            # Skip empty lines
            if not line.strip():
                line_idx += 1
                continue
                
            # Check for decorator
            decorator_match = self.decorator_pattern.match(line)
            decorators = []
            while decorator_match:
                decorators.append(decorator_match.group(1))
                line_idx += 1
                if line_idx >= line_count:
                    break
                line = lines[line_idx]
                decorator_match = self.decorator_pattern.match(line)
            
            # If we've gone past the end of the file during decorator processing
            if line_idx >= line_count:
                break
            
            # Recalculate line number after processing decorators
            line_num = line_idx + 1
            
            # Check for functions
            function_match = self.function_pattern.match(line)
            if function_match:
                func_name = function_match.group(1)
                indent_level = self._count_indentation(line)
                
                # Determine if this is a method or a function
                element_type = ElementType.METHOD if stack and stack[-1].element_type == ElementType.CLASS else ElementType.FUNCTION
                
                # Find the end of the function by checking indentation
                end_idx = self._find_block_end(lines, line_idx, indent_level)
                
                # Extract the full function code
                func_code = "\n".join(lines[line_idx:end_idx+1])
                
                # Extract return type annotation if present
                return_type = None
                return_match = self.return_type_pattern.search(line)
                if return_match:
                    return_type = return_match.group(1).strip()
                
                # Parent element will be the last item on the stack if any
                parent = stack[-1] if stack else None
                
                # Create metadata with decorators and return type
                metadata = {
                    "decorators": decorators,
                    "return_type": return_type
                }
                
                # Create the function element
                element = CodeElement(
                    element_type=element_type,
                    name=func_name,
                    start_line=line_num,
                    end_line=end_idx + 1,
                    code=func_code,
                    parent=parent,
                    metadata=metadata
                )
                
                # Check for docstring that might follow
                docstring = self._extract_docstring(lines, line_idx + 1, indent_level)
                if docstring:
                    doc_start = line_idx + 1
                    doc_end = doc_start + len(docstring.splitlines()) - 1
                    element.metadata["docstring"] = docstring
                    
                self.elements.append(element)
                
                # Update the current element for possible nested elements
                current_element = element
                stack.append(current_element)
                
                # Skip to the end of the function
                line_idx = end_idx + 1
                continue
            
            # Check for classes
            class_match = self.class_pattern.match(line)
            if class_match:
                class_name = class_match.group(1)
                indent_level = self._count_indentation(line)
                
                # Find the end of the class by checking indentation
                end_idx = self._find_block_end(lines, line_idx, indent_level)
                
                # Extract the full class code
                class_code = "\n".join(lines[line_idx:end_idx+1])
                
                # Parent element will be the last item on the stack if any
                parent = stack[-1] if stack else None
                
                # Create metadata with decorators
                metadata = {
                    "decorators": decorators
                }
                
                # Create the class element
                element = CodeElement(
                    element_type=ElementType.CLASS,
                    name=class_name,
                    start_line=line_num,
                    end_line=end_idx + 1,
                    code=class_code,
                    parent=parent,
                    metadata=metadata
                )
                
                # Check for docstring that might follow
                docstring = self._extract_docstring(lines, line_idx + 1, indent_level)
                if docstring:
                    element.metadata["docstring"] = docstring
                
                self.elements.append(element)
                
                # Update the current element for possible nested elements
                current_element = element
                stack.append(current_element)
                
                # Skip to the end of the class
                line_idx = end_idx + 1
                continue
            
            # Check for global variables
            variable_match = self.variable_pattern.match(line)
            if variable_match and self._count_indentation(line) == 0:  # Only consider top-level variables
                var_name = variable_match.group(1)
                
                # Create the variable element
                element = CodeElement(
                    element_type=ElementType.VARIABLE,
                    name=var_name,
                    start_line=line_num,
                    end_line=line_num,
                    code=line.strip(),
                    parent=None
                )
                
                self.elements.append(element)
            
            # Check for imports
            import_match = self.import_pattern.match(line)
            if import_match:
                import_name = import_match.group(1)
                
                # Create the import element
                element = CodeElement(
                    element_type=ElementType.IMPORT,
                    name=import_name,
                    start_line=line_num,
                    end_line=line_num,
                    code=line.strip(),
                    parent=None
                )
                
                self.elements.append(element)
            
            # Check if we need to pop elements from the stack
            # If the current line's indentation level is less than the current element's
            while stack and line_idx < line_count:
                # If we're at the end of the file, break
                if line_idx >= line_count:
                    break
                    
                # Get the current line's indentation
                current_indent = self._count_indentation(lines[line_idx])
                
                # Get the indent level of the current element in the stack
                if not stack:
                    break
                    
                # Get the first line of the current element
                current_element = stack[-1]
                element_first_line = lines[current_element.start_line - 1]
                element_indent = self._count_indentation(element_first_line)
                
                # If current indent is less than element indent, pop from stack
                if current_indent <= element_indent and current_indent < self._count_indentation(lines[current_element.start_line - 1]):
                    stack.pop()
                else:
                    break
            
            # Move to the next line
            line_idx += 1
        
        return self.elements
    
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
        current_idx = start_idx + 1
        
        # Skip empty lines or comments at the beginning of the block
        while current_idx < line_count:
            line = lines[current_idx].rstrip()
            if not line or line.lstrip().startswith('#'):
                current_idx += 1
                continue
            break
        
        # If we've reached the end of the file, return the last line
        if current_idx >= line_count:
            return line_count - 1
        
        # Get the indentation level of the first non-empty line in the block
        first_line = lines[current_idx]
        if not first_line.strip():
            # If the first line is empty, find the next non-empty line
            for idx in range(current_idx + 1, line_count):
                if lines[idx].strip():
                    first_line = lines[idx]
                    break
        
        block_indent = self._count_indentation(first_line)
        
        # If the block is empty or improperly indented, return the start line
        if block_indent <= indent_level:
            return start_idx
        
        # Now find the end of the block
        for idx in range(current_idx, line_count):
            line = lines[idx].rstrip()
            
            # Skip empty lines or comments
            if not line or line.lstrip().startswith('#'):
                continue
                
            current_indent = self._count_indentation(line)
            
            # If we find a line with an indentation level less than or equal to the
            # block start, we've found the end of the block
            if current_indent <= indent_level:
                return idx - 1
        
        # If we reach the end of the file, the block ends at the last line
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
        docstring_match = self.docstring_pattern.match(line)
        if not docstring_match:
            return None
            
        # Check if the indentation is correct
        doc_indent = len(docstring_match.group(1))
        if doc_indent <= indent_level:
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
