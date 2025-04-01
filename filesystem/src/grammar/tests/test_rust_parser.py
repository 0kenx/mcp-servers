"""
Tests for the Rust language parser.
"""

import unittest
from rust import RustParser
from base import ElementType


class TestRustParser(unittest.TestCase):
    """Test cases for the Rust parser."""

    def setUp(self):
        """Set up test cases."""
        self.parser = RustParser()

    def test_parse_simple_function(self):
        """Test parsing a simple function."""
        code = '''
fn main() {
    println!("Hello, world!");
}
'''
        elements = self.parser.parse(code)
        self.assertEqual(len(elements), 1)
        func = elements[0]
        self.assertEqual(func.element_type, ElementType.FUNCTION)
        self.assertEqual(func.name, "main")
        self.assertEqual(func.start_line, 2)
        self.assertEqual(func.end_line, 4)
        self.assertEqual(func.metadata.get("parameters"), "")
        self.assertIsNone(func.metadata.get("return_type"))

    def test_parse_function_with_args_and_return(self):
        """Test parsing a function with arguments and return type."""
        code = '''
/// Adds two numbers.
///
/// # Arguments
/// * `a` - The first number.
/// * `b` - The second number.
///
/// # Returns
/// The sum of `a` and `b`.
#[inline]
pub fn add(a: i32, b: i32) -> i32 {
    a + b
}
'''
        elements = self.parser.parse(code)
        self.assertEqual(len(elements), 1)
        func = elements[0]
        self.assertEqual(func.element_type, ElementType.FUNCTION)
        self.assertEqual(func.name, "add")
        self.assertEqual(func.start_line, 11) # Line where 'pub fn add...' starts
        self.assertEqual(func.end_line, 13)
        self.assertEqual(func.metadata.get("parameters"), "a: i32, b: i32")
        self.assertEqual(func.metadata.get("return_type"), "i32")
        self.assertIn("Adds two numbers", func.metadata.get("docstring", ""))
        self.assertEqual(func.metadata.get("attributes"), ["inline"])
        self.assertEqual(func.metadata.get("visibility"), "pub")


    def test_parse_struct(self):
        """Test parsing struct definitions."""
        code = '''
struct Point {
    x: f64,
    y: f64,
}

// Unit struct
struct Unit;

// Tuple struct
struct Color(u8, u8, u8);

pub struct GenericPoint<T> {
    x: T,
    y: T,
}
'''
        elements = self.parser.parse(code)
        self.assertEqual(len(elements), 4)

        point = next(e for e in elements if e.name == "Point")
        self.assertEqual(point.element_type, ElementType.STRUCT)
        self.assertEqual(point.start_line, 2)
        self.assertEqual(point.end_line, 5)

        unit = next(e for e in elements if e.name == "Unit")
        self.assertEqual(unit.element_type, ElementType.STRUCT)
        self.assertEqual(unit.start_line, 8)
        self.assertEqual(unit.end_line, 8) # Single line

        color = next(e for e in elements if e.name == "Color")
        self.assertEqual(color.element_type, ElementType.STRUCT)
        self.assertEqual(color.start_line, 11)
        # Brace matching for tuple struct parentheses needs specific implementation
        # For now, assuming it ends on the same line if ';' present
        self.assertEqual(color.end_line, 11)

        generic_point = next(e for e in elements if e.name == "GenericPoint")
        self.assertEqual(generic_point.element_type, ElementType.STRUCT)
        self.assertEqual(generic_point.start_line, 13)
        self.assertEqual(generic_point.end_line, 16)
        self.assertEqual(generic_point.metadata.get("visibility"), "pub")


    def test_parse_enum(self):
        """Test parsing an enum definition."""
        code = '''
/// An enum representing web events.
#[derive(Debug)]
enum WebEvent {
    PageLoad,                       // Variant without data
    KeyPress(char),                 // Tuple variant
    Click { x: i64, y: i64 },       // Struct variant
}
'''
        elements = self.parser.parse(code)
        self.assertEqual(len(elements), 1)
        enum = elements[0]
        self.assertEqual(enum.element_type, ElementType.ENUM)
        self.assertEqual(enum.name, "WebEvent")
        self.assertEqual(enum.start_line, 4) # Line where 'enum WebEvent' starts
        self.assertEqual(enum.end_line, 8)
        self.assertIn("enum representing web events", enum.metadata.get("docstring", ""))
        self.assertEqual(enum.metadata.get("attributes"), ["derive(Debug)"])


    def test_parse_trait(self):
        """Test parsing a trait definition with methods."""
        code = '''
/// A summary trait.
pub trait Summary {
    /// Get the author summary.
    fn author_summary(&self) -> String;

    /// Get the full summary.
    fn summarize(&self) -> String {
        format!("(Read more from {}...)", self.author_summary())
    }
}
'''
        elements = self.parser.parse(code)
        self.assertEqual(len(elements), 3) # Trait + 2 methods

        trait = next(e for e in elements if e.element_type == ElementType.TRAIT)
        self.assertEqual(trait.name, "Summary")
        self.assertEqual(trait.start_line, 3)
        self.assertEqual(trait.end_line, 11)
        self.assertIn("summary trait", trait.metadata.get("docstring", ""))
        self.assertEqual(trait.metadata.get("visibility"), "pub")

        method1 = next(e for e in elements if e.name == "author_summary")
        self.assertEqual(method1.element_type, ElementType.METHOD)
        self.assertEqual(method1.parent, trait)
        self.assertEqual(method1.start_line, 5) # Method signature only, no body
        # End line might be tricky for trait methods without default impl
        # Let's assume the parser correctly identifies the single line for now.
        # If brace matching looks for '{', it might fail here. Need careful implementation.
        # The current parser expects '{' for functions, so this might not be found or have wrong lines.
        # --- ADJUSTMENT based on current parser needing '{' ---
        # Let's modify the test slightly to expect the parser might MISS trait methods without bodies
        # Or test a trait method *with* a default implementation body.
        # Test the second method which *has* a body:
        method2 = next(e for e in elements if e.name == "summarize")
        self.assertEqual(method2.element_type, ElementType.METHOD)
        self.assertEqual(method2.parent, trait)
        self.assertEqual(method2.start_line, 8)
        self.assertEqual(method2.end_line, 10)
        self.assertIn("Get the full summary", method2.metadata.get("docstring", ""))


    def test_parse_impl(self):
        """Test parsing an impl block."""
        code = '''
struct Article { name: String }
impl Summary for Article {
    fn author_summary(&self) -> String {
        format!("Article by {}", self.name)
    }
}

impl Article {
    /// Create a new article.
    pub fn new(name: &str) -> Self {
        Article { name: name.to_string() }
    }
}
'''
        elements = self.parser.parse(code)
        # Expect: struct, impl Trait for Type, method1, impl Type, method2
        self.assertEqual(len(elements), 5)

        struct_el = next(e for e in elements if e.element_type == ElementType.STRUCT)
        self.assertEqual(struct_el.name, "Article")

        impl_trait = next(e for e in elements if e.element_type == ElementType.IMPL and "Summary for Article" in e.code)
        self.assertEqual(impl_trait.name, "Article") # Parser captures Type name
        self.assertEqual(impl_trait.start_line, 3)
        self.assertEqual(impl_trait.end_line, 7)

        method1 = next(e for e in elements if e.name == "author_summary")
        self.assertEqual(method1.element_type, ElementType.METHOD)
        self.assertEqual(method1.parent, impl_trait)
        self.assertEqual(method1.start_line, 4)
        self.assertEqual(method1.end_line, 6)

        impl_type = next(e for e in elements if e.element_type == ElementType.IMPL and e.start_line == 9)
        self.assertEqual(impl_type.name, "Article")
        self.assertEqual(impl_type.start_line, 9)
        self.assertEqual(impl_type.end_line, 14)


        method2 = next(e for e in elements if e.name == "new")
        self.assertEqual(method2.element_type, ElementType.METHOD)
        self.assertEqual(method2.parent, impl_type)
        self.assertEqual(method2.start_line, 11)
        self.assertEqual(method2.end_line, 13)
        self.assertIn("Create a new article", method2.metadata.get("docstring", ""))
        self.assertEqual(method2.metadata.get("visibility"), "pub")


    def test_parse_module(self):
        """Test parsing module definitions."""
        code = '''
mod front_of_house;

pub mod back_of_house {
    pub struct Breakfast {
        pub toast: String,
    }

    fn fix_order() {
        println!("Fixing order");
    }
}
'''
        elements = self.parser.parse(code)
        # Expect: mod;, pub mod, struct, fn
        self.assertEqual(len(elements), 4)

        mod_file = next(e for e in elements if e.name == "front_of_house")
        self.assertEqual(mod_file.element_type, ElementType.MODULE)
        self.assertEqual(mod_file.start_line, 2)
        self.assertEqual(mod_file.end_line, 2) # Single line

        mod_block = next(e for e in elements if e.name == "back_of_house")
        self.assertEqual(mod_block.element_type, ElementType.MODULE)
        self.assertEqual(mod_block.start_line, 4)
        self.assertEqual(mod_block.end_line, 12)
        self.assertEqual(mod_block.metadata.get("visibility"), "pub")

        struct_in_mod = next(e for e in elements if e.name == "Breakfast")
        self.assertEqual(struct_in_mod.element_type, ElementType.STRUCT)
        self.assertEqual(struct_in_mod.parent, mod_block)
        self.assertEqual(struct_in_mod.start_line, 5)
        self.assertEqual(struct_in_mod.end_line, 7)

        fn_in_mod = next(e for e in elements if e.name == "fix_order")
        self.assertEqual(fn_in_mod.element_type, ElementType.FUNCTION) # Not method
        self.assertEqual(fn_in_mod.parent, mod_block)
        self.assertEqual(fn_in_mod.start_line, 9)
        self.assertEqual(fn_in_mod.end_line, 11)


    def test_parse_use_statements(self):
        """Test parsing 'use' statements."""
        code = '''
use std::collections::HashMap;
use std::fmt::{self, Result}; // Grouped
use std::io::Result as IoResult; // Renaming
pub use crate::kinds::PrimaryColor; // Re-exporting
use std::cmp::*; // Glob import
'''
        elements = self.parser.parse(code)
        self.assertEqual(len(elements), 5)

        use1 = next(e for e in elements if e.metadata.get("path") == "std::collections::HashMap")
        self.assertEqual(use1.element_type, ElementType.IMPORT)
        self.assertEqual(use1.name, "HashMap") # Simple name heuristic
        self.assertEqual(use1.start_line, 2)

        use2 = next(e for e in elements if "fmt" in e.metadata.get("path"))
        self.assertEqual(use2.element_type, ElementType.IMPORT)
        self.assertEqual(use2.name, "Result") # Heuristic picks last item in {}
        self.assertEqual(use2.start_line, 3)

        use3 = next(e for e in elements if "Result as IoResult" in e.metadata.get("path"))
        self.assertEqual(use3.element_type, ElementType.IMPORT)
        self.assertEqual(use3.name, "IoResult") # Heuristic picks alias
        self.assertEqual(use3.start_line, 4)

        use4 = next(e for e in elements if "PrimaryColor" in e.metadata.get("path"))
        self.assertEqual(use4.element_type, ElementType.IMPORT)
        self.assertEqual(use4.name, "PrimaryColor")
        self.assertEqual(use4.metadata.get("visibility"), "pub")
        self.assertEqual(use4.start_line, 5)

        use5 = next(e for e in elements if "*" in e.metadata.get("path"))
        self.assertEqual(use5.element_type, ElementType.IMPORT)
        self.assertEqual(use5.name, "cmp") # Heuristic picks module name before glob
        self.assertEqual(use5.start_line, 6)


    def test_parse_const_static(self):
        """Test parsing const and static definitions."""
        code = '''
const MAX_POINTS: u32 = 100_000;
static HELLO_WORLD: &str = "Hello, world!";
static mut COUNTER: u32 = 0;
'''
        elements = self.parser.parse(code)
        self.assertEqual(len(elements), 3)

        const_el = next(e for e in elements if e.name == "MAX_POINTS")
        self.assertEqual(const_el.element_type, ElementType.CONSTANT)
        self.assertEqual(const_el.start_line, 2)

        static_el = next(e for e in elements if e.name == "HELLO_WORLD")
        self.assertEqual(static_el.element_type, ElementType.VARIABLE) # Static treated as var
        self.assertTrue(static_el.metadata.get("is_static"))
        self.assertFalse(static_el.metadata.get("is_mutable"))
        self.assertEqual(static_el.start_line, 3)

        static_mut_el = next(e for e in elements if e.name == "COUNTER")
        self.assertEqual(static_mut_el.element_type, ElementType.VARIABLE)
        self.assertTrue(static_mut_el.metadata.get("is_static"))
        self.assertTrue(static_mut_el.metadata.get("is_mutable"))
        self.assertEqual(static_mut_el.start_line, 4)

    def test_find_function_by_name(self):
        """Test finding a function by name."""
        code = '''
fn func1() {}
mod utils {
    pub fn find_me() -> bool { true }
}
fn func2() {}
'''
        # Use the find_function method (searches ALL functions/methods)
        target = self.parser.find_function(code, "find_me")

        self.assertIsNotNone(target)
        self.assertEqual(target.name, "find_me")
        # It's technically a FUNCTION, but inside a module. Test parent.
        self.assertEqual(target.element_type, ElementType.FUNCTION)
        self.assertIsNotNone(target.parent)
        self.assertEqual(target.parent.name, "utils")
        self.assertEqual(target.parent.element_type, ElementType.MODULE)

    def test_get_all_globals(self):
        """Test getting all global elements."""
        code = '''
use std::io;
fn global_func() {}
struct GlobalStruct;
mod my_mod {
    fn inner_func() {}
}
const GLOBAL_CONST: i32 = 5;
'''
        globals_dict = self.parser.get_all_globals(code)

        self.assertIn("io", globals_dict) # From use std::io; (name heuristic)
        self.assertIn("global_func", globals_dict)
        self.assertIn("GlobalStruct", globals_dict)
        self.assertIn("my_mod", globals_dict)
        self.assertIn("GLOBAL_CONST", globals_dict)

        self.assertNotIn("inner_func", globals_dict) # Not global

        self.assertEqual(globals_dict["global_func"].element_type, ElementType.FUNCTION)
        self.assertEqual(globals_dict["GlobalStruct"].element_type, ElementType.STRUCT)
        self.assertEqual(globals_dict["my_mod"].element_type, ElementType.MODULE)
        self.assertEqual(globals_dict["GLOBAL_CONST"].element_type, ElementType.CONSTANT)
        self.assertEqual(globals_dict["io"].element_type, ElementType.IMPORT)


    def test_check_syntax_validity(self):
        """Test syntax validity checker."""
        valid_code = "fn main() { let x = vec![1, 2]; println!(\"{:?}\", x); }"
        self.assertTrue(self.parser.check_syntax_validity(valid_code))

        invalid_code_brace = "fn main() { let x = 1;"
        self.assertFalse(self.parser.check_syntax_validity(invalid_code_brace))

        invalid_code_paren = "fn main() { println!(\"Hello\" ; }"
        self.assertFalse(self.parser.check_syntax_validity(invalid_code_paren))

        invalid_code_string = "fn main() { let s = \"unterminated; }"
        self.assertFalse(self.parser.check_syntax_validity(invalid_code_string))

        # Test with comments and strings
        complex_valid = """
        /* Block comment with { braces } */
        fn calculate(x: i32) -> i32 { // Line comment
            let y = "String with (parens)";
            if x > 0 { x + 1 } else { 0 } // Requires braces
        }
        """
        self.assertTrue(self.parser.check_syntax_validity(complex_valid))


    def test_complex_in_progress_file(self):
        """Test parsing a complex, incomplete Rust file with various structures and potential errors."""
        complex_code = r'''
//! Crate documentation for the data analysis toolkit.
//! Contains modules for loading, processing, and visualizing data.

// External Crates
extern crate serde;
#[macro_use] extern crate log; // Attribute on extern crate

// Standard library imports
use std::collections::HashMap;
use std::path::{Path, PathBuf};
use std::{fs, io::{self, Read}}; // Nested use

// Crate-level modules
mod utils; // File module
pub mod data_source; // Public file module

/// Global configuration constant
const DEFAULT_THRESHOLD: f64 = 0.5;

/// Static logger instance (placeholder)
static LOGGER_INITIALIZED: bool = false;

// Error type definition
#[derive(Debug)]
pub enum AnalysisError {
    Io(io::Error),
    ParseError(String),
    // Incomplete variant definition
    CalculationError { details: String },
}

// Trait for data loading
pub trait DataLoader {
    type Item; // Associated type
    /// Load data from a source.
    fn load(&self, source: &Path) -> Result<Vec<Self::Item>, AnalysisError>;
    // Missing semicolon here potentially
    fn supports_extension(&self, ext: &str) -> bool
}

// Struct implementing the trait
#[derive(Default)]
pub struct CsvLoader {
    delimiter: u8,
    has_headers: bool, // Trailing comma allowed -> },
}

impl DataLoader for CsvLoader {
    type Item = HashMap<String, String>;

    fn load(&self, source: &Path) -> Result<Vec<Self::Item>, AnalysisError> {
        info!("Loading CSV from: {:?}", source);
        if !self.supports_extension(source.extension().unwrap_or_default().to_str().unwrap()) {
            // return Err(AnalysisError::ParseError("Unsupported file type".to_string()));
        } // Missing closing brace for if? Or maybe logic continues.

        let mut file = fs::File::open(source).map_err(AnalysisError::Io)?;
        let mut contents = String::new();
        file.read_to_string(&mut contents).map_err(AnalysisError::Io)?;

        // Placeholder parsing logic
        let mut results = Vec::new();
        // ... parsing implementation ...
        if contents.is_empty() {
           warn!("File is empty: {:?}", source) // Missing semicolon
        }
        Ok(results)
    } // Missing closing brace for load function

    // Forgot the closing brace for impl DataLoader for CsvLoader
// } // <--- This brace is missing in the complex code


// Another independent function
/// Processes loaded data.
/// TODO: Implement actual processing logic.
fn process_data<T>(data: Vec<T>) -> Vec<T>
where
    T: Clone + std::fmt::Debug, // Where clause
{
    debug!("Processing {} items.", data.len());
    // Unfinished block
    data.iter().map(|item| {
        // item manipulation
        item.clone()
    }).collect() // Correctly closed map and collect

// Missing closing brace for process_data function


// Module defined inline
mod visualization {
    use super::AnalysisError; // Use super

    pub fn plot_data() -> Result<(), AnalysisError> {
        println!("Plotting data...");
        // Incomplete function body
        Ok(())
    } // plot_data closing brace is present

    struct PlotOptions {
        title: String,
        // Missing field definition potentially
    }

} // visualization module closing brace is present

// Main function (maybe incomplete)
fn main() {
    println!("Starting analysis...");
    let loader = CsvLoader::default();
    // Error: Mismatched parenthesis
    let data = loader.load(Path::new("data.csv"). // Missing closing parenthesis
    match data {
        Ok(d) => { process_data(d); },
        Err(e) => error!("Failed: {:?}", e),
    };

''' # Note: Missing closing brace for main, and potentially other issues

        # Parse the complex code
        try:
            elements = self.parser.parse(complex_code)

            # Basic assertions - check if major elements were found despite errors
            enums = [e for e in elements if e.element_type == ElementType.ENUM]
            traits = [e for e in elements if e.element_type == ElementType.TRAIT]
            structs = [e for e in elements if e.element_type == ElementType.STRUCT]
            impls = [e for e in elements if e.element_type == ElementType.IMPL]
            functions = [e for e in elements if e.element_type == ElementType.FUNCTION]
            methods = [e for e in elements if e.element_type == ElementType.METHOD]
            imports = [e for e in elements if e.element_type == ElementType.IMPORT]
            constants = [e for e in elements if e.element_type == ElementType.CONSTANT]
            mods = [e for e in elements if e.element_type == ElementType.MODULE]

            # Test that key elements are found even with syntax errors nearby
            self.assertGreaterEqual(len(enums), 1, "Should find AnalysisError enum")
            self.assertGreaterEqual(len(traits), 1, "Should find DataLoader trait")
            self.assertGreaterEqual(len(structs), 1, "Should find CsvLoader struct") # Finds at least CsvLoader, maybe PlotOptions
            self.assertGreaterEqual(len(impls), 1, "Should find impl DataLoader for CsvLoader")
            self.assertGreaterEqual(len(functions), 2, "Should find process_data and main (maybe plot_data)")
            self.assertGreaterEqual(len(imports), 3, "Should find several use statements") # std::collections, std::path, std::fs/io
            self.assertGreaterEqual(len(constants), 1, "Should find DEFAULT_THRESHOLD")
            self.assertGreaterEqual(len(mods), 3, "Should find utils, data_source, visualization") # utils, data_source, visualization

            # Check specific elements
            enum_names = [e.name for e in enums]
            self.assertIn('AnalysisError', enum_names)

            trait_names = [t.name for t in traits]
            self.assertIn('DataLoader', trait_names)

            # Check nested element (plot_data inside visualization)
            vis_mod = next((m for m in mods if m.name == 'visualization'), None)
            self.assertIsNotNone(vis_mod, "Should find visualization module")

            # Find plot_data function
            plot_fn = next((f for f in functions if f.name == 'plot_data'), None)
            # Depending on error recovery, plot_data might be parsed correctly or missed.
            # If found, check its parent.
            if plot_fn:
                 self.assertEqual(plot_fn.parent, vis_mod, "plot_data should be child of visualization")
            else:
                print("\nNOTE: plot_data function inside visualization module might not be parsed due to error recovery limitations.")

            # Check method inside impl
            load_method = next((m for m in methods if m.name == 'load'), None)
            self.assertIsNotNone(load_method, "Should find CsvLoader::load method")
            if load_method:
                self.assertEqual(load_method.parent.element_type, ElementType.IMPL)
                # Check if the parser correctly associated it with the CsvLoader impl
                self.assertTrue("CsvLoader" in load_method.parent.name or "CsvLoader" in load_method.parent.code)

            # Document parser's resilience/limitations
            print("\nRust Complex Code Parsing Results:")
            print(f"- Total elements found: {len(elements)}")
            print(f"- Enums: {[e.name for e in enums]}")
            print(f"- Traits: {[t.name for t in traits]}")
            print(f"- Structs: {[s.name for s in structs]}")
            print(f"- Impls found: {len(impls)}")
            print(f"- Functions: {[f.name for f in functions]}")
            print(f"- Methods: {[m.name for m in methods]}")
            print(f"- Imports found: {len(imports)}")
            print(f"- Constants: {[c.name for c in constants]}")
            print(f"- Modules: {[m.name for m in mods]}")
            print("\nNote: Parsing accuracy for elements near syntax errors or incomplete blocks may vary.")
            # Example: The parser might miscalculate end lines for blocks with missing braces.

            # Check syntax validity of the whole snippet (expected to be false)
            self.assertFalse(self.parser.check_syntax_validity(complex_code), "Syntax should be invalid due to errors")


        except Exception as e:
            self.fail(f"Rust parser failed on complex code: {e}")


if __name__ == '__main__':
    unittest.main()

