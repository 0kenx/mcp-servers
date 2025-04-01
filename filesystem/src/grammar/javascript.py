"""
JavaScript language parser for extracting structured information from JavaScript code.
"""

import re
from typing import List, Dict, Optional, Tuple, Set, Any
from .base import BaseParser, CodeElement, ElementType


class JavaScriptParser(BaseParser):
    """
    Parser for JavaScript code that extracts functions, classes, and variables.
    """
    
    def __init__(self):
        """Initialize the JavaScript parser."""
        super().__init__()
        
        # Patterns for identifying JavaScript elements
        
        # Function declarations (traditional functions)
        self.function_pattern = re.compile(
            r'^\s*(?:export\s+)?(?:async\s+)?function\s*(?:\*\s*)?([a-zA-Z_$][a-zA-Z0-9_$]*)'
            r'\s*\((.*?)\)'
            r'\s*\{'
        )
        
        # Arrow functions assigned to variables
        self.arrow_function_pattern = re.compile(
            r'^\s*(?:export\s+)?(?:const|let|var)\s+([a-zA-Z_$][a-zA-Z0-9_$]*)'
            r'\s*=\s*(?:async\s+)?(?:\((.*?)\)|([a-zA-Z_$][a-zA-Z0-9_$]*))'
            r'\s*=>'
        )
        
        # Class declarations
        self.class_pattern = re.compile(
            r'^\s*(?:export\s+)?class\s+([a-zA-Z_$][a-zA-Z0-9_$]*)'
            r'(?:\s+extends\s+([a-zA-Z_$][a-zA-Z0-9_$.]*))?'
            r'\s*\{'
        )
        
        # Class methods
        self.method_pattern = re.compile(
            r'^\s*(?:async\s+)?(?:static\s+)?(?:get\s+|set\s+)?([a-zA-Z_$][a-zA-Z0-9_$]*)'
            r'\s*\((.*?)\)'
            r'\s*\{'
        )
        
        # Object methods (in object literals)
        self.object_method_pattern = re.compile(
            r'^\s*([a-zA-Z_$][a-zA-Z0-9_$]*)'
            r'\s*:\s*(?:async\s+)?function\s*(?:\*\s*)?'
            r'\s*\((.*?)\)'
            r'\s*\{'
        )
        
        # Variable declarations
        self.variable_pattern = re.compile(
            r'^\s*(?:export\s+)?(?:const|let|var)\s+([a-zA-Z_$][a-zA-Z0-9_$]*)'
            r'\s*=\s*([^;]*);?'
        )
        
        # Import statements
        self.import_pattern = re.compile(
            r'^\s*import\s+(?:{(.*?)}|(\*\s+as\s+[a-zA-Z_$][a-zA-Z0-9_$]*)|([a-zA-Z_$][a-zA-Z0-9_$]*))'
            r'\s+from\s+[\'"](.+?)[\'"]\s*;?'
        )
        
        # Export statements
        self.export_pattern = re.compile(
            r'^\s*export\s+(?:default\s+)?(?:{(.*?)}|(\*\s+from\s+[\'"]\S+[\'"]))'
            r'\s*;?'
        )
        
        # JSDoc pattern
        self.jsdoc_pattern = re.compile(r'^\s*/\*\*')
        self.jsdoc_end_pattern = re.compile(r'\*/')
        
        # Comment patterns
        self.line_comment_pattern = re.compile(r'^(\s*)\/\/')
        self.comment_start_pattern = re.compile(r'^(\s*)\/\*')
        
    def parse(self, code: str) -> List[CodeElement]:
        """
        Parse JavaScript code and extract structured information.
        
        Args:
            code: JavaScript source code
            
        Returns:
            List of identified code elements
        """
        self.elements = []
        
        # Normalize line endings
        code = code.replace('\r\n', '\n').replace('\r', '\n')
        
        # Split into lines for processing
        lines = self._split_into_lines(code)
        line_count = len(lines)
        
        # Stack to keep track of the current parent element
        stack = []
        
        # Track JSDoc comments
        current_jsdoc = []
        in_jsdoc = False
        jsdoc_lines = []
        
        # Track line comments for documentation
        line_comments = {}  # Maps line number to comment text
        
        # Process lines
        line_idx = 0
        while line_idx < line_count:
            line = lines[line_idx]
            line_num = line_idx + 1  # Convert to 1-based indexing
            
            # Process JSDoc comments
            if self.jsdoc_pattern.match(line) and not in_jsdoc:
                in_jsdoc = True
                jsdoc_lines = [line_idx]
                current_jsdoc = [line]
            elif in_jsdoc:
                current_jsdoc.append(line)
                jsdoc_lines.append(line_idx)
                if self.jsdoc_end_pattern.search(line):
                    # End of JSDoc block
                    jsdoc_text = '\n'.join(current_jsdoc)
                    # Store the JSDoc for the next declaration
                    line_comments[line_idx] = jsdoc_text
                    in_jsdoc = False
                    current_jsdoc = []
            
            # Process line comments
            elif self.line_comment_pattern.match(line):
                # Store single-line comments
                if line_idx - 1 in line_comments and not any(l in jsdoc_lines for l in range(line_idx-2, line_idx)):
                    # Add to previous comment if they're adjacent
                    line_comments[line_idx - 1] += '\n' + line
                else:
                    line_comments[line_idx] = line
            
            # Skip empty lines and comments
            if not line.strip() or line.strip().startswith('//') or in_jsdoc:
                line_idx += 1
                continue
            
            # Check for class declarations
            class_match = self.class_pattern.match(line)
            if class_match:
                class_name = class_match.group(1)
                parent_class = class_match.group(2) if class_match.group(2) else None
                
                # Find the end of the class (closing brace)
                end_idx = self._find_matching_brace(lines, line_idx)
                
                # Extract the full class code
                class_code = "\n".join(lines[line_idx:end_idx+1])
                
                # Look for preceding JSDoc comment
                jsdoc = None
                for i in range(line_idx-1, max(0, line_idx-10), -1):
                    if i in line_comments:
                        jsdoc = line_comments[i]
                        break
                
                # Parent element will be the last item on the stack if any
                parent = stack[-1] if stack else None
                
                # Create the class element
                element = CodeElement(
                    element_type=ElementType.CLASS,
                    name=class_name,
                    start_line=line_num,
                    end_line=end_idx + 1,
                    code=class_code,
                    parent=parent,
                    metadata={
                        "parent_class": parent_class,
                        "docstring": jsdoc
                    }
                )
                
                self.elements.append(element)
                
                # Push the class onto the stack as the new parent for nested elements
                stack.append(element)
                
                # Skip to end of the class definition
                line_idx = end_idx + 1
                continue
            
            # Check for function declarations
            function_match = self.function_pattern.match(line)
            if function_match:
                func_name = function_match.group(1)
                params = function_match.group(2)
                
                # Find the end of the function (closing brace)
                end_idx = self._find_matching_brace(lines, line_idx)
                
                # Extract the full function code
                func_code = "\n".join(lines[line_idx:end_idx+1])
                
                # Look for preceding JSDoc comment
                jsdoc = None
                for i in range(line_idx-1, max(0, line_idx-10), -1):
                    if i in line_comments:
                        jsdoc = line_comments[i]
                        break
                
                # Parent element will be the last item on the stack if any
                parent = stack[-1] if stack else None
                
                # Determine if this is a method or a function
                element_type = ElementType.METHOD if parent and parent.element_type == ElementType.CLASS else ElementType.FUNCTION
                
                # Create the function element
                element = CodeElement(
                    element_type=element_type,
                    name=func_name,
                    start_line=line_num,
                    end_line=end_idx + 1,
                    code=func_code,
                    parent=parent,
                    metadata={
                        "parameters": params,
                        "docstring": jsdoc,
                        "is_async": 'async' in line and 'async' in line.split('function')[0]
                    }
                )
                
                self.elements.append(element)
                
                # Skip to end of the function
                line_idx = end_idx + 1
                continue
            
            # Check for arrow functions assigned to variables
            arrow_match = self.arrow_function_pattern.match(line)
            if arrow_match:
                func_name = arrow_match.group(1)
                params = arrow_match.group(2) or arrow_match.group(3) or ""
                
                # Find the end of the arrow function
                # This could be a one-liner or a block
                # A block will start with { and end with }
                # A one-liner will end with a semicolon or newline
                
                if "{" in line[line.find("=>"):]:
                    # Block-style arrow function
                    start_brace_idx = line.find("{", line.find("=>"))
                    end_idx = self._find_matching_brace_from_position(lines, line_idx, start_brace_idx)
                else:
                    # One-liner arrow function
                    if ";" in line[line.find("=>"):]:
                        # Ends with semicolon
                        end_idx = line_idx
                    else:
                        # Might continue on next lines if part of an expression
                        end_idx = line_idx
                        for i in range(line_idx + 1, line_count):
                            if lines[i].strip().endswith(";") or lines[i].strip().endswith(","):
                                end_idx = i
                                break
                            elif not lines[i].strip() or lines[i].strip().startswith("//"):
                                continue
                            else:
                                # If we hit another statement, end at the previous line
                                break
                
                # Extract the full arrow function code
                func_code = "\n".join(lines[line_idx:end_idx+1])
                
                # Look for preceding JSDoc comment
                jsdoc = None
                for i in range(line_idx-1, max(0, line_idx-10), -1):
                    if i in line_comments:
                        jsdoc = line_comments[i]
                        break
                
                # Parent element will be the last item on the stack if any
                parent = stack[-1] if stack else None
                
                # Create the arrow function element
                element = CodeElement(
                    element_type=ElementType.FUNCTION,
                    name=func_name,
                    start_line=line_num,
                    end_line=end_idx + 1,
                    code=func_code,
                    parent=parent,
                    metadata={
                        "parameters": params,
                        "docstring": jsdoc,
                        "is_arrow": True,
                        "is_async": 'async' in line and 'async' in line.split('=>')[0]
                    }
                )
                
                self.elements.append(element)
                
                # Skip to end of the arrow function
                line_idx = end_idx + 1
                continue
            
            # Inside a class, check for method definitions
            if stack and stack[-1].element_type == ElementType.CLASS:
                method_match = self.method_pattern.match(line)
                if method_match:
                    method_name = method_match.group(1)
                    params = method_match.group(2)
                    
                    # Find the end of the method (closing brace)
                    end_idx = self._find_matching_brace(lines, line_idx)
                    
                    # Extract the full method code
                    method_code = "\n".join(lines[line_idx:end_idx+1])
                    
                    # Look for preceding JSDoc comment
                    jsdoc = None
                    for i in range(line_idx-1, max(0, line_idx-10), -1):
                        if i in line_comments:
                            jsdoc = line_comments[i]
                            break
                    
                    # Parent is the current class
                    parent = stack[-1]
                    
                    # Check for special method types
                    is_static = 'static' in line and 'static' in line.split(method_name)[0]
                    is_getter = 'get ' in line and 'get ' in line.split(method_name)[0]
                    is_setter = 'set ' in line and 'set ' in line.split(method_name)[0]
                    
                    # Create the method element
                    element = CodeElement(
                        element_type=ElementType.METHOD,
                        name=method_name,
                        start_line=line_num,
                        end_line=end_idx + 1,
                        code=method_code,
                        parent=parent,
                        metadata={
                            "parameters": params,
                            "docstring": jsdoc,
                            "is_static": is_static,
                            "is_getter": is_getter,
                            "is_setter": is_setter,
                            "is_async": 'async' in line and 'async' in line.split(method_name)[0]
                        }
                    )
                    
                    self.elements.append(element)
                    
                    # Skip to end of the method
                    line_idx = end_idx + 1
                    continue
            
            # Check for variable declarations
            variable_match = self.variable_pattern.match(line)
            if variable_match:
                var_name = variable_match.group(1)
                var_value = variable_match.group(2).strip() if variable_match.group(2) else ""
                
                # Skip if this is already handled as an arrow function
                if "=>" in var_value:
                    line_idx += 1
                    continue
                
                # Look for preceding JSDoc comment
                jsdoc = None
                for i in range(line_idx-1, max(0, line_idx-10), -1):
                    if i in line_comments:
                        jsdoc = line_comments[i]
                        break
                
                # Parent element will be the last item on the stack if any
                parent = stack[-1] if stack else None
                
                # Determine type based on declaration keyword
                if 'const' in line.split(var_name)[0]:
                    element_type = ElementType.CONSTANT
                else:
                    element_type = ElementType.VARIABLE
                
                # Create the variable element
                element = CodeElement(
                    element_type=element_type,
                    name=var_name,
                    start_line=line_num,
                    end_line=line_num,
                    code=line.strip(),
                    parent=parent,
                    metadata={
                        "value": var_value,
                        "docstring": jsdoc
                    }
                )
                
                self.elements.append(element)
                
                # Move to next line
                line_idx += 1
                continue
            
            # Check for import statements
            import_match = self.import_pattern.match(line)
            if import_match:
                # Determine what is being imported
                import_items = import_match.group(1) or import_match.group(2) or import_match.group(3)
                module_path = import_match.group(4)
                
                # Create the import element
                element = CodeElement(
                    element_type=ElementType.IMPORT,
                    name=module_path,
                    start_line=line_num,
                    end_line=line_num,
                    code=line.strip(),
                    parent=None,
                    metadata={
                        "imported_items": import_items
                    }
                )
                
                self.elements.append(element)
                
                # Move to next line
                line_idx += 1
                continue
            
            # Check for export statements
            export_match = self.export_pattern.match(line)
            if export_match:
                # Determine what is being exported
                export_items = export_match.group(1) or export_match.group(2) or ""
                
                # Create the export element (not typically used directly by LLMs, but useful for context)
                element = CodeElement(
                    element_type=ElementType.MODULE,
                    name="exports",
                    start_line=line_num,
                    end_line=line_num,
                    code=line.strip(),
                    parent=None,
                    metadata={
                        "exported_items": export_items
                    }
                )
                
                self.elements.append(element)
                
                # Move to next line
                line_idx += 1
                continue
            
            # Handle closing braces that pop elements off the stack
            if line.strip() == '}' and stack:
                stack.pop()
            
            # Move to next line
            line_idx += 1
        
        return self.elements
    
    def _find_matching_brace(self, lines: List[str], start_idx: int) -> int:
        """
        Find the line with the matching closing brace for an opening brace.
        
        Args:
            lines: List of code lines
            start_idx: Index of the line with the opening brace
            
        Returns:
            Index of the line with the matching closing brace
        """
        line = lines[start_idx]
        brace_idx = line.find('{')
        return self._find_matching_brace_from_position(lines, start_idx, brace_idx)
    
    def _find_matching_brace_from_position(self, lines: List[str], start_idx: int, brace_idx: int) -> int:
        """
        Find the line with the matching closing brace from a specific position.
        
        Args:
            lines: List of code lines
            start_idx: Index of the line with the opening brace
            brace_idx: Position of the opening brace within the line
            
        Returns:
            Index of the line with the matching closing brace
        """
        brace_count = 0
        in_string = False
        in_template = False
        escape_next = False
        
        # Process the start line from the brace position
        for i in range(brace_idx, len(lines[start_idx])):
            char = lines[start_idx][i]
            
            if escape_next:
                escape_next = False
                continue
            
            if char == '\\':
                escape_next = True
            elif char == '"' or char == "'":
                if not in_template:  # Ignore quotes in template literals
                    in_string = not in_string
            elif char == '`':
                in_template = not in_template
            elif not in_string and not in_template:
                if char == '{':
                    brace_count += 1
                elif char == '}':
                    brace_count -= 1
                    if brace_count == 0:
                        return start_idx
        
        # Process subsequent lines
        for i in range(start_idx + 1, len(lines)):
            escape_next = False
            for j in range(len(lines[i])):
                char = lines[i][j]
                
                if escape_next:
                    escape_next = False
                    continue
                
                if char == '\\':
                    escape_next = True
                elif char == '"' or char == "'":
                    if not in_template:  # Ignore quotes in template literals
                        in_string = not in_string
                elif char == '`':
                    in_template = not in_template
                elif not in_string and not in_template:
                    if char == '{':
                        brace_count += 1
                    elif char == '}':
                        brace_count -= 1
                        if brace_count == 0:
                            return i
        
        # If matching brace not found, return the last line
        return len(lines) - 1
    
    def check_syntax_validity(self, code: str) -> bool:
        """
        Perform a basic check for JavaScript syntax validity.
        
        Args:
            code: JavaScript source code
            
        Returns:
            True if syntax appears valid, False otherwise
        """
        # Strip comments first
        code_without_comments = self._strip_comments(code, '//', '/*', '*/')
        
        # Check for balanced braces, parentheses, and brackets
        brace_count = 0
        paren_count = 0
        bracket_count = 0
        in_string = False
        in_template = False
        escape_next = False
        
        for char in code_without_comments:
            if escape_next:
                escape_next = False
                continue
                
            if char == '\\':
                escape_next = True
            elif char == '"' or char == "'":
                if not in_template:  # Ignore quotes in template literals
                    in_string = not in_string
            elif char == '`':
                in_template = not in_template
            elif not in_string and not in_template:
                if char == '{':
                    brace_count += 1
                elif char == '}':
                    brace_count -= 1
                    if brace_count < 0:
                        return False  # Unbalanced closing brace
                elif char == '(':
                    paren_count += 1
                elif char == ')':
                    paren_count -= 1
                    if paren_count < 0:
                        return False  # Unbalanced closing parenthesis
                elif char == '[':
                    bracket_count += 1
                elif char == ']':
                    bracket_count -= 1
                    if bracket_count < 0:
                        return False  # Unbalanced closing bracket
        
        # All counts should be zero for balanced code
        return brace_count == 0 and paren_count == 0 and bracket_count == 0
