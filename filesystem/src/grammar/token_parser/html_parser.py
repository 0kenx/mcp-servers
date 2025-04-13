"""
HTML parser for the grammar parser system.

This module provides a parser specific to HTML, handling elements, attributes,
comments, and document structure.
"""

from typing import List, Dict, Any
import re

from .token import Token, TokenType
from .token_parser import TokenParser
from .parser_state import ParserState
from .symbol_table import SymbolTable
from .html_tokenizer import HTMLTokenizer


class HTMLParser(TokenParser):
    """
    Parser for HTML code.

    This parser processes HTML syntax, handling elements, attributes,
    and document structure.
    """

    def __init__(self):
        """Initialize the HTML parser."""
        super().__init__()
        self.tokenizer = HTMLTokenizer()
        self.state = ParserState()
        self.symbol_table = SymbolTable()

        # Context types specific to HTML
        self.context_types = {
            "element": "element",
            "script": "script",
            "style": "style",
            "comment": "comment",
            "doctype": "doctype",
        }

    def parse(self, code: str) -> Dict[str, Any]:
        """
        Parse HTML code and build an abstract syntax tree.

        Args:
            code: HTML source code

        Returns:
            Dictionary representing the abstract syntax tree
        """
        # Reset state for a new parse
        self.state = ParserState()
        self.symbol_table = SymbolTable()

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
            "type": "Document",
            "children": [],
            "tokens": tokens,
            "start": 0,
            "end": len(tokens) - 1 if tokens else 0,
        }

        # Stack for tracking parent nodes
        stack = [ast]

        i = 0
        while i < len(tokens):
            token = tokens[i]

            if token.token_type == TokenType.DOCTYPE:
                doctype_node = {
                    "type": "Doctype",
                    "value": token.value,
                    "start": i,
                    "end": i,
                    "parent": stack[-1],
                    "children": [],
                }
                stack[-1]["children"].append(doctype_node)
                i += 1

            elif token.token_type == TokenType.OPEN_TAG:
                # Extract tag name
                tag_match = re.match(r"<\s*([a-zA-Z0-9_-]+)", token.value)
                tag_name = tag_match.group(1) if tag_match else "unknown"

                # Check if this is a special tag (script, style)
                is_special_tag = tag_name.lower() in ["script", "style"]

                # Create element node
                element_node = {
                    "type": "Element",
                    "tagName": tag_name,
                    "attributes": self._extract_attributes(token.value),
                    "start": i,
                    "end": None,  # Will be set when closing tag is found
                    "parent": stack[-1],
                    "children": [],
                }

                # Add to symbol table
                self.symbol_table.add_symbol(
                    name=tag_name,
                    symbol_type="element",
                    position=token.position,
                    line=token.line,
                    column=token.column,
                    metadata={"attributes": element_node["attributes"]},
                )

                stack[-1]["children"].append(element_node)
                stack.append(element_node)

                # If it's a script or style tag, we need special handling for content
                if is_special_tag:
                    # Find the corresponding closing tag
                    j = i + 1
                    content_start = j
                    while j < len(tokens):
                        if (
                            tokens[j].token_type == TokenType.CLOSE_TAG
                            and f"</{tag_name}" in tokens[j].value.lower()
                        ):
                            break
                        j += 1

                    # Extract content between tags
                    if j > content_start:
                        content = "".join(t.value for t in tokens[content_start:j])
                        content_node = {
                            "type": f"{tag_name.capitalize()}Content",
                            "value": content,
                            "start": content_start,
                            "end": j - 1,
                            "parent": element_node,
                            "children": [],
                        }
                        element_node["children"].append(content_node)

                    # Skip to the closing tag
                    i = j
                else:
                    i += 1

            elif token.token_type == TokenType.CLOSE_TAG:
                # Extract tag name
                tag_match = re.match(r"</\s*([a-zA-Z0-9_-]+)", token.value)
                tag_name = tag_match.group(1) if tag_match else "unknown"

                # Find matching opening tag in stack
                j = len(stack) - 1
                while j >= 0:
                    if (
                        stack[j].get("type") == "Element"
                        and stack[j].get("tagName", "").lower() == tag_name.lower()
                    ):
                        # Set end position
                        stack[j]["end"] = i

                        # Pop elements up to and including the matched element
                        while len(stack) > j:
                            stack.pop()

                        break
                    j -= 1

                i += 1

            elif token.token_type == TokenType.SELF_CLOSING_TAG:
                # Extract tag name
                tag_match = re.match(r"<\s*([a-zA-Z0-9_-]+)", token.value)
                tag_name = tag_match.group(1) if tag_match else "unknown"

                # Create element node
                element_node = {
                    "type": "Element",
                    "tagName": tag_name,
                    "attributes": self._extract_attributes(token.value),
                    "selfClosing": True,
                    "start": i,
                    "end": i,
                    "parent": stack[-1],
                    "children": [],
                }

                # Add to symbol table
                self.symbol_table.add_symbol(
                    name=tag_name,
                    symbol_type="element",
                    position=token.position,
                    line=token.line,
                    column=token.column,
                    metadata={"attributes": element_node["attributes"]},
                )

                stack[-1]["children"].append(element_node)
                i += 1

            elif token.token_type == TokenType.COMMENT:
                comment_node = {
                    "type": "Comment",
                    "value": token.value,
                    "start": i,
                    "end": i,
                    "parent": stack[-1],
                    "children": [],
                }
                stack[-1]["children"].append(comment_node)
                i += 1

            elif token.token_type == TokenType.TEXT:
                text_node = {
                    "type": "Text",
                    "value": token.value,
                    "start": i,
                    "end": i,
                    "parent": stack[-1],
                    "children": [],
                }
                stack[-1]["children"].append(text_node)
                i += 1

            else:
                # Skip whitespace and other tokens
                i += 1

        # Validate and repair the AST
        self.validate_and_repair_ast()

        return ast

    def _extract_attributes(self, tag_content: str) -> List[Dict[str, Any]]:
        """
        Extract attributes from a tag string.

        Args:
            tag_content: Content of the tag including '<' and '>'

        Returns:
            List of attribute dictionaries with name and value
        """
        # Remove the tag name and brackets
        tag_name_match = re.match(r"<\s*([a-zA-Z0-9_-]+)", tag_content)
        if not tag_name_match:
            return []

        tag_name = tag_name_match.group(1)
        content = tag_content[tag_name_match.end() :]

        # Remove closing part of tag
        content = re.sub(r"\s*\/?>$", "", content)

        # Match attributes
        # Format: name="value", name='value', or name
        attribute_pattern = (
            r'([a-zA-Z0-9_-]+)(?:\s*=\s*(?:"([^"]*)"|\'([^\']*)\'|([^\s>]*)?))?'
        )

        attributes = []
        for match in re.finditer(attribute_pattern, content):
            name = match.group(1)
            # Find the first non-None value in groups 2, 3, or 4
            value = next(
                (
                    g
                    for g in (match.group(2), match.group(3), match.group(4))
                    if g is not None
                ),
                "",
            )

            attributes.append({"name": name, "value": value})

        return attributes
