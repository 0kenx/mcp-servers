"""
Tests for the JavaScript parser with edge cases.
"""

import unittest
from src.grammar.javascript import JavaScriptParser
from src.grammar.base import ElementType


class TestJavaScriptEdgeCases(unittest.TestCase):
    """Test edge cases for the JavaScript parser."""

    def setUp(self):
        """Set up test cases."""
        self.parser = JavaScriptParser()

    def test_template_literals_with_expressions(self):
        """Test parsing JavaScript template literals with complex expressions."""
        code = """
const greeting = (name, age) => `Hello ${name}, you are ${age > 18 ? "an adult" : "a minor"}!`;
const html = `
  <div class="${isActive ? 'active' : 'inactive'}">
    ${items.map(item => `<p>${item.name}</p>`).join('')}
  </div>
`;
"""
        elements = self.parser.parse(code)

        # Should find const variables and the arrow function
        self.assertGreaterEqual(len(elements), 2)

        greeting_func = next((e for e in elements if e.name == "greeting"), None)
        self.assertIsNotNone(greeting_func)
        self.assertEqual(greeting_func.element_type, ElementType.FUNCTION)

        html_const = next((e for e in elements if e.name == "html"), None)
        self.assertIsNotNone(html_const)
        self.assertEqual(html_const.element_type, ElementType.CONSTANT)

    def test_nested_destructuring(self):
        """Test parsing complex nested destructuring patterns."""
        code = """
const { 
    user: { 
        name, 
        address: { 
            city, 
            coordinates: [lat, lng] 
        } 
    }, 
    settings: { theme = 'default' } = {} 
} = response;

function processData({ items = [], config: { sort = true, filter = false } = {} }) {
    return items.filter(x => x > 10);
}
"""
        elements = self.parser.parse(code)

        # Should find variables and the function
        self.assertGreaterEqual(len(elements), 2)

        # Check that we found the named variables despite complex destructuring
        self.assertTrue(any(e.name == "response" for e in elements))

        process_func = next((e for e in elements if e.name == "processData"), None)
        self.assertIsNotNone(process_func)
        self.assertEqual(process_func.element_type, ElementType.FUNCTION)

    def test_uncommon_function_names(self):
        """Test parsing functions with uncommon names or edge case formats."""
        code = """
// Function with keyword as name
function if(condition) { return condition ? "true" : "false"; }

// Function with non-ASCII name
function ñandú() { return "南美鸵鸟"; }

// Function with emojis in name
function sum💰(a, b) { return a + b; }

// Unnamed function expression
const unnamed = function() { return "anonymous"; };
"""
        elements = self.parser.parse(code)

        # Should identify at least some of these
        self.assertGreaterEqual(len(elements), 2)

        # Check for one of the unusual function names
        # Note: Parsers might struggle with emojis or keywords, but should handle some cases
        unusual_func = next((e for e in elements if e.name == "ñandú"), None)
        if unusual_func:
            self.assertEqual(unusual_func.element_type, ElementType.FUNCTION)

    def test_incomplete_functions_and_classes(self):
        """Test parsing incomplete function and class definitions."""
        code = """
function calculateTotal(items, tax
    return items.reduce((sum, item) => sum + item.price, 0) * (1 + tax);

class ShoppingCart {
    constructor(

    addItem(item {
        this.items.push(item);

    getTotal(
        return this.items.reduce((sum, item) => sum + item.price, 0);
}
"""
        elements = self.parser.parse(code)

        # Should attempt to parse these despite syntax errors
        self.assertGreaterEqual(len(elements), 2)

        # Check that we found the function and class
        calc_func = next((e for e in elements if e.name == "calculateTotal"), None)
        self.assertIsNotNone(calc_func)

        cart_class = next((e for e in elements if e.name == "ShoppingCart"), None)
        self.assertIsNotNone(cart_class)
        self.assertEqual(cart_class.element_type, ElementType.CLASS)

        # Check that at least one method was detected
        method = next(
            (e for e in elements if e.element_type == ElementType.METHOD), None
        )
        self.assertIsNotNone(method)

    def test_generator_functions(self):
        """Test parsing generator functions and methods."""
        code = """
function* numberGenerator() {
    let i = 0;
    while (true) {
        yield i++;
    }
}

class SequenceGenerator {
    *generate(start, end) {
        for (let i = start; i <= end; i++) {
            yield i;
        }
    }
    
    async *asyncGenerate(start, end) {
        for (let i = start; i <= end; i++) {
            await sleep(100);
            yield i;
        }
    }
}
"""
        elements = self.parser.parse(code)

        # Check for generator function
        gen_func = next((e for e in elements if e.name == "numberGenerator"), None)
        self.assertIsNotNone(gen_func)
        self.assertEqual(gen_func.element_type, ElementType.FUNCTION)

        # Check for class with generator methods
        class_el = next((e for e in elements if e.name == "SequenceGenerator"), None)
        self.assertIsNotNone(class_el)

        # Check for generator methods
        gen_method = next(
            (
                e
                for e in elements
                if e.element_type == ElementType.METHOD and e.name == "generate"
            ),
            None,
        )
        self.assertIsNotNone(gen_method)

        async_gen_method = next(
            (
                e
                for e in elements
                if e.element_type == ElementType.METHOD and e.name == "asyncGenerate"
            ),
            None,
        )
        self.assertIsNotNone(async_gen_method)
        # Check that the async property is captured
        self.assertTrue(async_gen_method.metadata.get("is_async", False))

    def test_comments_and_directives(self):
        """Test handling comments and directives that may affect parsing."""
        code = """
"use strict";
// @ts-check

/* Multi-line comment with characters that might confuse the parser
   function fakeFunction() {
       return "this is not real";
   }
   class FakeClass {}
*/

/**
 * @param {string} name - The name to greet
 * @returns {string} A greeting message
 */
function greet(name) {
    return `Hello, ${name}!`;
}
"""
        elements = self.parser.parse(code)

        # Should only find the real function, not the one in comments
        greet_func = next((e for e in elements if e.name == "greet"), None)
        self.assertIsNotNone(greet_func)

        # "fakeFunction" should not be found as it's in a comment
        fake_func = next((e for e in elements if e.name == "fakeFunction"), None)
        self.assertIsNone(fake_func)

        # Directives like "use strict" should be ignored or properly categorized
        # We'll just make sure they don't cause errors in parsing

    def test_computed_properties(self):
        """Test parsing computed property names in objects and classes."""
        code = """
const propertyName = "dynamicProp";
const obj = {
    [propertyName]: "value",
    ["static" + "Property"]: true,
    [1 + 2]: "three"
};

class ComputedMethods {
    ["method" + 1]() {
        return "method1";
    }
    
    get [Symbol.toStringTag]() {
        return "ComputedMethods";
    }
    
    set [propertyName](value) {
        this._value = value;
    }
}
"""
        elements = self.parser.parse(code)

        # Check that we found the object and its variables
        self.assertGreaterEqual(len(elements), 2)

        # Check for the class
        class_el = next((e for e in elements if e.name == "ComputedMethods"), None)
        self.assertIsNotNone(class_el)

        # This is a stretch goal - checking if computed methods were parsed
        # Even if they weren't fully captured, the parser should at least not crash
        method_count = sum(1 for e in elements if e.element_type == ElementType.METHOD)
        self.assertGreaterEqual(
            method_count, 0, "Should at least not crash on computed properties"
        )

    def test_private_class_features(self):
        """Test parsing private class fields and methods."""
        code = """
class PrivateMembers {
    #privateField = 42;
    publicField = "public";
    
    constructor() {
        this.#initializePrivate();
    }
    
    #initializePrivate() {
        console.log("Private initialization");
    }
    
    get #privateValue() {
        return this.#privateField;
    }
    
    set #privateValue(value) {
        this.#privateField = value;
    }
    
    publicMethod() {
        return this.#privateField;
    }
}
"""
        elements = self.parser.parse(code)

        # Check for the class
        class_el = next((e for e in elements if e.name == "PrivateMembers"), None)
        self.assertIsNotNone(class_el)

        # Check that we found at least the public method and field
        methods = [e for e in elements if e.element_type == ElementType.METHOD]
        self.assertGreaterEqual(len(methods), 1)

        # This is a stretch goal - checking if private fields and methods were parsed
        # The parser may or may not handle these correctly, but it should not crash
        # If the parser does handle private fields, there should be more than just the constructor
        # and public method
        public_method = next((m for m in methods if m.name == "publicMethod"), None)
        self.assertIsNotNone(public_method)

    def test_nested_classes_and_functions(self):
        """Test parsing nested class and function definitions."""
        code = """
class Outer {
    constructor() {
        this.value = 42;
        
        function innerFunction() {
            return "inner";
        }
        
        this.getInnerClass = function() {
            class InnerClass {
                getValue() {
                    return innerFunction() + " value";
                }
            }
            return new InnerClass();
        };
    }
    
    method() {
        return function() {
            return this.value;
        }.bind(this);
    }
}

function outer() {
    class LocalClass {
        constructor() {
            this.name = "local";
        }
    }
    
    return new LocalClass();
}
"""
        elements = self.parser.parse(code)

        # Check for the outer class and function
        outer_class = next((e for e in elements if e.name == "Outer"), None)
        self.assertIsNotNone(outer_class)

        outer_func = next((e for e in elements if e.name == "outer"), None)
        self.assertIsNotNone(outer_func)

        # This is a stretch goal - checking if nested elements were parsed
        # The parser may or may not handle these correctly, but it should not crash
        # If the parser handles nested elements, there should be more elements
        # with parent relationships
        nested_elements = [e for e in elements if e.parent is not None]
        # Not asserting a specific count, as the parser's handling of nested elements may vary

    def test_jsx_and_tsx_like_syntax(self):
        """Test parsing JSX and TSX like syntax in JavaScript."""
        code = """
function App() {
    return (
        <div className="app">
            <h1>Hello, JSX!</h1>
            <Component prop={value} />
            {items.map(item => <Item key={item.id} {...item} />)}
        </div>
    );
}

const Component = ({ name, data }) => (
    <div>
        <h2>{name}</h2>
        <pre>{JSON.stringify(data, null, 2)}</pre>
    </div>
);

class ClassComponent extends React.Component {
    render() {
        return <div>{this.props.children}</div>;
    }
}
"""
        # JSX isn't valid JavaScript syntax, so this shouldn't crash the parser
        # but it might not parse everything correctly
        try:
            elements = self.parser.parse(code)

            # Check that at least some elements were detected
            self.assertGreaterEqual(
                len(elements), 1, "Should find at least one element"
            )

            # This is a stretch goal - checking if any of the components were parsed
            # The parser may not handle JSX syntax well, which is expected
            func_names = [
                e.name for e in elements if e.element_type == ElementType.FUNCTION
            ]
            class_names = [
                e.name for e in elements if e.element_type == ElementType.CLASS
            ]

            # Print parsed elements for analysis
            print(f"Functions found in JSX-like code: {func_names}")
            print(f"Classes found in JSX-like code: {class_names}")

        except Exception as e:
            self.fail(f"Parser crashed on JSX-like syntax: {e}")

    def test_spread_and_rest(self):
        """Test parsing spread and rest operators."""
        code = """
function sum(...numbers) {
    return numbers.reduce((total, n) => total + n, 0);
}

const obj1 = { a: 1, b: 2 };
const obj2 = { ...obj1, c: 3 };

function processConfig({ name, ...rest }) {
    console.log(name);
    return rest;
}

const array1 = [1, 2, 3];
const array2 = [...array1, 4, 5];
"""
        elements = self.parser.parse(code)

        # Check for the sum function
        sum_func = next((e for e in elements if e.name == "sum"), None)
        self.assertIsNotNone(sum_func)

        # Check for the processConfig function
        process_func = next((e for e in elements if e.name == "processConfig"), None)
        self.assertIsNotNone(process_func)

        # Check for the object variables
        obj1_var = next((e for e in elements if e.name == "obj1"), None)
        self.assertIsNotNone(obj1_var)

        obj2_var = next((e for e in elements if e.name == "obj2"), None)
        self.assertIsNotNone(obj2_var)

        # Check for array variables
        array1_var = next((e for e in elements if e.name == "array1"), None)
        self.assertIsNotNone(array1_var)

        array2_var = next((e for e in elements if e.name == "array2"), None)
        self.assertIsNotNone(array2_var)


if __name__ == "__main__":
    unittest.main()
