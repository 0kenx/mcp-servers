"""
C parser for the grammar parser system.

This module provides a parser specific to the C programming language,
building on the base token parser framework.
"""

from typing import List, Dict, Optional, Any, Tuple

from .token import Token, TokenType
from .token_parser import TokenParser
from .parser_state import ParserState
from .symbol_table import SymbolTable
from .context_tracker import ContextTracker
from .c_tokenizer import CTokenizer
from .generic_brace_block_parser import BraceBlockParser
from .base import CodeElement, ElementType


class CParser(TokenParser):
    """
    Parser for C code.

    This parser processes C-specific syntax, handling constructs like structs,
    typedefs, functions, preprocessor directives, and more.
    """

    def __init__(self):
        """Initialize the C parser."""
        super().__init__()
        self.tokenizer = CTokenizer()
        self.state = ParserState()
        self.symbol_table = SymbolTable()

        # Context types specific to C
        self.context_types = {
            "function": "function",
            "struct": "struct",
            "union": "union",
            "enum": "enum",
            "typedef": "typedef",
            "if": "if",
            "else": "else",
            "for": "for",
            "while": "while",
            "do_while": "do_while",
            "switch": "switch",
            "preprocessor": "preprocessor",
        }

        # Track blocks
        self.brace_stack = []
        self.paren_stack = []

    def parse(self, code: str) -> List[CodeElement]:
        """
        Parse C code and return a list of code elements.

        Args:
            code: C source code

        Returns:
            List of code elements
        """
        # Reset state for a new parse
        self.elements = []
        self.state = ParserState()
        self.symbol_table = SymbolTable()
        self.context_tracker = ContextTracker()
        self.brace_stack = []
        self.paren_stack = []

        # Tokenize the code
        tokens = self.tokenize(code)

        # Process the tokens to build elements directly
        self._build_elements_from_tokens(tokens)
        
        # Validate and repair AST
        self.validate_and_repair_ast()
        
        return self.elements

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

            # Handle preprocessor directives
            if tokens[i].token_type == TokenType.PREPROCESSOR:
                directive = self._parse_preprocessor_directive(tokens, i)
                if directive:
                    ast["body"].append(directive["node"])
                    ast["children"].append(directive["node"])
                    i = directive["next_index"]
                    continue

            # Parse statements based on token type
            if tokens[i].token_type == TokenType.KEYWORD:
                stmt = self._parse_keyword_statement(tokens, i)
                if stmt:
                    ast["body"].append(stmt["node"])
                    ast["children"].append(stmt["node"])
                    i = stmt["next_index"]
                else:
                    i += 1
            elif tokens[i].token_type == TokenType.IDENTIFIER:
                stmt = self._parse_declaration_or_definition(tokens, i)
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

    def _parse_preprocessor_directive(
        self, tokens: List[Token], index: int
    ) -> Optional[Dict[str, Any]]:
        """
        Parse a preprocessor directive.

        Args:
            tokens: List of tokens
            index: Current index in the token list

        Returns:
            Dictionary with the parsed node and next index, or None if parsing failed
        """
        if index >= len(tokens) or tokens[index].token_type != TokenType.PREPROCESSOR:
            return None

        directive_text = tokens[index].value.lstrip()
        directive_type = "unknown"

        # Determine the directive type
        if directive_text.startswith("#include"):
            directive_type = "include"
        elif directive_text.startswith("#define"):
            directive_type = "define"
        elif directive_text.startswith("#ifdef") or directive_text.startswith(
            "#ifndef"
        ):
            directive_type = "conditional"
        elif directive_text.startswith("#endif"):
            directive_type = "endif"
        elif directive_text.startswith("#pragma"):
            directive_type = "pragma"

        # Create directive node
        directive_node = {
            "type": "PreprocessorDirective",
            "directive_type": directive_type,
            "text": directive_text,
            "start": index,
            "end": index,
            "parent": None,
            "children": [],
        }

        return {"node": directive_node, "next_index": index + 1}

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

        if keyword == "struct" or keyword == "union":
            return self._parse_struct_or_union(tokens, index)
        elif keyword == "enum":
            return self._parse_enum(tokens, index)
        elif keyword == "typedef":
            return self._parse_typedef(tokens, index)
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

        # Default simple statement
        return self._parse_expression_statement(tokens, index)

    def _parse_struct_or_union(
        self, tokens: List[Token], index: int
    ) -> Optional[Dict[str, Any]]:
        """
        Parse a struct or union declaration.

        Args:
            tokens: List of tokens
            index: Current index in the token list

        Returns:
            Dictionary with the parsed node and next index, or None if parsing failed
        """
        start_index = index
        kind = tokens[index].value  # "struct" or "union"
        index += 1

        # Skip whitespace
        while index < len(tokens) and tokens[index].token_type == TokenType.WHITESPACE:
            index += 1

        # Get struct/union name (optional)
        name = None
        name_index = None
        if index < len(tokens) and tokens[index].token_type == TokenType.IDENTIFIER:
            name = tokens[index].value
            name_index = index
            index += 1

            # Skip whitespace
            while (
                index < len(tokens) and tokens[index].token_type == TokenType.WHITESPACE
            ):
                index += 1

        # Check for body (open brace)
        has_body = False
        body_tokens = []
        if index < len(tokens) and tokens[index].token_type == TokenType.OPEN_BRACE:
            has_body = True

            # Context metadata
            context_metadata = {"name": name} if name else {"name": f"anonymous_{kind}"}

            # Add struct/union to symbol table if it has a name
            if name and name_index is not None:
                self.symbol_table.add_symbol(
                    name=name,
                    symbol_type=kind,
                    position=tokens[name_index].position,
                    line=tokens[name_index].line,
                    column=tokens[name_index].column,
                    metadata={},
                )

            # Parse struct/union body
            body_indices, next_index = BraceBlockParser.parse_block(
                tokens, index, self.state, self.context_types[kind], context_metadata
            )

            body_tokens = body_indices
            index = next_index

        # Skip semicolon if present
        if index < len(tokens) and tokens[index].token_type == TokenType.SEMICOLON:
            index += 1

        # Create struct/union node
        struct_node = {
            "type": "StructOrUnionDeclaration",
            "kind": kind,
            "name": name,
            "has_body": has_body,
            "body": body_tokens,
            "start": start_index,
            "end": index - 1,
            "parent": None,
            "children": [],
        }

        return {"node": struct_node, "next_index": index}

    def _parse_enum(self, tokens: List[Token], index: int) -> Optional[Dict[str, Any]]:
        """
        Parse an enum declaration.

        Args:
            tokens: List of tokens
            index: Current index in the token list

        Returns:
            Dictionary with the parsed node and next index, or None if parsing failed
        """
        start_index = index
        index += 1  # Skip 'enum' keyword

        # Skip whitespace
        while index < len(tokens) and tokens[index].token_type == TokenType.WHITESPACE:
            index += 1

        # Get enum name (optional)
        name = None
        name_index = None
        if index < len(tokens) and tokens[index].token_type == TokenType.IDENTIFIER:
            name = tokens[index].value
            name_index = index
            index += 1

            # Skip whitespace
            while (
                index < len(tokens) and tokens[index].token_type == TokenType.WHITESPACE
            ):
                index += 1

        # Check for body (open brace)
        has_body = False
        body_tokens = []
        if index < len(tokens) and tokens[index].token_type == TokenType.OPEN_BRACE:
            has_body = True

            # Context metadata
            context_metadata = {"name": name} if name else {"name": "anonymous_enum"}

            # Add enum to symbol table if it has a name
            if name and name_index is not None:
                self.symbol_table.add_symbol(
                    name=name,
                    symbol_type="enum",
                    position=tokens[name_index].position,
                    line=tokens[name_index].line,
                    column=tokens[name_index].column,
                    metadata={},
                )

            # Parse enum body
            body_indices, next_index = BraceBlockParser.parse_block(
                tokens, index, self.state, self.context_types["enum"], context_metadata
            )

            body_tokens = body_indices
            index = next_index

        # Skip semicolon if present
        if index < len(tokens) and tokens[index].token_type == TokenType.SEMICOLON:
            index += 1

        # Create enum node
        enum_node = {
            "type": "EnumDeclaration",
            "name": name,
            "has_body": has_body,
            "body": body_tokens,
            "start": start_index,
            "end": index - 1,
            "parent": None,
            "children": [],
        }

        return {"node": enum_node, "next_index": index}

    def _parse_typedef(
        self, tokens: List[Token], index: int
    ) -> Optional[Dict[str, Any]]:
        """
        Parse a typedef declaration.

        Args:
            tokens: List of tokens
            index: Current index in the token list

        Returns:
            Dictionary with the parsed node and next index, or None if parsing failed
        """
        start_index = index
        index += 1  # Skip 'typedef' keyword

        # Parse to the end of the statement (simplified)
        typedef_tokens = []
        while index < len(tokens) and tokens[index].token_type != TokenType.SEMICOLON:
            typedef_tokens.append(index)
            index += 1

        # Skip semicolon
        if index < len(tokens) and tokens[index].token_type == TokenType.SEMICOLON:
            index += 1

        # Create typedef node
        typedef_node = {
            "type": "TypedefDeclaration",
            "tokens": typedef_tokens,
            "start": start_index,
            "end": index - 1,
            "parent": None,
            "children": [],
        }

        return {"node": typedef_node, "next_index": index}

    def _parse_declaration_or_definition(
        self, tokens: List[Token], index: int
    ) -> Optional[Dict[str, Any]]:
        """
        Parse a declaration or definition (variable or function).

        Args:
            tokens: List of tokens
            index: Current index in the token list

        Returns:
            Dictionary with the parsed node and next index, or None if parsing failed
        """
        # This is a simplified implementation
        start_index = index

        # Parse to the end of the statement or function body
        declaration_tokens = []
        while index < len(tokens):
            if tokens[index].token_type == TokenType.SEMICOLON:
                # End of declaration
                declaration_tokens.append(index)
                index += 1
                break
            elif tokens[index].token_type == TokenType.OPEN_BRACE:
                # Start of function body
                function_body, next_index = BraceBlockParser.parse_block(
                    tokens,
                    index,
                    self.state,
                    self.context_types["function"],
                    {"name": "function"},  # Simplified
                )
                declaration_tokens.extend(function_body)
                index = next_index
                break
            else:
                declaration_tokens.append(index)
                index += 1

        # Create declaration node
        declaration_node = {
            "type": "Declaration",
            "tokens": declaration_tokens,
            "start": start_index,
            "end": index - 1,
            "parent": None,
            "children": [],
        }

        return {"node": declaration_node, "next_index": index}

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
        # Simplified implementation
        start_index = index

        # Parse to the end of the statement
        statement_tokens = []
        while index < len(tokens) and tokens[index].token_type != TokenType.SEMICOLON:
            statement_tokens.append(index)
            index += 1

        # Skip semicolon
        if index < len(tokens) and tokens[index].token_type == TokenType.SEMICOLON:
            index += 1

        # Create statement node
        statement_node = {
            "type": "ExpressionStatement",
            "tokens": statement_tokens,
            "start": start_index,
            "end": index - 1,
            "parent": None,
            "children": [],
        }

        return {"node": statement_node, "next_index": index}

    def _parse_if_statement(
        self, tokens: List[Token], index: int
    ) -> Optional[Dict[str, Any]]:
        """Placeholder for parsing if statements."""
        # This would be implemented similarly to the struct and enum parsers
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

    def _fix_parent_child_relationships(self, ast: Dict[str, Any]) -> None:
        """
        Fix parent-child relationships in the AST.

        Args:
            ast: The abstract syntax tree to fix
        """
        # This would walk the AST and ensure all nodes have correct parent and children references
        pass
        
    def _build_elements_from_tokens(self, tokens: List[Token]) -> None:
        """
        Build CodeElement objects directly from tokens.
        
        This method processes tokens and builds a list of CodeElement objects
        representing functions, structs, classes, etc. found in the code.
        
        Args:
            tokens: List of tokens from the tokenizer
        """
        i = 0
        line_map = {}
        current_line = 1
        
        # First pass: build a mapping of token indices to line numbers
        for i, token in enumerate(tokens):
            if token.token_type == TokenType.NEWLINE:
                current_line += 1
            line_map[i] = current_line
        
        i = 0
        while i < len(tokens):
            # Skip whitespace and newlines
            if tokens[i].token_type in [TokenType.WHITESPACE, TokenType.NEWLINE]:
                i += 1
                continue
                
            # Handle preprocessor directives
            if tokens[i].token_type == TokenType.PREPROCESSOR:
                directive = self._parse_preprocessor_directive(tokens, i)
                if directive:
                    i = directive["next_index"]
                    continue
            
            # Check for function or struct definitions
            if tokens[i].token_type == TokenType.KEYWORD:
                stmt = self._parse_keyword_statement(tokens, i)
                if stmt:
                    node = stmt["node"]
                    # Create CodeElement from AST node
                    element = self._convert_node_to_element(node, line_map)
                    if element:
                        self.elements.append(element)
                    i = stmt["next_index"]
                    continue
            
            # Check for declarations or definitions starting with identifiers
            if tokens[i].token_type == TokenType.IDENTIFIER:
                stmt = self._parse_declaration_or_definition(tokens, i)
                if stmt:
                    node = stmt["node"]
                    # Create CodeElement from AST node
                    element = self._convert_node_to_element(node, line_map)
                    if element:
                        self.elements.append(element)
                    i = stmt["next_index"]
                    continue
            
            # Move to next token if no pattern matched
            i += 1
    
    def _convert_node_to_element(self, node: Dict[str, Any], line_map: Dict[int, int]) -> Optional[CodeElement]:
        """
        Convert an AST node to a CodeElement.
        
        Args:
            node: The AST node to convert
            line_map: Mapping from token indices to line numbers
            
        Returns:
            A CodeElement or None if the node cannot be converted
        """
        element_type = None
        name = ""
        start_line = 1
        end_line = 1
        parameters = []
        children = []
        
        # Get name and type based on node type
        if "type" in node:
            if node["type"] == "FunctionDefinition":
                element_type = ElementType.FUNCTION
                if "name" in node:
                    name = node["name"]
                # Extract parameters if available
                if "parameters" in node:
                    parameters = node["parameters"]
            elif node["type"] == "StructOrUnionDeclaration":
                if node["kind"] == "struct":
                    element_type = ElementType.STRUCT
                else:
                    element_type = ElementType.UNION
                if "name" in node:
                    name = node["name"]
            elif node["type"] == "ClassDeclaration":
                element_type = ElementType.CLASS
                if "name" in node:
                    name = node["name"]
        
        # Get start and end lines
        if "start" in node and node["start"] in line_map:
            start_line = line_map[node["start"]]
        if "end" in node and node["end"] in line_map:
            end_line = line_map[node["end"]]
            
        # Skip if we couldn't determine the element type
        if not element_type:
            return None
            
        # Create the element
        element = CodeElement(
            name=name,
            element_type=element_type,
            start_line=start_line,
            end_line=end_line
        )
        
        # Set parameters if available
        if parameters:
            element.parameters = parameters
            
        # Add children
        if "children" in node:
            for child_node in node["children"]:
                child_element = self._convert_node_to_element(child_node, line_map)
                if child_element:
                    child_element.parent = element
                    element.children.append(child_element)
                    
        return element
