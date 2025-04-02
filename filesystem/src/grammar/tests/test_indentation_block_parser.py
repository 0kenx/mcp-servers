import unittest
from generic_indentation_block import IndentationBlockParser
from base import ElementType
from test_utils import ParserTestHelper

class TestIndentationBlockParser(unittest.TestCase):
    """Test cases for the generic IndentationBlockParser."""

    def setUp(self):
        """Set up test cases."""
        self.helper = ParserTestHelper(IndentationBlockParser)
        # Assuming default INDENT_WIDTH = 4 for tests

    def test_parse_python_function(self):
        """Test parsing a Python-style function."""
        code = """
# A function definition
def calculate(x):
    # Docstring
    \"\"\"Calculates square.\"\"\"
    y = x * x
    return y # Return the result

def another_func():
    pass # Simple one
"""
        elements = self.helper.parse_code(code)
        self.assertEqual(len(elements), 2)

        calc_func = self.helper.find_element(elements, ElementType.FUNCTION, "calculate")
        self.assertIsNotNone(calc_func)
        self.assertEqual(calc_func.start_line, 3)
        self.assertEqual(calc_func.end_line, 8) # Includes return line and following blank line
        self.assertEqual(calc_func.metadata.get("docstring"), '"""Calculates square."""')
        self.assertIsNone(calc_func.parent)

        another_func = self.helper.find_element(elements, ElementType.FUNCTION, "another_func")
        self.assertIsNotNone(another_func)
        self.assertEqual(another_func.start_line, 9)
        self.assertEqual(another_func.end_line, 10)

    def test_parse_python_class(self):
        """Test parsing a Python-style class with methods."""
        code = """
class MyClass:
    # Doc
    '''A simple class'''

    def __init__(self, value):
        self.value = value

    def get_value(self):
        # Returns the value
        return self.value
"""
        elements = self.helper.parse_code(code)
        # Class, __init__ method, get_value method
        self.assertEqual(len(elements), 3)

        class_el = self.helper.find_element(elements, ElementType.CLASS, "MyClass")
        self.assertIsNotNone(class_el)
        self.assertEqual(class_el.start_line, 2)
        self.assertEqual(class_el.end_line, 11)
        self.assertEqual(class_el.metadata.get("docstring"), "'''A simple class'''")
        self.assertEqual(len(class_el.children), 2)

        init_method = self.helper.find_element(elements, ElementType.METHOD, "__init__")
        self.assertIsNotNone(init_method)
        self.assertEqual(init_method.parent, class_el)
        self.assertEqual(init_method.start_line, 6)
        self.assertEqual(init_method.end_line, 8)

        get_method = self.helper.find_element(elements, ElementType.METHOD, "get_value")
        self.assertIsNotNone(get_method)
        self.assertEqual(get_method.parent, class_el)
        self.assertEqual(get_method.start_line, 9)
        self.assertEqual(get_method.end_line, 11)

    def test_parse_nested_python(self):
        """Test parsing nested functions."""
        code = """
def outer(a):
    b = a + 1
    def inner(c):
        d = c * b
        return d
    return inner(a)
"""
        elements = self.helper.parse_code(code)
        self.assertEqual(len(elements), 2) # outer, inner

        outer_func = self.helper.find_element(elements, ElementType.FUNCTION, "outer")
        self.assertIsNotNone(outer_func)
        self.assertIsNone(outer_func.parent)
        self.assertEqual(len(outer_func.children), 1)

        inner_func = self.helper.find_element(elements, ElementType.FUNCTION, "inner")
        self.assertIsNotNone(inner_func)
        self.assertEqual(inner_func.parent, outer_func)
        self.assertEqual(inner_func.start_line, 4)
        self.assertEqual(inner_func.end_line, 6)

    def test_syntax_validity_indentation(self):
        """Test the indentation consistency check."""
        valid_code = """
def func1():
    a = 1
    if a > 0:
        b = 2
def func2():
    pass
"""
        invalid_code = """
def func1():
    a = 1
  b = 2 # Bad dedent
"""
        mixed_indent_code = """
def func1():
	a = 1 # Tab
    b = 2 # Spaces - parser might handle if _count_indentation is smart, but validity check might fail
"""
        # Basic check should pass valid code
        self.assertTrue(self.helper.parser.check_syntax_validity(valid_code))
        # Basic check should fail inconsistent dedent
        self.assertFalse(self.helper.parser.check_syntax_validity(invalid_code))
        # Mixed tabs/spaces might pass or fail depending on how _count_indentation works
        # The default _count_indentation only counts spaces, so tabs are indent 0.
        # This will likely cause the validity check to fail if tabs are used for indentation.
        self.assertFalse(self.helper.parser.check_syntax_validity(mixed_indent_code), "Mixed tabs/spaces should fail basic check")


if __name__ == '__main__':
    unittest.main()
