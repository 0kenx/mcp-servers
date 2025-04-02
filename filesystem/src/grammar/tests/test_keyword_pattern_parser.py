import unittest
from src.grammar.generic_keyword_pattern import KeywordPatternParser
from src.grammar.base import ElementType
from src.grammar.tests.test_utils import ParserTestHelper


class TestKeywordPatternParser(unittest.TestCase):
    """Test cases for the generic KeywordPatternParser."""

    def setUp(self):
        """Set up test cases."""
        self.helper = ParserTestHelper(KeywordPatternParser)

    def test_find_various_keywords(self):
        """Test finding elements across different language styles."""
        code = """
# Python
def py_func(a): pass
class PyClass: pass
MY_CONST = 10
my_var = "hello"

// JavaScript
function jsFunc(b) { return b; }
class JsClass {}
const JS_CONST = 20;
let jsVar = true;

-- SQL
CREATE FUNCTION sql_func (p INT) RETURNS INT AS $$ BEGIN RETURN p; END; $$ LANGUAGE plpgsql;
CREATE PROCEDURE sql_proc() LANGUAGE SQL AS $$ SELECT 1; $$;

# Shell
sh_func() {
  echo "hello"
}
function other_sh_func {
  ls
}
export SH_VAR=abc

# Basic Import
import os
from mymod import other
require 'some_gem'
use MyApp::Helper;
include <stdio.h>
"""
        elements = self.helper.parse_code(code)

        # Check counts (approximate, depends on pattern overlap)
        functions = self.helper.count_elements(elements, ElementType.FUNCTION)
        classes = self.helper.count_elements(elements, ElementType.CLASS)
        constants = self.helper.count_elements(elements, ElementType.CONSTANT)
        variables = self.helper.count_elements(elements, ElementType.VARIABLE)
        imports = self.helper.count_elements(elements, ElementType.IMPORT)

        # Expected elements based on patterns (adjust if patterns change)
        self.assertGreaterEqual(
            functions, 6
        )  # py_func, jsFunc, sql_func, sql_proc, sh_func, other_sh_func
        self.assertGreaterEqual(classes, 2)  # PyClass, JsClass
        self.assertGreaterEqual(constants, 2)  # MY_CONST, JS_CONST
        self.assertGreaterEqual(
            variables, 3
        )  # my_var, jsVar, SH_VAR (catches export line)
        self.assertGreaterEqual(
            imports, 5
        )  # os, mymod, some_gem, MyApp::Helper, stdio.h

        # Check specific elements
        py_f = self.helper.find_element(elements, ElementType.FUNCTION, "py_func")
        self.assertIsNotNone(py_f)
        self.assertEqual(py_f.start_line, 3)
        self.assertEqual(py_f.end_line, 3)
        self.assertIsNone(py_f.parent)

        js_cls = self.helper.find_element(elements, ElementType.CLASS, "JsClass")
        self.assertIsNotNone(js_cls)
        self.assertEqual(js_cls.start_line, 10)

        sql_p = self.helper.find_element(elements, ElementType.FUNCTION, "sql_proc")
        self.assertIsNotNone(sql_p)
        self.assertEqual(sql_p.start_line, 16)

        sh_f = self.helper.find_element(elements, ElementType.FUNCTION, "sh_func")
        self.assertIsNotNone(sh_f)
        self.assertEqual(sh_f.start_line, 19)

        imp = self.helper.find_element(elements, ElementType.IMPORT, "os")
        self.assertIsNotNone(imp)
        self.assertEqual(imp.start_line, 27)

        # Test limitation: matching keywords in comments/strings
        code_with_comments = """
// function commented_func() {}
var name = " class MyString ";
# def commented_def(): pass
"""
        commented_elements = self.helper.parse_code(code_with_comments)
        # Patterns match from start-of-line, so commented keywords shouldn't match
        self.assertEqual(len(commented_elements), 1)  # Should only find 'name' variable
        self.assertIsNotNone(
            self.helper.find_element(commented_elements, ElementType.VARIABLE, "name")
        )
        self.assertIsNone(
            self.helper.find_element(
                commented_elements, ElementType.FUNCTION, "commented_func"
            )
        )
        self.assertIsNone(
            self.helper.find_element(
                commented_elements, ElementType.FUNCTION, "commented_def"
            )
        )

    def test_syntax_validity(self):
        """Test syntax validity check (always True)."""
        self.assertTrue(
            self.helper.parser.check_syntax_validity("anything goes here { [ (")
        )
        self.assertTrue(self.helper.parser.check_syntax_validity(""))


if __name__ == "__main__":
    unittest.main()
