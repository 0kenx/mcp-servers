"""
Tests for the JavaScript language parser.
"""

import unittest
from src.grammar.javascript import JavaScriptParser
from src.grammar.base import ElementType


class TestJavaScriptParser(unittest.TestCase):
    """Test cases for the JavaScript parser."""
    
    def setUp(self):
        """Set up test cases."""
        self.parser = JavaScriptParser()
    
    def test_parse_function_declaration(self):
        """Test parsing a function declaration."""
        code = '''
/**
 * Says hello to someone.
 * @param {string} name - The name to greet
 * @returns {string} The greeting
 */
function helloWorld(name = "World") {
    return `Hello, ${name}!`;
}
'''
        elements = self.parser.parse(code)
        
        # Should find one function
        self.assertEqual(len(elements), 1)
        
        # Check function properties
        func = elements[0]
        self.assertEqual(func.element_type, ElementType.FUNCTION)
        self.assertEqual(func.name, "helloWorld")
        self.assertEqual(func.start_line, 6)
        self.assertEqual(func.end_line, 8)
        self.assertIn("Says hello to someone", func.metadata.get("docstring", ""))
    
    def test_parse_arrow_function(self):
        """Test parsing an arrow function assigned to a variable."""
        code = '''
// Greeting function
const greet = (name = "World") => {
    return `Hello, ${name}!`;
};

// One-liner
const square = x => x * x;
'''
        elements = self.parser.parse(code)
        
        # Should find two functions
        self.assertEqual(len(elements), 2)
        
        # Check first function
        greet_func = elements[0]
        self.assertEqual(greet_func.element_type, ElementType.FUNCTION)
        self.assertEqual(greet_func.name, "greet")
        self.assertTrue(greet_func.metadata.get("is_arrow", False))
        
        # Check second function
        square_func = elements[1]
        self.assertEqual(square_func.element_type, ElementType.FUNCTION)
        self.assertEqual(square_func.name, "square")
        self.assertTrue(square_func.metadata.get("is_arrow", False))
    
    def test_parse_class(self):
        """Test parsing a class with methods."""
        code = '''
/**
 * Represents a person.
 */
class Person {
    /**
     * Create a person.
     */
    constructor(name, age) {
        this.name = name;
        this.age = age;
    }
    
    /**
     * Get a greeting from the person.
     */
    greet() {
        return `Hello, my name is ${this.name}!`;
    }
    
    // Static method
    static create(name, age) {
        return new Person(name, age);
    }
}
'''
        elements = self.parser.parse(code)
        
        # Should find one class and three methods
        class_elements = [e for e in elements if e.element_type == ElementType.CLASS]
        method_elements = [e for e in elements if e.element_type == ElementType.METHOD]
        
        self.assertEqual(len(class_elements), 1)
        self.assertEqual(len(method_elements), 3)
        
        # Check class
        class_element = class_elements[0]
        self.assertEqual(class_element.name, "Person")
        self.assertIn("Represents a person", class_element.metadata.get("docstring", ""))
        
        # Check methods
        constructor = next(e for e in method_elements if e.name == "constructor")
        self.assertEqual(constructor.parent, class_element)
        
        greet_method = next(e for e in method_elements if e.name == "greet")
        self.assertEqual(greet_method.parent, class_element)
        
        static_method = next(e for e in method_elements if e.name == "create")
        self.assertEqual(static_method.parent, class_element)
        self.assertTrue(static_method.metadata.get("is_static", False))
    
    def test_parse_async_functions(self):
        """Test parsing async functions."""
        code = '''
// Async function declaration
async function fetchData() {
    const response = await fetch('/api/data');
    return response.json();
}

// Async arrow function
const getData = async () => {
    const data = await fetchData();
    return data.filter(item => item.active);
};
'''
        elements = self.parser.parse(code)
        
        # Should find two functions
        self.assertEqual(len(elements), 2)
        
        # Check async properties
        fetch_func = next(e for e in elements if e.name == "fetchData")
        self.assertTrue(fetch_func.metadata.get("is_async", False))
        
        get_data_func = next(e for e in elements if e.name == "getData")
        self.assertTrue(get_data_func.metadata.get("is_async", False))
    
    def test_parse_module_elements(self):
        """Test parsing module-level elements like imports, exports, and variables."""
        code = '''
import React from 'react';
import { useState, useEffect } from 'react';

// Constants
const MAX_ITEMS = 100;
const API_URL = 'https://api.example.com';

// Function
function fetchItems() {
    return fetch(API_URL);
}

// Export
export const ItemList = () => {
    const [items, setItems] = useState([]);
    return <div>{items.map(item => <div key={item.id}>{item.name}</div>)}</div>;
};

export default ItemList;
'''
        elements = self.parser.parse(code)
        
        # Check imports
        imports = [e for e in elements if e.element_type == ElementType.IMPORT]
        self.assertEqual(len(imports), 2)
        self.assertTrue(any("react" in e.name for e in imports))
        
        # Check constants
        constants = [e for e in elements if e.element_type == ElementType.CONSTANT]
        self.assertEqual(len(constants), 2)
        self.assertTrue(any(e.name == "MAX_ITEMS" for e in constants))
        self.assertTrue(any(e.name == "API_URL" for e in constants))
        
        # Check function
        functions = [e for e in elements if e.element_type == ElementType.FUNCTION]
        self.assertTrue(any(e.name == "fetchItems" for e in functions))
        self.assertTrue(any(e.name == "ItemList" for e in functions))
    
    def test_find_function_by_name(self):
        """Test finding a function by name."""
        code = '''
function func1() {
    return 1;
}

function findMe() {
    // This is the function to find
    return "Found!";
}

const func2 = () => {
    return 2;
};
'''
        # Use the find_function method
        target = self.parser.find_function(code, "findMe")
        
        # Should find the function
        self.assertIsNotNone(target)
        self.assertEqual(target.name, "findMe")
        self.assertEqual(target.element_type, ElementType.FUNCTION)
    
    def test_get_all_globals(self):
        """Test getting all global elements."""
        code = '''
import React from 'react';

function globalFunc() {
    return true;
}

class GlobalClass {
    method() {
        return this;
    }
}

const CONSTANT = 42;
'''
        globals_dict = self.parser.get_all_globals(code)
        
        # Should find global function, class, and constant
        self.assertIn("globalFunc", globals_dict)
        self.assertIn("GlobalClass", globals_dict)
        self.assertIn("CONSTANT", globals_dict)
        self.assertIn("React", globals_dict)  # Import
        
        # Method should not be in globals
        self.assertNotIn("method", globals_dict)
    
    def test_check_syntax_validity(self):
        """Test syntax validity checker."""
        # Valid JavaScript
        valid_code = "function valid() { return 42; }"
        self.assertTrue(self.parser.check_syntax_validity(valid_code))
        
        # Invalid JavaScript (unbalanced braces)
        invalid_code = "function invalid() { return 42;"
        self.assertFalse(self.parser.check_syntax_validity(invalid_code))
        
        # Invalid JavaScript (unbalanced string)
        invalid_code2 = "const str = \"unbalanced;"
        self.assertFalse(self.parser.check_syntax_validity(invalid_code2))


if __name__ == '__main__':
    unittest.main()
