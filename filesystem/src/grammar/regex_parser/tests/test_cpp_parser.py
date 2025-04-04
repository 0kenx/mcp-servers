"""
Tests for the C/C++ language parser.
"""

import unittest
from src.grammar.c_cpp import CCppParser
from src.grammar.base import ElementType


class TestCCppParser(unittest.TestCase):
    """Test cases for the C/C++ parser."""

    def setUp(self):
        """Set up test cases."""
        self.parser = CCppParser()

    def test_parse_function(self):
        """Test parsing a C/C++ function."""
        code = """
/**
 * Add two numbers.
 * @param a First number
 * @param b Second number
 * @return Sum of a and b
 */
int add(int a, int b) {
    return a + b;
}
"""
        elements = self.parser.parse(code)

        # Should find one function
        self.assertEqual(len(elements), 1)

        # Check function properties
        func = elements[0]
        self.assertEqual(func.element_type, ElementType.FUNCTION)
        self.assertEqual(func.name, "add")
        self.assertEqual(func.start_line, 7)
        self.assertEqual(func.end_line, 9)
        self.assertIn("Add two numbers", func.metadata.get("docstring", ""))
        self.assertEqual(func.metadata.get("return_type"), "int")
        self.assertEqual(func.metadata.get("parameters"), "int a, int b")

    def test_parse_class(self):
        """Test parsing a C++ class."""
        code = """
/**
 * A simple rectangle class.
 */
class Rectangle {
private:
    int width;
    int height;
    
public:
    // Constructor
    Rectangle(int w, int h) : width(w), height(h) {}
    
    // Method to calculate area
    int area() const {
        return width * height;
    }
    
    // Getters and setters
    int getWidth() const { return width; }
    void setWidth(int w) { width = w; }
    
    int getHeight() const { return height; }
    void setHeight(int h) { height = h; }
};
"""
        elements = self.parser.parse(code)

        # Should find one class and several methods
        class_elements = [e for e in elements if e.element_type == ElementType.CLASS]
        method_elements = [e for e in elements if e.element_type == ElementType.METHOD]

        self.assertEqual(len(class_elements), 1)
        self.assertGreaterEqual(len(method_elements), 5)  # Constructor and 4 methods

        # Check class
        class_element = class_elements[0]
        self.assertEqual(class_element.name, "Rectangle")
        self.assertIn(
            "simple rectangle class", class_element.metadata.get("docstring", "")
        )

        # Check methods
        area_method = next(e for e in method_elements if e.name == "area")
        self.assertEqual(area_method.parent, class_element)
        self.assertEqual(area_method.metadata.get("return_type"), "int")
        self.assertTrue(area_method.metadata.get("is_const", False))

    def test_parse_namespace(self):
        """Test parsing a C++ namespace."""
        code = """
namespace Utils {
    // Helper function
    int max(int a, int b) {
        return (a > b) ? a : b;
    }
    
    // Nested namespace (C++17)
    namespace Math {
        const double PI = 3.14159265359;
        
        double area(double radius) {
            return PI * radius * radius;
        }
    }
}
"""
        elements = self.parser.parse(code)

        # Should find namespaces, function, constant
        namespaces = [e for e in elements if e.element_type == ElementType.NAMESPACE]
        functions = [e for e in elements if e.element_type == ElementType.FUNCTION]
        constants = [e for e in elements if e.element_type == ElementType.CONSTANT]

        self.assertGreaterEqual(len(namespaces), 2)  # Utils and Math
        self.assertGreaterEqual(len(functions), 2)  # max and area
        self.assertGreaterEqual(len(constants), 1)  # PI

        # Check namespace hierarchy
        utils_ns = next(e for e in namespaces if e.name == "Utils")
        math_ns = next(e for e in namespaces if e.name == "Math")
        self.assertEqual(math_ns.parent, utils_ns)

        # Check function parents
        max_func = next(e for e in functions if e.name == "max")
        self.assertEqual(max_func.parent, utils_ns)

        area_func = next(e for e in functions if e.name == "area")
        self.assertEqual(area_func.parent, math_ns)

        # Check constant parent
        pi_const = next(e for e in constants if e.name == "PI")
        self.assertEqual(pi_const.parent, math_ns)

    def test_parse_struct(self):
        """Test parsing a C/C++ struct."""
        code = """
/**
 * Point structure to represent a 2D point.
 */
struct Point {
    int x;
    int y;
    
    // Method
    double distance(const Point& other) const {
        int dx = x - other.x;
        int dy = y - other.y;
        return sqrt(dx*dx + dy*dy);
    }
};
"""
        elements = self.parser.parse(code)

        # Should find one struct and one method
        struct_elements = [e for e in elements if e.element_type == ElementType.STRUCT]
        method_elements = [e for e in elements if e.element_type == ElementType.METHOD]

        self.assertEqual(len(struct_elements), 1)
        self.assertGreaterEqual(len(method_elements), 1)

        # Check struct
        struct_element = struct_elements[0]
        self.assertEqual(struct_element.name, "Point")
        self.assertIn("2D point", struct_element.metadata.get("docstring", ""))

        # Check method
        distance_method = next(e for e in method_elements if e.name == "distance")
        self.assertEqual(distance_method.parent, struct_element)
        self.assertEqual(distance_method.metadata.get("return_type"), "double")

    def test_parse_enum(self):
        """Test parsing a C++ enum."""
        code = """
/**
 * Days of the week.
 */
enum class Day {
    Monday,
    Tuesday,
    Wednesday,
    Thursday,
    Friday,
    Saturday,
    Sunday
};

// C-style enum
enum Color {
    Red,
    Green,
    Blue
};
"""
        elements = self.parser.parse(code)

        # Should find two enums
        enum_elements = [e for e in elements if e.element_type == ElementType.ENUM]
        self.assertEqual(len(enum_elements), 2)

        # Check enum class
        day_enum = next(e for e in enum_elements if e.name == "Day")
        self.assertIn("Days of the week", day_enum.metadata.get("docstring", ""))

        # Check C-style enum
        color_enum = next(e for e in enum_elements if e.name == "Color")

    def test_parse_template(self):
        """Test parsing a C++ template function and class."""
        code = """
/**
 * Generic maximum function.
 */
template <typename T>
T max(T a, T b) {
    return (a > b) ? a : b;
}

/**
 * Generic container class.
 */
template <typename T, int Size = 10>
class Container {
private:
    T data[Size];
    
public:
    Container() {}
    
    T& get(int index) {
        return data[index];
    }
    
    void set(int index, const T& value) {
        data[index] = value;
    }
};
"""
        elements = self.parser.parse(code)

        # Should find template function and class
        functions = [e for e in elements if e.element_type == ElementType.FUNCTION]
        classes = [e for e in elements if e.element_type == ElementType.CLASS]

        self.assertGreaterEqual(len(functions), 1)
        self.assertGreaterEqual(len(classes), 1)

        # Check template function
        max_func = next(e for e in functions if e.name == "max")
        self.assertIn("Generic maximum", max_func.metadata.get("docstring", ""))
        self.assertIn("template", max_func.metadata.get("template_params", ""))

        # Check template class
        container_class = next(e for e in classes if e.name == "Container")
        self.assertIn(
            "Generic container", container_class.metadata.get("docstring", "")
        )
        self.assertIn("template", container_class.metadata.get("template_params", ""))

    def test_parse_header_includes(self):
        """Test parsing C/C++ header includes."""
        code = """
#include <iostream>
#include <vector>
#include <string>
#include "myheader.h"

using namespace std;

int main() {
    cout << "Hello, World!" << endl;
    return 0;
}
"""
        elements = self.parser.parse(code)

        # Should find includes and using directive
        imports = [e for e in elements if e.element_type == ElementType.IMPORT]
        functions = [e for e in elements if e.element_type == ElementType.FUNCTION]

        self.assertGreaterEqual(len(imports), 5)  # 4 includes + 1 using directive
        self.assertGreaterEqual(len(functions), 1)  # main function

        # Check includes
        includes = [e for e in imports if e.metadata.get("kind") == "include"]
        self.assertEqual(len(includes), 4)
        include_names = [e.name for e in includes]
        self.assertIn("iostream", include_names)
        self.assertIn("vector", include_names)
        self.assertIn("string", include_names)
        self.assertIn("myheader.h", include_names)

        # Check using directive
        using_directives = [e for e in imports if e.metadata.get("kind") == "using"]
        self.assertGreaterEqual(len(using_directives), 1)

    def test_parse_constants(self):
        """Test parsing C/C++ constants and static variables."""
        code = """
// Global constants
const int MAX_SIZE = 100;
constexpr double PI = 3.14159265359;

// Global variable
int counter = 0;

// Static variable
static char buffer[1024];

// Static constant
static const char* VERSION = "1.0.0";
"""
        elements = self.parser.parse(code)

        # Should find constants and variables
        constants = [e for e in elements if e.element_type == ElementType.CONSTANT]
        variables = [e for e in elements if e.element_type == ElementType.VARIABLE]

        self.assertGreaterEqual(len(constants), 2)  # MAX_SIZE, PI
        self.assertGreaterEqual(len(variables), 2)  # counter, buffer

        # Check constants
        const_names = [e.name for e in constants]
        self.assertIn("MAX_SIZE", const_names)
        self.assertIn("PI", const_names)

        # Check variables
        var_names = [e.name for e in variables]
        self.assertIn("counter", var_names)
        self.assertIn("buffer", var_names)

    def test_find_function_by_name(self):
        """Test finding a function by name."""
        code = """
int func1() {
    return 1;
}

// Function to find
int findMe(int x) {
    return x * 2;
}

double func2(double y) {
    return y / 2;
}
"""
        # Use the find_function method
        target = self.parser.find_function(code, "findMe")

        # Should find the function
        self.assertIsNotNone(target)
        self.assertEqual(target.name, "findMe")
        self.assertEqual(target.element_type, ElementType.FUNCTION)

    def test_get_all_globals(self):
        """Test getting all global elements."""
        code = """
#include <iostream>

const int MAX_SIZE = 100;

class MyClass {
public:
    void method() {}
};

namespace MyNamespace {
    void helper() {}
}

int main() {
    return 0;
}
"""
        globals_dict = self.parser.get_all_globals(code)

        # Should find includes, constants, class, namespace, and function
        self.assertIn("iostream", globals_dict)  # include
        self.assertIn("MAX_SIZE", globals_dict)  # constant
        self.assertIn("MyClass", globals_dict)  # class
        self.assertIn("MyNamespace", globals_dict)  # namespace
        self.assertIn("main", globals_dict)  # function

        # Method should not be in globals
        self.assertNotIn("method", globals_dict)
        self.assertNotIn("helper", globals_dict)

    def test_check_syntax_validity(self):
        """Test syntax validity checker."""
        # Valid C++
        valid_code = "int main() { return 0; }"
        self.assertTrue(self.parser.check_syntax_validity(valid_code))

        # Invalid C++ (unbalanced braces)
        invalid_code = "int main() { return 0;"
        self.assertFalse(self.parser.check_syntax_validity(invalid_code))


if __name__ == "__main__":
    unittest.main()
