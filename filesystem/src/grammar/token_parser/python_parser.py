"""
Python parser for the grammar parser system.

This module provides a parser specific to the Python programming language,
building on the base token parser framework.
"""

from typing import List, Dict, Optional, Any, Tuple

from .token import Token, TokenType
from .token_parser import TokenParser
from .parser_state import ParserState, ContextInfo
from .symbol_table import SymbolTable
from .context_tracker import ContextTracker
from .python_tokenizer import PythonTokenizer
from .generic_indentation_block_parser import IndentationBlockParser
from .base import CodeElement, ElementType


class PythonParser(TokenParser):
    """
    Parser for Python code.

    This parser processes Python-specific syntax, handling indentation-based blocks,
    function and class definitions, and produces an abstract syntax tree.
    """

    def __init__(self):
        """Initialize the Python parser."""
        super().__init__()
        self.tokenizer = PythonTokenizer()
        self.state = ParserState()
        self.symbol_table = SymbolTable()

        # Context types specific to Python
        self.context_types = {
            "function": "function",
            "class": "class",
            "method": "method",
            "if": "if",
            "else": "else",
            "elif": "elif",
            "for": "for",
            "while": "while",
            "try": "try",
            "except": "except",
            "finally": "finally",
            "with": "with",
            "comprehension": "comprehension",
            "lambda": "lambda",
            "decorator": "decorator",
        }

        # Mapping of indentation levels to their line numbers
        self.indent_levels: Dict[int, int] = {}
        self.current_indent_level = 0

    def parse(self, code: str) -> List[CodeElement]:
        """
        Parse Python code and return a list of code elements.

        Args:
            code: Python source code

        Returns:
            List of code elements
        """
        # Reset state for a new parse
        self.elements = []
        self.state = ParserState()
        self.symbol_table = SymbolTable()
        self.context_tracker = ContextTracker()
        self.indent_levels = {}
        self.current_indent_level = 0

        # Tokenize the code
        tokens = self.tokenize(code)

        # Process the tokens to build the elements directly
        self._build_elements_from_tokens(tokens)

        # Validate and repair AST
        self.validate_and_repair_ast()

        return self.elements

    def _build_elements_from_tokens(self, tokens: List[Token]) -> None:
        """
        Build code elements directly from the tokens.

        This method processes tokens to create CodeElement objects directly
        instead of creating an intermediate dictionary-based AST.

        Args:
            tokens: List of tokens from the tokenizer
        """
        i = 0
        while i < len(tokens):
            # Track indentation changes
            if tokens[i].token_type == TokenType.WHITESPACE and (
                i == 0 or tokens[i - 1].token_type == TokenType.NEWLINE
            ):
                indent_size = len(tokens[i].value)
                if "indent_size" in tokens[i].metadata:
                    indent_size = tokens[i].metadata["indent_size"]

                if indent_size > self.current_indent_level:
                    # Indentation increased - start a new block
                    self.indent_levels[indent_size] = i
                    self.current_indent_level = indent_size
                elif indent_size < self.current_indent_level:
                    # Indentation decreased - end blocks
                    for level in sorted(self.indent_levels.keys(), reverse=True):
                        if level > indent_size:
                            # End this block
                            del self.indent_levels[level]
                    self.current_indent_level = indent_size

            # Skip whitespace and newlines for element building
            if tokens[i].token_type in [TokenType.WHITESPACE, TokenType.NEWLINE]:
                i += 1
                continue

            # Parse statements based on token type
            if i < len(tokens):
                if tokens[i].token_type == TokenType.KEYWORD:
                    # Process Python keywords (def, class, etc.)
                    if tokens[i].value == "def":
                        function, next_index = self._parse_function_direct(tokens, i)
                        if function:
                            self.elements.append(function)
                            i = next_index
                        else:
                            i += 1
                    elif tokens[i].value == "class":
                        class_element, next_index = self._parse_class_direct(tokens, i)
                        if class_element:
                            self.elements.append(class_element)
                            i = next_index
                        else:
                            i += 1
                    else:
                        # Other keywords (if, for, while, etc.)
                        i += 1
                else:
                    # Other token types
                    i += 1

    def _parse_function_direct(
        self, tokens: List[Token], index: int
    ) -> Tuple[Optional[CodeElement], int]:
        """
        Parse a function definition directly into a CodeElement.

        Args:
            tokens: List of tokens
            index: Current index in the token list

        Returns:
            Tuple of (parsed function element or None, new index)
        """
        start_index = index
        start_line = tokens[index].line

        # Skip 'def' keyword
        index += 1

        # Skip whitespace
        while index < len(tokens) and tokens[index].token_type == TokenType.WHITESPACE:
            index += 1

        # Get function name
        if index >= len(tokens) or tokens[index].token_type != TokenType.IDENTIFIER:
            return None, index  # Not a valid function definition

        function_name = tokens[index].value
        index += 1

        # Skip to opening parenthesis
        while index < len(tokens) and tokens[index].token_type == TokenType.WHITESPACE:
            index += 1

        if index >= len(tokens) or tokens[index].token_type != TokenType.OPEN_PAREN:
            return None, index  # Not a valid function definition

        # Skip opening parenthesis
        index += 1

        # Parse parameters
        parameters = []

        # Process parameters until closing parenthesis
        param_start = index
        current_param = None
        param_name = ""
        param_type = None
        param_default = None
        paren_depth = 1  # Initialize paren_depth to 1 (we've already consumed the opening parenthesis)

        # For each parameter (separated by comma)
        while index < len(tokens) and paren_depth > 0:
            token = tokens[index]

            # Parameter name
            if token.token_type == TokenType.IDENTIFIER and param_name == "":
                param_name = token.value

            # Type annotation
            elif token.token_type == TokenType.COLON:
                index += 1  # Skip colon

                # Skip whitespace
                while (
                    index < len(tokens)
                    and tokens[index].token_type == TokenType.WHITESPACE
                ):
                    index += 1

                if (
                    index < len(tokens)
                    and tokens[index].token_type == TokenType.IDENTIFIER
                ):
                    param_type = tokens[index].value

            # Default value
            elif token.token_type == TokenType.EQUALS:
                index += 1  # Skip equals

                # Skip whitespace
                while (
                    index < len(tokens)
                    and tokens[index].token_type == TokenType.WHITESPACE
                ):
                    index += 1

                # Collect default value (can be complex)
                default_start = index
                default_depth = 0

                # Parse until comma or closing paren
                while (
                    index < len(tokens)
                    and not (
                        tokens[index].token_type == TokenType.COMMA
                        and default_depth == 0
                    )
                    and not (
                        tokens[index].token_type == TokenType.CLOSE_PAREN
                        and default_depth == 0
                    )
                ):
                    if tokens[index].token_type in (
                        TokenType.OPEN_PAREN,
                        TokenType.OPEN_BRACKET,
                        TokenType.OPEN_BRACE,
                    ):
                        default_depth += 1
                    elif tokens[index].token_type in (
                        TokenType.CLOSE_PAREN,
                        TokenType.CLOSE_BRACKET,
                        TokenType.CLOSE_BRACE,
                    ):
                        default_depth -= 1
                        if (
                            tokens[index].token_type == TokenType.CLOSE_PAREN
                            and default_depth < 0
                        ):
                            # We've reached the end of the parameter list
                            break

                    index += 1

                # Extract the default value
                default_text = "".join(
                    tokens[i].value for i in range(default_start, index)
                )
                param_default = default_text

                # Back up one position since we'll increment at the end of the loop
                index -= 1

            # Parameter separator (comma)
            elif token.token_type == TokenType.COMMA:
                # Save the current parameter if we have a name
                if param_name:
                    parameters.append(
                        {
                            "name": param_name,
                            "type": param_type,
                            "default": param_default,
                        }
                    )
                    # Reset for next parameter
                    param_name = ""
                    param_type = None
                    param_default = None

            # Update paren depth
            if token.token_type == TokenType.OPEN_PAREN:
                paren_depth += 1
            elif token.token_type == TokenType.CLOSE_PAREN:
                paren_depth -= 1

                # If we're at the end of parameters, add the last one
                if paren_depth == 0 and param_name:
                    parameters.append(
                        {
                            "name": param_name,
                            "type": param_type,
                            "default": param_default,
                        }
                    )

            index += 1

        # Index should now be at the position after closing parenthesis

        # Check for return type annotation (-> type)
        return_type = None
        # Skip whitespace after parenthesis
        while index < len(tokens) and tokens[index].token_type == TokenType.WHITESPACE:
            index += 1

        # Look for the arrow token
        if index < len(tokens) and tokens[index].token_type == TokenType.ARROW:
            index += 1  # Skip the arrow

            # Skip whitespace after arrow
            while (
                index < len(tokens) and tokens[index].token_type == TokenType.WHITESPACE
            ):
                index += 1

            # Get the return type
            if index < len(tokens) and tokens[index].token_type == TokenType.IDENTIFIER:
                return_type = tokens[index].value
                index += 1

                # Handle complex return types like List[str]
                if (
                    index < len(tokens)
                    and tokens[index].token_type == TokenType.OPEN_BRACKET
                ):
                    # Just collect the entire type up to the matching bracket
                    bracket_depth = 1
                    index += 1
                    type_suffix = "["

                    while index < len(tokens) and bracket_depth > 0:
                        if tokens[index].token_type == TokenType.OPEN_BRACKET:
                            bracket_depth += 1
                        elif tokens[index].token_type == TokenType.CLOSE_BRACKET:
                            bracket_depth -= 1

                        type_suffix += tokens[index].value
                        index += 1

                    return_type += type_suffix

        # Skip to colon
        while index < len(tokens) and tokens[index].token_type != TokenType.COLON:
            index += 1

        if index >= len(tokens):
            return None, index  # Not a valid function definition

        # Skip colon
        index += 1

        # Find the end of the function body based on indentation
        end_line = start_line
        next_index = index
        while next_index < len(tokens):
            if tokens[next_index].line > end_line:
                end_line = tokens[next_index].line
            next_index += 1

        # Create the CodeElement for the function
        # Extract the actual code
        code_fragment = ""
        for i in range(start_index, next_index):
            if i < len(tokens):
                code_fragment += tokens[i].value

        function = CodeElement(
            name=function_name,
            element_type=ElementType.FUNCTION,
            start_line=start_line,
            end_line=end_line,
            code=code_fragment,
        )

        # Add parameters and return type metadata
        function.parameters = parameters
        function.return_type = return_type

        return function, next_index

    def _parse_class_direct(
        self, tokens: List[Token], index: int
    ) -> Tuple[Optional[CodeElement], int]:
        """
        Parse a class definition directly into a CodeElement.

        Args:
            tokens: List of tokens
            index: Current index in the token list

        Returns:
            Tuple of (parsed class element or None, new index)
        """
        # Similar implementation as _parse_function_direct but for classes
        # TODO: Implement class parsing
        return None, index

    def build_ast(self, tokens: List[Token]) -> Dict[str, Any]:
        """
        Build an abstract syntax tree from a list of tokens.

        Args:
            tokens: List of tokens from the tokenizer

        Returns:
            Dictionary representing the abstract syntax tree
        """
        ast: Dict[str, Any] = {
            "type": "Program",
            "body": [],
            "tokens": tokens,
            "start": 0,
            "end": len(tokens) - 1 if tokens else 0,
            "children": [],
        }

        i = 0
        while i < len(tokens):
            # Track indentation changes
            if tokens[i].token_type == TokenType.WHITESPACE and tokens[i].line == 1:
                indent_size = len(tokens[i].value)
                if "indent_size" in tokens[i].metadata:
                    indent_size = tokens[i].metadata["indent_size"]

                if indent_size > self.current_indent_level:
                    # Indentation increased - start a new block
                    self.indent_levels[indent_size] = tokens[i].line
                    self.current_indent_level = indent_size
                elif indent_size < self.current_indent_level:
                    # Indentation decreased - end blocks
                    for level in sorted(self.indent_levels.keys(), reverse=True):
                        if level > indent_size:
                            # End this block
                            del self.indent_levels[level]
                    self.current_indent_level = indent_size

            # Skip whitespace and newlines for AST building
            if tokens[i].token_type in [TokenType.WHITESPACE, TokenType.NEWLINE]:
                i += 1
                continue

            # Parse statements based on token type
            if i < len(tokens):
                if tokens[i].token_type == TokenType.KEYWORD:
                    stmt = self._parse_keyword_statement(tokens, i)
                    if stmt:
                        ast["body"].append(stmt["node"])
                        ast["children"].append(stmt["node"])
                        i = stmt["next_index"]
                    else:
                        i += 1
                elif tokens[i].token_type == TokenType.IDENTIFIER:
                    stmt = self._parse_expression_statement(tokens, i)
                    if stmt:
                        ast["body"].append(stmt["node"])
                        ast["children"].append(stmt["node"])
                        i = stmt["next_index"]
                    else:
                        i += 1
                else:
                    # Other token types
                    i += 1

        # Post-process the AST to fix parent-child relationships
        self._fix_parent_child_relationships(ast)

        # Validate and repair the AST
        self.validate_and_repair_ast()

        return ast

    def _parse_keyword_statement(
        self, tokens: List[Token], index: int
    ) -> Optional[Dict[str, Any]]:
        """
        Parse a statement that starts with a keyword.

        Args:
            tokens: List of tokens
            index: Current index in the token list

        Returns:
            Dictionary with the parsed node and next index, or None if parsing failed
        """
        if index >= len(tokens):
            return None

        keyword = tokens[index].value

        if keyword == "def":
            return self._parse_function_definition(tokens, index)
        elif keyword == "class":
            return self._parse_class_definition(tokens, index)
        elif keyword == "if":
            return self._parse_if_statement(tokens, index)
        elif keyword == "for":
            return self._parse_for_statement(tokens, index)
        elif keyword == "while":
            return self._parse_while_statement(tokens, index)
        elif keyword == "return":
            return self._parse_return_statement(tokens, index)
        elif keyword in ["import", "from"]:
            return self._parse_import_statement(tokens, index)
        elif keyword in ["try", "except", "finally"]:
            return self._parse_try_statement(tokens, index)
        elif keyword == "with":
            return self._parse_with_statement(tokens, index)

        # Default simple statement
        return self._parse_expression_statement(tokens, index)

    def _parse_function_definition(
        self, tokens: List[Token], index: int
    ) -> Optional[Dict[str, Any]]:
        """
        Parse a function definition.

        Args:
            tokens: List of tokens
            index: Current index in the token list

        Returns:
            Dictionary with the parsed node and next index, or None if parsing failed
        """
        start_index = index
        index += 1  # Skip 'def' keyword

        # Skip whitespace
        while index < len(tokens) and tokens[index].token_type == TokenType.WHITESPACE:
            index += 1

        # Get function name
        if index >= len(tokens) or tokens[index].token_type != TokenType.IDENTIFIER:
            return None

        function_name = tokens[index].value
        name_index = index
        index += 1

        # Skip whitespace
        while index < len(tokens) and tokens[index].token_type == TokenType.WHITESPACE:
            index += 1

        # Expect open parenthesis
        if index >= len(tokens) or tokens[index].token_type != TokenType.OPEN_PAREN:
            return None

        index += 1

        # Parse parameters
        parameters = []
        while index < len(tokens) and tokens[index].token_type != TokenType.CLOSE_PAREN:
            # Skip whitespace
            if tokens[index].token_type == TokenType.WHITESPACE:
                index += 1
                continue

            # Parameter name
            if tokens[index].token_type == TokenType.IDENTIFIER:
                param_name = tokens[index].value
                param_index = index
                index += 1

                # Check for type annotation
                param_type = None
                if index < len(tokens) and tokens[index].token_type == TokenType.COLON:
                    index += 1

                    # Skip whitespace
                    while (
                        index < len(tokens)
                        and tokens[index].token_type == TokenType.WHITESPACE
                    ):
                        index += 1

                    # Get type annotation
                    if (
                        index < len(tokens)
                        and tokens[index].token_type == TokenType.IDENTIFIER
                    ):
                        param_type = tokens[index].value
                        index += 1

                    # Support complex type annotations like List[str], Dict[str, int], etc.
                    if (
                        index < len(tokens)
                        and tokens[index].token_type == TokenType.OPEN_BRACKET
                    ):
                        bracket_depth = 1
                        index += 1

                        # Collect the entire type annotation
                        while index < len(tokens) and bracket_depth > 0:
                            if tokens[index].token_type == TokenType.OPEN_BRACKET:
                                bracket_depth += 1
                            elif tokens[index].token_type == TokenType.CLOSE_BRACKET:
                                bracket_depth -= 1
                            index += 1

                # Check for default value
                default_value = None
                if index < len(tokens) and tokens[index].token_type == TokenType.EQUALS:
                    index += 1

                    # Skip whitespace
                    while (
                        index < len(tokens)
                        and tokens[index].token_type == TokenType.WHITESPACE
                    ):
                        index += 1

                    # Parse default value expression
                    default_expr = self._parse_expression(tokens, index)
                    if default_expr:
                        default_value = default_expr["node"]
                        index = default_expr["next_index"]

                # Create parameter node
                param_node = {
                    "type": "Parameter",
                    "name": param_name,
                    "type_annotation": param_type,
                    "default_value": default_value,
                    "start": param_index,
                    "end": index - 1,
                    "parent": None,
                    "children": [],
                }

                # Add parameter to symbol table
                self.symbol_table.add_symbol(
                    name=param_name,
                    symbol_type="parameter",
                    position=tokens[param_index].position,
                    line=tokens[param_index].line,
                    column=tokens[param_index].column,
                    metadata={"type": param_type},
                )

                parameters.append(param_node)

                # Set parent-child relationship for default value
                if default_value:
                    default_value["parent"] = param_node
                    param_node["children"].append(default_value)

            # Skip comma
            if index < len(tokens) and tokens[index].token_type == TokenType.COMMA:
                index += 1
                continue

        # Skip closing parenthesis
        if index < len(tokens) and tokens[index].token_type == TokenType.CLOSE_PAREN:
            index += 1

        # Check for return type annotation
        return_type = None
        if index < len(tokens) and tokens[index].token_type == TokenType.ARROW:
            index += 1

            # Skip whitespace
            while (
                index < len(tokens) and tokens[index].token_type == TokenType.WHITESPACE
            ):
                index += 1

            # Get return type annotation
            if index < len(tokens) and tokens[index].token_type == TokenType.IDENTIFIER:
                return_type = tokens[index].value
                index += 1

                # Support complex return types like List[str], Dict[str, int], etc.
                if (
                    index < len(tokens)
                    and tokens[index].token_type == TokenType.OPEN_BRACKET
                ):
                    bracket_depth = 1
                    index += 1

                    # Collect the entire return type
                    while index < len(tokens) and bracket_depth > 0:
                        if tokens[index].token_type == TokenType.OPEN_BRACKET:
                            bracket_depth += 1
                        elif tokens[index].token_type == TokenType.CLOSE_BRACKET:
                            bracket_depth -= 1
                        index += 1

        # Skip whitespace and colon
        while index < len(tokens) and tokens[index].token_type == TokenType.WHITESPACE:
            index += 1

        if index < len(tokens) and tokens[index].token_type == TokenType.COLON:
            index += 1
        else:
            return None  # Malformed function definition

        # Calculate the current indentation level
        current_indent_level = 0
        for i in range(start_index - 1, -1, -1):
            if tokens[i].token_type == TokenType.NEWLINE:
                # Found the start of the current line
                if (
                    i + 1 < len(tokens)
                    and tokens[i + 1].token_type == TokenType.WHITESPACE
                ):
                    # Get indentation level
                    indent_token = tokens[i + 1]
                    current_indent_level = len(indent_token.value)
                    if "indent_size" in indent_token.metadata:
                        current_indent_level = indent_token.metadata["indent_size"]
                break

        # Determine if we're in a class context (method vs function)
        is_method = self.is_in_context(self.context_types["class"])
        context_type = (
            self.context_types["method"]
            if is_method
            else self.context_types["function"]
        )

        # Context metadata
        context_metadata = {
            "name": function_name,
            "parameters": [p["name"] for p in parameters],
            "return_type": return_type,
            "is_method": is_method,
        }

        # Add function/method to symbol table
        self.symbol_table.add_symbol(
            name=function_name,
            symbol_type="method" if is_method else "function",
            position=tokens[name_index].position,
            line=tokens[name_index].line,
            column=tokens[name_index].column,
            metadata={
                "parameters": [p["name"] for p in parameters],
                "return_type": return_type,
            },
        )

        # Enter function context
        if self.context_tracker:
            self.context_tracker.enter_context(
                context_type, function_name, context_metadata, start_index
            )
        else:
            # For backward compatibility
            self.state.enter_context(ContextInfo(context_type, context_metadata))

        # Parse function body using generic indentation block parser
        body_token_indices, next_index = IndentationBlockParser.parse_block(
            tokens,
            index,
            current_indent_level,
            self.state,
            None,  # Don't push context again, we already did it above
            context_metadata,
        )

        # Process the body tokens into actual nodes
        body_nodes = []
        i = 0
        while i < len(body_token_indices):
            token_index = body_token_indices[i]

            # Skip whitespace and newlines
            if tokens[token_index].token_type in [
                TokenType.WHITESPACE,
                TokenType.NEWLINE,
            ]:
                i += 1
                continue

            # Parse statement based on token type
            if tokens[token_index].token_type == TokenType.KEYWORD:
                stmt = self._parse_keyword_statement(tokens, token_index)
                if stmt:
                    body_nodes.append(stmt["node"])
                    # Skip ahead to tokens after this statement
                    while (
                        i < len(body_token_indices)
                        and body_token_indices[i] < stmt["next_index"]
                    ):
                        i += 1
                else:
                    i += 1
            elif tokens[token_index].token_type == TokenType.IDENTIFIER:
                stmt = self._parse_expression_statement(tokens, token_index)
                if stmt:
                    body_nodes.append(stmt["node"])
                    # Skip ahead to tokens after this statement
                    while (
                        i < len(body_token_indices)
                        and body_token_indices[i] < stmt["next_index"]
                    ):
                        i += 1
                else:
                    i += 1
            else:
                # Other token types
                i += 1

        # Exit function context
        if self.context_tracker:
            self.context_tracker.exit_context(next_index)
        else:
            # For backward compatibility
            self.state.exit_context()

        # Create function node
        function_node = {
            "type": "FunctionDefinition" if not is_method else "MethodDefinition",
            "name": function_name,
            "parameters": parameters,
            "return_type": return_type,
            "body": body_nodes,
            "start": start_index,
            "end": next_index - 1,
            "parent": None,
            "children": [],
        }

        # Set parent-child relationships for parameters and body nodes
        for param in parameters:
            param["parent"] = function_node
            function_node["children"].append(param)

        for node in body_nodes:
            node["parent"] = function_node
            function_node["children"].append(node)

        return {"node": function_node, "next_index": next_index}

    def _parse_class_definition(
        self, tokens: List[Token], index: int
    ) -> Optional[Dict[str, Any]]:
        """
        Parse a class definition.

        Args:
            tokens: List of tokens
            index: Current index in the token list

        Returns:
            Dictionary with the parsed node and next index, or None if parsing failed
        """
        start_index = index
        index += 1  # Skip 'class' keyword

        # Skip whitespace
        while index < len(tokens) and tokens[index].token_type == TokenType.WHITESPACE:
            index += 1

        # Get class name
        if index >= len(tokens) or tokens[index].token_type != TokenType.IDENTIFIER:
            return None

        class_name = tokens[index].value
        name_index = index
        index += 1

        # Skip whitespace
        while index < len(tokens) and tokens[index].token_type == TokenType.WHITESPACE:
            index += 1

        # Check for inheritance
        bases = []
        if index < len(tokens) and tokens[index].token_type == TokenType.OPEN_PAREN:
            index += 1

            while (
                index < len(tokens)
                and tokens[index].token_type != TokenType.CLOSE_PAREN
            ):
                # Skip whitespace
                if tokens[index].token_type == TokenType.WHITESPACE:
                    index += 1
                    continue

                # Base class name
                if tokens[index].token_type == TokenType.IDENTIFIER:
                    base_name = tokens[index].value
                    base_index = index
                    index += 1

                    bases.append(
                        {
                            "type": "Identifier",
                            "name": base_name,
                            "start": base_index,
                            "end": base_index,
                            "parent": None,
                            "children": [],
                        }
                    )

                # Skip comma
                if index < len(tokens) and tokens[index].token_type == TokenType.COMMA:
                    index += 1
                    continue

            # Skip closing parenthesis
            if (
                index < len(tokens)
                and tokens[index].token_type == TokenType.CLOSE_PAREN
            ):
                index += 1

        # Skip whitespace and colon
        while index < len(tokens) and tokens[index].token_type == TokenType.WHITESPACE:
            index += 1

        if index < len(tokens) and tokens[index].token_type == TokenType.COLON:
            index += 1
        else:
            return None  # Malformed class definition

        # Calculate the current indentation level
        current_indent_level = 0
        for i in range(start_index - 1, -1, -1):
            if tokens[i].token_type == TokenType.NEWLINE:
                # Found the start of the current line
                if (
                    i + 1 < len(tokens)
                    and tokens[i + 1].token_type == TokenType.WHITESPACE
                ):
                    # Get indentation level
                    indent_token = tokens[i + 1]
                    current_indent_level = len(indent_token.value)
                    if "indent_size" in indent_token.metadata:
                        current_indent_level = indent_token.metadata["indent_size"]
                break

        # Context metadata
        context_metadata = {"name": class_name, "bases": [b["name"] for b in bases]}

        # Add class to symbol table
        self.symbol_table.add_symbol(
            name=class_name,
            symbol_type="class",
            position=tokens[name_index].position,
            line=tokens[name_index].line,
            column=tokens[name_index].column,
            metadata={"bases": [b["name"] for b in bases]},
        )

        # Enter class context
        if self.context_tracker:
            self.context_tracker.enter_context(
                self.context_types["class"], class_name, context_metadata, start_index
            )
        else:
            # For backward compatibility
            self.state.enter_context(
                ContextInfo(self.context_types["class"], context_metadata)
            )

        # Parse class body using generic indentation block parser
        body_token_indices, next_index = IndentationBlockParser.parse_block(
            tokens,
            index,
            current_indent_level,
            self.state,
            None,  # Don't push context again, we already did it above
            context_metadata,
        )

        # Process the body tokens into actual nodes
        body_nodes = []
        i = 0
        while i < len(body_token_indices):
            token_index = body_token_indices[i]

            # Skip whitespace and newlines
            if tokens[token_index].token_type in [
                TokenType.WHITESPACE,
                TokenType.NEWLINE,
            ]:
                i += 1
                continue

            # Parse statement based on token type
            if tokens[token_index].token_type == TokenType.KEYWORD:
                stmt = self._parse_keyword_statement(tokens, token_index)
                if stmt:
                    body_nodes.append(stmt["node"])
                    # Skip ahead to tokens after this statement
                    while (
                        i < len(body_token_indices)
                        and body_token_indices[i] < stmt["next_index"]
                    ):
                        i += 1
                else:
                    i += 1
            elif tokens[token_index].token_type == TokenType.IDENTIFIER:
                stmt = self._parse_expression_statement(tokens, token_index)
                if stmt:
                    body_nodes.append(stmt["node"])
                    # Skip ahead to tokens after this statement
                    while (
                        i < len(body_token_indices)
                        and body_token_indices[i] < stmt["next_index"]
                    ):
                        i += 1
                else:
                    i += 1
            else:
                # Other token types
                i += 1

        # Exit class context
        if self.context_tracker:
            self.context_tracker.exit_context(next_index)
        else:
            # For backward compatibility
            self.state.exit_context()

        # Create class node
        class_node = {
            "type": "ClassDefinition",
            "name": class_name,
            "bases": bases,
            "body": body_nodes,
            "start": start_index,
            "end": next_index - 1,
            "parent": None,
            "children": [],
        }

        # Set parent-child relationships for bases and body nodes
        for base in bases:
            base["parent"] = class_node
            class_node["children"].append(base)

        for node in body_nodes:
            node["parent"] = class_node
            class_node["children"].append(node)

        return {"node": class_node, "next_index": next_index}

    def _parse_expression_statement(
        self, tokens: List[Token], index: int
    ) -> Optional[Dict[str, Any]]:
        """
        Parse an expression statement.

        Args:
            tokens: List of tokens
            index: Current index in the token list

        Returns:
            Dictionary with the parsed node and next index, or None if parsing failed
        """
        expr = self._parse_expression(tokens, index)
        if not expr:
            return None

        stmt = {
            "type": "ExpressionStatement",
            "expression": expr["node"],
            "start": expr["node"]["start"],
            "end": expr["node"]["end"],
            "parent": None,
            "children": [expr["node"]],
        }

        expr["node"]["parent"] = stmt

        return {"node": stmt, "next_index": expr["next_index"]}

    def _parse_expression(
        self, tokens: List[Token], index: int
    ) -> Optional[Dict[str, Any]]:
        """
        Parse an expression.

        Args:
            tokens: List of tokens
            index: Current index in the token list

        Returns:
            Dictionary with the parsed node and next index, or None if parsing failed
        """
        # For simplicity, we'll just parse basic expressions
        if index >= len(tokens):
            return None

        if tokens[index].token_type == TokenType.IDENTIFIER:
            # Variable reference or function call
            identifier = tokens[index].value
            start_index = index
            index += 1

            # Check if it's a function call
            if index < len(tokens) and tokens[index].token_type == TokenType.OPEN_PAREN:
                index += 1

                # Parse arguments
                arguments = []
                while (
                    index < len(tokens)
                    and tokens[index].token_type != TokenType.CLOSE_PAREN
                ):
                    # Skip whitespace
                    if tokens[index].token_type == TokenType.WHITESPACE:
                        index += 1
                        continue

                    # Parse argument expression
                    arg_expr = self._parse_expression(tokens, index)
                    if arg_expr:
                        arguments.append(arg_expr["node"])
                        index = arg_expr["next_index"]
                    else:
                        # Skip this token if we couldn't parse an expression
                        index += 1

                    # Skip comma
                    if (
                        index < len(tokens)
                        and tokens[index].token_type == TokenType.COMMA
                    ):
                        index += 1

                # Skip closing parenthesis
                if (
                    index < len(tokens)
                    and tokens[index].token_type == TokenType.CLOSE_PAREN
                ):
                    index += 1

                # Create call expression node
                call_node = {
                    "type": "CallExpression",
                    "callee": {
                        "type": "Identifier",
                        "name": identifier,
                        "start": start_index,
                        "end": start_index,
                        "parent": None,
                        "children": [],
                    },
                    "arguments": arguments,
                    "start": start_index,
                    "end": index - 1,
                    "parent": None,
                    "children": [],
                }

                # Set parent-child relationships
                call_node["callee"]["parent"] = call_node
                call_node["children"].append(call_node["callee"])

                for arg in arguments:
                    arg["parent"] = call_node
                    call_node["children"].append(arg)

                return {"node": call_node, "next_index": index}
            else:
                # Simple identifier
                return {
                    "node": {
                        "type": "Identifier",
                        "name": identifier,
                        "start": start_index,
                        "end": start_index,
                        "parent": None,
                        "children": [],
                    },
                    "next_index": index,
                }
        elif tokens[index].token_type == TokenType.NUMBER:
            # Numeric literal
            return {
                "node": {
                    "type": "NumericLiteral",
                    "value": tokens[index].value,
                    "start": index,
                    "end": index,
                    "parent": None,
                    "children": [],
                },
                "next_index": index + 1,
            }
        elif tokens[index].token_type == TokenType.STRING_START:
            # String literal
            start_index = index
            string_value = ""
            index += 1

            # Collect string content
            while index < len(tokens):
                if tokens[index].token_type == TokenType.STRING_END:
                    index += 1
                    break

                string_value += tokens[index].value
                index += 1

            return {
                "node": {
                    "type": "StringLiteral",
                    "value": string_value,
                    "start": start_index,
                    "end": index - 1,
                    "parent": None,
                    "children": [],
                },
                "next_index": index,
            }

        # Default case
        return None

    def _parse_if_statement(
        self, tokens: List[Token], index: int
    ) -> Optional[Dict[str, Any]]:
        """Placeholder for parsing if statements."""
        # This would be implemented similarly to the function and class parsers
        return None

    def _parse_for_statement(
        self, tokens: List[Token], index: int
    ) -> Optional[Dict[str, Any]]:
        """Placeholder for parsing for statements."""
        return None

    def _parse_while_statement(
        self, tokens: List[Token], index: int
    ) -> Optional[Dict[str, Any]]:
        """Placeholder for parsing while statements."""
        return None

    def _parse_return_statement(
        self, tokens: List[Token], index: int
    ) -> Optional[Dict[str, Any]]:
        """Placeholder for parsing return statements."""
        return None

    def _parse_import_statement(
        self, tokens: List[Token], index: int
    ) -> Optional[Dict[str, Any]]:
        """Placeholder for parsing import statements."""
        return None

    def _parse_try_statement(
        self, tokens: List[Token], index: int
    ) -> Optional[Dict[str, Any]]:
        """Placeholder for parsing try-except statements."""
        return None

    def _parse_with_statement(
        self, tokens: List[Token], index: int
    ) -> Optional[Dict[str, Any]]:
        """Placeholder for parsing with statements."""
        return None

    def _fix_parent_child_relationships(self, ast: Dict[str, Any]) -> None:
        """
        Fix parent-child relationships in the AST.

        Args:
            ast: The abstract syntax tree to fix
        """
        # Implement parent-child relationship fixing logic here
        # This would walk the AST and ensure all nodes have correct parent and children references
        pass
