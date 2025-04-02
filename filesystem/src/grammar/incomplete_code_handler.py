"""
Utilities for handling incomplete code in parsers.

This module provides helpers to process code that might have syntax issues
like unmatched braces, incorrect indentation, etc.
"""

from typing import List, Tuple
import re


class IncompleteCodeHandler:
    """
    Utilities for handling incomplete code in parsers.
    Helps parsers deal with unmatched braces and incorrect indentation.
    """
    
    @staticmethod
    def balance_braces(code: str) -> Tuple[str, bool]:
        """
        Balance unmatched braces in code by adding missing closing braces.
        
        Args:
            code: Source code that may have unmatched braces
            
        Returns:
            Tuple of (balanced code, was_modified flag)
        """
        stack = []
        modified = False
        
        # First, check if we have unbalanced braces
        for i, char in enumerate(code):
            if char == '{':
                stack.append(i)
            elif char == '}':
                if stack:
                    stack.pop()
                # Ignore extra closing braces
        
        # If stack is empty, braces are balanced
        if not stack:
            return code, modified
            
        # Add missing closing braces at the end
        modified = True
        balanced_code = code + '\n' + '}'.join([''] * len(stack))
        
        return balanced_code, modified
    
    @staticmethod
    def fix_indentation(lines: List[str]) -> Tuple[List[str], bool]:
        """
        Attempt to fix incorrect indentation in code.
        
        Args:
            lines: Source code lines that may have incorrect indentation
            
        Returns:
            Tuple of (fixed lines, was_modified flag)
        """
        if not lines:
            return lines, False
            
        modified = False
        fixed_lines = lines.copy()
        
        # Identify standard indentation unit (2 or 4 spaces, or tab)
        indent_sizes = []
        prev_indent = 0
        
        for i, line in enumerate(lines):
            if not line.strip():  # Skip empty lines
                continue
                
            current_indent = len(line) - len(line.lstrip())
            if current_indent > prev_indent and current_indent - prev_indent not in indent_sizes:
                indent_sizes.append(current_indent - prev_indent)
            
            prev_indent = current_indent
        
        # Determine most common indent unit
        if not indent_sizes:
            indent_unit = 4  # Default to 4 spaces
        else:
            most_common = max(set(indent_sizes), key=indent_sizes.count) if indent_sizes else 4
            indent_unit = most_common if most_common > 0 else 4
        
        # Fix common indentation issues
        for i in range(1, len(lines)):
            if not lines[i].strip():  # Skip empty lines
                continue
                
            current_indent = len(lines[i]) - len(lines[i].lstrip())
            prev_indent = len(lines[i-1]) - len(lines[i-1].lstrip())
            
            # Check for sudden large increases in indentation (more than indent_unit)
            if current_indent > prev_indent + indent_unit and current_indent % indent_unit != 0:
                # Fix to nearest indent_unit multiple
                correct_indent = (current_indent // indent_unit) * indent_unit
                fixed_lines[i] = ' ' * correct_indent + lines[i].lstrip()
                modified = True
        
        return fixed_lines, modified
    
    @staticmethod
    def fix_python_indentation(lines: List[str]) -> Tuple[List[str], bool]:
        """
        Special handling for Python indentation which is syntactically significant.
        
        Args:
            lines: Python source code lines
            
        Returns:
            Tuple of (fixed lines, was_modified flag)
        """
        if not lines:
            return lines, False
            
        modified = False
        fixed_lines = lines.copy()
        
        # Track expected indentation stack
        indent_stack = [0]  # Start with 0 indentation
        block_starters = [":", "\\{", "\\(", "\\["]
        
        for i in range(len(lines) - 1):
            line = lines[i].rstrip()
            if not line:  # Skip empty lines
                continue
                
            # Check if line ends with a block starter
            ends_with_block_starter = any(re.search(f"{pattern}\\s*$", line) for pattern in block_starters)
            
            if ends_with_block_starter:
                # Next line should be indented
                current_indent = len(lines[i]) - len(lines[i].lstrip())
                next_line = lines[i+1]
                next_indent = len(next_line) - len(next_line.lstrip())
                
                # If next line has same or less indentation but should be indented
                if next_indent <= current_indent and next_line.strip():
                    # Add 4 spaces of indentation
                    fixed_lines[i+1] = ' ' * (current_indent + 4) + next_line.lstrip()
                    modified = True
        
        return fixed_lines, modified
    
    @staticmethod
    def recover_incomplete_blocks(code: str) -> Tuple[str, bool]:
        """
        Recover blocks with missing closing elements (e.g., function/class definitions without full bodies).
        
        Args:
            code: Source code that may have incomplete blocks
            
        Returns:
            Tuple of (recovered code, was_modified flag)
        """
        lines = code.splitlines()
        modified = False
        
        # Check for function/class definitions at the end of the file without body
        if lines and len(lines) > 0:
            last_line = lines[-1].strip()
            
            # Common patterns for definitions that should have a body
            patterns = [
                r'^\s*(?:def|class|function|if|for|while)\s+\w+.*:$',  # Python
                r'^\s*(?:function|class|if|for|while)\s+.*\($',        # JavaScript-like
                r'^\s*.*\)\s*{?$',                                     # C-like function
                r'^\s*.*\s+{$'                                         # Block start
            ]
            
            for pattern in patterns:
                if re.match(pattern, last_line):
                    # Add a minimal body
                    if ':' in last_line:  # Python-like
                        lines.append('    pass')
                    elif '{' in last_line:  # Brace-based
                        lines.append('}')
                    else:
                        lines.append('{')
                        lines.append('}')
                    modified = True
                    break
        
        return '\n'.join(lines), modified
    
    @staticmethod
    def preprocess_code(code: str) -> Tuple[str, bool]:
        """
        Apply all preprocessing strategies to handle incomplete code.
        
        Args:
            code: Original source code
            
        Returns:
            Tuple of (preprocessed code, was_modified flag)
        """
        modified = False
        
        # Balance braces
        code, braces_modified = IncompleteCodeHandler.balance_braces(code)
        modified = modified or braces_modified
        
        # Fix indentation
        lines, indent_modified = IncompleteCodeHandler.fix_indentation(code.splitlines())
        if indent_modified:
            code = '\n'.join(lines)
            modified = True
        
        # Fix Python-specific indentation
        lines, python_indent_modified = IncompleteCodeHandler.fix_python_indentation(code.splitlines())
        if python_indent_modified:
            code = '\n'.join(lines)
            modified = True
        
        # Recover incomplete blocks
        code, blocks_modified = IncompleteCodeHandler.recover_incomplete_blocks(code)
        modified = modified or blocks_modified
        
        return code, modified
