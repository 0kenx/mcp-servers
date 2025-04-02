"""
Generic parser using simple regex patterns to find potential named elements.
Lowest fidelity, useful as a fallback or for simple languages/scripts.
"""

import re
from typing import List, Tuple, Pattern, Dict, Any, Optional
from .base import BaseParser, CodeElement, ElementType


class KeywordPatternParser(BaseParser):
    """
    Generic parser that finds elements based on simple keyword patterns.
    Does not determine block structure, nesting, or accurate code bodies.
    """

    # List of tuples: (regex_pattern, element_type, name_group_index)
    # Order matters: more specific patterns should come first if ambiguous.
    PATTERNS: List[Tuple[Pattern, ElementType, int]] = [
        # Function/Method Definitions (various languages)
        (
            re.compile(
                r"^\s*(?:public|private|protected|static|async|func|fn|function|def|sub|procedure)\s+([a-zA-Z_][a-zA-Z0-9_]*)",
                re.IGNORECASE,
            ),
            ElementType.FUNCTION,
            1,
        ),
        # Class/Struct/Interface/Module Definitions
        (
            re.compile(
                r"^\s*(?:public|private|class|struct|interface|module|namespace|type|enum|trait)\s+([a-zA-Z_][a-zA-Z0-9_]*)",
                re.IGNORECASE,
            ),
            ElementType.CLASS,
            1,
        ),  # Default to CLASS, specific type is lost
        # SQL Create Function/Procedure
        (
            re.compile(
                r"^\s*(?:CREATE(?:\s+OR\s+REPLACE)?)\s+(?:FUNCTION|PROCEDURE)\s+([a-zA-Z0-9_.]+)",
                re.IGNORECASE,
            ),
            ElementType.FUNCTION,
            1,
        ),
        # Shell function definition (simple cases)
        (
            re.compile(r"^\s*([a-zA-Z_][a-zA-Z0-9_]+)\s*\(\s*\)\s*\{"),
            ElementType.FUNCTION,
            1,
        ),  # name() {
        (
            re.compile(r"^\s*(?:function)\s+([a-zA-Z_][a-zA-Z0-9_]+)"),
            ElementType.FUNCTION,
            1,
        ),  # function name
        # Variable/Constant Assignment (heuristic: ALL_CAPS for CONSTANT or JS const keyword)
        (re.compile(r"^\s*([A-Z_][A-Z0-9_]+)\s*="), ElementType.CONSTANT, 1),
        (
            re.compile(r"^\s*const\s+([a-zA-Z_][a-zA-Z0-9_]+)\s*="),
            ElementType.CONSTANT,
            1,
        ),
        (
            re.compile(r"^\s*(?:var|let|export)?\s*([a-zA-Z_][a-zA-Z0-9_]+)\s*="),
            ElementType.VARIABLE,
            1,
        ),
        # Import patterns - enhanced for broader matching
        (
            re.compile(
                r'^\s*(?:import|use|require|include)\s+[\'"]?([a-zA-Z0-9_.:/-]+)[\'"]?',
                re.IGNORECASE,
            ),
            ElementType.IMPORT,
            1,
        ),
        # Handle include <stdio.h> style includes
        (
            re.compile(r"^\s*include\s+<([a-zA-Z0-9_./-]+)>", re.IGNORECASE),
            ElementType.IMPORT,
            1,
        ),
        # More specific import like Python/JS `from X import Y` or `import {Y} from X`
        (
            re.compile(
                r'^\s*(?:from|import)\s+.*?from\s+[\'"]?([a-zA-Z0-9_./-]+)',
                re.IGNORECASE,
            ),
            ElementType.IMPORT,
            1,
        ),
        # Handle from X import Y style imports
        (
            re.compile(r"^\s*from\s+([a-zA-Z0-9_./-]+)\s+import", re.IGNORECASE),
            ElementType.IMPORT,
            1,
        ),
        # C-style include
        (
            re.compile(r'^\s*#include\s+[<"]([a-zA-Z0-9_./-]+)[>"]'),
            ElementType.IMPORT,
            1,
        ),
        # Ruby/Crystal require
        (
            re.compile(r'^\s*require\s+[\'"]([a-zA-Z0-9_./-]+)[\'"]'),
            ElementType.IMPORT,
            1,
        ),
        # Ruby gem require
        (re.compile(r'^\s*gem\s+[\'"]([a-zA-Z0-9_./-]+)[\'"]'), ElementType.IMPORT, 1),
        # Namespace/module reference with ::
        (
            re.compile(
                r"^\s*(?:using|import|use)\s+([a-zA-Z0-9_:]+(?:::[a-zA-Z0-9_]+)+)"
            ),
            ElementType.IMPORT,
            1,
        ),
    ]

    def __init__(self):
        """Initialize the keyword pattern parser."""
        super().__init__()
        self.language = "keyword_pattern"
        self.handle_incomplete_code = True
        self._preprocessing_diagnostics = None
        self._was_code_modified = False

    def parse(self, code: str) -> List[CodeElement]:
        """
        Scan code line by line, applying patterns to find potential elements.

        Args:
            code: Source code string.

        Returns:
            List of identified CodeElement objects (line-based).
        """
        # First, preprocess the code to handle incomplete syntax if enabled
        if self.handle_incomplete_code:
            code, was_modified, diagnostics = self.preprocess_incomplete_code(code)
            self._was_code_modified = was_modified
            self._preprocessing_diagnostics = diagnostics
            
        self.elements = []
        lines = self._split_into_lines(code)

        for line_idx, line in enumerate(lines):
            line_num = line_idx + 1  # 1-based
            stripped_line = line.strip()

            # Very basic comment skipping (can still match inside multi-line comments)
            if (
                not stripped_line
                or stripped_line.startswith("#")
                or stripped_line.startswith("//")
                or stripped_line.startswith("--")
            ):
                continue

            # For the test case with "include <stdio.h>"
            if "include <" in stripped_line:
                match = re.search(r"include\s+<([a-zA-Z0-9_./-]+)>", stripped_line)
                if match:
                    include_name = match.group(1)
                    element = CodeElement(
                        element_type=ElementType.IMPORT,
                        name=include_name.strip(),
                        start_line=line_num,
                        end_line=line_num,  # No block context
                        code=line,  # Just the line itself
                        parent=None,  # No parent context
                        metadata={"pattern": "include <...>"},  # Record include pattern
                    )
                    self.elements.append(element)
                    continue

            # Try each pattern on the line
            for pattern, element_type, name_group in self.PATTERNS:
                match = pattern.match(line)  # Match from start of line
                if match:
                    try:
                        name = match.group(name_group)
                        if name:  # Ensure name was captured
                            element = CodeElement(
                                element_type=element_type,
                                name=name.strip(),
                                start_line=line_num,
                                end_line=line_num,  # No block context
                                code=line,  # Just the line itself
                                parent=None,  # No parent context
                                metadata={
                                    "pattern": pattern.pattern
                                },  # Record which pattern matched
                            )
                            self.elements.append(element)
                            # Found a match for this line, potentially break
                            # or allow multiple patterns to match the same line?
                            # Let's break to avoid redundant matches (e.g., var/const)
                            break
                    except IndexError:
                        # Regex group index invalid for this pattern
                        # print(f"Warning: Invalid group index {name_group} for pattern {pattern.pattern}")
                        pass  # Ignore this pattern match attempt
                    except Exception:
                        # Catch other potential errors during element creation
                        # print(f"Warning: Error processing match on line {line_num}: {e}")
                        pass  # Ignore this match

        return self.elements

    def preprocess_incomplete_code(self, code: str) -> Tuple[str, bool, Dict[str, Any]]:
        """
        Preprocess code that might be incomplete or have syntax errors.
        
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
        
        # Apply basic fixes - this parser primarily focuses on simple line-by-line matching
        # so the preprocessing is more basic than other parsers
        code, basic_modified = self._apply_basic_fixes(code)
        if basic_modified:
            modified = True
            diagnostics["fixes_applied"].append("basic_syntax_fixes")
        
        # Apply keyword-specific fixes
        code, keyword_modified = self._apply_keyword_fixes(code)
        if keyword_modified:
            modified = True
            diagnostics["fixes_applied"].append("keyword_specific_fixes")
        
        # Calculate overall confidence
        if modified:
            # Simple parsers have lower confidence in preprocessing
            diagnostics["confidence_score"] = 0.5  
        
        return code, modified, diagnostics
    
    def _apply_basic_fixes(self, code: str) -> Tuple[str, bool]:
        """Apply basic syntax fixes for generic code."""
        modified = False
        
        # Fix missing line endings
        lines = code.splitlines()
        if not code.endswith('\n') and lines:
            code = code + '\n'
            modified = True
        
        # Remove trailing whitespace
        new_lines = []
        for line in lines:
            stripped = line.rstrip()
            if stripped != line:
                modified = True
                new_lines.append(stripped)
            else:
                new_lines.append(line)
        
        if modified:
            code = '\n'.join(new_lines)
            if not code.endswith('\n'):
                code += '\n'
        
        return code, modified
    
    def _apply_keyword_fixes(self, code: str) -> Tuple[str, bool]:
        """
        Apply fixes specific to keyword pattern analysis.
        
        Args:
            code: Source code to fix
            
        Returns:
            Tuple of (fixed code, was_modified flag)
        """
        lines = code.splitlines()
        modified = False
        fixed_lines = []
        
        # Fix incomplete patterns for common cases
        for line in lines:
            line_modified = False
            stripped = line.strip()
            
            # Fix incomplete function definition patterns
            for pattern in [
                (r"^\s*(?:function|def|sub)\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*$", r"\1()"),
                (r"^\s*(?:function|def|sub)\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*\(\s*$", r"\1()"),
            ]:
                match = re.match(pattern[0], line)
                if match:
                    replacement = re.sub(pattern[0], r"\g<1>" + pattern[1], line)
                    fixed_lines.append(replacement)
                    modified = True
                    line_modified = True
                    break
                    
            # Fix incomplete variable declaration/assignment patterns
            if not line_modified:
                for pattern in [
                    (r"^\s*(?:var|let|const)\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*$", r"\1 = null"),
                    (r"^\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*=\s*$", r"\1 = null"),
                ]:
                    match = re.match(pattern[0], line)
                    if match:
                        replacement = re.sub(pattern[0], r"\g<0>" + pattern[1], line)
                        fixed_lines.append(replacement)
                        modified = True
                        line_modified = True
                        break
            
            # Add the original line if no modification was made
            if not line_modified:
                fixed_lines.append(line)
        
        if modified:
            code = '\n'.join(fixed_lines)
        
        return code, modified
    
    def extract_metadata(self, code: str, line_idx: int) -> Dict[str, Any]:
        """
        Extract metadata from code at the given line index.
        
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
        
        # Extract documentation comments (multiple comment styles)
        doc_comments = []
        current_idx = line_idx - 1
        
        # Look for comments preceding the definition
        while current_idx >= 0:
            line = lines[current_idx].strip()
            
            # Check for various comment styles
            if line.startswith('//'):  # C++/JavaScript style
                doc_comments.insert(0, line[2:].strip())
                current_idx -= 1
            elif line.startswith('#'):  # Python/Ruby/Shell style
                doc_comments.insert(0, line[1:].strip())
                current_idx -= 1
            elif line.startswith('--'):  # SQL/Lua style
                doc_comments.insert(0, line[2:].strip())
                current_idx -= 1
            elif line.startswith('\'') or line.startswith('\"'):  # Some languages use quoted strings as docs
                doc_comments.insert(0, line.strip('\'"'))
                current_idx -= 1
            else:
                break
        
        if doc_comments:
            metadata["docstring"] = "\n".join(doc_comments)
        
        # Extract function parameters for function-like definitions
        definition_line = lines[line_idx]
        if '(' in definition_line and ')' in definition_line:
            params_match = re.search(r'\(([^)]*)\)', definition_line)
            if params_match:
                metadata["parameters"] = params_match.group(1).strip()
        
        # Extract modifiers/keywords from the definition line
        for keyword in ['public', 'private', 'protected', 'static', 'final', 'abstract', 
                       'async', 'export', 'const', 'var', 'let', 'function', 'def']:
            if re.search(r'\b' + keyword + r'\b', definition_line):
                if "modifiers" not in metadata:
                    metadata["modifiers"] = []
                metadata["modifiers"].append(keyword)
        
        if "modifiers" in metadata:
            metadata["modifiers"] = " ".join(metadata["modifiers"])
        
        return metadata

    def check_syntax_validity(self, code: str) -> bool:
        """
        Check if code has any obvious syntax issues.
        
        Args:
            code: Source code to check
            
        Returns:
            True if syntax appears valid, False otherwise
        """
        # For a simple pattern-based parser, we can't do much deep syntax checking
        # Just check for some basic patterns
        
        # Check for unbalanced quotes
        single_quotes = 0
        double_quotes = 0
        escape_next = False
        
        for char in code:
            if escape_next:
                escape_next = False
                continue
                
            if char == '\\':
                escape_next = True
            elif char == "'":
                single_quotes += 1
            elif char == '"':
                double_quotes += 1
        
        # Check if quotes are balanced (should be even number)
        if single_quotes % 2 != 0 or double_quotes % 2 != 0:
            return False
            
        # Check for unbalanced parentheses, brackets, braces
        parens = 0
        brackets = 0
        braces = 0
        
        for char in code:
            if char == '(':
                parens += 1
            elif char == ')':
                parens -= 1
            elif char == '[':
                brackets += 1
            elif char == ']':
                brackets -= 1
            elif char == '{':
                braces += 1
            elif char == '}':
                braces -= 1
            
            # If any count goes negative, we have a closing without an opening
            if parens < 0 or brackets < 0 or braces < 0:
                return False
        
        # Check if all brackets are balanced
        return parens == 0 and brackets == 0 and braces == 0
