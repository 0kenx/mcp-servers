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
        
        # Include pattern
        self.include_pattern = re.compile(
            r'^\s*#\s*include\s*[<"]([^>"]+)[>"]'
        )
        
        # Typedef and using patterns
        self.typedef_pattern = re.compile(
            r'^\s*typedef\s+(.+?)\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*;'
        )
        
        self.using_pattern = re.compile(
            r'^\s*using\s+([a-zA-Z_][a-zA-Z0-9_]*)'
            r'(?:\s*=\s*(.+))?;'
        )
        
        # Preprocessor macro definition
        self.define_pattern = re.compile(
            r'^\s*#\s*define\s+([a-zA-Z_][a-zA-Z0-9_]*)'
            r'(?:\(([^)]*)\))?'  # Optional macro parameters
            r'(?:\s+(.*))?'  # Optional macro body
        )
        
        # Enum pattern
        self.enum_pattern = re.compile(
            r'^\s*(?:enum\s+class|enum)\s+([a-zA-Z_][a-zA-Z0-9_]*)'
            r'(?:\s*:\s*([a-zA-Z_][a-zA-Z0-9_]*))?\s*\{'
        )
        
        # Template pattern
        self.template_pattern = re.compile(
            r'^\s*template\s*<(.+?)>'
        )
        
    def parse(self, code: str) -> List[CodeElement]:
        """
        Parse C/C++ code and extract structured information.
        
        Args:
            code: C/C++ source code
            
        Returns:
            List of identified code elements
        """
        self.elements = []
        
        # First, normalize line endings
        code = code.replace('\r\n', '\n').replace('\r', '\n')
        
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
                if line_idx > 0 and (line_idx - 1) in line_comments:
                    docstring = line_comments[line_idx - 1]
                
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
                    start_line=line_num,
                    end_line=end_idx + 1,
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
                    if line_idx > 0 and (line_idx - 1) in line_comments:
                        docstring = line_comments[line_idx - 1]
                    
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
                        start_line=line_num,
                        end_line=end_idx + 1,
                        code=func_code,
                        parent=parent,
                        metadata=metadata
                    )
                    
                    self.elements.append(element)
                    
                    # Reset template state
                    current_template = None
                    
                    # Skip to end of the function
                    line_idx = end_idx + 1
                else:
                    # This is just a declaration, handle in a simpler way
                    func_code = line.strip()
                    
                    # Look for the preceding docstring/comment
                    docstring = None
                    if line_idx > 0 and (line_idx - 1) in line_comments:
                        docstring = line_comments[line_idx - 1]
                    
                    # Parent element will be the last item on the stack if any
                    parent = stack[-1] if stack else None
                    
                    # Determine if this is a method or a function
                    element_type = ElementType.METHOD if parent and parent.element_type in [ElementType.CLASS, ElementType.STRUCT] else ElementType.FUNCTION
                    
                    # Create metadata
                    metadata = {
                        "return_type": return_type,
                        "parameters": params,
                        "docstring": docstring,
                        "is_declaration": True,
                        "template_params": current_template
                    }
                    
                    # Create the function element
                    element = CodeElement(
                        element_type=element_type,
                        name=func_name,
                        start_line=line_num,
                        end_line=line_num,
                        code=func_code,
                        parent=parent,
                        metadata=metadata
                    )
                    
                    self.elements.append(element)
                    
                    # Reset template state
                    current_template = None
                    
                    # Move to next line
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
                if line_idx > 0 and (line_idx - 1) in line_comments:
                    docstring = line_comments[line_idx - 1]
                
                # Parent element will be the last item on the stack if any
                parent = stack[-1] if stack else None
                
                # Create the namespace element
                element = CodeElement(
                    element_type=ElementType.NAMESPACE,
                    name=namespace_name,
                    start_line=line_num,
                    end_line=end_idx + 1,
                    code=namespace_code,
                    parent=parent,
                    metadata={"docstring": docstring}
                )
                
                self.elements.append(element)
                
                # Push the namespace onto the stack as the new parent
                stack.append(element)
                
                # Move to next line (we'll still process the contents of the namespace)
                line_idx += 1
                continue
            
            # Process enum definitions
            enum_match = self.enum_pattern.match(line)
            if enum_match:
                enum_name = enum_match.group(1)
                base_type = enum_match.group(2) if enum_match.group(2) else None
                
                # Find the end of the enum (closing brace and semicolon)
                end_idx = self._find_matching_brace(lines, line_idx)
                
                # Extract the full enum code
                enum_code = "\n".join(lines[line_idx:end_idx+1])
                
                # Look for the preceding docstring/comment
                docstring = None
                if line_idx > 0 and (line_idx - 1) in line_comments:
                    docstring = line_comments[line_idx - 1]
                
                # Parent element will be the last item on the stack if any
                parent = stack[-1] if stack else None
                
                # Create metadata
                metadata = {
                    "base_type": base_type,
                    "docstring": docstring
                }
                
                # Create the enum element
                element = CodeElement(
                    element_type=ElementType.ENUM,
                    name=enum_name,
                    start_line=line_num,
                    end_line=end_idx + 1,
                    code=enum_code,
                    parent=parent,
                    metadata=metadata
                )
                
                self.elements.append(element)
                
                # Skip to end of the enum
                line_idx = end_idx + 1
                continue
            
            # Process typedefs
            typedef_match = self.typedef_pattern.match(line)
            if typedef_match:
                original_type = typedef_match.group(1).strip()
                new_type_name = typedef_match.group(2)
                
                # Look for the preceding docstring/comment
                docstring = None
                if line_idx > 0 and (line_idx - 1) in line_comments:
                    docstring = line_comments[line_idx - 1]
                
                # Parent element will be the last item on the stack if any
                parent = stack[-1] if stack else None
                
                # Create the typedef element
                element = CodeElement(
                    element_type=ElementType.TYPE_DEFINITION,
                    name=new_type_name,
                    start_line=line_num,
                    end_line=line_num,
                    code=line.strip(),
                    parent=parent,
                    metadata={
                        "original_type": original_type,
                        "docstring": docstring,
                        "kind": "typedef"
                    }
                )
                
                self.elements.append(element)
                
                # Move to next line
                line_idx += 1
                continue
            
            # Process using directives and type aliases
            using_match = self.using_pattern.match(line)
            if using_match:
                alias_name = using_match.group(1)
                original_type = using_match.group(2) if using_match.group(2) else None
                
                # Look for the preceding docstring/comment
                docstring = None
                if line_idx > 0 and (line_idx - 1) in line_comments:
                    docstring = line_comments[line_idx - 1]
                
                # Parent element will be the last item on the stack if any
                parent = stack[-1] if stack else None
                
                # Create the using element
                element = CodeElement(
                    element_type=ElementType.TYPE_DEFINITION if original_type else ElementType.IMPORT,
                    name=alias_name,
                    start_line=line_num,
                    end_line=line_num,
                    code=line.strip(),
                    parent=parent,
                    metadata={
                        "original_type": original_type,
                        "docstring": docstring,
                        "kind": "using"
                    }
                )
                
                self.elements.append(element)
                
                # Move to next line
                line_idx += 1
                continue
            
            # Process include directives
            include_match = self.include_pattern.match(line)
            if include_match:
                include_path = include_match.group(1)
                
                # Create the include element
                element = CodeElement(
                    element_type=ElementType.IMPORT,
                    name=include_path,
                    start_line=line_num,
                    end_line=line_num,
                    code=line.strip(),
                    parent=None,
                    metadata={"kind": "include"}
                )
                
                self.elements.append(element)
                
                # Move to next line
                line_idx += 1
                continue
            
            # Process preprocessor macro definitions
            define_match = self.define_pattern.match(line)
            if define_match:
                macro_name = define_match.group(1)
                macro_params = define_match.group(2) if define_match.group(2) else None
                macro_body = define_match.group(3) if define_match.group(3) else None
                
                # Create the define element
                element = CodeElement(
                    element_type=ElementType.CONSTANT if not macro_params else ElementType.FUNCTION,
                    name=macro_name,
                    start_line=line_num,
                    end_line=line_num,
                    code=line.strip(),
                    parent=None,
                    metadata={
                        "parameters": macro_params,
                        "body": macro_body,
                        "kind": "macro"
                    }
                )
                
                self.elements.append(element)
                
                # Move to next line
                line_idx += 1
                continue
            
            # Process global variables (only at global or namespace scope)
            if len(stack) <= 1:  # Only at global or namespace scope
                variable_match = self.variable_pattern.match(line)
                if variable_match:
                    var_type = variable_match.group(1).strip()
                    var_name = variable_match.group(2)
                    
                    # Look for the preceding docstring/comment
                    docstring = None
                    if line_idx > 0 and (line_idx - 1) in line_comments:
                        docstring = line_comments[line_idx - 1]
                    
                    # Parent element will be the last item on the stack if any
                    parent = stack[-1] if stack else None
                    
                    # Create the variable element
                    element = CodeElement(
                        element_type=ElementType.VARIABLE,
                        name=var_name,
                        start_line=line_num,
                        end_line=line_num,
                        code=line.strip(),
                        parent=parent,
                        metadata={
                            "type": var_type,
                            "docstring": docstring
                        }
                    )
                    
                    self.elements.append(element)
            
            # Update stack when we encounter the end of a block
            if line.strip() == '}' and stack:
                # Pop the stack when we exit a block
                stack.pop()
            
            # Move to next line
            line_idx += 1
        
        return self.elements
    
    def _find_matching_brace(self, lines: List[str], start_idx: int) -> int:
        """
        Find the matching closing brace for an opening brace.
        
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
        
        # Count the opening brace on the start line
        for char in lines[start_idx]:
            if char == '"' and not in_char and not in_line_comment and not in_block_comment:
                # Toggle string state, but only if not preceded by backslash
                # This is a simplification, doesn't handle escaped backslashes properly
                in_string = not in_string
            elif char == "'" and not in_string and not in_line_comment and not in_block_comment:
                # Toggle char state
                in_char = not in_char
            elif char == '/' and not in_string and not in_char:
                if in_line_comment:
                    continue
                if in_block_comment and char == '/' and lines[start_idx][max(0, i-1)] == '*':
                    in_block_comment = False
                    continue
                if not in_block_comment and char == '/' and i+1 < len(lines[start_idx]) and lines[start_idx][i+1] == '/':
                    in_line_comment = True
                    continue
                if not in_block_comment and char == '/' and i+1 < len(lines[start_idx]) and lines[start_idx][i+1] == '*':
                    in_block_comment = True
                    continue
            elif char == '*' and not in_string and not in_char and i+1 < len(lines[start_idx]) and lines[start_idx][i+1] == '/':
                if in_block_comment:
                    in_block_comment = False
                    continue
            elif char == '{' and not in_string and not in_char and not in_line_comment and not in_block_comment:
                brace_count += 1
            elif char == '}' and not in_string and not in_char and not in_line_comment and not in_block_comment:
                brace_count -= 1
                if brace_count == 0:
                    return start_idx
        
        # Continue searching in subsequent lines
        for i in range(start_idx + 1, len(lines)):
            in_line_comment = False  # Reset line comment flag for new line
            
            for j, char in enumerate(lines[i]):
                if char == '"' and not in_char and not in_line_comment and not in_block_comment:
                    # Handle string literals
                    if j > 0 and lines[i][j-1] == '\\':
                        # Escaped quote, not a string boundary
                        pass
                    else:
                        in_string = not in_string
                elif char == "'" and not in_string and not in_line_comment and not in_block_comment:
                    # Handle character literals
                    if j > 0 and lines[i][j-1] == '\\':
                        # Escaped quote, not a char boundary
                        pass
                    else:
                        in_char = not in_char
                elif not in_string and not in_char:
                    # Handle comments and braces only when not in string/char literals
                    if j < len(lines[i]) - 1 and char == '/' and lines[i][j+1] == '/' and not in_block_comment:
                        in_line_comment = True
                    elif j < len(lines[i]) - 1 and char == '/' and lines[i][j+1] == '*' and not in_line_comment:
                        in_block_comment = True
                    elif j > 0 and char == '/' and lines[i][j-1] == '*' and in_block_comment:
                        in_block_comment = False
                    elif char == '{' and not in_line_comment and not in_block_comment:
                        brace_count += 1
                    elif char == '}' and not in_line_comment and not in_block_comment:
                        brace_count -= 1
                        if brace_count == 0:
                            return i
        
        # If we couldn't find the matching brace, return the last line
        return len(lines) - 1
    
    def check_syntax_validity(self, code: str) -> bool:
        """
        Perform a basic check for C/C++ syntax validity.
        This is a simplified check that only looks for balanced braces, parentheses, etc.
        
        Args:
            code: C/C++ source code
            
        Returns:
            True if syntax appears valid, False otherwise
        """
        # This is a very simplified check
        # For a comprehensive check, we'd need a full C/C++ parser
        
        # Strip comments first
        code_without_comments = self._strip_comments(code, '//', '/*', '*/')
        
        # Check for balanced braces, parentheses, and brackets
        brace_count = 0
        paren_count = 0
        bracket_count = 0
        
        for char in code_without_comments:
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
