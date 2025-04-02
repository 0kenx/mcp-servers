"""
Tests for the TypeScript language parser.
"""

import unittest
from src.grammar.typescript import TypeScriptParser
from src.grammar.base import ElementType


class TestTypeScriptParser(unittest.TestCase):
    """Test cases for the TypeScript parser."""
    
    def setUp(self):
        """Set up test cases."""
        self.parser = TypeScriptParser()
    
    def test_parse_interface(self):
        """Test parsing a TypeScript interface."""
        code = '''
/**
 * Represents a person with name and age.
 */
interface Person {
    name: string;
    age: number;
    greet(): string;
}
'''
        elements = self.parser.parse(code)
        
        # Should find one interface
        self.assertEqual(len(elements), 1)
        
        # Check interface properties
        interface = elements[0]
        self.assertEqual(interface.element_type, ElementType.INTERFACE)
        self.assertEqual(interface.name, "Person")
        self.assertIn("Represents a person", interface.metadata.get("docstring", ""))
    
    def test_parse_type_alias(self):
        """Test parsing a type alias."""
        code = '''
/**
 * ID type.
 */
type ID = string | number;

// Generic type
type Result<T> = {
    success: boolean;
    data?: T;
    error?: string;
};
'''
        elements = self.parser.parse(code)
        
        # Should find two type definitions
        self.assertEqual(len(elements), 2)
        
        # Check type properties
        id_type = next(e for e in elements if e.name == "ID")
        self.assertEqual(id_type.element_type, ElementType.TYPE_DEFINITION)
        self.assertIn("ID type", id_type.metadata.get("docstring", ""))
        
        result_type = next(e for e in elements if e.name == "Result")
        self.assertEqual(result_type.element_type, ElementType.TYPE_DEFINITION)
    
    def test_parse_enum(self):
        """Test parsing an enum."""
        code = '''
/**
 * Direction enum.
 */
enum Direction {
    Up,
    Down,
    Left,
    Right
}

// Const enum with values
const enum HttpStatus {
    OK = 200,
    NotFound = 404,
    ServerError = 500
}
'''
        elements = self.parser.parse(code)
        
        # Should find two enums
        self.assertEqual(len(elements), 2)
        
        # Check enum properties
        direction_enum = next(e for e in elements if e.name == "Direction")
        self.assertEqual(direction_enum.element_type, ElementType.ENUM)
        self.assertIn("Direction enum", direction_enum.metadata.get("docstring", ""))
        self.assertFalse(direction_enum.metadata.get("is_const", False))
        
        status_enum = next(e for e in elements if e.name == "HttpStatus")
        self.assertEqual(status_enum.element_type, ElementType.ENUM)
        self.assertTrue(status_enum.metadata.get("is_const", False))
    
    def test_parse_function_with_types(self):
        """Test parsing functions with TypeScript type annotations."""
        code = '''
/**
 * Add two numbers.
 */
function add(a: number, b: number): number {
    return a + b;
}

// Arrow function with type annotations
const multiply = (a: number, b: number): number => a * b;

// Generic function
function identity<T>(value: T): T {
    return value;
}
'''
        elements = self.parser.parse(code)
        
        # Should find three functions
        self.assertEqual(len(elements), 3)
        
        # Check function properties
        add_func = next(e for e in elements if e.name == "add")
        self.assertEqual(add_func.element_type, ElementType.FUNCTION)
        
        multiply_func = next(e for e in elements if e.name == "multiply")
        self.assertEqual(multiply_func.element_type, ElementType.FUNCTION)
        self.assertTrue(multiply_func.metadata.get("is_arrow", False))
        
        identity_func = next(e for e in elements if e.name == "identity")
        self.assertEqual(identity_func.element_type, ElementType.FUNCTION)
    
    def test_parse_class_with_properties(self):
        """Test parsing a class with typed properties."""
        code = '''
/**
 * User class.
 */
class User {
    // Properties with type annotations
    private id: number;
    public name: string;
    protected email: string;
    readonly createdAt: Date;
    
    // Constructor with parameter properties
    constructor(
        id: number,
        name: string,
        email: string,
        readonly role: string = "user"
    ) {
        this.id = id;
        this.name = name;
        this.email = email;
        this.createdAt = new Date();
    }
    
    // Method with return type
    public getInfo(): string {
        return `${this.name} (${this.email})`;
    }
}
'''
        elements = self.parser.parse(code)
        
        # Should find one class, several properties, and methods
        class_elements = [e for e in elements if e.element_type == ElementType.CLASS]
        self.assertEqual(len(class_elements), 1)
        
        # Check class properties
        class_element = class_elements[0]
        self.assertEqual(class_element.name, "User")
        
        # Find all properties and methods
        properties = [e for e in elements if e.element_type == ElementType.VARIABLE and e.parent == class_element]
        methods = [e for e in elements if e.element_type == ElementType.METHOD and e.parent == class_element]
        
        # Should have properties and methods
        self.assertGreaterEqual(len(properties), 4)  # id, name, email, createdAt
        self.assertGreaterEqual(len(methods), 1)     # constructor and getInfo
        
        # Check a property
        id_prop = next((p for p in properties if p.name == "id"), None)
        if id_prop:
            self.assertTrue(id_prop.metadata.get("is_private", False))
        
        # Check a method
        get_info = next((m for m in methods if m.name == "getInfo"), None)
        if get_info:
            self.assertEqual(get_info.metadata.get("return_type", ""), "string")
    
    def test_parse_namespace(self):
        """Test parsing a namespace."""
        code = '''
/**
 * Utilities namespace.
 */
namespace Utils {
    export function format(value: any): string {
        return String(value);
    }
    
    export const VERSION = "1.0.0";
}
'''
        elements = self.parser.parse(code)
        
        # Should find a namespace
        namespace = next((e for e in elements if e.element_type == ElementType.NAMESPACE), None)
        self.assertIsNotNone(namespace)
        self.assertEqual(namespace.name, "Utils")
        self.assertIn("Utilities namespace", namespace.metadata.get("docstring", ""))
    
    def test_parse_decorated_class(self):
        """Test parsing a class with decorators."""
        code = '''
@Component({
    selector: 'app-root',
    template: '<div>Hello</div>'
})
class AppComponent {
    constructor() {}
}

@Injectable()
class Service {
    @Input() data: string;
    
    @Log()
    doSomething() {}
}
'''
        elements = self.parser.parse(code)
        
        # Should find classes with decorators
        classes = [e for e in elements if e.element_type == ElementType.CLASS]
        self.assertEqual(len(classes), 2)
        
        # Check decorators
        app_component = next(e for e in classes if e.name == "AppComponent")
        self.assertIsNotNone(app_component.metadata.get("decorators"))
        self.assertIn("Component", app_component.metadata.get("decorators")[0])
        
        service = next(e for e in classes if e.name == "Service")
        self.assertIsNotNone(service.metadata.get("decorators"))
        self.assertIn("Injectable", service.metadata.get("decorators")[0])
    
    def test_get_all_globals(self):
        """Test getting all global elements in a TypeScript file."""
        code = '''
import { Component } from '@angular/core';

interface User {
    id: number;
    name: string;
}

type ID = number;

enum Status {
    Active,
    Inactive
}

const API_URL = 'https://api.example.com';

class UserService {
    getUsers(): User[] {
        return [];
    }
}

function formatUser(user: User): string {
    return user.name;
}

export default UserService;
'''
        globals_dict = self.parser.get_all_globals(code)
        
        # Should find all top-level elements
        self.assertIn("User", globals_dict)  # interface
        self.assertIn("ID", globals_dict)    # type
        self.assertIn("Status", globals_dict)  # enum
        self.assertIn("API_URL", globals_dict)  # constant
        self.assertIn("UserService", globals_dict)  # class
        self.assertIn("formatUser", globals_dict)  # function
        self.assertIn("Component", globals_dict)  # import
        
        # Method should not be in globals
        self.assertNotIn("getUsers", globals_dict)
    
    def test_check_syntax_validity(self):
        """Test syntax validity checker for TypeScript code."""
        # Valid TypeScript
        valid_code = "function valid(): number { return 42; }"
        self.assertTrue(self.parser.check_syntax_validity(valid_code))
        
        # Invalid TypeScript (unbalanced generics)
        invalid_code = "function invalid<T(param: T): T { return param; }"
        self.assertFalse(self.parser.check_syntax_validity(invalid_code))


if __name__ == '__main__':
    unittest.main()
