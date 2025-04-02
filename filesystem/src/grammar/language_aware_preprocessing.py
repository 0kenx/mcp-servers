"""
Language-aware preprocessing for incomplete code.

This module provides advanced preprocessing capabilities that leverage
knowledge of language features to make better decisions when fixing
incomplete or syntactically incorrect code.
"""

from typing import List, Tuple, Dict, Set, Optional
import re


class LanguageFeatures:
    """Base class for language-specific features and constraints."""

    # Common allowable nesting patterns expressed as (parent, child) tuples
    # Example: (ElementType.CLASS, ElementType.METHOD) means methods can be inside classes
    ALLOWED_NESTINGS: List[Tuple[str, str]] = []
    
    # Maximum realistic nesting depth for this language
    MAX_NESTING_DEPTH: int = 5
    
    # Identifier patterns
    IDENTIFIER_PATTERN: str = r'[a-zA-Z_][a-zA-Z0-9_]*'
    
    # Block delimiters
    BLOCK_START: str = ''
    BLOCK_END: str = ''
    
    # Standard indentation
    STANDARD_INDENT: int = 4
    
    @classmethod
    def can_be_nested(cls, parent_type: str, child_type: str) -> bool:
        """Check if the child element can be nested inside the parent element."""
        return (parent_type, child_type) in cls.ALLOWED_NESTINGS


class PythonFeatures(LanguageFeatures):
    """Python-specific language features and constraints."""
    
    ALLOWED_NESTINGS = [
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
    
    MAX_NESTING_DEPTH = 4
    BLOCK_START = ':'
    STANDARD_INDENT = 4
    
    # Patterns for Python code elements
    FUNCTION_PATTERN = r'^\s*def\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*\('
    CLASS_PATTERN = r'^\s*class\s+([a-zA-Z_][a-zA-Z0-9_]*)'
    DECORATOR_PATTERN = r'^\s*@([a-zA-Z_][a-zA-Z0-9_\.]*)'
    IMPORT_PATTERN = r'^\s*(?:import|from)\s+'
    
    @staticmethod
    def get_scope_likelihood(element_type: str, nesting_level: int) -> float:
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


class JavaScriptFeatures(LanguageFeatures):
    """JavaScript-specific language features and constraints."""
    
    ALLOWED_NESTINGS = [
        ('global', 'function'),
        ('global', 'class'),
        ('global', 'variable'),
        ('global', 'import'),
        ('function', 'function'),
        ('function', 'variable'),
        ('function', 'class'),  # Classes can be defined in functions
        ('class', 'method'),
        ('class', 'variable'),
        ('method', 'function'),
        ('method', 'variable'),
        ('method', 'class'),
        ('block', 'function'),  # Functions can be defined in blocks (if, for, etc.)
        ('block', 'variable'),
        ('block', 'class'),
    ]
    
    MAX_NESTING_DEPTH = 5
    BLOCK_START = '{'
    BLOCK_END = '}'
    STANDARD_INDENT = 2
    
    # Patterns for JavaScript code elements
    FUNCTION_PATTERN = r'^\s*(?:function\s+([a-zA-Z_$][a-zA-Z0-9_$]*)|(?:const|let|var)\s+([a-zA-Z_$][a-zA-Z0-9_$]*)\s*=\s*(?:function|\(.*\)\s*=>))'
    CLASS_PATTERN = r'^\s*class\s+([a-zA-Z_$][a-zA-Z0-9_$]*)'
    METHOD_PATTERN = r'^\s*(?:async\s+)?(?:static\s+)?(?:get\s+|set\s+)?([a-zA-Z_$][a-zA-Z0-9_$]*)\s*\('
    IMPORT_PATTERN = r'^\s*import\s+'
    
    @staticmethod
    def get_scope_likelihood(element_type: str, nesting_level: int) -> float:
        """
        Get the likelihood score for an element at a specific nesting level.
        Returns a value between 0-1 where higher is more likely.
        """
        if nesting_level == 0:  # Global level
            return 1.0  # Everything can be at global level in JS
        elif nesting_level == 1:  # First level nesting
            if element_type in ('method', 'variable') and element_type == 'class':
                return 0.9
            elif element_type in ('function', 'variable'):
                return 0.8
            return 0.5
        else:  # Deep nesting
            # JS allows lots of nesting but it gets less common
            return max(0.2, 1.0 - (nesting_level * 0.15))


class LanguageAwarePreprocessor:
    """
    Advanced preprocessor that uses language knowledge to make intelligent
    decisions when fixing incomplete code.
    """
    
    def __init__(self, language: str = "generic"):
        """
        Initialize the preprocessor with language-specific knowledge.
        
        Args:
            language: The programming language of the code
        """
        self.language = language.lower()
        self.language_features = self._get_language_features()
        
    def _get_language_features(self) -> LanguageFeatures:
        """Get the appropriate language features object."""
        if self.language == "python":
            return PythonFeatures()
        elif self.language in ("javascript", "typescript"):
            return JavaScriptFeatures()
        else:
            return LanguageFeatures()
    
    def preprocess_code(self, code: str) -> Tuple[str, bool, Dict[str, any]]:
        """
        Apply intelligent language-aware preprocessing to fix issues.
        
        Args:
            code: Source code that may be incomplete
            
        Returns:
            Tuple of (preprocessed code, was_modified flag, diagnostics)
        """
        diagnostics = {
            "fixes_applied": [],
            "nesting_analysis": {},
            "confidence_score": 0.0
        }
        
        modified = False
        
        # First apply language-agnostic fixes
        code, basic_modified = self._apply_basic_fixes(code)
        modified = modified or basic_modified
        
        if basic_modified:
            diagnostics["fixes_applied"].append("basic_syntax_fixes")
            
        # Then apply language-specific fixes
        code, lang_modified, lang_diagnostics = self._apply_language_specific_fixes(code)
        modified = modified or lang_modified
        
        if lang_modified:
            diagnostics["fixes_applied"].append("language_specific_fixes")
            
        # Update diagnostics
        diagnostics.update(lang_diagnostics)
            
        # Apply structure-aware fixes last
        code, struct_modified, struct_diagnostics = self._fix_structural_issues(code)
        modified = modified or struct_modified
        
        if struct_modified:
            diagnostics["fixes_applied"].append("structural_fixes")
            
        # Update diagnostics
        diagnostics.update(struct_diagnostics)
        
        # Calculate overall confidence
        if modified:
            # More fixes = less confidence
            num_fixes = len(diagnostics["fixes_applied"])
            diagnostics["confidence_score"] = max(0.3, 1.0 - (num_fixes * 0.2))
        else:
            diagnostics["confidence_score"] = 1.0  # No modifications needed
            
        return code, modified, diagnostics
    
    def _apply_basic_fixes(self, code: str) -> Tuple[str, bool]:
        """Apply basic syntax fixes regardless of language."""
        from incomplete_code_handler import IncompleteCodeHandler
        return IncompleteCodeHandler.preprocess_code(code)
        
    def _apply_language_specific_fixes(self, code: str) -> Tuple[str, bool, Dict[str, any]]:
        """Apply fixes specific to the current language."""
        diagnostics = {}
        modified = False
        
        if self.language == "python":
            code, modified, python_diag = self._fix_python_specific(code)
            diagnostics.update(python_diag)
        elif self.language in ("javascript", "typescript"):
            code, modified, js_diag = self._fix_js_specific(code)
            diagnostics.update(js_diag)
            
        return code, modified, diagnostics
    
    def _fix_python_specific(self, code: str) -> Tuple[str, bool, Dict[str, any]]:
        """Apply Python-specific fixes."""
        lines = code.splitlines()
        modified = False
        diagnostics = {"python_fixes": []}
        
        # Check for missing colons in function/class definitions
        colon_fixed_lines = []
        for line in lines:
            # Look for function/class definitions without colons
            def_match = re.match(PythonFeatures.FUNCTION_PATTERN.replace(r'\s*\(', r'\s*\([^)]*\)\s*$'), line)
            class_match = re.match(PythonFeatures.CLASS_PATTERN + r'\s*$', line)
            
            if def_match or class_match:
                if not line.rstrip().endswith(':'):
                    line = line.rstrip() + ':'
                    modified = True
                    diagnostics["python_fixes"].append("added_missing_colon")
            
            colon_fixed_lines.append(line)
        
        if modified:
            code = '\n'.join(colon_fixed_lines)
        
        # Check for missing 'pass' in empty blocks
        pass_fixed_lines = []
        in_def_or_class = False
        current_indent = 0
        
        for i, line in enumerate(colon_fixed_lines):
            pass_fixed_lines.append(line)
            
            stripped = line.strip()
            if not stripped:
                continue
                
            # Check if this is a definition
            if re.match(PythonFeatures.FUNCTION_PATTERN, line) or re.match(PythonFeatures.CLASS_PATTERN, line):
                current_indent = len(line) - len(line.lstrip())
                in_def_or_class = True
                
                # Check next line
                if i + 1 < len(colon_fixed_lines):
                    next_line = colon_fixed_lines[i + 1]
                    next_indent = len(next_line) - len(next_line.lstrip())
                    
                    # If next line isn't indented or is another definition, add 'pass'
                    if (not next_line.strip() or next_indent <= current_indent) and line.rstrip().endswith(':'):
                        pass_fixed_lines.append(' ' * (current_indent + 4) + 'pass')
                        modified = True
                        diagnostics["python_fixes"].append("added_missing_pass")
                elif line.rstrip().endswith(':'):  # At end of file
                    pass_fixed_lines.append(' ' * (current_indent + 4) + 'pass')
                    modified = True
                    diagnostics["python_fixes"].append("added_missing_pass")
        
        if modified and pass_fixed_lines != colon_fixed_lines:
            code = '\n'.join(pass_fixed_lines)
            
        return code, modified, diagnostics
    
    def _fix_js_specific(self, code: str) -> Tuple[str, bool, Dict[str, any]]:
        """Apply JavaScript-specific fixes."""
        lines = code.splitlines()
        modified = False
        diagnostics = {"js_fixes": []}
        
        # Check for missing semicolons
        semicolon_fixed_lines = []
        for line in lines:
            stripped = line.rstrip()
            
            # Don't add semicolons to lines that end with braces, keywords, or already have semicolons
            ends_with_brace = stripped.endswith('{') or stripped.endswith('}')
            ends_with_semicolon = stripped.endswith(';')
            is_control_statement = re.match(r'^\s*(?:if|for|while|switch|function|class|import|export)\b', stripped)
            
            if (stripped and not ends_with_brace and not ends_with_semicolon and not is_control_statement and 
                not stripped.endswith(':')):
                line = stripped + ';'
                modified = True
                diagnostics["js_fixes"].append("added_missing_semicolon")
                
            semicolon_fixed_lines.append(line)
            
        if modified:
            code = '\n'.join(semicolon_fixed_lines)
            
        # Check for missing braces in blocks
        brace_fixed_lines = []
        in_control_statement = False
        needs_brace = False
        
        for i, line in enumerate(semicolon_fixed_lines):
            stripped = line.strip()
            
            # Check if this is a control statement without braces
            control_match = re.match(r'^\s*(?:if|for|while|switch)\s*\([^)]*\)\s*$', line)
            
            if control_match:
                in_control_statement = True
                needs_brace = True
                brace_fixed_lines.append(line + ' {')
                modified = True
                diagnostics["js_fixes"].append("added_missing_brace")
            elif in_control_statement and needs_brace:
                if i + 1 < len(semicolon_fixed_lines):
                    # Add closing brace after the next non-empty line
                    if stripped:
                        indent = len(line) - len(line.lstrip())
                        brace_fixed_lines.append(line)
                        brace_fixed_lines.append(' ' * indent + '}')
                        in_control_statement = False
                        needs_brace = False
                        modified = True
                        diagnostics["js_fixes"].append("added_missing_brace")
                    else:
                        brace_fixed_lines.append(line)
                else:
                    # At the end of the file
                    brace_fixed_lines.append(line)
                    if needs_brace:
                        brace_fixed_lines.append('}')
                        modified = True
                        diagnostics["js_fixes"].append("added_missing_brace")
            else:
                brace_fixed_lines.append(line)
                
        if modified and brace_fixed_lines != semicolon_fixed_lines:
            code = '\n'.join(brace_fixed_lines)
            
        return code, modified, diagnostics
    
    def _fix_structural_issues(self, code: str) -> Tuple[str, bool, Dict[str, any]]:
        """Apply fixes for structural issues based on language knowledge."""
        modified = False
        diagnostics = {"structural_fixes": []}
        
        # Analyze the nesting structure
        nesting_analysis = self._analyze_nesting(code)
        diagnostics["nesting_analysis"] = nesting_analysis
        
        # Fix issues based on nesting analysis
        code, struct_modified = self._fix_nesting_issues(code, nesting_analysis)
        modified = modified or struct_modified
        
        if struct_modified:
            diagnostics["structural_fixes"].append("fixed_nesting_issues")
            
        # Fix issues with block completion
        code, blocks_modified = self._fix_incomplete_blocks(code, nesting_analysis)
        modified = modified or blocks_modified
        
        if blocks_modified:
            diagnostics["structural_fixes"].append("fixed_incomplete_blocks")
            
        return code, modified, diagnostics
    
    def _analyze_nesting(self, code: str) -> Dict[str, any]:
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
                if self.language == "python":
                    if re.match(PythonFeatures.FUNCTION_PATTERN, lines[i-1]):
                        current_nesting.append("function")
                    elif re.match(PythonFeatures.CLASS_PATTERN, lines[i-1]):
                        current_nesting.append("class")
                    else:
                        current_nesting.append("block")
                elif self.language in ("javascript", "typescript"):
                    # For JS, check for { in previous line
                    if i > 0 and "{" in lines[i-1]:
                        if re.search(JavaScriptFeatures.FUNCTION_PATTERN, lines[i-1]):
                            current_nesting.append("function")
                        elif re.search(JavaScriptFeatures.CLASS_PATTERN, lines[i-1]):
                            current_nesting.append("class")
                        elif re.search(JavaScriptFeatures.METHOD_PATTERN, lines[i-1]):
                            current_nesting.append("method")
                        else:
                            current_nesting.append("block")
                    else:
                        current_nesting.append("block")
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
                
                # Get language features to check allowed nestings
                features = self.language_features
                if not features.can_be_nested(parent, child):
                    analysis["unusual_nestings"].append({
                        "line": level_info["line"],
                        "parent": parent,
                        "child": child,
                        "likelihood": features.get_scope_likelihood(child, level_info["depth"]) if hasattr(features, "get_scope_likelihood") else 0.2,
                    })
        
        # Check for unclosed blocks at the end
        if current_nesting:
            analysis["unclosed_blocks"] = current_nesting.copy()
            
        return analysis
    
    def _fix_nesting_issues(self, code: str, nesting_analysis: Dict[str, any]) -> Tuple[str, bool]:
        """Fix issues with unusual or invalid nesting."""
        modified = False
        lines = code.splitlines()
        
        # Fix unusual nestings
        for unusual in nesting_analysis.get("unusual_nestings", []):
            line_idx = unusual["line"] - 1
            
            # If the nesting is very unlikely, we might want to fix the indentation
            if unusual.get("likelihood", 0) < 0.3 and line_idx < len(lines):
                # This is likely a mistake - adjust indentation to be at a more appropriate level
                line = lines[line_idx]
                current_indent = len(line) - len(line.lstrip())
                
                # Find a more appropriate indentation level
                appropriate_indent = 0
                
                if len(unusual["stack"]) > 2:
                    # Try to match indentation of the grandparent level
                    for level_info in nesting_analysis["nesting_levels"]:
                        if len(level_info["stack"]) == len(unusual["stack"]) - 2:
                            # Find a line at this nesting level
                            check_idx = level_info["line"] - 1
                            if check_idx < len(lines):
                                appropriate_indent = len(lines[check_idx]) - len(lines[check_idx].lstrip())
                                break
                
                if appropriate_indent > 0 and appropriate_indent != current_indent:
                    lines[line_idx] = ' ' * appropriate_indent + line.lstrip()
                    modified = True
        
        if modified:
            code = '\n'.join(lines)
            
        return code, modified
    
    def _fix_incomplete_blocks(self, code: str, nesting_analysis: Dict[str, any]) -> Tuple[str, bool]:
        """Fix incomplete blocks based on nesting analysis."""
        modified = False
        lines = code.splitlines()
        
        # Add closing elements for unclosed blocks
        unclosed_blocks = nesting_analysis.get("unclosed_blocks", [])
        if unclosed_blocks:
            if self.language in ("javascript", "typescript"):
                # Add closing braces
                for _ in unclosed_blocks:
                    lines.append('}')
                modified = True
            elif self.language == "python":
                # Python doesn't need explicit closing, but we can add comments
                if len(lines) > 0:
                    last_line = lines[-1]
                    current_indent = len(last_line) - len(last_line.lstrip())
                    
                    # Add a comment indicating the end of blocks
                    for block in reversed(unclosed_blocks):
                        indent = max(0, current_indent - self.language_features.STANDARD_INDENT)
                        comment_line = ' ' * indent + f"# End of {block}"
                        lines.append(comment_line)
                        current_indent = indent
                    
                    modified = True
        
        if modified:
            code = '\n'.join(lines)
            
        return code, modified


# Factory method to get a language-aware preprocessor
def get_preprocessor(language: str) -> LanguageAwarePreprocessor:
    """
    Get a language-aware preprocessor for the specified language.
    
    Args:
        language: The programming language
        
    Returns:
        A LanguageAwarePreprocessor instance
    """
    return LanguageAwarePreprocessor(language)
