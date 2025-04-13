"""
JavaScript parser for the grammar parser system.

This module provides a parser specific to the JavaScript programming language,
building on the base token parser framework.
"""

from typing import List, Dict, Optional, Any

from .token import Token, TokenType
from .token_parser import TokenParser
from .parser_state import ParserState
from .symbol_table import SymbolTable
from .javascript_tokenizer import JavaScriptTokenizer
from .generic_brace_block_parser import BraceBlockParser


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

    def parse(self, code: str) -> Dict[str, Any]:
        """
        Parse JavaScript code and build an abstract syntax tree.

        Args:
            code: JavaScript source code

        Returns:
            Dictionary representing the abstract syntax tree
        """
        # Reset state for a new parse
        self.state = ParserState()
        self.symbol_table = SymbolTable()
        self.brace_stack = []
        self.bracket_stack = []
        self.paren_stack = []

        # Tokenize the code
        tokens = self.tokenize(code)

        # Process the tokens to build the AST
        return self.build_ast(tokens)

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
