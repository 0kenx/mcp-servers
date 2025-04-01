"""
Tests for the Python language parser.
"""

import unittest
from src.grammar.python import PythonParser
from src.grammar.base import ElementType


class TestPythonParser(unittest.TestCase):
    """Test cases for the Python parser."""
    
    def setUp(self):
        """Set up test cases."""
        self.parser = PythonParser()
    
    def test_parse_function(self):
        """Test parsing a simple Python function."""
        code = '''
def hello_world(name: str = "World") -> str:
    """Say hello to someone."""
    return f"Hello, {name}!"
'''
        elements = self.parser.parse(code)
        
        # Should find one function
        self.assertEqual(len(elements), 1)
        
        # Check the function properties
        func = elements[0]
        self.assertEqual(func.element_type, ElementType.FUNCTION)
        self.assertEqual(func.name, "hello_world")
        self.assertEqual(func.start_line, 2)
        self.assertEqual(func.end_line, 4)
        self.assertIn("Say hello to someone", func.metadata.get("docstring", ""))
    
    def test_parse_class(self):
        """Test parsing a Python class with methods."""
        code = '''
class Person:
    """A simple person class."""
    
    def __init__(self, name, age):
        """Initialize the person."""
        self.name = name
        self.age = age
    
    def greet(self):
        """Return a greeting."""
        return f"Hello, my name is {self.name}!"
'''
        elements = self.parser.parse(code)
        
        # Should find one class and two methods
        self.assertEqual(len(elements), 3)
        
        # Check class
        class_element = next(e for e in elements if e.element_type == ElementType.CLASS)
        self.assertEqual(class_element.name, "Person")
        self.assertIn("simple person class", class_element.metadata.get("docstring", ""))
        
        # Check methods
        init_method = next(e for e in elements if e.name == "__init__")
        self.assertEqual(init_method.element_type, ElementType.METHOD)
        self.assertEqual(init_method.parent, class_element)
        
        greet_method = next(e for e in elements if e.name == "greet")
        self.assertEqual(greet_method.element_type, ElementType.METHOD)
        self.assertEqual(greet_method.parent, class_element)
    
    def test_parse_decorated_function(self):
        """Test parsing a function with decorators."""
        code = '''
@app.route("/")
@login_required
def index():
    """Home page."""
    return "Welcome!"
'''
        elements = self.parser.parse(code)
        
        # Should find one function
        self.assertEqual(len(elements), 1)
        
        # Check function and decorators
        func = elements[0]
        self.assertEqual(func.name, "index")
        decorators = func.metadata.get("decorators", [])
        self.assertEqual(len(decorators), 2)
        self.assertIn("app.route", decorators[0])
        self.assertIn("login_required", decorators[1])
    
    def test_parse_nested_elements(self):
        """Test parsing nested functions and classes."""
        code = '''
def outer_function():
    """Outer function."""
    
    def inner_function():
        """Inner function."""
        return "Inside!"
    
    class InnerClass:
        """Inner class."""
        def method(self):
            return "Method!"
    
    return inner_function() + InnerClass().method()
'''
        elements = self.parser.parse(code)
        
        # Should find outer function, inner function, inner class, and inner method
        self.assertEqual(len(elements), 4)
        
        # Check outer function
        outer_func = next(e for e in elements if e.name == "outer_function")
        self.assertEqual(outer_func.element_type, ElementType.FUNCTION)
        self.assertIsNone(outer_func.parent)
        
        # Check inner function
        inner_func = next(e for e in elements if e.name == "inner_function")
        self.assertEqual(inner_func.element_type, ElementType.FUNCTION)
        self.assertEqual(inner_func.parent, outer_func)
        
        # Check inner class
        inner_class = next(e for e in elements if e.name == "InnerClass")
        self.assertEqual(inner_class.element_type, ElementType.CLASS)
        self.assertEqual(inner_class.parent, outer_func)
        
        # Check inner method
        inner_method = next(e for e in elements if e.name == "method")
        self.assertEqual(inner_method.element_type, ElementType.METHOD)
        self.assertEqual(inner_method.parent, inner_class)
    
    def test_parse_module_elements(self):
        """Test parsing module-level elements like imports and variables."""
        code = '''
import os
import sys
from typing import List, Dict, Optional

# Constants
MAX_RETRIES = 3
DEFAULT_TIMEOUT = 30.0

# A class
class Config:
    """Configuration class."""
    def __init__(self):
        self.debug = False
'''
        elements = self.parser.parse(code)
        
        # Should find imports, variables, class, and method
        self.assertTrue(any(e.element_type == ElementType.IMPORT and "os" in e.name for e in elements))
        self.assertTrue(any(e.element_type == ElementType.IMPORT and "sys" in e.name for e in elements))
        self.assertTrue(any(e.element_type == ElementType.IMPORT and "typing" in e.name for e in elements))
        
        self.assertTrue(any(e.element_type == ElementType.VARIABLE and e.name == "MAX_RETRIES" for e in elements))
        self.assertTrue(any(e.element_type == ElementType.VARIABLE and e.name == "DEFAULT_TIMEOUT" for e in elements))
        
        self.assertTrue(any(e.element_type == ElementType.CLASS and e.name == "Config" for e in elements))
    
    def test_find_function_by_name(self):
        """Test finding a function by name."""
        code = '''
def func1():
    pass

def func2():
    pass

def find_me():
    """This is the function to find."""
    return "Found!"

def func3():
    pass
'''
        elements = self.parser.parse(code)
        
        # Use the find_function method
        target = self.parser.find_function(code, "find_me")
        
        # Should find the function
        self.assertIsNotNone(target)
        self.assertEqual(target.name, "find_me")
        self.assertEqual(target.element_type, ElementType.FUNCTION)
        self.assertIn("function to find", target.metadata.get("docstring", ""))
    
    def test_get_all_globals(self):
        """Test getting all global elements."""
        code = '''
import os

def global_func():
    pass

class GlobalClass:
    def method(self):
        pass

CONSTANT = 42
'''
        globals_dict = self.parser.get_all_globals(code)
        
        # Should find global function, class, and constant
        self.assertIn("global_func", globals_dict)
        self.assertIn("GlobalClass", globals_dict)
        self.assertIn("CONSTANT", globals_dict)
        self.assertIn("os", globals_dict)  # Import
        
        # Method should not be in globals
        self.assertNotIn("method", globals_dict)
    
    def test_check_syntax_validity(self):
        """Test syntax validity checker."""
        # Valid Python
        valid_code = "def valid():\n    return 42\n"
        self.assertTrue(self.parser.check_syntax_validity(valid_code))
        
        # Invalid Python
        invalid_code = "def invalid():\n    return 42\n}"
        self.assertFalse(self.parser.check_syntax_validity(invalid_code))


if __name__ == '__main__':
    unittest.main()
