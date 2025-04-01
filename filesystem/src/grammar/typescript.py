"""
TypeScript language parser for extracting structured information from TypeScript code.
"""

import re
from typing import List, Dict, Optional, Tuple, Set, Any
from .javascript import JavaScriptParser
from .base import CodeElement, ElementType


class TypeScriptParser(JavaScriptParser):
    """
    Parser for TypeScript code that extends the JavaScript parser.
    Handles additional TypeScript syntax elements like interfaces, type aliases, etc.
    """
    
    def __init__(self):
        """Initialize the TypeScript parser."""
        super().__init__()
        
        # Additional patterns for TypeScript-specific elements
        
        # Interface declarations
        self.interface_pattern = re.compile(
            r'^\s*(?:export\s+)?interface\s+([a-zA-Z_$][a-zA-Z0-9_$]*)'
            r'(?:\s+extends\s+([a-zA-Z_$][a-zA-Z0-9_$.,\s]*))?'
            r'\s*\{'
        )
        
        # Type aliases
        self.type_pattern = re.compile(
            r'^\s*(?:export\s+)?type\s+([a-zA-Z_$][a-zA-Z0-9_$]*)'
            r'(?:<.*?>)?\s*='
        )
        
        # Enum declarations
        self.enum_pattern = re.compile(
            r'^\s*(?:export\s+)?(?:const\s+)?enum\s+([a-zA-Z_$][a-zA-Z0-9_$]*)'
            r'\s*\{'
        )
        
        # Function declarations with return type
        self.ts_function_pattern = re.compile(
            r'^\s*(?:export\s+)?(?:async\s+)?function\s*(?:\*\s*)?([a-zA-Z_$][a-zA-Z0-9_$]*)'
            r'\s*(?:<.*?>)?\s*\((.*?)\)'
            r'\s*(?::\s*([a-zA-Z_$][a-zA-Z0-9_$<>\[\],\.\s|&]*))?\s*'
            r'(?:\{|=>)'
        )
        
        # Arrow functions with type annotations
        self.ts_arrow_function_pattern = re.compile(
            r'^\s*(?:export\s+)?(?:const|let|var)\s+([a-zA-Z_$][a-zA-Z0-9_$]*)'
            r'\s*(?::\s*([a-zA-Z_$][a-zA-Z0-9_$<>\[\],\.\s|&]*))?'
            r'\s*=\s*(?:async\s+)?(?:\((.*?)\)|([a-zA-Z_$][a-zA-Z0-9_$]*))'
            r'\s*(?::\s*([a-zA-Z_$][a-zA-Z0-9_$<>\[\],\.\s|&]*))?\s*=>'
        )
        
        # Class properties with type annotations
        self.class_property_pattern = re.compile(
            r'^\s*(?:private\s+|protected\s+|public\s+|readonly\s+)*'
            r'([a-zA-Z_$][a-zA-Z0-9_$]*)'
            r'\s*(?:\?\s*)?:\s*([a-zA-Z_$][a-zA-Z0-9_$<>\[\],\.\s|&]*)'
            r'\s*(?:=\s*([^;]*))?;'
        )
        
        # Constructor parameters with visibility modifiers (shorthand for class properties)
        self.constructor_param_pattern = re.compile(
            r'^\s*constructor\s*\(\s*'
            r'(?:private|protected|public|readonly)\s+'
        )
        
        # Namespace declarations
        self.namespace_pattern = re.compile(
            r'^\s*(?:export\s+)?namespace\s+([a-zA-Z_$][a-zA-Z0-9_$\.]*)'
            r'\s*\{'
        )
        
        # Decorator pattern
        self.decorator_pattern = re.compile(
            r'^\s*@([a-zA-Z_$][a-zA-Z0-9_$\.]*)'
            r'(?:\(.*\))?'
        )
        
    def parse(self, code: str) -> List[CodeElement]:
        """
        Parse TypeScript code and extract structured information.
        Extends the JavaScript parser with TypeScript-specific elements.
        
        Args:
            code: TypeScript source code
            
        Returns:
            List of identified code elements
        """
        # Start with basic JavaScript parsing
        elements = super().parse(code)
        
        # Now we'll handle TypeScript-specific elements
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
        
        # Track line comments for documentation
        line_comments = {}  # Maps line number to comment text
        
        # Track decorators
        decorators = []
        
        # Process lines
        line_idx = 0
        while line_idx < line_count:
            line = lines[line_idx]
            line_num = line_idx + 1  # Convert to 1-based indexing
            
            # Process JSDoc comments
            if self.jsdoc_pattern.match(line) and not in_jsdoc:
                in_jsdoc = True
                current_jsdoc = [line]
            elif in_jsdoc:
                current_jsdoc.append(line)
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
                if line_idx - 1 in line_comments and line_idx - 2 not in line_comments:
                    # Add to previous comment if they're adjacent
                    line_comments[line_idx - 1] += '\n' + line
                else:
                    line_comments[line_idx] = line
            
            # Skip empty lines and comments
            if not line.strip() or line.strip().startswith('//') or in_jsdoc:
                line_idx += 1
                continue
            
            # Check for decorators
            decorator_match = self.decorator_pattern.match(line)
            if decorator_match:
                # Store the decorator to associate with the next class/method/property
                decorators.append((decorator_match.group(1), line.strip()))
                line_idx += 1
                continue
            
            # Check for interface declarations
            interface_match = self.interface_pattern.match(line)
            if interface_match:
                interface_name = interface_match.group(1)
                extends_clause = interface_match.group(2) if interface_match.group(2) else None
                
                # Find the end of the interface (closing brace)
                end_idx = self._find_matching_brace(lines, line_idx)
                
                # Extract the full interface code
                interface_code = "\n".join(lines[line_idx:end_idx+1])
                
                # Look for preceding JSDoc comment
                jsdoc = None
                for i in range(line_idx-1, max(0, line_idx-10), -1):
                    if i in line_comments:
                        jsdoc = line_comments[i]
                        break
                
                # Parent element will be the last item on the stack if any
                parent = stack[-1] if stack else None
                
                # Create the interface element
                element = CodeElement(
                    element_type=ElementType.INTERFACE,
                    name=interface_name,
                    start_line=line_num,
                    end_line=end_idx + 1,
                    code=interface_code,
                    parent=parent,
                    metadata={
                        "extends": extends_clause,
                        "docstring": jsdoc,
                        "decorators": decorators.copy() if decorators else None
                    }
                )
                
                # Clear decorators
                decorators = []
                
                # Add to list of elements
                elements.append(element)
                
                # Skip to end of the interface
                line_idx = end_idx + 1
                continue
            
            # Check for type alias declarations
            type_match = self.type_pattern.match(line)
            if type_match:
                type_name = type_match.group(1)
                
                # Find the end of the type declaration (semicolon)
                end_idx = line_idx
                for i in range(line_idx, line_count):
                    if ';' in lines[i]:
                        end_idx = i
                        break
                
                # Extract the full type code
                type_code = "\n".join(lines[line_idx:end_idx+1])
                
                # Look for preceding JSDoc comment
                jsdoc = None
                for i in range(line_idx-1, max(0, line_idx-10), -1):
                    if i in line_comments:
                        jsdoc = line_comments[i]
                        break
                
                # Parent element will be the last item on the stack if any
                parent = stack[-1] if stack else None
                
                # Create the type element
                element = CodeElement(
                    element_type=ElementType.TYPE_DEFINITION,
                    name=type_name,
                    start_line=line_num,
                    end_line=end_idx + 1,
                    code=type_code,
                    parent=parent,
                    metadata={
                        "docstring": jsdoc,
                        "decorators": decorators.copy() if decorators else None
                    }
                )
                
                # Clear decorators
                decorators = []
                
                # Add to list of elements
                elements.append(element)
                
                # Skip to end of the type declaration
                line_idx = end_idx + 1
                continue
            
            # Check for enum declarations
            enum_match = self.enum_pattern.match(line)
            if enum_match:
                enum_name = enum_match.group(1)
                
                # Find the end of the enum (closing brace)
                end_idx = self._find_matching_brace(lines, line_idx)
                
                # Extract the full enum code
                enum_code = "\n".join(lines[line_idx:end_idx+1])
                
                # Look for preceding JSDoc comment
                jsdoc = None
                for i in range(line_idx-1, max(0, line_idx-10), -1):
                    if i in line_comments:
                        jsdoc = line_comments[i]
                        break
                
                # Parent element will be the last item on the stack if any
                parent = stack[-1] if stack else None
                
                # Create the enum element
                element = CodeElement(
                    element_type=ElementType.ENUM,
                    name=enum_name,
                    start_line=line_num,
                    end_line=end_idx + 1,
                    code=enum_code,
                    parent=parent,
                    metadata={
                        "docstring": jsdoc,
                        "decorators": decorators.copy() if decorators else None,
                        "is_const": 'const' in line and 'const' in line.split('enum')[0]
                    }
                )
                
                # Clear decorators
                decorators = []
                
                # Add to list of elements
                elements.append(element)
                
                # Skip to end of the enum
                line_idx = end_idx + 1
                continue
            
            # Check for namespace declarations
            namespace_match = self.namespace_pattern.match(line)
            if namespace_match:
                namespace_name = namespace_match.group(1)
                
                # Find the end of the namespace (closing brace)
                end_idx = self._find_matching_brace(lines, line_idx)
                
                # Extract the full namespace code
                namespace_code = "\n".join(lines[line_idx:end_idx+1])
                
                # Look for preceding JSDoc comment
                jsdoc = None
                for i in range(line_idx-1, max(0, line_idx-10), -1):
                    if i in line_comments:
                        jsdoc = line_comments[i]
                        break
                
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
                    metadata={
                        "docstring": jsdoc,
                        "decorators": decorators.copy() if decorators else None
                    }
                )
                
                # Clear decorators
                decorators = []
                
                # Add to list of elements
                elements.append(element)
                
                # Push the namespace onto the stack as the new parent
                stack.append(element)
                
                # Move to next line, we'll process the namespace contents later
                line_idx += 1
                continue
            
            # Inside a class, check for class properties with type annotations
            if stack and stack[-1].element_type == ElementType.CLASS:
                property_match = self.class_property_pattern.match(line)
                if property_match:
                    property_name = property_match.group(1)
                    property_type = property_match.group(2)
                    
                    # Look for preceding JSDoc comment
                    jsdoc = None
                    for i in range(line_idx-1, max(0, line_idx-10), -1):
                        if i in line_comments:
                            jsdoc = line_comments[i]
                            break
                    
                    # Parent is the current class
                    parent = stack[-1]
                    
                    # Check for access modifiers
                    is_private = 'private' in line and 'private' in line.split(property_name)[0]
                    is_protected = 'protected' in line and 'protected' in line.split(property_name)[0]
                    is_readonly = 'readonly' in line and 'readonly' in line.split(property_name)[0]
                    
                    # Create the property element
                    element = CodeElement(
                        element_type=ElementType.VARIABLE,
                        name=property_name,
                        start_line=line_num,
                        end_line=line_num,
                        code=line.strip(),
                        parent=parent,
                        metadata={
                            "type": property_type,
                            "docstring": jsdoc,
                            "is_private": is_private,
                            "is_protected": is_protected,
                            "is_readonly": is_readonly,
                            "decorators": decorators.copy() if decorators else None
                        }
                    )
                    
                    # Clear decorators
                    decorators = []
                    
                    # Add to list of elements
                    elements.append(element)
                    
                    # Move to next line
                    line_idx += 1
                    continue
            
            # If we've processed a line with decorators but didn't match any of the types above,
            # clear the decorator list to avoid associating them incorrectly
            if decorators and not self.decorator_pattern.match(line):
                decorators = []
            
            # Handle closing braces that pop elements off the stack
            if line.strip() == '}' and stack:
                stack.pop()
            
            # Move to next line
            line_idx += 1
        
        return elements
    
    def get_all_globals(self, code: str) -> Dict[str, CodeElement]:
        """
        Get all global elements in the code, including TypeScript specific elements.
        
        Args:
            code: TypeScript source code
            
        Returns:
            Dictionary mapping element names to CodeElement objects
        """
        elements = self.parse(code)
        globals_dict = {}
        
        for element in elements:
            # Only include top-level elements (no parent)
            if not element.parent:
                globals_dict[element.name] = element
                
        return globals_dict
    
    def check_syntax_validity(self, code: str) -> bool:
        """
        Perform a basic check for TypeScript syntax validity.
        Extends the JavaScript syntax check with TypeScript-specific syntax.
        
        Args:
            code: TypeScript source code
            
        Returns:
            True if syntax appears valid, False otherwise
        """
        # Use the JavaScript syntax validator as a base
        if not super().check_syntax_validity(code):
            return False
        
        # Additional TypeScript-specific checks could be added here
        # For now, we'll just check for some basic TypeScript syntax patterns
        
        # Check for mismatched generic brackets
        generic_depth = 0
        in_string = False
        in_template = False
        in_comment = False
        
        for i, char in enumerate(code):
            # Skip strings and comments
            if char == '"' or char == "'":
                if not in_comment and not in_template:
                    in_string = not in_string
            elif char == '`':
                if not in_comment:
                    in_template = not in_template
            elif i > 0 and not in_string and not in_template:
                # Check for comment start/end
                if char == '/' and code[i-1] == '/':
                    in_comment = True
                elif char == '\n' and in_comment:
                    in_comment = False
                elif i > 0 and char == '*' and code[i-1] == '/':
                    in_comment = True
                elif i > 0 and char == '/' and code[i-1] == '*':
                    in_comment = False
                
                # Check generic brackets
                if not in_comment:
                    if char == '<' and code[i-1].isalnum():
                        generic_depth += 1
                    elif char == '>' and generic_depth > 0:
                        generic_depth -= 1
        
        # If generic brackets are unbalanced, syntax is invalid
        if generic_depth != 0:
            return False
            
        return True
