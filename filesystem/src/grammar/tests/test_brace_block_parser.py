
import unittest
from generic_brace_block import BraceBlockParser
from base import ElementType, CodeElement
from test_utils import ParserTestHelper

class TestBraceBlockParser(unittest.TestCase):
    """Test cases for the generic BraceBlockParser."""

    def setUp(self):
        """Set up test cases."""
        self.helper = ParserTestHelper(BraceBlockParser)

    def test_parse_c_style_function(self):
        """Test parsing a C/C++ style function."""
        code = """
int add(int a, int b) {
  // Add two numbers
  return a + b;
}

void no_op() { } // Single line
"""
        elements = self.helper.parse_code(code)
        self.assertEqual(len(elements), 2)

        add_func = self.helper.find_element(elements, ElementType.FUNCTION, "add")
        self.assertIsNotNone(add_func)
        self.assertEqual(add_func.start_line, 2)
        self.assertEqual(add_func.end_line, 5)
        self.assertEqual(add_func.metadata.get("parameters"), "(int a, int b)")
        self.assertIsNone(add_func.parent)

        noop_func = self.helper.find_element(elements, ElementType.FUNCTION, "no_op")
        self.assertIsNotNone(noop_func)
        self.assertEqual(noop_func.start_line, 7)
        self.assertEqual(noop_func.end_line, 7) # End line is the same for single-line block

    def test_parse_java_class(self):
        """Test parsing a Java-style class with methods."""
        code = """
public class MyClass {
    private int value;

    public MyClass(int val) {
        this.value = val;
    }

    public int getValue() {
        return this.value; // Return value
    }
} // End class
"""
        elements = self.helper.parse_code(code)
        # Should find Class, Constructor (as Method), Method
        self.assertEqual(len(elements), 3)

        class_el = self.helper.find_element(elements, ElementType.CLASS, "MyClass")
        self.assertIsNotNone(class_el)
        self.assertEqual(class_el.start_line, 2)
        self.assertEqual(class_el.end_line, 11)
        self.assertIsNone(class_el.parent)
        self.assertEqual(len(class_el.children), 2) # Constructor and getValue method

        constructor = self.helper.find_element(elements, ElementType.METHOD, "MyClass")
        self.assertIsNotNone(constructor)
        self.assertEqual(constructor.start_line, 5)
        self.assertEqual(constructor.end_line, 7)
        self.assertEqual(constructor.parent, class_el)
        self.assertIn("public", constructor.metadata.get("modifiers",""))

        get_method = self.helper.find_element(elements, ElementType.METHOD, "getValue")
        self.assertIsNotNone(get_method)
        self.assertEqual(get_method.start_line, 9)
        self.assertEqual(get_method.end_line, 11) # Brace matching includes the final line
        self.assertEqual(get_method.parent, class_el)

    def test_parse_javascript_function_and_class(self):
        """Test parsing JS function and class."""
        code = """
function calculate(x) {
  return x * x;
}

class Point {
  constructor(x, y) {
    this.x = x;
    this.y = y;
  }

  display() {
    console.log(`Point(${this.x}, ${this.y})`);
  }
}
"""
        elements = self.helper.parse_code(code)
        self.assertEqual(len(elements), 3) # calculate func, Point class, display method

        calc_func = self.helper.find_element(elements, ElementType.FUNCTION, "calculate")
        self.assertIsNotNone(calc_func)
        self.assertIsNone(calc_func.parent)

        point_class = self.helper.find_element(elements, ElementType.CLASS, "Point")
        self.assertIsNotNone(point_class)
        self.assertEqual(len(point_class.children), 2) # Constructor + display

        # Constructor is identified as METHOD named "constructor"
        constructor = self.helper.find_element(elements, ElementType.METHOD, "constructor")
        self.assertIsNotNone(constructor)
        self.assertEqual(constructor.parent, point_class)

        display_method = point_class.children[1] if len(point_class.children) > 1 else None
        self.assertIsNotNone(display_method)
        self.assertEqual(display_method.parent, point_class)

    def test_parse_rust_struct_and_impl(self):
        """Test parsing Rust struct and impl block."""
        code = """
struct Vec2 {
    x: f64,
    y: f64,
}

impl Vec2 {
    fn new(x: f64, y: f64) -> Self {
        Vec2 { x, y }
    } // end new

    // Another method
    fn length(&self) -> f64 {
        (self.x.powi(2) + self.y.powi(2)).sqrt()
    }
} // end impl
"""
        elements = self.helper.parse_code(code)
        # Struct, Impl block, new method, length method
        self.assertEqual(len(elements), 4)

        struct_el = self.helper.find_element(elements, ElementType.STRUCT, "Vec2")
        self.assertIsNotNone(struct_el)
        self.assertEqual(struct_el.start_line, 2)
        self.assertEqual(struct_el.end_line, 5)

        impl_el = self.helper.find_element(elements, ElementType.IMPL, "Vec2") # Name derived from type
        self.assertIsNotNone(impl_el)
        self.assertEqual(impl_el.start_line, 7)
        self.assertEqual(impl_el.end_line, 16)
        self.assertEqual(len(impl_el.children), 2) # new, length

        new_method = self.helper.find_element(elements, ElementType.METHOD, "new")
        self.assertIsNotNone(new_method)
        self.assertEqual(new_method.parent, impl_el)

        length_method = self.helper.find_element(elements, ElementType.METHOD, "length")
        self.assertIsNotNone(length_method)
        self.assertEqual(length_method.parent, impl_el)

    def test_parse_nested_blocks(self):
        """Test parsing nested functions/blocks."""
        code = """
void outer() {
    int x = 10;
    if (x > 5) {
        printf("Greater");
        function inner() { // JS style nested function
           return x;
        }
    } // end if
} // end outer
"""
        # Generic parser might identify 'if' if keyword added, or just outer/inner
        # Let's assume 'if' is NOT a keyword it tracks by default
        elements = self.helper.parse_code(code)
        # Expecting outer() and inner()
        self.assertEqual(len(elements), 2)

        outer_func = self.helper.find_element(elements, ElementType.FUNCTION, "outer")
        self.assertIsNotNone(outer_func)
        self.assertEqual(outer_func.start_line, 2)
        self.assertEqual(outer_func.end_line, 10)
        self.assertIsNone(outer_func.parent)
        self.assertEqual(len(outer_func.children), 1)

        inner_func = self.helper.find_element(elements, ElementType.FUNCTION, "inner")
        self.assertIsNotNone(inner_func)
        self.assertEqual(inner_func.start_line, 6)
        self.assertEqual(inner_func.end_line, 8)
        self.assertEqual(inner_func.parent, outer_func)

    def test_comments_and_strings_braces(self):
        """Test handling of braces within comments and strings."""
        code = """
void process() {
    char *str = "This { has } braces { inside }"; // String literal
    /* Block comment with { braces }
       spanning multiple { lines }
    */
    // Line comment { also }
    if (true) {
       call_func("another { string }");
    }
} // Closing brace for process
"""
        elements = self.helper.parse_code(code)
        self.assertEqual(len(elements), 1) # Only the process function

        process_func = self.helper.find_element(elements, ElementType.FUNCTION, "process")
        self.assertIsNotNone(process_func)
        self.assertEqual(process_func.start_line, 2)
        self.assertEqual(process_func.end_line, 11) # Brace matching should work
        # Inner 'if' block is not identified as a named element by default

    def test_syntax_validity_check(self):
        """Test the basic syntax validity check."""
        valid_code = "class T { void M() { if(true) {} } }"
        invalid_code_brace = "class T { void M() { if(true) {} } " # Missing closing brace
        invalid_code_paren = "class T { void M() { if(true {} ) }" # Missing closing paren
        invalid_code_string = "class T { void M() { char *s = \"abc; } }" # Unterminated string

        self.assertTrue(self.helper.parser.check_syntax_validity(valid_code))
        self.assertFalse(self.helper.parser.check_syntax_validity(invalid_code_brace))
        self.assertFalse(self.helper.parser.check_syntax_validity(invalid_code_paren))
        # Basic check might pass unterminated string if quotes balance happens to work out
        # Let's test a clearly unterminated one
        self.assertFalse(self.helper.parser.check_syntax_validity(invalid_code_string))

    def test_multiple_definitions_no_nesting(self):
        """Test multiple definitions at the same level."""
        code = """
struct Point { int x; };
struct Rect { Point tl, br; };
void draw(Rect r) { /* draw */ }
"""
        elements = self.helper.parse_code(code)
        self.assertEqual(len(elements), 3)
        self.assertIsNotNone(self.helper.find_element(elements, ElementType.STRUCT, "Point"))
        self.assertIsNotNone(self.helper.find_element(elements, ElementType.STRUCT, "Rect"))
        self.assertIsNotNone(self.helper.find_element(elements, ElementType.FUNCTION, "draw"))


    def test_brace_on_next_line(self):
        """Test when the opening brace is on the next line."""
        code = """
public class Example
{ // Brace on next line
    void method()
    {
        // code
    }
}
"""
        elements = self.helper.parse_code(code)
        self.assertEqual(len(elements), 2) # Class, Method

        class_el = self.helper.find_element(elements, ElementType.CLASS, "Example")
        self.assertIsNotNone(class_el)
        self.assertEqual(class_el.start_line, 2) # Definition starts here
        self.assertEqual(class_el.end_line, 8)
        self.assertEqual(len(class_el.children), 1)

        method_el = self.helper.find_element(elements, ElementType.METHOD, "method")
        self.assertIsNotNone(method_el)
        self.assertEqual(method_el.start_line, 4)
        self.assertEqual(method_el.end_line, 7)
        self.assertEqual(method_el.parent, class_el)


if __name__ == '__main__':
    unittest.main()
