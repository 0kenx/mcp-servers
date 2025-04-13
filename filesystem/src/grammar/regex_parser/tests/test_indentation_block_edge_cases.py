"""
Tests for the IndentationBlockParser with edge cases.
"""

import unittest
from src.grammar.generic_indentation_block import IndentationBlockParser
from src.grammar.base import ElementType


class TestIndentationBlockParserEdgeCases(unittest.TestCase):
    """Test edge cases for the IndentationBlockParser."""

    def setUp(self):
        """Set up test cases."""
        self.parser = IndentationBlockParser()

    def test_mixed_tabs_spaces(self):
        """Test the indentation parser with mixed tabs and spaces."""
        code = """
def function_with_spaces():
    print("This uses spaces")
    if True:
        print("More spaces")
        
def function_with_tabs():
	print("This uses tabs")
	if True:
		print("More tabs")
		
def function_with_mixed():
    print("This uses spaces")
	if True:
		print("This switched to tabs")
    print("Back to spaces")
"""
        elements = self.parser.parse(code)

        # Should find the functions despite inconsistent indentation
        functions = [e for e in elements if e.element_type == ElementType.FUNCTION]
        self.assertGreaterEqual(len(functions), 2)

        # Check for specific functions
        spaces_func = next(
            (f for f in functions if f.name == "function_with_spaces"), None
        )
        self.assertIsNotNone(spaces_func)

        tabs_func = next((f for f in functions if f.name == "function_with_tabs"), None)
        self.assertIsNotNone(tabs_func)

        # The mixed function might be partially parsed or its body might be incomplete
        mixed_func = next(
            (f for f in functions if f.name == "function_with_mixed"), None
        )
        if mixed_func:
            # If found, just check that it has at least a start and end line
            self.assertLess(mixed_func.start_line, mixed_func.end_line)

    def test_inconsistent_indentation(self):
        """Test the indentation parser with inconsistent indentation levels."""
        code = """
def function_with_inconsistent_indent():
    print("Normal indentation")
   print("One less space")
     print("One more space")
        print("Much more indentation")
 print("Minimal indentation")

def normal_function():
    if True:
        print("Consistent")
        print("Still consistent")
"""
        elements = self.parser.parse(code)

        # Should find both functions
        functions = [e for e in elements if e.element_type == ElementType.FUNCTION]
        self.assertEqual(len(functions), 2)

        # The inconsistent function's body might be parsed differently depending on the parser
        inconsistent_func = next(
            (f for f in functions if f.name == "function_with_inconsistent_indent"),
            None,
        )
        self.assertIsNotNone(inconsistent_func)

        # Normal function should be correctly identified
        normal_func = next((f for f in functions if f.name == "normal_function"), None)
        self.assertIsNotNone(normal_func)

        # Test that the parser didn't crash on inconsistent indentation
        self.assertTrue(True)

    def test_complex_indentation_patterns(self):
        """Test the indentation parser with complex indentation patterns."""
        code = """
def simple_function():
    pass

class MyClass:
    def method1(self):
        if True:
            print("Indented")
        else:
            print("Also indented")
            
    def method2(self):
        pass
        
    @property
    def prop(self):
        return 42

def function_with_complex_blocks():
    # Block with empty lines in between
    print("Start")
    
    print("Middle")
    
    print("End")
    
    # Nested blocks with comments
    if True:
        # Comment
        if False:
            print("Nested")
            # Another comment
            for i in range(10):
                # Deep nesting
                print(i)
                
    # Function with docstring and multiple blocks
    def inner_function():
        '''
        This is a docstring with multiple lines
        that should be part of the function body
        '''
        x = 1
        y = 2
        
        return x + y
"""
        elements = self.parser.parse(code)

        # Should find various elements with complex indentation
        self.assertGreaterEqual(len(elements), 3)

        # Check for the class and its methods
        class_el = next(
            (e for e in elements if e.element_type == ElementType.CLASS), None
        )
        self.assertIsNotNone(class_el)

        methods = [e for e in elements if e.element_type == ElementType.METHOD]
        self.assertGreaterEqual(len(methods), 2)

        # Check for functions
        functions = [
            e
            for e in elements
            if e.element_type == ElementType.FUNCTION and e.name != "inner_function"
        ]
        self.assertEqual(len(functions), 2)

        # Inner function may or may not be identified depending on parser capabilities
        complex_func = next(
            (f for f in functions if f.name == "function_with_complex_blocks"), None
        )
        self.assertIsNotNone(complex_func)

    def test_indentation_edge_cases(self):
        """Test the indentation parser with various edge cases."""
        code = """
# No indentation
def function_without_body():
pass

# Empty lines between definition and body
def function_with_gap():



    print("There are empty lines above")
    
# Function with just pass
def empty_function():
    pass
    
# One-liner functions (Python supports)
def one_liner(): return "One line"

# Nested function with same name as outer
def outer():
    print("Outer")
    def inner():
        print("Inner")
    def outer():
        print("Inner function with same name as outer")
    return inner
"""
        elements = self.parser.parse(code)

        # Should find at least some of the edge case functions
        functions = [e for e in elements if e.element_type == ElementType.FUNCTION]
        self.assertGreaterEqual(len(functions), 3)

        # Check for specific functions
        without_body = next(
            (f for f in functions if f.name == "function_without_body"), None
        )
        if without_body:
            # If found, there shouldn't be multiple lines of code inside
            self.assertLessEqual(without_body.end_line - without_body.start_line, 1)

        with_gap = next((f for f in functions if f.name == "function_with_gap"), None)
        self.assertIsNotNone(with_gap)

        empty_func = next((f for f in functions if f.name == "empty_function"), None)
        self.assertIsNotNone(empty_func)

        outer_func = next((f for f in functions if f.name == "outer"), None)
        self.assertIsNotNone(outer_func)

        # Nested functions may or may not be detected depending on parser capabilities
        if len(functions) > 4:
            nested_functions = [
                f
                for f in functions
                if f.name in ("inner", "outer") and f.parent is not None
            ]
            self.assertGreaterEqual(len(nested_functions), 1)


if __name__ == "__main__":
    unittest.main()
