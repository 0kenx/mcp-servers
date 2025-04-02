"""
Rust language parser for extracting structured information from Rust code.
"""

import re
from typing import List, Dict, Optional, Tuple, Any
from .base import BaseParser, CodeElement, ElementType

class RustParser(BaseParser):
    """
    Parser for Rust code that extracts functions, structs, enums, traits, impl blocks,
    modules, constants, statics, and imports (use statements).
    """

    def __init__(self):
        """Initialize the Rust parser."""
        super().__init__()

        # Regex patterns for Rust elements
        # Visibility (optional 'pub', 'pub(crate)', etc.)
        vis_pattern = r'(?:pub(?:\([^)]+\))?\s+)?'

        # Function definition (fn name<generics>(params) -> ret {)
        self.function_pattern = re.compile(
            rf'^\s*{vis_pattern}(?:(?:const|async|unsafe)\s+)*fn\s+([a-zA-Z_][a-zA-Z0-9_]*)'
            r'(?:<.*?>)?'  # Optional generics
            r'\s*\((.*?)\)' # Parameters
            r'(?:\s*->\s*(.*?))?' # Optional return type
            r'\s*(?:where\s*.*?)?' # Optional where clause
            r'\s*\{'
        )

        # ADD pattern for trait method signatures ending in semicolon
        self.trait_method_signature_pattern = re.compile(
            rf'^\s*(?:(?:async|unsafe)\s+)*fn\s+([a-zA-Z_][a-zA-Z0-9_]*)'
            r'(?:<.*?>)?'  # Optional generics
            r'\s*\((.*?)\)' # Parameters
            r'(?:\s*->\s*(.*?))?' # Optional return type
            r'\s*(?:where\s*.*?)?' # Optional where clause
            r'\s*;' # Ends with semicolon
        )

        # Struct definition (struct Name<generics> { | ; | ( )
        self.struct_pattern = re.compile(
            rf'^\s*{vis_pattern}struct\s+([a-zA-Z_][a-zA-Z0-9_]*)'
            r'(?:<.*?>)?' # Optional generics
            r'\s*(?:where\s*.*?)?' # Optional where clause
            r'\s*(?:\{|;|\()' # Body starts with {, ; (unit), or ( (tuple)
        )

        # Enum definition (enum Name<generics> {)
        self.enum_pattern = re.compile(
            rf'^\s*{vis_pattern}enum\s+([a-zA-Z_][a-zA-Z0-9_]*)'
            r'(?:<.*?>)?' # Optional generics
            r'\s*(?:where\s*.*?)?' # Optional where clause
            r'\s*\{'
        )

        # Trait definition (trait Name<generics> {)
        self.trait_pattern = re.compile(
            rf'^\s*{vis_pattern}(?:unsafe\s+)?trait\s+([a-zA-Z_][a-zA-Z0-9_]*)'
            r'(?:<.*?>)?' # Optional generics
            r'\s*(?::\s*.*?)?' # Optional supertraits
            r'\s*(?:where\s*.*?)?' # Optional where clause
            r'\s*\{'
        )

        # Impl block (impl<generics> Trait for Type where ... {) or (impl<generics> Type where ... {)
        # This is complex, we'll capture the first line mainly
        self.impl_pattern = re.compile(
            rf'^\s*(?:unsafe\s+)?impl(?:\s*<.*?>)?' # Optional unsafe, generics
            # Attempt to capture trait and type, or just type
            r'(?:\s+(.*?)\s+for)?' # Optional "Trait for" part - GROUP 1
            r'\s+([a-zA-Z_][a-zA-Z0-9_:]+)' # Capture the Type (or Trait if "for" is absent) - GROUP 2
            r'(?:<.*?>)?' # Optional generics for the type/trait
            r'\s*(?:where\s*.*?)?' # Optional where clause
            r'\s*\{'
        )

        # Module definition (mod name; or mod name {)
        # --- Corrected f-string with doubled brace ---
        self.mod_pattern = re.compile(
             rf'^\s*{vis_pattern}mod\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*({{)?(?:;)?'
        )

        # Use statement (use path::to::{Item, Another};)
        # Captures the full path for simplicity
        self.use_pattern = re.compile(
            rf'^\s*{vis_pattern}use\s+(.*?);'
        )

        # Const definition (const NAME: Type = value;)
        self.const_pattern = re.compile(
            rf'^\s*{vis_pattern}const\s+([A-Z_][A-Z0-9_]*)\s*:\s*.*?;'
        )

        # Static definition (static NAME: Type = value;)
        self.static_pattern = re.compile(
             rf'^\s*{vis_pattern}static\s+(?:mut\s+)?([A-Z_][A-Z0-9_]*)\s*:\s*.*?;'
        )

        # Type alias (type Name = Type;)
        self.type_alias_pattern = re.compile(
            rf'^\s*{vis_pattern}type\s+([a-zA-Z_][a-zA-Z0-9_]*)'
            r'(?:<.*?>)?' # Optional generics
            r'\s*=\s*.*?;'
        )

        # Doc comment patterns
        self.doc_comment_outer_pattern = re.compile(r'^\s*///(.*)')
        self.doc_comment_inner_pattern = re.compile(r'^\s*//!(.*)')
        # Attribute pattern
        self.attribute_pattern = re.compile(r'^\s*#\[(.*?)\]')


    def parse(self, code: str) -> List[CodeElement]:
        """
        Parse Rust code and extract structured information.

        Args:
            code: Rust source code

        Returns:
            List of identified code elements
        """
        self.elements = []
        lines = self._split_into_lines(code)
        line_count = len(lines)

        # Stack to keep track of the current parent element (module, impl, trait, class, etc.)
        stack: List[CodeElement] = []

        # Store preceding doc comments and attributes
        pending_doc_comments = []
        pending_attributes = []

        line_idx = 0
        while line_idx < line_count:
            line = lines[line_idx]
            line_num = line_idx + 1 # 1-based indexing

            # --- Collect Docs and Attributes ---
            doc_match_outer = self.doc_comment_outer_pattern.match(line)
            doc_match_inner = self.doc_comment_inner_pattern.match(line)
            attr_match = self.attribute_pattern.match(line)

            if doc_match_outer:
                pending_doc_comments.append(doc_match_outer.group(1).strip())
                line_idx += 1
                continue
            elif doc_match_inner:
                # Inner comments apply to the parent scope (module/crate)
                 parent_doc = doc_match_inner.group(1).strip()
                 if stack:
                     if "docstring" not in stack[-1].metadata:
                         stack[-1].metadata["docstring"] = ""
                     stack[-1].metadata["docstring"] += parent_doc + "\n"
                 # Don't necessarily clear pending outer docs here
                 # Let's keep inner docs primarily associated with the parent scope
                 line_idx += 1
                 continue
            elif attr_match:
                pending_attributes.append(attr_match.group(1))
                line_idx += 1
                continue

            # Skip empty lines or lines that are only normal comments
            if not line.strip() or (line.strip().startswith("//") and not doc_match_outer and not doc_match_inner):
                 # Clear pending items if the line is blank or a normal comment
                 # If we just processed docs/attrs, they should apply to the NEXT non-blank/non-comment line
                 # This reset logic should only happen if we didn't just see a doc/attr
                 # However, the current structure handles this via the final reset check.
                 pending_doc_comments = []
                 pending_attributes = []
                 line_idx += 1
                 continue

            # --- Identify Elements ---
            current_parent = stack[-1] if stack else None
            # Base metadata collected BEFORE matching for the current line_idx
            base_metadata = {
                "docstring": "\n".join(pending_doc_comments).strip() or None,
                "attributes": pending_attributes[:] or None, # Copy list
                "visibility": "pub" if line.strip().startswith("pub") else "private",
            }
            # Clean None values from base metadata collected
            base_metadata = {k: v for k, v in base_metadata.items() if v is not None}

            found_element = False

            # Function (Check first)
            func_match = self.function_pattern.match(line)
            if func_match:
                name = func_match.group(1)
                params = func_match.group(2)
                return_type = func_match.group(3)
                is_async = "async fn" in line
                is_unsafe = "unsafe fn" in line

                end_idx = self._find_matching_brace(lines, line_idx)
                code_block = "\n".join(lines[line_idx : end_idx + 1])

                # Explicitly build metadata for the function
                final_metadata = base_metadata.copy()
                final_metadata["parameters"] = params.strip() if params else "" # Ensure ""
                if return_type:
                    final_metadata["return_type"] = return_type.strip()
                if is_async: final_metadata["is_async"] = True
                if is_unsafe: final_metadata["is_unsafe"] = True

                element = CodeElement(
                    element_type=ElementType.FUNCTION if not current_parent or current_parent.element_type not in [ElementType.IMPL, ElementType.TRAIT] else ElementType.METHOD,
                    name=name,
                    start_line=line_num,
                    end_line=end_idx + 1,
                    code=code_block,
                    parent=current_parent,
                    metadata=final_metadata
                )
                self.elements.append(element)
                # Functions defined within functions are rare, skipping stack push here.
                line_idx = end_idx + 1
                found_element = True

            # Trait method signature check (Check after function with body)
            else: # Only check if it wasn't a full function definition
                 trait_method_match = self.trait_method_signature_pattern.match(line)
                 if trait_method_match:
                    name = trait_method_match.group(1)
                    params = trait_method_match.group(2)
                    return_type = trait_method_match.group(3)
                    is_async = "async fn" in line
                    is_unsafe = "unsafe fn" in line

                    end_idx = line_idx # Signature ends on the same line
                    code_block = line

                    # Explicitly build metadata for the signature
                    final_metadata = base_metadata.copy()
                    final_metadata["parameters"] = params.strip() if params else "" # Ensure ""
                    if return_type:
                        final_metadata["return_type"] = return_type.strip()
                    if is_async: final_metadata["is_async"] = True
                    if is_unsafe: final_metadata["is_unsafe"] = True
                    final_metadata["is_signature"] = True # Add flag

                    element = CodeElement(
                        element_type=ElementType.METHOD, # Assume it's a method
                        name=name,
                        start_line=line_num,
                        end_line=line_num,
                        code=code_block,
                        # Parent will be the trait if the trait was pushed immediately
                        parent=current_parent,
                        metadata=final_metadata
                    )
                    self.elements.append(element)
                    line_idx += 1
                    found_element = True

            # Struct
            if not found_element and self.struct_pattern.match(line):
                struct_match = self.struct_pattern.match(line)
                name = struct_match.group(1)
                # Check character after name/generics to determine type
                # This is simplified; real parsing handles whitespace/comments better.
                relevant_part = line[struct_match.end():].lstrip()
                end_char = relevant_part[0] if relevant_part else '{' # Default to brace

                if end_char == ';': # Unit struct
                    end_idx = line_idx
                    code_block = line
                elif end_char == '(': # Tuple struct
                     # Find matching ')' potentially across lines
                     end_idx = self._find_matching_delimiter(lines, line_idx, '(', ')')
                     # Include the line with the closing parenthesis in the code block
                     code_block = "\n".join(lines[line_idx : end_idx + 1])
                else: # Regular struct with braces assumed
                    end_idx = self._find_matching_brace(lines, line_idx)
                    code_block = "\n".join(lines[line_idx : end_idx + 1])

                element = CodeElement(
                    element_type=ElementType.STRUCT,
                    name=name,
                    start_line=line_num,
                    end_line=end_idx + 1,
                    code=code_block,
                    parent=current_parent,
                    metadata=base_metadata.copy()
                )
                self.elements.append(element)
                line_idx = end_idx + 1
                found_element = True

            # Enum
            elif not found_element and self.enum_pattern.match(line):
                enum_match = self.enum_pattern.match(line)
                name = enum_match.group(1)
                end_idx = self._find_matching_brace(lines, line_idx)
                code_block = "\n".join(lines[line_idx : end_idx + 1])

                element = CodeElement(
                    element_type=ElementType.ENUM,
                    name=name,
                    start_line=line_num,
                    end_line=end_idx + 1, # Temp end line
                    code=code_block,
                    parent=current_parent,
                    metadata=base_metadata.copy()
                )
                self.elements.append(element)
                # Enum body parsing skipped for simplicity
                line_idx = end_idx + 1
                found_element = True

            # Trait Definition
            elif not found_element and self.trait_pattern.match(line):
                trait_match = self.trait_pattern.match(line)
                name = trait_match.group(1)
                end_idx = self._find_matching_brace(lines, line_idx)
                code_block = "\n".join(lines[line_idx : end_idx + 1])

                element = CodeElement(
                    element_type=ElementType.TRAIT,
                    name=name,
                    start_line=line_num,
                    end_line=end_idx + 1, # Temp end line
                    code=code_block,
                    parent=current_parent,
                    metadata=base_metadata.copy()
                )
                self.elements.append(element)
                stack.append(element) # Push trait onto stack immediately
                line_idx += 1 # Move to parse body
                found_element = True

            # Impl blocks
            elif not found_element and self.impl_pattern.match(line):
                impl_match = self.impl_pattern.match(line)
                trait_name = impl_match.group(1) if impl_match.groups()[0] is not None else None  # Optional trait - GROUP 1
                type_name = impl_match.group(2)  # Type being implemented - GROUP 2

                # Determine if this is a standalone impl block or trait implementation
                impl_metadata = base_metadata.copy()
                if trait_name:
                    impl_metadata["trait"] = trait_name.strip()

                impl_element = CodeElement(
                    element_type=ElementType.IMPL,
                    name=f"impl {(trait_name + ' for ' if trait_name else '')}{type_name}",
                    start_line=line_num,
                    end_line=line_num,  # Will be updated when we find the closing brace
                    code=line,
                    parent=current_parent,
                    metadata=impl_metadata
                )
                
                self.elements.append(impl_element)
                stack.append(impl_element)
                current_parent = impl_element  # Set as current parent
                line_idx += 1
                found_element = True

            # Module Definition
            elif not found_element and self.mod_pattern.match(line):
                 mod_match = self.mod_pattern.match(line)
                 name = mod_match.group(1)
                 has_block = mod_match.group(2) == '{'

                 if has_block:
                     end_idx = self._find_matching_brace(lines, line_idx)
                     code_block = "\n".join(lines[line_idx : end_idx + 1])
                     element = CodeElement(
                         element_type=ElementType.MODULE,
                         name=name,
                         start_line=line_num,
                         end_line=end_idx + 1, # Temp end line
                         code=code_block,
                         parent=current_parent,
                         metadata=base_metadata.copy()
                     )
                     self.elements.append(element)
                     stack.append(element) # Push module onto stack immediately
                     line_idx += 1 # Move into the block
                 else: # mod name; (file module)
                     end_idx = line_idx
                     code_block = line
                     element = CodeElement(
                         element_type=ElementType.MODULE,
                         name=name,
                         start_line=line_num,
                         end_line=line_num,
                         code=code_block,
                         parent=current_parent,
                         metadata=base_metadata.copy()
                     )
                     self.elements.append(element)
                     line_idx += 1 # Move past the line
                 found_element = True

            # Use statement
            elif not found_element and self.use_pattern.match(line):
                use_match = self.use_pattern.match(line)
                path = use_match.group(1)
                full_path_name = path

                # --- Refined Name Heuristic for 'use' ---
                simple_name = path.split('::')[-1].strip()
                alias_in_simple = ' as ' in simple_name

                if simple_name.startswith('{') and simple_name.endswith('}'):
                    items_str = simple_name[1:-1].strip()
                    items = [item.strip() for item in items_str.split(',') if item.strip()]

                    best_name = None
                    last_item_name = None
                    found_alias = None

                    for item in items:
                        if ' as ' in item:
                            found_alias = item.split(' as ')[-1].strip()
                            # Keep checking, use the last alias found in the group
                        if item.split(' as ')[0].strip() != 'self':
                             last_item_name = item.split(' as ')[0].strip()

                    if found_alias:
                        best_name = found_alias
                    elif last_item_name:
                        best_name = last_item_name

                    if best_name:
                        simple_name = best_name
                    else: # Fallback: use module name before braces
                         parts = path.split('::')
                         simple_name = parts[-2] if len(parts) > 1 else path

                elif alias_in_simple:
                    simple_name = simple_name.split(' as ')[-1].strip()
                elif simple_name == '*':
                    parts = path.split('::')
                    simple_name = parts[-2] if len(parts) > 1 else path
                # --- End Refined Name Heuristic ---

                use_metadata = base_metadata.copy()
                use_metadata["path"] = full_path_name

                element = CodeElement(
                    element_type=ElementType.IMPORT,
                    name=simple_name,
                    start_line=line_num,
                    end_line=line_num,
                    code=line,
                    parent=current_parent,
                    metadata=use_metadata
                )
                self.elements.append(element)
                line_idx += 1
                found_element = True

            # Const
            elif not found_element and self.const_pattern.match(line):
                 const_match = self.const_pattern.match(line)
                 name = const_match.group(1)
                 element = CodeElement(
                     element_type=ElementType.CONSTANT,
                     name=name,
                     start_line=line_num,
                     end_line=line_num,
                     code=line,
                     parent=current_parent,
                     metadata=base_metadata.copy()
                 )
                 self.elements.append(element)
                 line_idx += 1
                 found_element = True

            # Static
            elif not found_element and self.static_pattern.match(line):
                static_match = self.static_pattern.match(line)
                name = static_match.group(1)
                static_metadata = base_metadata.copy()
                static_metadata["is_static"] = True
                static_metadata["is_mutable"] = "static mut" in line

                element = CodeElement(
                    element_type=ElementType.VARIABLE, # Treat static as variable
                    name=name,
                    start_line=line_num,
                    end_line=line_num,
                    code=line,
                    parent=current_parent,
                    metadata=static_metadata
                )
                self.elements.append(element)
                line_idx += 1
                found_element = True

            # Type Alias
            elif not found_element and self.type_alias_pattern.match(line):
                type_match = self.type_alias_pattern.match(line)
                name = type_match.group(1)
                element = CodeElement(
                    element_type=ElementType.TYPE_DEFINITION,
                    name=name,
                    start_line=line_num,
                    end_line=line_num,
                    code=line,
                    parent=current_parent,
                    metadata=base_metadata.copy()
                )
                self.elements.append(element)
                line_idx += 1
                found_element = True


            # --- Stack Pop & Default Line Increment ---
            if not found_element:
                # Only process '}' and increment if no specific element handler advanced line_idx
                is_closing_brace = line.strip() == '}'
                if is_closing_brace and stack:
                    closed_element = stack.pop()
                    # Update the end_line of the element popped from the stack
                    # Use max to avoid setting end_line earlier than start_line
                    closed_element.end_line = max(line_num, closed_element.end_line)
                    # Check if the element we just popped corresponds to a block that
                    # should have its end_line set here.
                    # This helps fix end_lines for blocks closed by this brace.
                    if closed_element.end_line < line_num: # Avoid rewriting if already set correctly by block finder
                        closed_element.end_line = line_num

                # Always advance line index if no handler did it
                line_idx += 1

            # Clear pending items if an element was found OR if the line wasn't a doc/attr
            # This ensures docs/attrs apply only to the immediately following element
            if found_element or not (doc_match_outer or doc_match_inner or attr_match):
                 pending_doc_comments = []
                 pending_attributes = []


        # Final check: Ensure end_lines are set correctly for elements still on stack (e.g., EOF)
        final_line_num = len(lines)
        while stack:
            element_on_stack = stack.pop()
            # Make sure end line is at least the final line number
            element_on_stack.end_line = max(final_line_num, element_on_stack.end_line)


        return self.elements

    def check_syntax_validity(self, code: str) -> bool:
        """
        Perform a basic check for Rust syntax validity (balanced braces/brackets/parens).

        Args:
            code: Rust source code

        Returns:
            True if syntax appears superficially valid, False otherwise
        """
        # Basic check for balanced braces, brackets, parentheses
        # Ignores comments, strings, character literals, lifetimes for simplicity
        brace_count = 0
        paren_count = 0
        bracket_count = 0
        in_string = False
        in_char = False
        in_line_comment = False
        in_block_comment = 0 # Nested block comments level
        escape_next = False

        code = code.replace('\r\n', '\n').replace('\r', '\n') # Normalize line endings

        i = 0
        while i < len(code):
            char = code[i]
            current_escape = escape_next
            escape_next = False # Reset escape status for this char

            # Handle line comments
            if in_line_comment:
                if char == '\n':
                    in_line_comment = False
                i += 1
                continue

            # Handle block comments
            if in_block_comment > 0:
                if char == '*' and i + 1 < len(code) and code[i+1] == '/':
                    in_block_comment -= 1
                    i += 2
                    continue
                elif char == '/' and i + 1 < len(code) and code[i+1] == '*':
                    in_block_comment += 1
                    i += 2
                    continue
                i += 1
                continue

            # Detect start of comments
            if char == '/' and i + 1 < len(code):
                if code[i+1] == '/':
                    in_line_comment = True
                    i += 2
                    continue
                elif code[i+1] == '*':
                    in_block_comment += 1
                    i += 2
                    continue

            # Handle strings and escapes
            if char == '"' and not in_char and not current_escape:
                in_string = not in_string
            elif char == '\'' and not in_string and not current_escape:
                # Basic toggle for char literals - imperfect but ok for brace balancing
                in_char = not in_char

            # Set escape flag for the *next* character
            if char == '\\' and not current_escape:
                escape_next = True

            # Count braces/brackets/parens if not inside string/char literal
            if not in_string and not in_char:
                if char == '{':
                    brace_count += 1
                elif char == '}':
                    brace_count -= 1
                elif char == '(':
                    paren_count += 1
                elif char == ')':
                    paren_count -= 1
                elif char == '[':
                    bracket_count += 1
                elif char == ']':
                    bracket_count -= 1

            # Check for immediate imbalance
            if brace_count < 0 or paren_count < 0 or bracket_count < 0:
                return False

            i += 1

        # Final check for balance and unterminated constructs
        return (brace_count == 0 and paren_count == 0 and bracket_count == 0 and
                not in_string and not in_char and in_block_comment == 0)


    def _find_matching_brace(self, lines: List[str], start_idx: int) -> int:
        """Find the line index of the matching closing brace '{'."""
        return self._find_matching_delimiter(lines, start_idx, '{', '}')

    def _find_matching_paren(self, lines: List[str], start_idx: int) -> int:
        """Find the line index of the matching closing parenthesis '('."""
        return self._find_matching_delimiter(lines, start_idx, '(', ')')

    def _find_matching_delimiter(self, lines: List[str], start_idx: int, open_delim: str, close_delim: str) -> int:
        """
        Find the line index of the matching closing delimiter for an opening one.
        Handles nested delimiters, comments, strings, and char literals.
        """
        depth = 0
        in_string = False
        in_char = False
        in_line_comment = False
        in_block_comment = 0
        escape_next = False

        # Find the column of the *first* opening delimiter on the start line
        start_col = -1
        for c_idx, char in enumerate(lines[start_idx]):
             # Basic comment/string skip on the start line before finding delimiter
            if char == '"': in_string = not in_string
            elif char == '/' and c_idx + 1 < len(lines[start_idx]) and lines[start_idx][c_idx+1] == '/': break # Line comment starts
            if not in_string and char == open_delim:
                 start_col = c_idx
                 break
        # Reset in_string for multi-line processing
        in_string = False
        if start_col == -1: # Delimiter not found on start line (error?)
            # Maybe it started on a previous line due to multiline definition?
            # This basic finder assumes it's on start_idx. Return start_idx as fallback.
             return start_idx

        for line_idx in range(start_idx, len(lines)):
            line = lines[line_idx]
            # Start searching from start_col only on the first line
            col_start_index = start_col if line_idx == start_idx else 0

            i = col_start_index
            while i < len(line):
                char = line[i]
                current_escape = escape_next
                escape_next = False

                 # --- Comment Handling ---
                if in_line_comment:
                    if i == len(line) - 1: # Reached end of line
                        in_line_comment = False
                    i += 1
                    continue

                if in_block_comment > 0:
                    if char == '*' and i + 1 < len(line) and line[i+1] == '/':
                        in_block_comment -= 1
                        i += 2
                        continue
                    elif char == '/' and i + 1 < len(line) and line[i+1] == '*':
                        in_block_comment += 1
                        i += 2
                        continue
                    i += 1
                    continue

                if char == '/' and i + 1 < len(line):
                    if line[i+1] == '/':
                        in_line_comment = True
                        i += 2
                        continue
                    elif line[i+1] == '*':
                        in_block_comment += 1
                        i += 2
                        continue

                # --- String/Char Literal Handling ---
                if char == '"' and not in_char and not current_escape:
                    in_string = not in_string
                elif char == '\'' and not in_string and not current_escape:
                    # Basic toggle - might misinterpret lifetimes but ok for balance
                    in_char = not in_char

                # --- Escape Character ---
                if char == '\\' and not current_escape:
                    escape_next = True

                # --- Delimiter Matching ---
                if not in_string and not in_char:
                    if char == open_delim:
                        depth += 1
                    elif char == close_delim:
                        depth -= 1
                        if depth == 0:
                            # Found the matching delimiter on this line
                            return line_idx

                i += 1 # Move to next character

             # Reset start_col search restriction after the first line
            start_col = 0


        # If loop finishes without finding match, assume EOF or error
        return len(lines) - 1


    def get_all_globals(self, code: str) -> Dict[str, CodeElement]:
        """
        Get all global elements in the code (top-level items).

        Args:
            code: Rust source code

        Returns:
            Dictionary mapping element names to CodeElement objects
        """
        elements = self.parse(code)
        globals_dict = {}

        for element in elements:
            # Include elements with no parent (true globals)
            if element.parent is None:
                 globals_dict[element.name] = element

        return globals_dict

