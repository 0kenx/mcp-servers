"""
C/C++ language parser for extracting structured information from C/C++ code.
"""

import re
from typing import List, Dict, Optional, Tuple, Set, Any
from .base import BaseParser, CodeElement, ElementType


class CCppParser(BaseParser):
    """
    Parser for C/C++ code that extracts functions, classes, structs, and global variables.
    """

    def __init__(self):
        """Initialize the C/C++ parser."""
        super().__init__()
        # Patterns for identifying various C/C++ elements

        # Function pattern matches both declarations and definitions
        # Captures: return type, name, parameters
        self.function_pattern = re.compile(
            r'^\s*(?:static\s+|inline\s+|extern\s+|virtual\s+|constexpr\s+)*'
            r'((?:const\s+)?[a-zA-Z_][a-zA-Z0-9_:]*(?:\s*<.*?>)?(?:\s*\*+|\s*&+)?)'  # Return type
            r'\s+([a-zA-Z_][a-zA-Z0-9_]*)'  # Function name
            r'\s*\((.*?)\)'  # Parameters
            r'(?:\s*const)?'  # Potentially const method
            r'(?:\s*=\s*0)?'  # Pure virtual function
            r'(?:\s*\{|\s*;)'  # Either a definition with { or a declaration with ;
        )

        # Class pattern matches class and struct definitions
        self.class_pattern = re.compile(
            r'^\s*(class|struct)\s+([a-zA-Z_][a-zA-Z0-9_]*)'
            r'(?:\s*:\s*(?:public|protected|private)?\s*([a-zA-Z_][a-zA-Z0-9_:]*))?'  # Inheritance
            r'\s*\{'
        )

        # Namespace pattern
        self.namespace_pattern = re.compile(
            r'^\s*namespace\s+([a-zA-Z_][a-zA-Z0-9_]*)'
            r'\s*\{'
        )

        # Global variable pattern (at global scope)
        self.variable_pattern = re.compile(
            r'^\s*(?:static\s+|extern\s+|const\s+)*'
            r'([a-zA-Z_][a-zA-Z0-9_:<>]*(?:\s*\*+|\s*&+)?)'  # Type
            r'\s+([a-zA-Z_][a-zA-Z0-9_]*)'  # Variable name
            r'(?:\s*=\s*[^;]*)?;'  # Optional initialization
        )

        # Constant/enum pattern
        self.constant_pattern = re.compile(
            r'^\s*(?:const|constexpr|#define)\s+'
            r'([a-zA-Z_][a-zA-Z0-9_]*)'  # Constant name
            r'(?:\s+|\s*=\s*|\s+)(.*?)(?:;|$)'  # Value
        )

        # Include pattern
        self.include_pattern = re.compile(
            r'^\s*#include\s+(?:<([^>]+)>|"([^"]+)")'
        )

        # Using directive
        self.using_pattern = re.compile(
            r'^\s*using\s+(namespace\s+)?([a-zA-Z_][a-zA-Z0-9_:]*)\s*;'
        )

        # Enum pattern
        self.enum_pattern = re.compile(
            r'^\s*enum(?:\s+class)?\s+([a-zA-Z_][a-zA-Z0-9_]*)'
            r'(?:\s*:\s*([a-zA-Z_][a-zA-Z0-9_]*))?'  # Optional underlying type
            r'\s*\{'
        )

        # Template pattern
        self.template_pattern = re.compile(
            r'^\s*template\s*<([^>]+)>'
        )

    def parse(self, code: str) -> List[CodeElement]:
        """
        Parse C/C++ code and extract all code elements.

        Args:
            code: The C/C++ code to parse.

        Returns:
            A list of CodeElement objects representing the parsed code.
        """
        self.elements = []

        # Split into lines for processing
        lines = self._split_into_lines(code)
        line_count = len(lines)

        # Stack to keep track of the current parent element
        stack = []

        # Track comments and docstrings
        in_comment_block = False
        comment_start = 0
        current_comment = []
        line_comments = {}  # Maps line number to comment text

        # Track template declarations
        current_template = None

        # Process lines
        line_idx = 0
        while line_idx < line_count:
            line = lines[line_idx]
            line_num = line_idx + 1  # Convert to 1-based indexing

            # Process C-style comments first
            if '/*' in line and not in_comment_block:
                comment_start = line_idx
                in_comment_block = True
                start_pos = line.find('/*')
                current_comment.append(line[start_pos:])
            elif '*/' in line and in_comment_block:
                end_pos = line.find('*/') + 2
                current_comment.append(line[:end_pos])
                # Store the complete comment
                comment_text = '\n'.join(current_comment)
                line_comments[comment_start] = comment_text
                in_comment_block = False
                current_comment = []
            elif in_comment_block:
                current_comment.append(line)

            # Process C++ line comments
            elif line.strip().startswith('//'):
                line_comments[line_idx] = line

            # Check for template declarations
            template_match = self.template_pattern.match(line)
            if template_match:
                current_template = template_match.group(1)
                line_idx += 1
                continue

            # Process class and struct definitions
            class_match = self.class_pattern.match(line)
            if class_match:
                class_type = class_match.group(1)  # 'class' or 'struct'
                class_name = class_match.group(2)
                parent_class = class_match.group(3) if class_match.group(3) else None

                # Find the end of the class (closing brace and semicolon)
                end_idx = self._find_matching_brace(lines, line_idx)

                # Extract the full class code
                class_code = "\n".join(lines[line_idx:end_idx+1])

                # Look for the preceding docstring/comment
                docstring = None
                if line_idx > 0:
                    # Get the closest preceding comment
                    for i in range(line_idx-1, -1, -1):
                        if i in line_comments:
                            docstring = line_comments[i]
                            break

                # Parent element will be the last item on the stack if any
                parent = stack[-1] if stack else None

                # Create metadata
                metadata = {
                    "parent_class": parent_class,
                    "docstring": docstring,
                    "template_params": current_template
                }

                # Create the class element
                element = CodeElement(
                    element_type=ElementType.CLASS if class_type == 'class' else ElementType.STRUCT,
                    name=class_name,
                    start_line=line_num-1,
                    end_line=end_idx,
                    code=class_code,
                    parent=parent,
                    metadata=metadata
                )

                self.elements.append(element)

                # Push the class onto the stack as the new parent
                stack.append(element)

                # Reset template state
                current_template = None

                # Skip to end of the class
                line_idx = end_idx + 1
                continue

            # Process function definitions and declarations
            function_match = self.function_pattern.match(line)
            if function_match:
                return_type = function_match.group(1).strip()
                func_name = function_match.group(2)
                params = function_match.group(3)

                # Determine if this is just a declaration or a definition
                is_definition = '{' in line

                if is_definition:
                    # Find the end of the function (closing brace)
                    end_idx = self._find_matching_brace(lines, line_idx)

                    # Extract the full function code
                    func_code = "\n".join(lines[line_idx:end_idx+1])

                    # Look for the preceding docstring/comment
                    docstring = None
                    if line_idx > 0:
                        # Get the closest preceding comment
                        for i in range(line_idx-1, -1, -1):
                            if i in line_comments:
                                docstring = line_comments[i]
                                break

                    # Parent element will be the last item on the stack if any
                    parent = stack[-1] if stack else None

                    # Determine if this is a method or a function
                    element_type = ElementType.METHOD if parent and parent.element_type in [ElementType.CLASS, ElementType.STRUCT] else ElementType.FUNCTION

                    # Create metadata
                    metadata = {
                        "return_type": return_type,
                        "parameters": params,
                        "docstring": docstring,
                        "template_params": current_template
                    }

                    # Create the function element
                    element = CodeElement(
                        element_type=element_type,
                        name=func_name,
                        start_line=line_num-1,
                        end_line=end_idx,
                        code=func_code,
                        parent=parent,
                        metadata=metadata
                    )

                    self.elements.append(element)

                    # Reset template state
                    current_template = None

                    # Skip to the end of the function
                    line_idx = end_idx + 1
                    continue
                else:
                    # This is just a declaration (ends with semicolon)
                    # Extract just the declaration
                    func_code = line

                    # Look for the preceding docstring/comment
                    docstring = None
                    if line_idx > 0:
                        # Get the closest preceding comment
                        for i in range(line_idx-1, -1, -1):
                            if i in line_comments:
                                docstring = line_comments[i]
                                break

                    # Parent element will be the last item on the stack if any
                    parent = stack[-1] if stack else None

                    # Determine if this is a method or a function
                    element_type = ElementType.METHOD if parent and parent.element_type in [ElementType.CLASS, ElementType.STRUCT] else ElementType.FUNCTION

                    # Create metadata
                    metadata = {
                        "return_type": return_type,
                        "parameters": params,
                        "docstring": docstring,
                        "template_params": current_template,
                        "is_declaration": True
                    }

                    # Create the function element
                    element = CodeElement(
                        element_type=element_type,
                        name=func_name,
                        start_line=line_num-1,
                        end_line=line_num,
                        code=func_code,
                        parent=parent,
                        metadata=metadata
                    )

                    self.elements.append(element)

                    # Reset template state
                    current_template = None

                    # Move to the next line
                    line_idx += 1
                    continue

            # Process namespace definitions
            namespace_match = self.namespace_pattern.match(line)
            if namespace_match:
                namespace_name = namespace_match.group(1)

                # Find the end of the namespace (closing brace)
                end_idx = self._find_matching_brace(lines, line_idx)

                # Extract the full namespace code
                namespace_code = "\n".join(lines[line_idx:end_idx+1])

                # Look for the preceding docstring/comment
                docstring = None
                if line_idx > 0:
                    # Get the closest preceding comment
                    for i in range(line_idx-1, -1, -1):
                        if i in line_comments:
                            docstring = line_comments[i]
                            break

                # Parent element will be the last item on the stack if any
                parent = stack[-1] if stack else None

                # Create the namespace element
                element = CodeElement(
                    element_type=ElementType.NAMESPACE,
                    name=namespace_name,
                    start_line=line_num-1,
                    end_line=end_idx,
                    code=namespace_code,
                    parent=parent,
                    metadata={"docstring": docstring}
                )

                self.elements.append(element)

                # Push the namespace onto the stack as the new parent
                stack.append(element)

                # Skip to end of the namespace
                line_idx = end_idx + 1
                continue

            # Process enum definitions
            enum_match = self.enum_pattern.match(line)
            if enum_match:
                enum_name = enum_match.group(1)
                underlying_type = enum_match.group(2) if enum_match.group(2) else None

                # Find the end of the enum (closing brace and semicolon)
                end_idx = self._find_matching_brace(lines, line_idx)

                # Extract the full enum code
                enum_code = "\n".join(lines[line_idx:end_idx+1])

                # Look for the preceding docstring/comment
                docstring = None
                if line_idx > 0:
                    # Get the closest preceding comment
                    for i in range(line_idx-1, -1, -1):
                        if i in line_comments:
                            docstring = line_comments[i]
                            break

                # Parent element will be the last item on the stack if any
                parent = stack[-1] if stack else None

                # Create the enum element
                element = CodeElement(
                    element_type=ElementType.ENUM,
                    name=enum_name,
                    start_line=line_num-1,
                    end_line=end_idx,
                    code=enum_code,
                    parent=parent,
                    metadata={
                        "docstring": docstring,
                        "underlying_type": underlying_type
                    }
                )

                self.elements.append(element)

                # Skip to end of the enum
                line_idx = end_idx + 1
                continue

            # Process variable declarations
            variable_match = self.variable_pattern.match(line)
            if variable_match:
                var_type = variable_match.group(1).strip()
                var_name = variable_match.group(2)

                # Look for the preceding docstring/comment
                docstring = None
                if line_idx > 0:
                    # Get the closest preceding comment
                    for i in range(line_idx-1, -1, -1):
                        if i in line_comments:
                            docstring = line_comments[i]
                            break

                # Parent element will be the last item on the stack if any
                parent = stack[-1] if stack else None

                # Create the variable element
                element = CodeElement(
                    element_type=ElementType.VARIABLE,
                    name=var_name,
                    start_line=line_num-1,
                    end_line=line_num,
                    code=line,
                    parent=parent,
                    metadata={
                        "type": var_type,
                        "docstring": docstring
                    }
                )

                self.elements.append(element)

                # Move to the next line
                line_idx += 1
                continue

            # Process constant definitions
            constant_match = self.constant_pattern.match(line)
            if constant_match:
                const_name = constant_match.group(1)
                const_value = constant_match.group(2).strip()

                # Look for the preceding docstring/comment
                docstring = None
                if line_idx > 0:
                    # Get the closest preceding comment
                    for i in range(line_idx-1, -1, -1):
                        if i in line_comments:
                            docstring = line_comments[i]
                            break

                # Parent element will be the last item on the stack if any
                parent = stack[-1] if stack else None

                # Create the constant element
                element = CodeElement(
                    element_type=ElementType.CONSTANT,
                    name=const_name,
                    start_line=line_num-1,
                    end_line=line_num,
                    code=line,
                    parent=parent,
                    metadata={
                        "value": const_value,
                        "docstring": docstring
                    }
                )

                self.elements.append(element)

                # Move to the next line
                line_idx += 1
                continue

            # Process includes
            include_match = self.include_pattern.match(line)
            if include_match:
                include_name = include_match.group(1) if include_match.group(1) else include_match.group(2)

                # Create the include element
                element = CodeElement(
                    element_type=ElementType.IMPORT,
                    name=include_name,
                    start_line=line_num-1,
                    end_line=line_num,
                    code=line,
                    parent=None,
                    metadata={"is_system": bool(include_match.group(1))}
                )

                self.elements.append(element)

                # Move to the next line
                line_idx += 1
                continue

            # Process using directives
            using_match = self.using_pattern.match(line)
            if using_match:
                is_namespace = bool(using_match.group(1))
                using_name = using_match.group(2)

                # Create the using element
                element = CodeElement(
                    element_type=ElementType.IMPORT if is_namespace else ElementType.TYPE_ALIAS,
                    name=using_name,
                    start_line=line_num-1,
                    end_line=line_num,
                    code=line,
                    parent=None,
                    metadata={"is_namespace": is_namespace}
                )

                self.elements.append(element)

                # Move to the next line
                line_idx += 1
                continue

            # Check for closing braces to pop the stack
            if line.strip() == '}' or line.strip() == '};':
                if stack:
                    stack.pop()

            # Move to the next line
            line_idx += 1

        # Process parent-child relationships for nested elements
        self._process_parent_child_relationships()

        return self.elements

    def _find_matching_brace(self, lines: List[str], start_idx: int) -> int:
        """
        Find the line number of the matching closing brace for a given opening brace.

        Args:
            lines: List of code lines
            start_idx: Index of the line with the opening brace

        Returns:
            Index of the line with the matching closing brace
        """
        brace_count = 0
        in_string = False
        in_char = False
        in_line_comment = False
        in_block_comment = False

        # Find the opening brace in the start line
        for char in lines[start_idx]:
            if char == '"' and not in_char and not in_line_comment and not in_block_comment:
                in_string = not in_string
            elif char == "'" and not in_string and not in_line_comment and not in_block_comment:
                in_char = not in_char
            elif char == '/' and not in_string and not in_char:
                if in_line_comment:
                    continue
                if in_block_comment and char == '*':
                    in_block_comment = False
                    continue
                in_line_comment = True
            elif char == '*' and not in_string and not in_char and not in_line_comment:
                if in_block_comment:
                    in_block_comment = False
                    continue
                in_block_comment = True
            elif char == '{' and not in_string and not in_char and not in_line_comment and not in_block_comment:
                brace_count += 1

        # Search for the matching brace in subsequent lines
        for i in range(start_idx + 1, len(lines)):
            line = lines[i]
            j = 0
            while j < len(line):
                char = line[j]
                if char == '"' and not in_char and not in_line_comment and not in_block_comment:
                    in_string = not in_string
                elif char == "'" and not in_string and not in_line_comment and not in_block_comment:
                    in_char = not in_char
                elif char == '/' and j < len(line) - 1 and line[j+1] == '/' and not in_string and not in_char and not in_block_comment:
                    in_line_comment = True
                    j += 2
                    continue
                elif char == '/' and j < len(line) - 1 and line[j+1] == '*' and not in_string and not in_char and not in_line_comment:
                    in_block_comment = True
                    j += 2
                    continue
                elif char == '*' and j < len(line) - 1 and line[j+1] == '/' and not in_string and not in_char and in_block_comment:
                    in_block_comment = False
                    j += 2
                    continue
                elif char == '{' and not in_string and not in_char and not in_line_comment and not in_block_comment:
                    brace_count += 1
                elif char == '}' and not in_string and not in_char and not in_line_comment and not in_block_comment:
                    brace_count -= 1
                    if brace_count == 0:
                        return i
                j += 1

            # Reset line comment flag at the end of each line
            in_line_comment = False

        # If no matching brace found, return the last line
        return len(lines) - 1

    def find_function(self, code: str, function_name: str) -> Optional[CodeElement]:
        """
        Find a function by name in the code.

        Args:
            code: The C/C++ code to search.
            function_name: The name of the function to find.

        Returns:
            A CodeElement for the found function, or None if not found.
        """
        elements = self.parse(code)
        for element in elements:
            if (element.element_type == ElementType.FUNCTION or 
                element.element_type == ElementType.METHOD) and element.name == function_name:
                return element
        return None
    
    def find_class(self, code: str, class_name: str) -> Optional[CodeElement]:
        """
        Find a class by name in the code.

        Args:
            code: The C/C++ code to search.
            class_name: The name of the class to find.

        Returns:
            A CodeElement for the found class, or None if not found.
        """
        elements = self.parse(code)
        for element in elements:
            if element.element_type == ElementType.CLASS and element.name == class_name:
                return element
        return None

    def get_all_globals(self, code: str) -> Dict[str, CodeElement]:
        """
        Get all global elements (functions, classes, variables, etc.) in the code.

        Args:
            code: The C/C++ code to analyze.

        Returns:
            A dictionary mapping global element names to their CodeElement objects.
        """
        elements = self.parse(code)
        globals_dict = {}
        
        for element in elements:
            # Only include top-level elements (no parent)
            if element.parent is None:
                globals_dict[element.name] = element
        
        return globals_dict

    def _process_parent_child_relationships(self):
        """
        Process parent-child relationships for nested elements.
        This should be called after all elements have been identified.
        """
        # Update children lists for all parents
        for element in self.elements:
            if element.parent:
                if not hasattr(element.parent, 'children'):
                    element.parent.children = []
                element.parent.children.append(element)

    def check_syntax_validity(self, code: str) -> bool:
        """
        Check if the code has valid C/C++ syntax.
        
        This is a simple check and not a full compilation. It looks for unbalanced
        braces, missing semicolons, and other common issues.

        Args:
            code: The C/C++ code to check.

        Returns:
            True if the code appears to have valid syntax, False otherwise.
        """
        try:
            # Check for balanced braces
            brace_count = 0
            in_string = False
            in_char = False
            in_line_comment = False
            in_block_comment = False
            
            for char in code:
                if char == '"' and not in_char and not in_line_comment and not in_block_comment:
                    in_string = not in_string
                elif char == "'" and not in_string and not in_line_comment and not in_block_comment:
                    in_char = not in_char
                elif char == '/' and not in_string and not in_char:
                    if in_line_comment:
                        continue
                    if in_block_comment and char == '*':
                        in_block_comment = False
                        continue
                    in_line_comment = True
                elif char == '*' and not in_string and not in_char and not in_line_comment:
                    if in_block_comment:
                        in_block_comment = False
                        continue
                    in_block_comment = True
                elif char == '\n':
                    in_line_comment = False
                elif char == '{' and not in_string and not in_char and not in_line_comment and not in_block_comment:
                    brace_count += 1
                elif char == '}' and not in_string and not in_char and not in_line_comment and not in_block_comment:
                    brace_count -= 1
                    if brace_count < 0:
                        return False
            
            if brace_count != 0 or in_string or in_char or in_block_comment:
                return False
            
            # Simple check for function calls without semicolons
            lines = self._split_into_lines(code)
            for line in lines:
                line = line.strip()
                if (line and not line.startswith('#') and not line.startswith('/') and
                    not line.endswith('{') and not line.endswith('}') and 
                    not line.endswith(';') and not line.endswith('\\') and
                    not line.endswith(':')):
                    # Check for function calls without semicolons
                    if re.search(r'[a-zA-Z_][a-zA-Z0-9_]*\([^)]*\)', line):
                        return False
            
            return True
            
        except Exception:
            return False
