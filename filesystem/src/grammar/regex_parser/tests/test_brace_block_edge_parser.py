"""
Tests for the BraceBlockParser with edge cases.
"""

import unittest
from src.grammar.generic_brace_block import BraceBlockParser
from src.grammar.base import ElementType


class TestBraceBlockParserEdgeCases(unittest.TestCase):
    """Test edge cases for the BraceBlockParser."""

    def setUp(self):
        """Set up test cases."""
        self.parser = BraceBlockParser()

    def test_deeply_nested_blocks(self):
        """Test the brace parser with deeply nested blocks."""
        code = """
function level1() {
  if (condition1) {
    while (condition2) {
      for (let i = 0; i < 10; i++) {
        if (condition3) {
          function level2() {
            // Another nested function
            if (condition4) {
              try {
                function level3() {
                  // Deep nesting
                  while (true) {
                    if (true) {
                      {
                        // Anonymous block
                        console.log("Deep");
                      }
                    }
                  }
                }
              } catch (e) {
                console.log(e);
              }
            }
          }
        }
      }
    }
  }
  
  return "Done";
}"""
        elements = self.parser.parse(code)
        
        # Check that we found the nested functions
        self.assertGreaterEqual(len(elements), 2)
        
        # Check for the top-level function
        level1_func = next((e for e in elements if e.name == "level1"), None)
        self.assertIsNotNone(level1_func)
        
        # Check for nested functions - depending on how deep the parser can go
        nested_funcs = [e for e in elements if e.name in ("level2", "level3")]
        self.assertGreaterEqual(len(nested_funcs), 1)
        
        # Check nested relationships if the parser supports parent-child relationships
        if nested_funcs and hasattr(nested_funcs[0], 'parent') and nested_funcs[0].parent is not None:
            level2_func = next((e for e in nested_funcs if e.name == "level2"), None)
            if level2_func:
                # level2 should be a child of level1
                self.assertEqual(level2_func.parent, level1_func)

    def test_unbalanced_braces(self):
        """Test the brace parser with unbalanced braces."""
        code = """
function missingClosingBrace() {
  if (condition) {
    console.log("This block is not properly closed");
  
// Extra closing brace
function extraClosingBrace() {
  if (condition) {
    console.log("Normal block");
  }
}}

// Unbalanced in string literals and comments
function validDespiteAppearance() {
  let str = "This has a } that looks unbalanced";
  // Here's a { in a comment
  let regex = /\\{.*\\}/;  // Regex with braces
  return "All good";
}
"""
        try:
            elements = self.parser.parse(code)
            
            # Should find at least some elements despite unbalanced braces
            self.assertGreaterEqual(len(elements), 1)
            
            # Check that we found the valid function
            valid_func = next((e for e in elements if e.name == "validDespiteAppearance"), None)
            self.assertIsNotNone(valid_func)
            
            # The parser should either skip or correct invalid elements
            # For robustness, it should not crash
        except Exception as e:
            self.fail(f"Parser crashed on unbalanced braces: {e}")

    def test_code_with_different_languages(self):
        """Test the brace parser with code that looks like different languages."""
        code = """
// This has C-style syntax
void c_function(int x) {
    printf("Value: %d\\n", x);
    return;
}

// This has Java-style syntax
public class JavaClass {
    private int value;
    
    public JavaClass(int value) {
        this.value = value;
    }
    
    public int getValue() {
        return this.value;
    }
}

// This has JavaScript-style syntax
function jsFunction() {
    const obj = {
        key: "value",
        method: function() {
            return this.key;
        }
    };
    return obj;
}

// This has PHP-style syntax
<?php
function php_function($param) {
    echo "This is PHP-like syntax";
    return $param;
}
?>
"""
        elements = self.parser.parse(code)
        
        # Should recognize elements across different language-like syntaxes
        self.assertGreaterEqual(len(elements), 3)
        
        # Check that we found various elements
        c_func = next((e for e in elements if e.name == "c_function"), None)
        self.assertIsNotNone(c_func)
        
        java_class = next((e for e in elements if e.name == "JavaClass"), None)
        self.assertIsNotNone(java_class)
        
        js_func = next((e for e in elements if e.name == "jsFunction"), None)
        self.assertIsNotNone(js_func)
        
        # PHP function may or may not be detected depending on parser capabilities
        php_func = next((e for e in elements if e.name == "php_function"), None)
        if php_func:
            self.assertEqual(php_func.element_type, ElementType.FUNCTION)

    def test_brace_styles(self):
        """Test the brace parser with different brace styles."""
        code = """
// K&R style
function krStyle() {
    if (condition) {
        doSomething();
    }
}

// Allman style
function allmanStyle() 
{
    if (condition) 
    {
        doSomething();
    }
}

// Whitesmiths style
function whitesmithsStyle() 
    {
    if (condition) 
        {
        doSomething();
        }
    }

// GNU style
function gnuStyle()
  {
    if (condition)
      {
        doSomething();
      }
  }
"""
        elements = self.parser.parse(code)
        
        # Should recognize functions with different brace styles
        functions = [e for e in elements if e.element_type == ElementType.FUNCTION]
        self.assertEqual(len(functions), 4)
        
        # Check that we found each function
        style_names = ["krStyle", "allmanStyle", "whitesmithsStyle", "gnuStyle"]
        for name in style_names:
            func = next((f for f in functions if f.name == name), None)
            self.assertIsNotNone(func)

    def test_braces_in_literals(self):
        """Test the brace parser with braces in literals and comments."""
        code = """
function handleStrings() {
    const str1 = "This string has { braces } inside";
    const str2 = 'Another string with { different } braces';
    const template = `Template with ${  
        // Even a complex expression with a {
        function() { return "value"; }()
    } interpolation`;
    
    // Comment with { braces } that should be ignored
    /* Multi-line comment
       with { nested } braces
       that should also be ignored */
    
    const regex1 = /\\{.*\\}/g;  // Regex with escaped braces
    const regex2 = new RegExp("\\{.*\\}");  // Another way to create regex
    
    return "Valid function despite all the braces in literals";
}
"""
        elements = self.parser.parse(code)
        
        # Should correctly parse the function despite braces in literals and comments
        self.assertEqual(len(elements), 1)
        
        # Check that we found the function
        handle_strings_func = next((e for e in elements if e.name == "handleStrings"), None)
        self.assertIsNotNone(handle_strings_func)
        self.assertEqual(handle_strings_func.element_type, ElementType.FUNCTION)


if __name__ == "__main__":
    unittest.main()
