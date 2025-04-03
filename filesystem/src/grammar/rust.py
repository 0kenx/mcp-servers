"""
Rust language parser for extracting structured information from Rust code.

This module provides a comprehensive parser for Rust code that can handle
incomplete or syntactically incorrect code, extract rich metadata, and
build a structured representation of the code elements.
"""

import re
from typing import List, Dict, Optional, Tuple, Any, Set
from .base import BaseParser, CodeElement, ElementType


class RustParser(BaseParser):
    """
    Parser for Rust code that extracts functions, structs, enums, traits, impl blocks,
    modules, constants, statics, and imports (use statements).
    
    Includes built-in preprocessing for incomplete code and metadata extraction.
    """

    def __init__(self):
        """Initialize the Rust parser."""
        super().__init__()
        self.language = "rust"
        self.handle_incomplete_code = True

        # Regex patterns for Rust elements
        # Visibility (optional 'pub', 'pub(crate)', etc.)
        vis_pattern = r"(?:pub(?:\([^)]+\))?\s+)?"

        # Function definition (fn name<generics>(params) -> ret {)
        self.function_pattern = re.compile(
            rf"^\s*{vis_pattern}(?:(?:const|async|unsafe)\s+)*fn\s+([a-zA-Z_][a-zA-Z0-9_]*)"
            r"(?:<.*?>)?"  # Optional generics
            r"\s*\((.*?)\)"  # Parameters
            r"(?:\s*->\s*(.*?))?"  # Optional return type
            r"(?:\s*where\s*.*?)?"  # Optional where clause
            r"\s*\{"
        )

        # ADD pattern for trait method signatures ending in semicolon
        self.trait_method_signature_pattern = re.compile(
            r"^\s*(?:(?:async|unsafe)\s+)*fn\s+([a-zA-Z_][a-zA-Z0-9_]*)"
            r"(?:<.*?>)?"  # Optional generics
            r"\s*\((.*?)\)"  # Parameters
            r"(?:\s*->\s*(.*?))?"  # Optional return type
            r"(?:\s*where\s*.*?)?"  # Optional where clause
            r"\s*;"  # Ends with semicolon
        )

        # Struct definition (struct Name<generics> { | ; | ( )
        self.struct_pattern = re.compile(
            rf"^\s*{vis_pattern}struct\s+([a-zA-Z_][a-zA-Z0-9_]*)"
            r"(?:<.*?>)?"  # Optional generics
            r"\s*(?:where\s*.*?)?"  # Optional where clause
            r"\s*(?:\{|;|\()"  # Body starts with {, ; (unit), or ( (tuple)
        )

        # Enum definition (enum Name<generics> {)
        self.enum_pattern = re.compile(
            rf"^\s*{vis_pattern}enum\s+([a-zA-Z_][a-zA-Z0-9_]*)"
            r"(?:<.*?>)?"  # Optional generics
            r"\s*(?:where\s*.*?)?"  # Optional where clause
            r"\s*\{"
        )

        # Trait definition (trait Name<generics> {)
        self.trait_pattern = re.compile(
            rf"^\s*{vis_pattern}(?:unsafe\s+)?trait\s+([a-zA-Z_][a-zA-Z0-9_]*)"
            r"(?:<.*?>)?"  # Optional generics
            r"\s*(?::\s*.*?)?"  # Optional supertraits
            r"\s*(?:where\s*.*?)?"  # Optional where clause
            r"\s*\{"
        )

        # Impl block (impl<generics> Trait for Type where ... {) or (impl<generics> Type where ... {)
        # This is complex, we'll capture the first line mainly
        self.impl_pattern = re.compile(
            r"^\s*(?:unsafe\s+)?impl(?:\s*<.*?>)?"  # Optional unsafe, generics
            # Attempt to capture trait and type, or just type
            r"(?:\s+(.*?)\s+for)?"  # Optional "Trait for" part - GROUP 1
            r"\s+([a-zA-Z_][a-zA-Z0-9_:]+)"  # Capture the Type (or Trait if "for" is absent) - GROUP 2
            r"(?:<.*?>)?"  # Optional generics for the type/trait
            r"\s*(?:where\s*.*?)?"  # Optional where clause
            r"\s*\{"
        )

        # Module definition (mod name; or mod name {)
        # --- Corrected f-string with doubled brace ---
        self.mod_pattern = re.compile(
            rf"^\s*{vis_pattern}mod\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*({{)?(?:;)?"
        )

        # Use statement (use path::to::{Item, Another};)
        # Captures the full path for simplicity
        self.use_pattern = re.compile(rf"^\s*{vis_pattern}use\s+(.*?);")

        # Const definition (const NAME: Type = value;)
        self.const_pattern = re.compile(
            rf"^\s*{vis_pattern}const\s+([A-Z_][A-Z0-9_]*)\s*:\s*.*?;"
        )

        # Static definition (static NAME: Type = value;)
        self.static_pattern = re.compile(
            rf"^\s*{vis_pattern}static\s+(?:mut\s+)?([A-Z_][A-Z0-9_]*)\s*:\s*.*?;"
        )

        # Type alias (type Name = Type;)
        self.type_alias_pattern = re.compile(
            rf"^\s*{vis_pattern}type\s+([a-zA-Z_][a-zA-Z0-9_]*)"
            r"(?:<.*?>)?"  # Optional generics
            r"\s*=\s*.*?;"
        )

        # Doc comment patterns
        self.doc_comment_outer_pattern = re.compile(r"^\s*///(.*)")
        self.doc_comment_inner_pattern = re.compile(r"^\s*//!(.*)")
        # Attribute pattern
        self.attribute_pattern = re.compile(r"^\s*#\[(.*?)\]")
        
        # Standard indentation for Rust
        self.standard_indent = 4
        
        # Allowed nesting patterns
        self.allowed_nestings = [
            ('module', 'function'),
            ('module', 'struct'),
            ('module', 'enum'),
            ('module', 'trait'),
            ('module', 'impl'),
            ('module', 'module'),
            ('module', 'const'),
            ('module', 'static'),
            ('module', 'import'),
            ('module', 'type_definition'),
            ('impl', 'function'),
            ('impl', 'const'),
            ('impl', 'type_definition'),
            ('trait', 'function'),
            ('trait', 'type_definition'),
            ('trait', 'const'),
            ('function', 'struct'),  # Nested structs are allowed in Rust 2018+
            ('function', 'enum'),    # Nested enums are allowed in Rust 2018+
            ('function', 'function'), # Nested functions not allowed in stable Rust but we'll support them
        ]
        
        # Diagnostics container
        self._preprocessing_diagnostics = None
        self._was_code_modified = False

    def parse(self, code: str) -> List[CodeElement]:
        """
        Parse Rust code and extract structured information.

        Args:
            code: Rust source code

        Returns:
            List of identified code elements
        """
        # First, preprocess the code to handle incomplete syntax if enabled
        if self.handle_incomplete_code:
            code, was_modified, diagnostics = self.preprocess_incomplete_code(code)
            self._was_code_modified = was_modified
            self._preprocessing_diagnostics = diagnostics

            
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
            line_num = line_idx + 1  # 1-based indexing

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
            if not line.strip() or (
                line.strip().startswith("//")
                and not doc_match_outer
                and not doc_match_inner
            ):
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
                "attributes": pending_attributes[:] or None,  # Copy list
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
                final_metadata["parameters"] = (
                    params.strip() if params else ""
                )  # Ensure ""
                if return_type:
                    final_metadata["return_type"] = return_type.strip()
                if is_async:
                    final_metadata["is_async"] = True
                if is_unsafe:
                    final_metadata["is_unsafe"] = True

                element = CodeElement(
                    element_type=ElementType.FUNCTION
                    if not current_parent
                    or current_parent.element_type
                    not in [ElementType.IMPL, ElementType.TRAIT]
                    else ElementType.METHOD,
                    name=name,
                    start_line=line_num,
                    end_line=end_idx + 1,
                    code=code_block,
                    parent=current_parent,
                    metadata=final_metadata,
                )
                self.elements.append(element)
                # Functions defined within functions are rare, skipping stack push here.
                line_idx = end_idx + 1
                found_element = True

            # Trait method signature check (Check after function with body)
            else:  # Only check if it wasn't a full function definition
                trait_method_match = self.trait_method_signature_pattern.match(line)
                if trait_method_match:
                    name = trait_method_match.group(1)
                    params = trait_method_match.group(2)
                    return_type = trait_method_match.group(3)
                    is_async = "async fn" in line
                    is_unsafe = "unsafe fn" in line

                    end_idx = line_idx  # Signature ends on the same line
                    code_block = line

                    # Explicitly build metadata for the signature
                    final_metadata = base_metadata.copy()
                    final_metadata["parameters"] = (
                        params.strip() if params else ""
                    )  # Ensure ""
                    if return_type:
                        final_metadata["return_type"] = return_type.strip()
                    if is_async:
                        final_metadata["is_async"] = True
                    if is_unsafe:
                        final_metadata["is_unsafe"] = True
                    final_metadata["is_signature"] = True  # Add flag

                    element = CodeElement(
                        element_type=ElementType.METHOD,  # Assume it's a method
                        name=name,
                        start_line=line_num,
                        end_line=line_num,
                        code=code_block,
                        # Parent will be the trait if the trait was pushed immediately
                        parent=current_parent,
                        metadata=final_metadata,
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
                relevant_part = line[struct_match.end() :].lstrip()
                end_char = (
                    relevant_part[0] if relevant_part else "{"
                )  # Default to brace

                if end_char == ";":  # Unit struct
                    end_idx = line_idx
                    code_block = line
                elif end_char == "(":  # Tuple struct
                    # Find matching ')' potentially across lines
                    end_idx = self._find_matching_delimiter(lines, line_idx, "(", ")")
                    # Include the line with the closing parenthesis in the code block
                    code_block = "\n".join(lines[line_idx : end_idx + 1])
                else:  # Regular struct with braces assumed
                    end_idx = self._find_matching_brace(lines, line_idx)
                    code_block = "\n".join(lines[line_idx : end_idx + 1])

                element = CodeElement(
                    element_type=ElementType.STRUCT,
                    name=name,
                    start_line=line_num,
                    end_line=end_idx + 1,
                    code=code_block,
                    parent=current_parent,
                    metadata=base_metadata.copy(),
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
                    end_line=end_idx + 1,  # Temp end line
                    code=code_block,
                    parent=current_parent,
                    metadata=base_metadata.copy(),
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
                    end_line=end_idx + 1,  # Temp end line
                    code=code_block,
                    parent=current_parent,
                    metadata=base_metadata.copy(),
                )
                self.elements.append(element)
                # Process trait body to find methods
                trait_end = end_idx  # Store the actual end index
                
                # Process trait methods
                current_line = line_idx + 1
                while current_line < trait_end:
                    method_line = lines[current_line]
                    
                    # Try to find method declarations/definitions
                    fn_match = self.function_pattern.match(method_line)
                    if fn_match:
                        fn_name = fn_match.group(1)
                        
                        # Check if this is a method with a body
                        if "{" in method_line:
                            # It has a body, find the end
                            method_end = self._find_matching_brace(lines, current_line)
                            method_code = "\n".join(lines[current_line : method_end + 1])
                            
                            # Create method element
                            method_element = CodeElement(
                                element_type=ElementType.METHOD,
                                name=fn_name,
                                start_line=current_line + 1,  # 1-indexed
                                end_line=method_end + 1,  # 1-indexed
                                code=method_code,
                                parent=element,
                                metadata=base_metadata.copy(),
                            )
                            self.elements.append(method_element)
                            element.children.append(method_element)
                            current_line = method_end + 1
                        else:  
                            # Method declaration without body
                            method_code = method_line
                            # Find where the declaration ends (usually with a semicolon)
                            method_end = current_line
                            while method_end < trait_end and ";" not in lines[method_end]:
                                method_end += 1
                                
                            # Create method element for the declaration
                            method_element = CodeElement(
                                element_type=ElementType.METHOD,
                                name=fn_name,
                                start_line=current_line + 1,  # 1-indexed
                                end_line=method_end + 1,  # 1-indexed for lines
                                code=method_line,
                                parent=element,
                                metadata=base_metadata.copy(),
                            )
                            self.elements.append(method_element)
                            element.children.append(method_element)
                            current_line = method_end + 1
                    else:
                        current_line += 1
                
                line_idx = end_idx + 1 # Skip past the trait definition
                found_element = True

            # Impl blocks
            elif not found_element and self.impl_pattern.match(line):
                impl_match = self.impl_pattern.match(line)
                trait_name = (
                    impl_match.group(1) if impl_match.groups()[0] is not None else None
                )  # Optional trait - GROUP 1
                type_name = impl_match.group(2)  # Type being implemented - GROUP 2

                # Determine if this is a standalone impl block or trait implementation
                impl_metadata = base_metadata.copy()
                if trait_name:
                    impl_metadata["trait"] = trait_name.strip()
                    impl_metadata["type"] = type_name.strip()
                
                # Fix the test by naming the impl block with just the type name
                impl_element = CodeElement(
                    element_type=ElementType.IMPL,
                    name=type_name,
                    start_line=line_num,
                    end_line=line_num,  # Will be updated when we find the closing brace
                    code=line,
                    parent=current_parent,
                    metadata=impl_metadata,
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
                has_block = mod_match.group(2) == "{"

                if has_block:
                    end_idx = self._find_matching_brace(lines, line_idx)
                    code_block = "\n".join(lines[line_idx : end_idx + 1])
                    element = CodeElement(
                        element_type=ElementType.MODULE,
                        name=name,
                        start_line=line_num,
                        end_line=end_idx + 1,  # Temp end line
                        code=code_block,
                        parent=current_parent,
                        metadata=base_metadata.copy(),
                    )
                    self.elements.append(element)
                    stack.append(element)  # Push module onto stack immediately
                    line_idx += 1  # Move into the block
                else:  # mod name; (file module)
                    end_idx = line_idx
                    code_block = line
                    element = CodeElement(
                        element_type=ElementType.MODULE,
                        name=name,
                        start_line=line_num,
                        end_line=line_num,
                        code=code_block,
                        parent=current_parent,
                        metadata=base_metadata.copy(),
                    )
                    self.elements.append(element)
                    line_idx += 1  # Move past the line
                found_element = True

            # Use statement
            elif not found_element and self.use_pattern.match(line):
                use_match = self.use_pattern.match(line)
                path = use_match.group(1)
                full_path_name = path

                # --- Refined Name Heuristic for 'use' ---
                simple_name = path.split("::")[-1].strip()
                alias_in_simple = " as " in simple_name

                if simple_name.startswith("{") and simple_name.endswith("}"):
                    items_str = simple_name[1:-1].strip()
                    items = [
                        item.strip() for item in items_str.split(",") if item.strip()
                    ]

                    best_name = None
                    last_item_name = None
                    found_alias = None

                    for item in items:
                        if " as " in item:
                            found_alias = item.split(" as ")[-1].strip()
                            # Keep checking, use the last alias found in the group
                        if item.split(" as ")[0].strip() != "self":
                            last_item_name = item.split(" as ")[0].strip()

                    if found_alias:
                        best_name = found_alias
                    elif last_item_name:
                        best_name = last_item_name

                    if best_name:
                        simple_name = best_name
                    else:  # Fallback: use module name before braces
                        parts = path.split("::")
                        simple_name = parts[-2] if len(parts) > 1 else path

                elif alias_in_simple:
                    simple_name = simple_name.split(" as ")[-1].strip()
                elif simple_name == "*":
                    parts = path.split("::")
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
                    metadata=use_metadata,
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
                    metadata=base_metadata.copy(),
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
                    element_type=ElementType.VARIABLE,  # Treat static as variable
                    name=name,
                    start_line=line_num,
                    end_line=line_num,
                    code=line,
                    parent=current_parent,
                    metadata=static_metadata,
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
                    metadata=base_metadata.copy(),
                )
                self.elements.append(element)
                line_idx += 1
                found_element = True

            # --- Stack Pop & Default Line Increment ---
            if not found_element:
                # Only process '}' and increment if no specific element handler advanced line_idx
                is_closing_brace = line.strip() == "}"
                if is_closing_brace and stack:
                    closed_element = stack.pop()
                    # Update the end_line of the element popped from the stack
                    # Use max to avoid setting end_line earlier than start_line
                    closed_element.end_line = max(line_num, closed_element.end_line)
                    # Check if the element we just popped corresponds to a block that
                    # should have its end_line set here.
                    # This helps fix end_lines for blocks closed by this brace.
                    if (
                        closed_element.end_line < line_num
                    ):  # Avoid rewriting if already set correctly by block finder
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
        in_block_comment = 0  # Nested block comments level
        escape_next = False

        code = code.replace("\r\n", "\n").replace("\r", "\n")  # Normalize line endings

        i = 0
        while i < len(code):
            char = code[i]
            current_escape = escape_next
            escape_next = False  # Reset escape status for this char

            # Handle line comments
            if in_line_comment:
                if char == "\n":
                    in_line_comment = False
                i += 1
                continue

            # Handle block comments
            if in_block_comment > 0:
                if char == "*" and i + 1 < len(code) and code[i + 1] == "/":
                    in_block_comment -= 1
                    i += 2
                    continue
                elif char == "/" and i + 1 < len(code) and code[i + 1] == "*":
                    in_block_comment += 1
                    i += 2
                    continue
                i += 1
                continue

            # Detect start of comments
            if char == "/" and i + 1 < len(code):
                if code[i + 1] == "/":
                    in_line_comment = True
                    i += 2
                    continue
                elif code[i + 1] == "*":
                    in_block_comment += 1
                    i += 2
                    continue

            # Handle strings and escapes
            if char == '"' and not in_char and not current_escape:
                in_string = not in_string
            elif char == "'" and not in_string and not current_escape:
                # Basic toggle for char literals - imperfect but ok for brace balancing
                in_char = not in_char

            # Set escape flag for the *next* character
            if char == "\\" and not current_escape:
                escape_next = True

            # Count braces/brackets/parens if not inside string/char literal
            if not in_string and not in_char:
                if char == "{":
                    brace_count += 1
                elif char == "}":
                    brace_count -= 1
                elif char == "(":
                    paren_count += 1
                elif char == ")":
                    paren_count -= 1
                elif char == "[":
                    bracket_count += 1
                elif char == "]":
                    bracket_count -= 1

            # Check for immediate imbalance
            if brace_count < 0 or paren_count < 0 or bracket_count < 0:
                return False

            i += 1

        # Final check for balance and unterminated constructs
        return (
            brace_count == 0
            and paren_count == 0
            and bracket_count == 0
            and not in_string
            and not in_char
            and in_block_comment == 0
        )

    def _find_matching_brace(self, lines: List[str], start_idx: int) -> int:
        """Find the line index of the matching closing brace '{'."""
        return self._find_matching_delimiter(lines, start_idx, "{", "}")

    def _find_matching_paren(self, lines: List[str], start_idx: int) -> int:
        """Find the line index of the matching closing parenthesis '('."""
        return self._find_matching_delimiter(lines, start_idx, "(", ")")

    def _find_matching_delimiter(
        self, lines: List[str], start_idx: int, open_delim: str, close_delim: str
    ) -> int:
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
            if char == '"':
                in_string = not in_string
            elif (
                char == "/"
                and c_idx + 1 < len(lines[start_idx])
                and lines[start_idx][c_idx + 1] == "/"
            ):
                break  # Line comment starts
            if not in_string and char == open_delim:
                start_col = c_idx
                break
        # Reset in_string for multi-line processing
        in_string = False
        if start_col == -1:  # Delimiter not found on start line (error?)
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
                    if i == len(line) - 1:  # Reached end of line
                        in_line_comment = False
                    i += 1
                    continue

                if in_block_comment > 0:
                    if char == "*" and i + 1 < len(line) and line[i + 1] == "/":
                        in_block_comment -= 1
                        i += 2
                        continue
                    elif char == "/" and i + 1 < len(line) and line[i + 1] == "*":
                        in_block_comment += 1
                        i += 2
                        continue
                    i += 1
                    continue

                if char == "/" and i + 1 < len(line):
                    if line[i + 1] == "/":
                        in_line_comment = True
                        i += 2
                        continue
                    elif line[i + 1] == "*":
                        in_block_comment += 1
                        i += 2
                        continue

                # --- String/Char Literal Handling ---
                if char == '"' and not in_char and not current_escape:
                    in_string = not in_string
                elif char == "'" and not in_string and not current_escape:
                    # Basic toggle - might misinterpret lifetimes but ok for balance
                    in_char = not in_char

                # --- Escape Character ---
                if char == "\\" and not current_escape:
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

                i += 1  # Move to next character

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

    def preprocess_incomplete_code(self, code: str) -> Tuple[str, bool, Dict[str, Any]]:
        """
        Preprocess Rust code that might be incomplete or have syntax errors.
        
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
        
        # First apply language-agnostic fixes
        code, basic_modified = self._apply_basic_fixes(code)
        if basic_modified:
            modified = True
            diagnostics["fixes_applied"].append("basic_syntax_fixes")
        
        # Apply Rust-specific fixes
        code, rust_modified, rust_diagnostics = self._fix_rust_specific(code)
        if rust_modified:
            modified = True
            diagnostics["fixes_applied"].append("rust_specific_fixes")
            diagnostics.update(rust_diagnostics)
        
        # Apply structural fixes
        code, struct_modified, struct_diagnostics = self._fix_structural_issues(code)
        if struct_modified:
            modified = True
            diagnostics["fixes_applied"].append("structural_fixes")
            diagnostics.update(struct_diagnostics)
        
        # Calculate overall confidence
        if modified:
            # More fixes = less confidence
            num_fixes = len(diagnostics["fixes_applied"])
            diagnostics["confidence_score"] = max(0.3, 1.0 - (num_fixes * 0.2))
        
        self._preprocessing_diagnostics = diagnostics
        self._was_code_modified = modified
        
        return code, modified, diagnostics
    
    def _apply_basic_fixes(self, code: str) -> Tuple[str, bool]:
        """Apply basic syntax fixes regardless of language."""
        modified = False
        
        # Balance braces
        code, braces_modified = self._balance_braces(code)
        modified = modified or braces_modified
        
        # Fix indentation
        lines, indent_modified = self._fix_indentation(code.splitlines())
        if indent_modified:
            code = '\n'.join(lines)
            modified = True
        
        # Recover incomplete blocks
        code, blocks_modified = self._recover_incomplete_blocks(code)
        modified = modified or blocks_modified
        
        return code, modified
    
    def _balance_braces(self, code: str) -> Tuple[str, bool]:
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
    
    def _fix_indentation(self, lines: List[str]) -> Tuple[List[str], bool]:
        """
        Attempt to fix incorrect indentation in Rust code.
        
        Args:
            lines: Source code lines that may have incorrect indentation
            
        Returns:
            Tuple of (fixed lines, was_modified flag)
        """
        if not lines:
            return lines, False
            
        modified = False
        fixed_lines = lines.copy()
        
        # Identify standard indentation unit (4 spaces for Rust by convention)
        indent_unit = self.standard_indent
        
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
            
            # Check if line ends with { and next line should be indented
            if lines[i-1].rstrip().endswith('{'):
                # Next line should be indented
                if current_indent <= prev_indent and lines[i].strip():
                    # Add proper indentation
                    fixed_lines[i] = ' ' * (prev_indent + indent_unit) + lines[i].lstrip()
                    modified = True
        
        return fixed_lines, modified
    
    def _recover_incomplete_blocks(self, code: str) -> Tuple[str, bool]:
        """
        Recover blocks with missing closing elements.
        
        Args:
            code: Source code that may have incomplete blocks
            
        Returns:
            Tuple of (recovered code, was_modified flag)
        """
        lines = code.splitlines()
        modified = False
        
        # Check for definitions at the end of the file without body
        if lines and len(lines) > 0:
            last_line = lines[-1].strip()
            
            # Common patterns for definitions that should have a body
            rust_patterns = [
                r'^\s*(?:pub\s+)?(?:fn|struct|enum|trait|impl|mod)\s+\w+.*\{$',  # Function/struct/etc definition with open brace
                r'^\s*(?:pub\s+)?(?:fn|struct|enum|trait|impl|mod)\s+\w+.*$',    # Incomplete definition
                r'^\s*\}$'                                                        # Lone closing brace
            ]
            
            for pattern in rust_patterns:
                if re.match(pattern, last_line):
                    # Add a minimal body or closing brace if needed
                    if last_line.endswith('{'):
                        lines.append('}')
                        modified = True
                    elif not last_line.endswith('}') and not last_line.endswith(';'):
                        # This might be an incomplete definition
                        if re.search(r'(?:fn|struct|enum|trait|impl|mod)\s+\w+', last_line):
                            lines.append('{')
                            lines.append('}')
                            modified = True
                    break
        
        return '\n'.join(lines), modified
    
    def _fix_rust_specific(self, code: str) -> Tuple[str, bool, Dict[str, Any]]:
        """
        Apply Rust-specific fixes.
        
        Args:
            code: Source code to fix
            
        Returns:
            Tuple of (fixed code, was_modified flag, diagnostics)
        """
        lines = code.splitlines()
        modified = False
        diagnostics = {"rust_fixes": []}
        
        # Fix missing semicolons
        semicolon_fixed_lines = []
        for line in lines:
            line_stripped = line.strip()
            if (
                line_stripped and 
                not line_stripped.endswith(';') and 
                not line_stripped.endswith('{') and
                not line_stripped.endswith('}') and
                not line_stripped.startswith('//') and
                not line_stripped.startswith('/*') and
                not line_stripped.endswith('*/') and
                (
                    # Lines that should end with semicolons
                    line_stripped.startswith('let ') or
                    line_stripped.startswith('use ') or
                    line_stripped.startswith('type ') or
                    line_stripped.startswith('const ') or
                    line_stripped.startswith('static ') or
                    re.match(r'^\s*(?:pub\s+)?let\s+\w+\s*=', line)
                ) and
                not (
                    # Exceptions where semicolons are not needed
                    re.match(r'^\s*(?:fn|struct|enum|trait|impl|mod|if|else|while|for|match)\s+', line) or
                    re.match(r'^\s*(?:pub|extern|unsafe|async)\s+', line)
                )
            ):
                semicolon_fixed_lines.append(line + ';')
                modified = True
                diagnostics["rust_fixes"].append("added_missing_semicolon")
                continue
            
            semicolon_fixed_lines.append(line)
        
        if modified:
            code = '\n'.join(semicolon_fixed_lines)
        
        # Fix missing impl blocks for trait method declarations
        impl_fixed_lines = code.splitlines()
        i = 0
        while i < len(impl_fixed_lines) - 1:
            line = impl_fixed_lines[i]
            
            # Look for trait method declarations without implementation
            if (
                self.trait_method_signature_pattern.match(line) and
                i + 1 < len(impl_fixed_lines) and
                not impl_fixed_lines[i+1].strip().startswith('{')
            ):
                # Add minimal implementation
                impl_fixed_lines.insert(i+1, ' ' * self.standard_indent + '{')
                impl_fixed_lines.insert(i+2, ' ' * self.standard_indent + '    // TODO: Implement this method')
                impl_fixed_lines.insert(i+3, ' ' * self.standard_indent + '}')
                
                modified = True
                diagnostics["rust_fixes"].append("added_missing_trait_implementation")
                i += 3  # Skip the added lines
            
            i += 1
        
        if modified:
            code = '\n'.join(impl_fixed_lines)
        
        # Fix unbalanced macro invocations (very common in Rust)
        macro_fixed_lines = []
        unmatched_macro_brackets = 0
        in_macro = False
        for line in code.splitlines():
            line_stripped = line.strip()
            
            # Detect macro invocations
            if re.match(r'^\s*\w+!\s*\(', line_stripped) and line_stripped.count('(') > line_stripped.count(')'):
                in_macro = True
                unmatched_macro_brackets += line_stripped.count('(') - line_stripped.count(')')
            elif in_macro:
                unmatched_macro_brackets += line_stripped.count('(') - line_stripped.count(')')
                if unmatched_macro_brackets <= 0:
                    in_macro = False
                    unmatched_macro_brackets = 0
            
            # Fix lines with unmatched macro brackets
            if in_macro and i == len(code.splitlines()) - 1 and unmatched_macro_brackets > 0:
                # This is the last line and we have unmatched macro brackets
                macro_fixed_lines.append(line + ')' * unmatched_macro_brackets + ';')
                modified = True
                diagnostics["rust_fixes"].append("fixed_unmatched_macro_brackets")
            else:
                macro_fixed_lines.append(line)
        
        if modified:
            code = '\n'.join(macro_fixed_lines)
        
        # Fix lifetime syntax in function signatures and struct declarations
        lifetime_fixed_lines = []
        for line in code.splitlines():
            # Fix common lifetime syntax issues
            if (("fn " in line or "struct " in line or "impl " in line) and 
                "<'" in line and 
                not re.search(r"<'[a-z_]+\s*(?:,|>)", line)):
                
                # Missing space after lifetime parameter
                line = re.sub(r"<'([a-z_]+)(?=[,>])", r"<'\1 ", line)
                modified = True
                diagnostics["rust_fixes"].append("fixed_lifetime_syntax")
            
            lifetime_fixed_lines.append(line)
        
        if modified:
            code = '\n'.join(lifetime_fixed_lines)
        
        return code, modified, diagnostics
    
    def _fix_structural_issues(self, code: str) -> Tuple[str, bool, Dict[str, Any]]:
        """
        Fix structural issues in the code based on nesting and language patterns.
        
        Args:
            code: Source code to fix
            
        Returns:
            Tuple of (fixed code, was_modified flag, diagnostics)
        """
        # Analyze code structure and nesting
        nesting_analysis = self._analyze_nesting(code)
        diagnostics = {"nesting_analysis": nesting_analysis}
        
        # Fix indentation based on nesting
        code, indent_modified = self._fix_indentation_based_on_nesting(code, nesting_analysis)
        
        return code, indent_modified, diagnostics
    
    def _analyze_nesting(self, code: str) -> Dict[str, Any]:
        """
        Analyze the nesting structure of the code.
        
        Args:
            code: Source code to analyze
            
        Returns:
            Dictionary with nesting analysis results
        """
        lines = code.splitlines()
        result = {
            "max_depth": 0,
            "invalid_nestings": [],
            "missing_closing_tokens": 0,
            "elements_by_depth": {},
        }
        
        # Stack to track nesting
        stack = []
        
        # Track the type of element at each nesting level
        current_nesting_type = ["module"]  # Rust files are implicitly modules
        
        for i, line in enumerate(lines):
            line_stripped = line.strip()
            
            # Skip comments and empty lines
            if not line_stripped or line_stripped.startswith('//') or line_stripped.startswith('/*'):
                continue
            
            # Detect element types
            element_type = None
            if self.function_pattern.match(line):
                element_type = "function"
            elif self.struct_pattern.match(line):
                element_type = "struct"
            elif self.enum_pattern.match(line):
                element_type = "enum"
            elif self.trait_pattern.match(line):
                element_type = "trait"
            elif self.impl_pattern.match(line):
                element_type = "impl"
            elif self.mod_pattern.match(line):
                element_type = "module"
            
            # Check for block start/end
            if '{' in line_stripped:
                depth = len(stack)
                stack.append('{')
                
                if depth + 1 > result["max_depth"]:
                    result["max_depth"] = depth + 1
                
                # Record element at this depth
                if element_type:
                    if str(depth) not in result["elements_by_depth"]:
                        result["elements_by_depth"][str(depth)] = []
                    result["elements_by_depth"][str(depth)].append(element_type)
                    
                    # Check if this nesting is valid
                    parent_type = current_nesting_type[-1] if current_nesting_type else "module"
                    if not self._can_be_nested(parent_type, element_type):
                        result["invalid_nestings"].append({
                            "line": i + 1,
                            "parent_type": parent_type,
                            "child_type": element_type,
                            "unlikely_score": 0.9
                        })
                    
                    # Push the new element type onto the stack
                    current_nesting_type.append(element_type)
            
            if '}' in line_stripped and stack:
                stack.pop()
                if current_nesting_type and len(current_nesting_type) > 1:
                    current_nesting_type.pop()
        
        # Count unclosed blocks
        result["missing_closing_tokens"] = len(stack)
        
        return result
    
    def _fix_indentation_based_on_nesting(self, code: str, nesting_analysis: Dict[str, Any]) -> Tuple[str, bool]:
        """
        Fix indentation issues based on nesting analysis.
        
        Args:
            code: Source code to fix
            nesting_analysis: Result of nesting analysis
            
        Returns:
            Tuple of (fixed code, was_modified flag)
        """
        lines = code.splitlines()
        modified = False
        
        # Stack to track braces
        stack = []
        expected_indent_level = 0
        
        # Process each line
        fixed_lines = []
        for line in lines:
            line_stripped = line.strip()
            current_indent = len(line) - len(line.lstrip())
            
            # Handle closing braces - they should be at parent's indent level
            if line_stripped.startswith('}'):
                if stack:
                    stack.pop()
                    expected_indent_level = len(stack) * self.standard_indent
                    # Adjust the indentation of this closing brace
                    if current_indent != expected_indent_level:
                        line = ' ' * expected_indent_level + line_stripped
                        modified = True
            
            # Normal line - should be at current indent level
            elif line_stripped:
                if current_indent != expected_indent_level and not line_stripped.startswith('//'):
                    # This line has incorrect indentation
                    line = ' ' * expected_indent_level + line_stripped
                    modified = True
            
            # Handle opening braces - increase expected indent for next line
            if '{' in line_stripped:
                stack.append('{')
                expected_indent_level = len(stack) * self.standard_indent
            
            fixed_lines.append(line)
        
        return '\n'.join(fixed_lines), modified
    
    def _can_be_nested(self, parent_type: str, child_type: str) -> bool:
        """Check if the child element can be nested inside the parent element."""
        return (parent_type, child_type) in self.allowed_nestings
    
    def _get_nesting_likelihood(self, element_type: str, nesting_level: int) -> float:
        """
        Get the likelihood score for an element at a specific nesting level.
        Returns a value between 0-1 where higher is more likely.
        """
        if nesting_level == 0:  # Module level
            return 1.0  # All top-level elements are typical
        elif nesting_level == 1:  # Inside module, impl, trait
            if element_type in ('function', 'struct', 'enum', 'trait', 'impl'):
                return 0.9
            return 0.5
        else:  # Deep nesting
            # Rust doesn't typically have deeply nested elements
            return max(0.1, 1.0 - (nesting_level * 0.3))
            
    def extract_metadata(self, code: str, line_idx: int) -> Dict[str, Any]:
        """
        Extract Rust-specific metadata from code.
        
        Args:
            code: The full source code
            line_idx: The line index where the symbol definition starts
            
        Returns:
            Dictionary containing docstrings, attributes, visibility, etc.
        """
        lines = code.splitlines()
        if line_idx >= len(lines):
            return {}
            
        metadata = {}
        
        # Extract doc comments
        doc_comments = []
        current_idx = line_idx - 1
        while current_idx >= 0:
            line = lines[current_idx]
            doc_match = self.doc_comment_outer_pattern.match(line)
            if doc_match:
                doc_comments.insert(0, doc_match.group(1).strip())
                current_idx -= 1
            else:
                break
        
        if doc_comments:
            metadata["docstring"] = "\n".join(doc_comments)
        
        # Extract attributes
        attributes = []
        current_idx = line_idx - 1
        
        # Skip doc comments if present
        if doc_comments:
            current_idx = line_idx - len(doc_comments) - 1
            
        while current_idx >= 0:
            line = lines[current_idx]
            attr_match = self.attribute_pattern.match(line)
            if attr_match:
                attributes.insert(0, attr_match.group(1))
                current_idx -= 1
            else:
                break
        
        if attributes:
            metadata["attributes"] = attributes
        
        # Extract visibility
        if line_idx < len(lines):
            line = lines[line_idx]
            if line.strip().startswith("pub"):
                metadata["visibility"] = "pub"
                
                # Check for restricted visibility
                if "pub(" in line:
                    vis_match = re.search(r'pub\(([^)]+)\)', line)
                    if vis_match:
                        metadata["visibility_restriction"] = vis_match.group(1)
            else:
                metadata["visibility"] = "private"
        
        # Extract function-specific metadata
        if self.function_pattern.match(lines[line_idx]):
            metadata["is_async"] = "async fn" in lines[line_idx]
            metadata["is_unsafe"] = "unsafe fn" in lines[line_idx]
            metadata["is_const"] = "const fn" in lines[line_idx]
            
            # Extract return type
            return_match = re.search(r'->\s*([^{;]+)', lines[line_idx])
            if return_match:
                metadata["return_type"] = return_match.group(1).strip()
        
        # Extract generics
        if '<' in lines[line_idx] and '>' in lines[line_idx]:
            generics_match = re.search(r'<([^>]+)>', lines[line_idx])
            if generics_match:
                metadata["generics"] = generics_match.group(1)
                
        return metadata
