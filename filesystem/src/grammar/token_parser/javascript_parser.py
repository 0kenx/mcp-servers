"""
JavaScript parser for the grammar parser system.

This module provides a parser specific to the JavaScript programming language,
building on the base token parser framework.
"""

from typing import List, Dict, Optional, Any, Tuple

from .token import Token, TokenType
from .token_parser import TokenParser
from .parser_state import ParserState
from .symbol_table import SymbolTable
from .context_tracker import ContextTracker
from .javascript_tokenizer import JavaScriptTokenizer
from .generic_brace_block_parser import BraceBlockParser
from .base import CodeElement, ElementType


class JavaScriptParser(TokenParser):
    """
    Parser for JavaScript code.

    This parser processes JavaScript-specific syntax, handling constructs like
    functions, classes, object literals, and more, producing an abstract syntax tree.
    """

    def __init__(self):
        """Initialize the JavaScript parser."""
        super().__init__()
        self.tokenizer = JavaScriptTokenizer()
        self.state = ParserState()
        self.symbol_table = SymbolTable()

        # Context types specific to JavaScript
        self.context_types = {
            "function": "function",
            "method": "method",
            "arrow_function": "arrow_function",
            "class": "class",
            "object_literal": "object_literal",
            "if": "if",
            "else": "else",
            "for": "for",
            "while": "while",
            "do_while": "do_while",
            "switch": "switch",
            "try": "try",
            "catch": "catch",
            "finally": "finally",
            "with": "with",
            "template_literal": "template_literal",
            "destructuring": "destructuring",
        }

        # Bracket and brace tracking
        self.brace_stack = []
        self.bracket_stack = []
        self.paren_stack = []

    def parse(self, code: str) -> List[CodeElement]:
        """
        Parse JavaScript code and return a list of code elements.

        Args:
            code: JavaScript source code

        Returns:
            List of code elements
        """
        # Reset state for a new parse
        self.elements = []
        self.state = ParserState()
        self.symbol_table = SymbolTable()
        self.context_tracker = ContextTracker()
        self.brace_stack = []
        self.bracket_stack = []
        self.paren_stack = []

        # Tokenize the code
        tokens = self.tokenize(code)

        # Process the tokens to build elements directly
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
        current_class = None  # Keep track of current class for methods

        while i < len(tokens):
            # Skip whitespace and newlines for element building
            if tokens[i].token_type in [TokenType.WHITESPACE, TokenType.NEWLINE]:
                i += 1
                continue

            # Parse statements based on token type
            if i < len(tokens):
                if tokens[i].token_type == TokenType.KEYWORD:
                    # Process JavaScript keywords (function, class, etc.)
                    if (
                        tokens[i].value == "function"
                        or tokens[i].value == "async"
                        and i + 1 < len(tokens)
                        and tokens[i + 1].value == "function"
                    ):
                        # Function declaration
                        function, next_index = self._parse_function_direct(tokens, i)
                        if function:
                            self.elements.append(function)
                            i = next_index
                        else:
                            i += 1
                    elif tokens[i].value == "class":
                        # Class declaration
                        class_element, next_index = self._parse_class_direct(tokens, i)
                        if class_element:
                            self.elements.append(class_element)
                            current_class = (
                                class_element  # Update current class context
                            )
                            i = next_index
                        else:
                            i += 1
                    elif tokens[i].value in ("const", "let", "var"):
                        # Variable declarations - may contain arrow functions
                        # TODO: Parse variable declarations with arrow functions
                        i += 1
                    else:
                        # Other keywords (if, for, while, etc.)
                        i += 1
                elif tokens[i].token_type == TokenType.IDENTIFIER:
                    # This could be an object method or property
                    if (
                        i + 1 < len(tokens)
                        and tokens[i + 1].token_type == TokenType.OPERATOR
                        and tokens[i + 1].value == "="
                    ):
                        # Potential assignment (including arrow functions)
                        name = tokens[i].value
                        i += 2  # Skip past the name and equals sign

                        # Check for arrow function
                        arrow_fn = self._try_parse_arrow_function(tokens, i, name)
                        if arrow_fn:
                            self.elements.append(arrow_fn)
                            # Skip to the end of the arrow function
                            i = arrow_fn.code.rfind("}") + 1
                        else:
                            # Regular assignment, not a function
                            i += 1
                    else:
                        # Not an assignment
                        i += 1
                else:
                    # Other token types
                    i += 1

    def _try_parse_arrow_function(
        self, tokens: List[Token], index: int, name: str
    ) -> Optional[CodeElement]:
        """
        Try to parse an arrow function expression.

        Args:
            tokens: List of tokens
            index: Current token index
            name: Name of the variable being assigned to

        Returns:
            A CodeElement if an arrow function is found, None otherwise
        """
        start_index = index
        start_line = tokens[index].line if index < len(tokens) else 0

        # Skip whitespace
        while index < len(tokens) and tokens[index].token_type == TokenType.WHITESPACE:
            index += 1

        # Check for arrow function syntax: either (params) => {...} or param => {...}
        parameters = []

        # Check for parameters in parentheses: (param1, param2) => {...}
        if index < len(tokens) and tokens[index].token_type == TokenType.OPEN_PAREN:
            # Parse parameters in parentheses
            index += 1  # Skip opening parenthesis
            param_name = ""
            paren_depth = 1

            while index < len(tokens) and paren_depth > 0:
                token = tokens[index]

                # Parameter name
                if token.token_type == TokenType.IDENTIFIER and not param_name:
                    param_name = token.value

                # Parameter separator (comma)
                elif token.token_type == TokenType.COMMA:
                    if param_name:
                        parameters.append({"name": param_name})
                        param_name = ""

                # Update paren depth
                if token.token_type == TokenType.OPEN_PAREN:
                    paren_depth += 1
                elif token.token_type == TokenType.CLOSE_PAREN:
                    paren_depth -= 1

                    # If we're at the end of parameters, add the last one
                    if paren_depth == 0 and param_name:
                        parameters.append({"name": param_name})

                index += 1

            # Skip whitespace after closing parenthesis
            while (
                index < len(tokens) and tokens[index].token_type == TokenType.WHITESPACE
            ):
                index += 1

        # Check for single parameter without parentheses: param => {...}
        elif index < len(tokens) and tokens[index].token_type == TokenType.IDENTIFIER:
            parameters.append({"name": tokens[index].value})
            index += 1

            # Skip whitespace after parameter
            while (
                index < len(tokens) and tokens[index].token_type == TokenType.WHITESPACE
            ):
                index += 1

        # Check for arrow token
        if (
            index + 1 < len(tokens)
            and tokens[index].token_type == TokenType.OPERATOR
            and tokens[index].value == "="
            and tokens[index + 1].token_type == TokenType.OPERATOR
            and tokens[index + 1].value == ">"
        ):
            # We have an arrow function!
            index += 2  # Skip past the arrow (=>)

            # Skip whitespace after arrow
            while (
                index < len(tokens) and tokens[index].token_type == TokenType.WHITESPACE
            ):
                index += 1

            # Find function body (either block or expression)
            end_index = index
            end_line = start_line

            if index < len(tokens) and tokens[index].token_type == TokenType.OPEN_BRACE:
                # Block body: {...}
                brace_depth = 1
                index += 1

                while index < len(tokens) and brace_depth > 0:
                    if tokens[index].token_type == TokenType.OPEN_BRACE:
                        brace_depth += 1
                    elif tokens[index].token_type == TokenType.CLOSE_BRACE:
                        brace_depth -= 1

                    if tokens[index].line > end_line:
                        end_line = tokens[index].line

                    index += 1
                    end_index = index
            else:
                # Expression body (find the end of the expression)
                while index < len(tokens) and tokens[index].token_type not in (
                    TokenType.SEMICOLON,
                    TokenType.NEWLINE,
                ):
                    if tokens[index].line > end_line:
                        end_line = tokens[index].line
                    index += 1
                    end_index = index

            # Extract code
            code_fragment = ""
            for i in range(
                start_index - 2, end_index
            ):  # Include the variable name and equals sign
                if i >= 0 and i < len(tokens):
                    code_fragment += tokens[i].value

            # Create CodeElement
            arrow_function = CodeElement(
                name=name,
                element_type=ElementType.FUNCTION,
                start_line=start_line,
                end_line=end_line,
                code=code_fragment,
            )

            # Add metadata
            arrow_function.parameters = parameters
            arrow_function.is_arrow_function = True

            return arrow_function

        # Not an arrow function
        return None

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

        # Check for async keyword
        is_async = False
        if tokens[index].value == "async":
            is_async = True
            index += 1  # Skip async keyword
            # Skip whitespace
            while (
                index < len(tokens) and tokens[index].token_type == TokenType.WHITESPACE
            ):
                index += 1
            # Make sure we have 'function' next
            if index >= len(tokens) or tokens[index].value != "function":
                return None, index  # Not a valid async function

        # Skip 'function' keyword
        index += 1

        # Check for generator function (function*)
        is_generator = False
        if (
            index < len(tokens)
            and tokens[index].token_type == TokenType.OPERATOR
            and tokens[index].value == "*"
        ):
            is_generator = True
            index += 1  # Skip * operator

        # Skip whitespace
        while index < len(tokens) and tokens[index].token_type == TokenType.WHITESPACE:
            index += 1

        # Get function name (might be empty for anonymous functions)
        function_name = ""
        if index < len(tokens) and tokens[index].token_type == TokenType.IDENTIFIER:
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
        param_name = ""
        paren_depth = 1

        # For each parameter (separated by comma)
        while index < len(tokens) and paren_depth > 0:
            token = tokens[index]

            # Parameter name
            if token.token_type == TokenType.IDENTIFIER and not param_name:
                param_name = token.value

            # Default value (handle = sign)
            elif token.token_type == TokenType.OPERATOR and token.value == "=":
                index += 1  # Skip = sign

                # Parse default value expression
                default_start = index
                default_depth = 0

                # Collect until comma or closing paren
                while (
                    index < len(tokens)
                    and not (
                        tokens[index].token_type == TokenType.COMMA
                        and default_depth == 0
                    )
                    and not (
                        tokens[index].token_type == TokenType.CLOSE_PAREN
                        and default_depth == 0
                        and paren_depth == 1
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
                            paren_depth -= 1
                            break

                    index += 1

                # We don't add default value to the parameter yet, but we've parsed it
                continue

            # Parameter separator (comma)
            elif token.token_type == TokenType.COMMA:
                if param_name:
                    parameters.append(
                        {
                            "name": param_name,
                        }
                    )
                    # Reset for next parameter
                    param_name = ""

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
                        }
                    )

            index += 1

        # Skip to opening brace
        while index < len(tokens) and tokens[index].token_type != TokenType.OPEN_BRACE:
            index += 1

        if index >= len(tokens):
            return None, index  # Not a valid function definition

        # Open brace found, now find matching closing brace
        index += 1
        brace_depth = 1
        end_line = start_line

        while index < len(tokens) and brace_depth > 0:
            if tokens[index].token_type == TokenType.OPEN_BRACE:
                brace_depth += 1
            elif tokens[index].token_type == TokenType.CLOSE_BRACE:
                brace_depth -= 1

            if tokens[index].line > end_line:
                end_line = tokens[index].line

            index += 1

        # Create the CodeElement for the function
        # Extract the actual code
        code_fragment = ""
        for i in range(start_index, index):
            if i < len(tokens):
                code_fragment += tokens[i].value

        function = CodeElement(
            name=function_name if function_name else "<anonymous>",
            element_type=ElementType.FUNCTION,
            start_line=start_line,
            end_line=end_line,
            code=code_fragment,
        )

        # Add metadata
        function.parameters = parameters
        function.is_async = is_async
        function.is_generator = is_generator

        return function, index

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
        start_index = index
        start_line = tokens[index].line

        # Skip 'class' keyword
        index += 1

        # Skip whitespace
        while index < len(tokens) and tokens[index].token_type == TokenType.WHITESPACE:
            index += 1

        # Get class name
        class_name = ""
        if index < len(tokens) and tokens[index].token_type == TokenType.IDENTIFIER:
            class_name = tokens[index].value
            index += 1
        else:
            # Anonymous classes aren't valid in standard JavaScript
            return None, index

        # Skip whitespace
        while index < len(tokens) and tokens[index].token_type == TokenType.WHITESPACE:
            index += 1

        # Check for extends clause
        extends = None
        if (
            index < len(tokens)
            and tokens[index].token_type == TokenType.KEYWORD
            and tokens[index].value == "extends"
        ):
            index += 1  # Skip 'extends' keyword

            # Skip whitespace
            while (
                index < len(tokens) and tokens[index].token_type == TokenType.WHITESPACE
            ):
                index += 1

            # Get superclass name
            if index < len(tokens) and tokens[index].token_type == TokenType.IDENTIFIER:
                extends = tokens[index].value
                index += 1

        # Skip to opening brace
        while index < len(tokens) and tokens[index].token_type != TokenType.OPEN_BRACE:
            index += 1

        if index >= len(tokens):
            return None, index  # Not a valid class definition

        # Found opening brace, now match closing brace
        index += 1
        brace_depth = 1
        end_line = start_line

        # Parse class body (find matching closing brace)
        while index < len(tokens) and brace_depth > 0:
            if tokens[index].token_type == TokenType.OPEN_BRACE:
                brace_depth += 1
            elif tokens[index].token_type == TokenType.CLOSE_BRACE:
                brace_depth -= 1

            if tokens[index].line > end_line:
                end_line = tokens[index].line

            index += 1

        # Create the CodeElement for the class
        # Extract the actual code
        code_fragment = ""
        for i in range(start_index, index):
            if i < len(tokens):
                code_fragment += tokens[i].value

        class_element = CodeElement(
            name=class_name,
            element_type=ElementType.CLASS,
            start_line=start_line,
            end_line=end_line,
            code=code_fragment,
        )

        # Add inheritance information if available
        if extends:
            class_element.extends = extends

        return class_element, index

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

        if keyword == "function":
            return self._parse_function_declaration(tokens, index)
        elif keyword == "class":
            return self._parse_class_declaration(tokens, index)
        elif keyword == "if":
            return self._parse_if_statement(tokens, index)
        elif keyword == "for":
            return self._parse_for_statement(tokens, index)
        elif keyword == "while":
            return self._parse_while_statement(tokens, index)
        elif keyword == "do":
            return self._parse_do_while_statement(tokens, index)
        elif keyword == "switch":
            return self._parse_switch_statement(tokens, index)
        elif keyword == "return":
            return self._parse_return_statement(tokens, index)
        elif keyword in ["import", "export"]:
            return self._parse_module_statement(tokens, index)
        elif keyword in ["try", "catch", "finally"]:
            return self._parse_try_statement(tokens, index)
        elif keyword == "const" or keyword == "let" or keyword == "var":
            return self._parse_variable_declaration(tokens, index)

        # Default simple statement
        return self._parse_expression_statement(tokens, index)

    def _parse_function_declaration(
        self, tokens: List[Token], index: int
    ) -> Optional[Dict[str, Any]]:
        """
        Parse a function declaration.

        Args:
            tokens: List of tokens
            index: Current index in the token list

        Returns:
            Dictionary with the parsed node and next index, or None if parsing failed
        """
        start_index = index
        index += 1  # Skip 'function' keyword

        # Skip whitespace
        while index < len(tokens) and tokens[index].token_type == TokenType.WHITESPACE:
            index += 1

        # Get function name (optional for function expressions)
        function_name = None
        name_index = None
        if index < len(tokens) and tokens[index].token_type == TokenType.IDENTIFIER:
            function_name = tokens[index].value
            name_index = index
            index += 1

            # Skip whitespace
            while (
                index < len(tokens) and tokens[index].token_type == TokenType.WHITESPACE
            ):
                index += 1

        # Expect open parenthesis
        if index >= len(tokens) or tokens[index].token_type != TokenType.OPEN_PAREN:
            return None

        self.paren_stack.append(index)
        index += 1

        # Parse parameters
        parameters = []
        while index < len(tokens) and tokens[index].token_type != TokenType.CLOSE_PAREN:
            # Skip whitespace and commas
            if tokens[index].token_type in [TokenType.WHITESPACE, TokenType.COMMA]:
                index += 1
                continue

            # Parameter name
            if tokens[index].token_type == TokenType.IDENTIFIER:
                param_name = tokens[index].value
                param_index = index
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
                    default_value_expr = self._parse_expression(tokens, index)
                    if default_value_expr:
                        default_value = default_value_expr["node"]
                        index = default_value_expr["next_index"]

                parameters.append(
                    {
                        "type": "Parameter",
                        "name": param_name,
                        "default": default_value,
                        "start": param_index,
                        "end": index - 1,
                        "parent": None,
                        "children": [],
                    }
                )
            else:
                # Skip other tokens
                index += 1

        # Skip closing parenthesis
        if index < len(tokens) and tokens[index].token_type == TokenType.CLOSE_PAREN:
            if self.paren_stack:
                self.paren_stack.pop()
            index += 1
        else:
            return None  # Malformed function declaration

        # Skip whitespace
        while index < len(tokens) and tokens[index].token_type == TokenType.WHITESPACE:
            index += 1

        # Expect open brace
        if index >= len(tokens) or tokens[index].token_type != TokenType.OPEN_BRACE:
            return None

        # Enter function context
        context_metadata = (
            {"name": function_name} if function_name else {"name": "anonymous_function"}
        )

        # Add function to symbol table if it has a name
        if function_name and name_index is not None:
            self.symbol_table.add_symbol(
                name=function_name,
                symbol_type="function",
                position=tokens[name_index].position,
                line=tokens[name_index].line,
                column=tokens[name_index].column,
                metadata={"parameters": [p["name"] for p in parameters]},
            )

        # Parse function body using generic brace block parser
        body_tokens, next_index = BraceBlockParser.parse_block(
            tokens, index, self.state, self.context_types["function"], context_metadata
        )

        # Create function node
        function_node = {
            "type": "FunctionDeclaration" if function_name else "FunctionExpression",
            "name": function_name,
            "parameters": parameters,
            "body": body_tokens,
            "start": start_index,
            "end": next_index - 1,
            "parent": None,
            "children": [],
        }

        # Set parent-child relationships for parameters
        for param in parameters:
            param["parent"] = function_node
            function_node["children"].append(param)

        return {"node": function_node, "next_index": next_index}

    def _parse_class_declaration(
        self, tokens: List[Token], index: int
    ) -> Optional[Dict[str, Any]]:
        """
        Parse a class declaration.

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

        # Check for extends
        extends_clause = None
        if (
            index < len(tokens)
            and tokens[index].token_type == TokenType.KEYWORD
            and tokens[index].value == "extends"
        ):
            index += 1

            # Skip whitespace
            while (
                index < len(tokens) and tokens[index].token_type == TokenType.WHITESPACE
            ):
                index += 1

            # Get parent class name
            if index < len(tokens) and tokens[index].token_type == TokenType.IDENTIFIER:
                extends_clause = {
                    "type": "Identifier",
                    "name": tokens[index].value,
                    "start": index,
                    "end": index,
                    "parent": None,
                    "children": [],
                }
                index += 1

                # Skip whitespace
                while (
                    index < len(tokens)
                    and tokens[index].token_type == TokenType.WHITESPACE
                ):
                    index += 1

        # Expect open brace
        if index >= len(tokens) or tokens[index].token_type != TokenType.OPEN_BRACE:
            return None

        # Context metadata
        context_metadata = {
            "name": class_name,
            "extends": extends_clause["name"] if extends_clause else None,
        }

        # Add class to symbol table
        self.symbol_table.add_symbol(
            name=class_name,
            symbol_type="class",
            position=tokens[name_index].position,
            line=tokens[name_index].line,
            column=tokens[name_index].column,
            metadata={"extends": extends_clause["name"] if extends_clause else None},
        )

        # Parse class body using generic brace block parser
        body_tokens, next_index = BraceBlockParser.parse_block(
            tokens, index, self.state, self.context_types["class"], context_metadata
        )

        # Create class node
        class_node = {
            "type": "ClassDeclaration",
            "name": class_name,
            "extends": extends_clause,
            "body": body_tokens,
            "start": start_index,
            "end": next_index - 1,
            "parent": None,
            "children": [],
        }

        # Set parent-child relationships
        if extends_clause:
            extends_clause["parent"] = class_node
            class_node["children"].append(extends_clause)

        return {"node": class_node, "next_index": next_index}

    def _parse_variable_declaration(
        self, tokens: List[Token], index: int
    ) -> Optional[Dict[str, Any]]:
        """
        Parse a variable declaration (let, const, var).

        Args:
            tokens: List of tokens
            index: Current index in the token list

        Returns:
            Dictionary with the parsed node and next index, or None if parsing failed
        """
        start_index = index
        declaration_kind = tokens[index].value  # "let", "const", or "var"
        index += 1

        # Skip whitespace
        while index < len(tokens) and tokens[index].token_type == TokenType.WHITESPACE:
            index += 1

        # Parse variable declarations
        declarations = []
        while index < len(tokens) and tokens[index].token_type != TokenType.SEMICOLON:
            # Skip commas and whitespace
            if tokens[index].token_type in [TokenType.COMMA, TokenType.WHITESPACE]:
                index += 1
                continue

            # Variable name
            if tokens[index].token_type == TokenType.IDENTIFIER:
                var_name = tokens[index].value
                var_index = index
                index += 1

                # Skip whitespace
                while (
                    index < len(tokens)
                    and tokens[index].token_type == TokenType.WHITESPACE
                ):
                    index += 1

                # Check for initialization
                init = None
                if index < len(tokens) and tokens[index].token_type == TokenType.EQUALS:
                    index += 1

                    # Skip whitespace
                    while (
                        index < len(tokens)
                        and tokens[index].token_type == TokenType.WHITESPACE
                    ):
                        index += 1

                    # Parse initializer expression
                    init_expr = self._parse_expression(tokens, index)
                    if init_expr:
                        init = init_expr["node"]
                        index = init_expr["next_index"]

                # Add variable to symbol table
                self.symbol_table.add_symbol(
                    name=var_name,
                    symbol_type="variable",
                    position=tokens[var_index].position,
                    line=tokens[var_index].line,
                    column=tokens[var_index].column,
                    metadata={"kind": declaration_kind},
                )

                # Create declaration node
                declaration = {
                    "type": "VariableDeclarator",
                    "id": {
                        "type": "Identifier",
                        "name": var_name,
                        "start": var_index,
                        "end": var_index,
                        "parent": None,
                        "children": [],
                    },
                    "init": init,
                    "start": var_index,
                    "end": index - 1,
                    "parent": None,
                    "children": [],
                }

                # Set parent-child relationships
                declaration["id"]["parent"] = declaration
                declaration["children"].append(declaration["id"])

                if init:
                    init["parent"] = declaration
                    declaration["children"].append(init)

                declarations.append(declaration)
            else:
                # Skip unexpected tokens
                index += 1

        # Skip semicolon if present
        if index < len(tokens) and tokens[index].token_type == TokenType.SEMICOLON:
            index += 1

        # Create variable declaration node
        var_decl_node = {
            "type": "VariableDeclaration",
            "kind": declaration_kind,
            "declarations": declarations,
            "start": start_index,
            "end": index - 1,
            "parent": None,
            "children": [],
        }

        # Set parent-child relationships for declarations
        for decl in declarations:
            decl["parent"] = var_decl_node
            var_decl_node["children"].append(decl)

        return {"node": var_decl_node, "next_index": index}

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

        # Skip to semicolon or end of statement
        next_index = expr["next_index"]
        while (
            next_index < len(tokens)
            and tokens[next_index].token_type != TokenType.SEMICOLON
        ):
            if tokens[next_index].token_type not in [
                TokenType.WHITESPACE,
                TokenType.NEWLINE,
            ]:
                break
            next_index += 1

        # Skip semicolon if found
        if (
            next_index < len(tokens)
            and tokens[next_index].token_type == TokenType.SEMICOLON
        ):
            next_index += 1

        stmt = {
            "type": "ExpressionStatement",
            "expression": expr["node"],
            "start": expr["node"]["start"],
            "end": next_index - 1,
            "parent": None,
            "children": [expr["node"]],
        }

        expr["node"]["parent"] = stmt

        return {"node": stmt, "next_index": next_index}

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
        # This is a simplified expression parser
        if index >= len(tokens):
            return None

        if tokens[index].token_type == TokenType.IDENTIFIER:
            # Variable reference, function call, or member expression
            identifier = tokens[index].value
            start_index = index
            index += 1

            # Skip whitespace
            while (
                index < len(tokens) and tokens[index].token_type == TokenType.WHITESPACE
            ):
                index += 1

            # Check for function call
            if index < len(tokens) and tokens[index].token_type == TokenType.OPEN_PAREN:
                self.paren_stack.append(index)
                index += 1

                # Parse arguments
                arguments = []
                while (
                    index < len(tokens)
                    and tokens[index].token_type != TokenType.CLOSE_PAREN
                ):
                    # Skip whitespace and commas
                    if tokens[index].token_type in [
                        TokenType.WHITESPACE,
                        TokenType.COMMA,
                    ]:
                        index += 1
                        continue

                    # Parse argument expression
                    arg_expr = self._parse_expression(tokens, index)
                    if arg_expr:
                        arguments.append(arg_expr["node"])
                        index = arg_expr["next_index"]
                    else:
                        # Skip problematic tokens
                        index += 1

                # Skip closing parenthesis
                if (
                    index < len(tokens)
                    and tokens[index].token_type == TokenType.CLOSE_PAREN
                ):
                    if self.paren_stack:
                        self.paren_stack.pop()
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

            # Check for member expression
            if index < len(tokens) and tokens[index].token_type == TokenType.DOT:
                index += 1

                # Skip whitespace
                while (
                    index < len(tokens)
                    and tokens[index].token_type == TokenType.WHITESPACE
                ):
                    index += 1

                # Get property name
                if (
                    index < len(tokens)
                    and tokens[index].token_type == TokenType.IDENTIFIER
                ):
                    prop_name = tokens[index].value
                    prop_index = index
                    index += 1

                    # Create member expression node
                    member_node = {
                        "type": "MemberExpression",
                        "object": {
                            "type": "Identifier",
                            "name": identifier,
                            "start": start_index,
                            "end": start_index,
                            "parent": None,
                            "children": [],
                        },
                        "property": {
                            "type": "Identifier",
                            "name": prop_name,
                            "start": prop_index,
                            "end": prop_index,
                            "parent": None,
                            "children": [],
                        },
                        "computed": False,
                        "start": start_index,
                        "end": prop_index,
                        "parent": None,
                        "children": [],
                    }

                    # Set parent-child relationships
                    member_node["object"]["parent"] = member_node
                    member_node["property"]["parent"] = member_node
                    member_node["children"].append(member_node["object"])
                    member_node["children"].append(member_node["property"])

                    return {"node": member_node, "next_index": index}

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

            # Collect string content (simplified)
            while index < len(tokens):
                if tokens[index].token_type == TokenType.STRING_END:
                    index += 1
                    break

                if tokens[index].token_type not in [
                    TokenType.WHITESPACE,
                    TokenType.NEWLINE,
                ]:
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
        elif tokens[index].token_type == TokenType.KEYWORD:
            # Handle keywords that can appear in expressions
            if tokens[index].value == "function":
                return self._parse_function_declaration(tokens, index)
            elif tokens[index].value == "new":
                # New expression
                start_index = index
                index += 1

                # Skip whitespace
                while (
                    index < len(tokens)
                    and tokens[index].token_type == TokenType.WHITESPACE
                ):
                    index += 1

                # Parse constructor expression
                constructor_expr = self._parse_expression(tokens, index)
                if not constructor_expr:
                    return None

                new_expr = {
                    "type": "NewExpression",
                    "callee": constructor_expr["node"],
                    "arguments": [],  # Simplified, we're not parsing arguments
                    "start": start_index,
                    "end": constructor_expr["node"]["end"],
                    "parent": None,
                    "children": [constructor_expr["node"]],
                }

                constructor_expr["node"]["parent"] = new_expr

                return {"node": new_expr, "next_index": constructor_expr["next_index"]}

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

    def _parse_do_while_statement(
        self, tokens: List[Token], index: int
    ) -> Optional[Dict[str, Any]]:
        """Placeholder for parsing do-while statements."""
        return None

    def _parse_switch_statement(
        self, tokens: List[Token], index: int
    ) -> Optional[Dict[str, Any]]:
        """Placeholder for parsing switch statements."""
        return None

    def _parse_return_statement(
        self, tokens: List[Token], index: int
    ) -> Optional[Dict[str, Any]]:
        """Placeholder for parsing return statements."""
        return None

    def _parse_module_statement(
        self, tokens: List[Token], index: int
    ) -> Optional[Dict[str, Any]]:
        """Placeholder for parsing import/export statements."""
        return None

    def _parse_try_statement(
        self, tokens: List[Token], index: int
    ) -> Optional[Dict[str, Any]]:
        """Placeholder for parsing try-catch statements."""
        return None

    def _fix_parent_child_relationships(self, ast: Dict[str, Any]) -> None:
        """
        Fix parent-child relationships in the AST.

        Args:
            ast: The abstract syntax tree to fix
        """
        # This would walk the AST and ensure all nodes have correct parent and children references
        pass
