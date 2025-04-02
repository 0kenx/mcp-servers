"""
Generic parser using simple regex patterns to find potential named elements.
Lowest fidelity, useful as a fallback or for simple languages/scripts.
"""

import re
from typing import List, Dict, Optional, Tuple, Any, Pattern
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
        (re.compile(r'^\s*(?:public|private|protected|static|async|func|fn|function|def|sub|procedure)\s+([a-zA-Z_][a-zA-Z0-9_]*)', re.IGNORECASE), ElementType.FUNCTION, 1),
        # Class/Struct/Interface/Module Definitions
        (re.compile(r'^\s*(?:public|private|class|struct|interface|module|namespace|type|enum|trait)\s+([a-zA-Z_][a-zA-Z0-9_]*)', re.IGNORECASE), ElementType.CLASS, 1), # Default to CLASS, specific type is lost
        # SQL Create Function/Procedure
        (re.compile(r'^\s*(?:CREATE(?:\s+OR\s+REPLACE)?)\s+(?:FUNCTION|PROCEDURE)\s+([a-zA-Z0-9_.]+)', re.IGNORECASE), ElementType.FUNCTION, 1),
        # Shell function definition (simple cases)
        (re.compile(r'^\s*([a-zA-Z_][a-zA-Z0-9_]+)\s*\(\s*\)\s*\{'), ElementType.FUNCTION, 1), # name() {
        (re.compile(r'^\s*(?:function)\s+([a-zA-Z_][a-zA-Z0-9_]+)'), ElementType.FUNCTION, 1), # function name
        # Variable/Constant Assignment (heuristic: ALL_CAPS for CONSTANT or JS const keyword)
        (re.compile(r'^\s*([A-Z_][A-Z0-9_]+)\s*='), ElementType.CONSTANT, 1),
        (re.compile(r'^\s*const\s+([a-zA-Z_][a-zA-Z0-9_]+)\s*='), ElementType.CONSTANT, 1),
        (re.compile(r'^\s*(?:var|let|export)?\s*([a-zA-Z_][a-zA-Z0-9_]+)\s*='), ElementType.VARIABLE, 1),
        # Import patterns - enhanced for broader matching
        (re.compile(r'^\s*(?:import|use|require|include)\s+[\'"]?([a-zA-Z0-9_./-]+)', re.IGNORECASE), ElementType.IMPORT, 1),
        # More specific import like Python/JS `from X import Y` or `import {Y} from X`
        (re.compile(r'^\s*(?:from|import)\s+.*?from\s+[\'"]?([a-zA-Z0-9_./-]+)', re.IGNORECASE), ElementType.IMPORT, 1),
        # C-style include
        (re.compile(r'^\s*#include\s+[<"]([a-zA-Z0-9_./-]+)[>"]'), ElementType.IMPORT, 1),
        # Ruby/Crystal require
        (re.compile(r'^\s*require\s+[\'"]([a-zA-Z0-9_./-]+)[\'"]'), ElementType.IMPORT, 1),
        # Ruby gem require
        (re.compile(r'^\s*gem\s+[\'"]([a-zA-Z0-9_./-]+)[\'"]'), ElementType.IMPORT, 1),
        # Namespace/module reference with ::
        (re.compile(r'^\s*(?:using|import)\s+([a-zA-Z0-9_:]+(?:::[a-zA-Z0-9_]+)+)'), ElementType.IMPORT, 1),
    ]


    def __init__(self):
        super().__init__()

    def parse(self, code: str) -> List[CodeElement]:
        """
        Scan code line by line, applying patterns to find potential elements.

        Args:
            code: Source code string.

        Returns:
            List of identified CodeElement objects (line-based).
        """
        self.elements = []
        lines = self._split_into_lines(code)

        for line_idx, line in enumerate(lines):
            line_num = line_idx + 1 # 1-based
            stripped_line = line.strip()

            # Very basic comment skipping (can still match inside multi-line comments)
            if not stripped_line or stripped_line.startswith('#') or stripped_line.startswith('//') or stripped_line.startswith('--'):
                continue

            # Try each pattern on the line
            for pattern, element_type, name_group in self.PATTERNS:
                match = pattern.match(line) # Match from start of line
                if match:
                    try:
                        name = match.group(name_group)
                        if name: # Ensure name was captured
                            element = CodeElement(
                                element_type=element_type,
                                name=name.strip(),
                                start_line=line_num,
                                end_line=line_num, # No block context
                                code=line,         # Just the line itself
                                parent=None,       # No parent context
                                metadata={'pattern': pattern.pattern} # Record which pattern matched
                            )
                            self.elements.append(element)
                            # Found a match for this line, potentially break
                            # or allow multiple patterns to match the same line?
                            # Let's break to avoid redundant matches (e.g., var/const)
                            break
                    except IndexError:
                         # Regex group index invalid for this pattern
                         # print(f"Warning: Invalid group index {name_group} for pattern {pattern.pattern}")
                         pass # Ignore this pattern match attempt
                    except Exception as e:
                         # Catch other potential errors during element creation
                         # print(f"Warning: Error processing match on line {line_num}: {e}")
                         pass # Ignore this match


        return self.elements

    def check_syntax_validity(self, code: str) -> bool:
        """
        This parser does not perform syntax checks. Always returns True.

        Args:
            code: Source code string.

        Returns:
            True.
        """
        return True
