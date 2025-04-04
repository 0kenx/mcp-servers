"""
Tests for the KeywordPatternParser with edge cases.
"""

import unittest
from src.grammar.generic_keyword_pattern import KeywordPatternParser
from src.grammar.base import ElementType


class TestKeywordPatternParserEdgeCases(unittest.TestCase):
    """Test edge cases for the KeywordPatternParser."""

    def setUp(self):
        """Set up test cases."""
        self.parser = KeywordPatternParser()
        # Configure with multiple keywords and patterns
        self.parser.keywords = [
            "function", "class", "method", "procedure", "subroutine", 
            "package", "module", "namespace"
        ]
        self.parser.patterns = [
            (r"function\s+(\w+)", ElementType.FUNCTION),
            (r"class\s+(\w+)", ElementType.CLASS),
            (r"method\s+(\w+)", ElementType.METHOD),
            (r"procedure\s+(\w+)", ElementType.FUNCTION),
            (r"subroutine\s+(\w+)", ElementType.FUNCTION),
            (r"package\s+(\w+)", ElementType.MODULE),
            (r"module\s+(\w+)", ElementType.MODULE),
            (r"namespace\s+(\w+)", ElementType.NAMESPACE),
            (r"(\w+)\s+as\s+function", ElementType.FUNCTION),  # Non-standard pattern
        ]

    def test_complex_patterns(self):
        """Test the keyword pattern parser with complex patterns."""
        code = """
function normalFunction() {
  // Normal function
}

class SimpleClass {
  // A class definition
}

procedure oldStyleProcedure() {
  // Old style procedure
}

subroutine legacyCode() {
  // Legacy code
}

package myPackage {
  // Package or module
}

namespace myNamespace {
  // Namespace definition
}

// Non-standard pattern
myCustomHandler as function {
  // Should still be detected
}
"""
        elements = self.parser.parse(code)
        
        # Should identify all elements based on patterns
        self.assertEqual(len(elements), 7)
        
        # Check element types
        element_types = [e.element_type for e in elements]
        self.assertIn(ElementType.FUNCTION, element_types)
        self.assertIn(ElementType.CLASS, element_types)
        self.assertIn(ElementType.MODULE, element_types)
        self.assertIn(ElementType.NAMESPACE, element_types)
        
        # Check specific names
        element_names = [e.name for e in elements]
        self.assertIn("normalFunction", element_names)
        self.assertIn("SimpleClass", element_names)
        self.assertIn("oldStyleProcedure", element_names)
        self.assertIn("legacyCode", element_names)
        self.assertIn("myPackage", element_names)
        self.assertIn("myNamespace", element_names)
        self.assertIn("myCustomHandler", element_names)

    def test_pattern_conflicts(self):
        """Test the keyword pattern parser with potentially conflicting patterns."""
        code = """
// Multiple matches on the same line
function classicFunction() {
  // This has 'function' and 'class' keywords
}

// Multiple patterns on the same line
class Function {
  // Both 'class' and 'function' are keywords
}

// Keywords in comments
// function shouldNotMatch() {}

// Keywords in string literals
const str = "function shouldNotMatchEither()";

// Pattern that spans multiple lines
function
multiline
() {
  // Complex case where the signature spans lines
}

// Keyword as part of another word
functionality(); // Should not match 'function'
"""
        elements = self.parser.parse(code)
        
        # Check that we found the expected elements
        self.assertGreaterEqual(len(elements), 2)
        
        # Keywords in comments and strings should not be matched
        elements_in_strings = [e for e in elements if e.name in ("shouldNotMatch", "shouldNotMatchEither")]
        self.assertEqual(len(elements_in_strings), 0)
        
        # Check that keywords as part of other words are not matched
        functionality_element = next((e for e in elements if e.name == "functionality"), None)
        self.assertIsNone(functionality_element)
        
        # Both 'function' and 'class' keywords should be found
        function_elements = [e for e in elements if e.element_type == ElementType.FUNCTION]
        self.assertGreaterEqual(len(function_elements), 1)
        
        class_elements = [e for e in elements if e.element_type == ElementType.CLASS]
        self.assertGreaterEqual(len(class_elements), 1)

    def test_custom_patterns(self):
        """Test the keyword pattern parser with custom patterns for different language styles."""
        # Add more complex patterns
        self.parser.patterns.extend([
            (r"def\s+(\w+)\s*\(", ElementType.FUNCTION),  # Python-style functions
            (r"CREATE\s+TABLE\s+(\w+)", ElementType.STRUCT),  # SQL-style tables
            (r"^\s*@interface\s+(\w+)", ElementType.CLASS),  # Objective-C style
            (r"trait\s+(\w+)", ElementType.TRAIT),  # Rust/Scala traits
            (r"struct\s+(\w+)", ElementType.STRUCT),  # C/Rust structs
            (r"enum\s+(\w+)", ElementType.ENUM),  # Enums
        ])
        
        code = """
// Python-style
def python_function(arg1, arg2):
    return arg1 + arg2

// SQL-style
CREATE TABLE users (
    id INT PRIMARY KEY,
    name VARCHAR(255)
);

// Objective-C style
@interface MyClass : NSObject
- (void)someMethod;
@end

// Rust/Scala style
trait Drawable {
    fn draw(&self);
}

// C/Rust struct
struct Point {
    x: i32,
    y: i32
}

// Enum
enum Color {
    RED,
    GREEN,
    BLUE
}
"""
        elements = self.parser.parse(code)
        
        # Should identify elements across different language styles
        self.assertGreaterEqual(len(elements), 5)
        
        # Check specific elements
        python_func = next((e for e in elements if e.name == "python_function"), None)
        self.assertIsNotNone(python_func)
        self.assertEqual(python_func.element_type, ElementType.FUNCTION)
        
        users_table = next((e for e in elements if e.name == "users"), None)
        self.assertIsNotNone(users_table)
        self.assertEqual(users_table.element_type, ElementType.STRUCT)
        
        my_class = next((e for e in elements if e.name == "MyClass"), None)
        self.assertIsNotNone(my_class)
        self.assertEqual(my_class.element_type, ElementType.CLASS)
        
        drawable_trait = next((e for e in elements if e.name == "Drawable"), None)
        self.assertIsNotNone(drawable_trait)
        self.assertEqual(drawable_trait.element_type, ElementType.TRAIT)
        
        point_struct = next((e for e in elements if e.name == "Point"), None)
        self.assertIsNotNone(point_struct)
        self.assertEqual(point_struct.element_type, ElementType.STRUCT)
        
        color_enum = next((e for e in elements if e.name == "Color"), None)
        self.assertIsNotNone(color_enum)
        self.assertEqual(color_enum.element_type, ElementType.ENUM)

    def test_pattern_edge_cases(self):
        """Test the keyword pattern parser with edge cases for patterns."""
        code = """
// Empty function/class names
function () { }
class { }

// Unusual identifiers
function $special_func() { }
function _private() { }
function func123() { }

// Very long identifier
function thisIsAReallyReallyReallyReallyReallyReallyReallyReallyReallyReallyReallyReallyReallyReallyReallyReallyLongFunctionName() { }

// Non-ASCII identifiers
function áéíóú() { }
function 你好() { }
function λ() { }

// Keywords in comments that look like definitions
// This is not a real function:
// function fake() { }

// Preprocessor directives (in C-like languages)
#define function not_a_real_function() // Shouldn't match
"""
        elements = self.parser.parse(code)
        
        # Check that valid elements were found
        self.assertGreaterEqual(len(elements), 3)
        
        # Special function names should be detected
        special_func = next((e for e in elements if e.name == "$special_func"), None)
        self.assertIsNotNone(special_func)
        
        private_func = next((e for e in elements if e.name == "_private"), None)
        self.assertIsNotNone(private_func)
        
        # Very long name should be detected
        long_name_funcs = [e for e in elements if "Really" in e.name]
        self.assertEqual(len(long_name_funcs), 1)
        
        # Non-ASCII names might be detected depending on parser capabilities
        non_ascii_funcs = [e for e in elements if any(ord(c) > 127 for c in e.name)]
        # We won't assert on this as it's dependent on parser capabilities
        
        # Elements in comments should not be detected
        fake_func = next((e for e in elements if e.name == "fake"), None)
        self.assertIsNone(fake_func)
        
        # Preprocessor directives should not create false matches
        not_real_func = next((e for e in elements if e.name == "not_a_real_function"), None)
        self.assertIsNone(not_real_func)


if __name__ == "__main__":
    unittest.main()
