"""
Tests for the JavaScript language parser.
"""

import unittest
from javascript import JavaScriptParser
from base import ElementType


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

    def test_complex_in_progress_file(self):
        """Test parsing a complex, incomplete JavaScript file with various structures and errors."""
        # This test simulates a large, messy file that's being actively worked on
        complex_code = '''
// DataAnalytics.js - Work in Progress
// A complex JavaScript application for data analytics

import React from 'react';
import { useState, useEffect, useMemo } from 'react';
import axios from 'axios';
import * as d3 from 'd3';
import _ from 'lodash';

// Configuration constants
const API_URL = 'https://api.example.com/data';
const MAX_RETRIES = 3;
const TIMEOUT_MS = 5000;
const DEBUG = true;

// Type definitions (using JSDoc for type hints)
/**
 * @typedef {Object} DataPoint
 * @property {string} id - Unique identifier
 * @property {string} label - Human readable label
 * @property {number} value - Numeric value
 * @property {Date} timestamp - When this data was recorded
 */

/**
 * @typedef {Object} AnalyticsConfig
 * @property {string} endpoint - API endpoint
 * @property {number} refreshInterval - Data refresh interval in ms
 * @property {string[]} metrics - List of metrics to track
 */

// Utility functions
/**
 * Format a number with commas for thousands
 * @param {number} num - Number to format
 * @return {string} Formatted number
 */
const formatNumber = (num) => {
    return num.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ",");
};

/**
 * Format a date for display
 * @param {Date} date - Date to format
 * @return {string} Formatted date
 */
function formatDate(date) {
    return new Date(date).toLocaleDateString('en-US', {
        year: 'numeric',
        month: 'short',
        day: 'numeric'
    });
}

// Error with missing closing parenthesis in function declaration
function calculateMovingAverage(data, window {
    if (!Array.isArray(data)) {
        throw new Error('Data must be an array');
    }
    
    const result = [];
    for (let i = 0; i < data.length; i++) {
        const start = Math.max(0, i - window + 1);
        const end = i + 1;
        const subset = data.slice(start, end);
        const sum = subset.reduce((acc, val) => acc + val, 0);
        result.push(sum / subset.length);
    }
    
    return result;
}

/**
 * Data analytics class for processing and visualizing data
 */
class DataAnalytics {
    /**
     * Create a new analytics instance
     * @param {AnalyticsConfig} config - Configuration object
     */
    constructor(config) {
        this.config = config;
        this.data = [];
        this.isLoading = false;
        this.error = null;
        this.retries = 0;
    }
    
    /**
     * Fetch data from the API
     * @return {Promise<DataPoint[]>} Fetched data points
     */
    async fetchData() {
        this.isLoading = true;
        try {
            const response = await axios.get(this.config.endpoint, {
                timeout: TIMEOUT_MS
            });
            
            this.data = response.data.map(item => ({
                ...item,
                timestamp: new Date(item.timestamp)
            }));
            
            this.retries = 0;
            return this.data;
        } catch (error) {
            this.error = error;
            if (this.retries < MAX_RETRIES) {
                this.retries++;
                // Retry with exponential backoff
                const backoff = 1000 * Math.pow(2, this.retries);
                console.warn(`Retrying in ${backoff}ms... (${this.retries}/${MAX_RETRIES})`);
                await new Promise(resolve => setTimeout(resolve, backoff));
                return this.fetchData();
            }
            throw error;
        } finally {
            this.isLoading = false;
        }
    }
    
    /**
     * Process the data through various transformations
     * @param {string[]} metrics - Metrics to calculate
     * @return {Object} Processed results
     */
    processData(metrics = this.config.metrics) {
        if (!this.data.length) {
            return {};
        }
        
        const results = {};
        
        // Calculate statistics for each metric
        metrics.forEach(metric => {
            const values = this.data.map(d => d[metric]).filter(v => !isNaN(v));
            
            if (!values.length) {
                results[metric] = { available: false };
                return;
            }
            
            const sorted = [...values].sort((a, b) => a - b);
            results[metric] = {
                available: true,
                count: values.length,
                sum: values.reduce((a, b) => a + b, 0),
                min: sorted[0],
                max: sorted[sorted.length - 1],
                mean: values.reduce((a, b) => a + b, 0) / values.length,
                median: sorted[Math.floor(sorted.length / 2)],
                // Error: missing closing bracket
                stdDev: Math.sqrt(
                    values.reduce((sq, n) => {
                        const diff = n - (values.reduce((a, b) => a + b, 0) / values.length);
                        return sq + diff * diff;
                    }, 0) / values.length
            };
        });
        
        return results;
    }
    
    // Method with indentation errors
  visualizeData(targetElement) {
    const chart = d3.select(targetElement);
      chart.selectAll('*').remove();
        if (!this.data.length) {
         return;
       }

    // Create visualization
    // Incomplete implementation
    const margin = {top: 20, right: 30, bottom: 30, left: 40};
    const width = 600 - margin.left - margin.right;
    const height = 400 - margin.top - margin.bottom;
    
    // Scale definitions with unbalanced braces and missing semicolons
    const x = d3.scaleTime()
        .domain(d3.extent(this.data, d => d.timestamp)
        .range([0, width])
        
    const y = d3.scaleLinear()
        .domain([0, d3.max(this.data, d => d.value))]  // Extra closing bracket
        .range([height, 0]);
  }
}

// React component for data visualization 
class DataVisualizer extends React.Component {
    constructor(props) {
        super(props);
        this.state = {
            loading: true,
            error: null,
            data: [],
            config: {
                endpoint: API_URL,
                refreshInterval: 60000,
                metrics: ['value', 'count', 'rate']
            }
        };
        this.chartRef = React.createRef();
        this.analytics = new DataAnalytics(this.state.config);
    }
    
    async componentDidMount() {
        try {
            // Load initial data
            const data = await this.analytics.fetchData();
            this.setState({ data, loading: false });
            
            // Set up refresh interval
            this.intervalId = setInterval(async () => {
                try {
                    const data = await this.analytics.fetchData();
                    this.setState({ data });
                } catch (error) {
                    console.error('Failed to refresh data:', error);
                }
            }, this.state.config.refreshInterval);
        } catch (error) {
            this.setState({ error, loading: false });
        }
    }
    
    componentDidUpdate(prevProps, prevState) {
        if (this.state.data !== prevState.data) {
            this.visualizeData();
        }
    }
    
    // Incomplete method implementation
    visualizeData() {
        if (this.chartRef.current && this.state.data.length) {
            this.analytics.visualizeData(this.chartRef.current);
        }
    }
    
    componentWillUnmount() {
        if (this.intervalId) {
            clearInterval(this.intervalId);
        }
    }
    
    // Missing render method
}

// Utility function with missing export
const debounce = (func, wait) => {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
};

// App initialization with syntax error (trailing comma in object)
 const initApp = () => {
    const container = document.getElementById('app');
    const app = new DataVisualizer({
        theme: 'light',
        showControls: true,
        autoRefresh: true,
    });
    
    // Not properly terminated
    return app
'''
    
        # Parse the complex code
        try:
            # Add debug prints to the JavaScript parser to show what it finds
            original_parse = self.parser.parse
            
            def debug_parse(self_parser, code):
                elements = original_parse(code)
                print("\nComplex JavaScript Parsing Results:")
                print(f"Total elements found: {len(elements)}")
                
                # Categorize elements
                imports = [e for e in elements if e.element_type == ElementType.IMPORT]
                functions = [e for e in elements if e.element_type == ElementType.FUNCTION]
                classes = [e for e in elements if e.element_type == ElementType.CLASS]
                methods = [e for e in elements if e.element_type == ElementType.METHOD]
                constants = [e for e in elements if e.element_type == ElementType.CONSTANT]
                variables = [e for e in elements if e.element_type == ElementType.VARIABLE]
                
                print(f"Imports found: {len(imports)} - {[i.name for i in imports]}")
                print(f"Functions found: {len(functions)} - {[f.name for f in functions]}")
                print(f"Classes found: {len(classes)} - {[c.name for c in classes]}")
                print(f"Methods found: {len(methods)} - {[m.name for m in methods]}")
                print(f"Constants found: {len(constants)} - {[c.name for c in constants]}")
                print(f"Variables found: {len(variables)} - {[v.name for v in variables]}")
                
                return elements
            
            # Temporarily replace the parse method for debugging
            self.parser.parse = lambda code: debug_parse(self.parser, code)
            
            # Parse the complex code
            elements = self.parser.parse(complex_code)
            
            # Restore the original parse method
            self.parser.parse = original_parse
            
            # Basic assertions
            # There should be at least some functions and classes identified
            functions = [e for e in elements if e.element_type == ElementType.FUNCTION]
            classes = [e for e in elements if e.element_type == ElementType.CLASS]
            constants = [e for e in elements if e.element_type == ElementType.CONSTANT]
            methods = [e for e in elements if e.element_type == ElementType.METHOD]
            
            # Test that key elements were found despite errors
            self.assertGreaterEqual(len(functions), 2)  # Should find at least 2 functions
            self.assertGreaterEqual(len(classes), 1)    # Should find at least 1 class
            self.assertGreaterEqual(len(constants), 2)  # Should find at least 2 constants
            
            # Test that specific elements were found
            function_names = [f.name for f in functions]
            self.assertIn('formatDate', function_names)
            
            class_names = [c.name for c in classes]
            self.assertIn('DataAnalytics', class_names)
            
            # Test that at least some methods were properly associated with their parent classes
            methods_with_parents = [m for m in methods if m.parent is not None]
            if methods_with_parents:
                # Check that at least one method has the correct parent
                has_correct_parent = any(m.parent.name == 'DataAnalytics' for m in methods_with_parents)
                self.assertTrue(has_correct_parent, "No methods were correctly associated with their parent class")
                
            # Test handling of bad syntax
            # The parser should continue despite syntax errors and extract valid elements
            if 'calculateMovingAverage' in function_names:
                # If it found the function with the syntax error, it should have detected the issue
                moving_avg_func = next(f for f in functions if f.name == 'calculateMovingAverage')
                self.assertFalse(self.parser.check_syntax_validity(moving_avg_func.code))
                
            # Document the parser's limitations
            print("\nParser Limitations:")
            print("- The JavaScript parser may skip some elements with syntax errors")
            print("- Nested elements like class methods may not be fully associated with their parents")
            print("- Complex nested structures might be partially detected")
            
        except Exception as e:
            self.fail(f"Parser failed to handle complex JavaScript code: {e}")

if __name__ == '__main__':
    unittest.main()
