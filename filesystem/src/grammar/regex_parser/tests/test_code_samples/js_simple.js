/**
 * A simple JavaScript program demonstrating basic language features
 * with some edge cases for parser testing
 */

// Unusual variable names and assignments
const $_ = \"parser\";
let _$ = 42;
var test123 = null;

// Template literals with expressions and escape sequences
const complexString = `Testing ${$_} with \\${escaped} and ${_$ + 5}`;

// Arrow functions with different syntaxes
const simpleFn = x => x * 2;
const multiParam = (a, b) => { 
  return a + b; 
};

// Function with default parameters and rest operator
function testFunction(param = 'default', ...rest) {
  // Unusual conditional
  if (param === 'default') return [...rest, param];
  
  // Labeled statement with break
  loop: for (let i = 0; i < 3; i++) {
    if (i === 1) break loop;
    console.log(i);
  }
  
  return rest;
}

// Self-invoking function with comma operator -> NOT DETECTED
(function(x, y) {
  console.log(x, y);
})(1, 2, (3, 4));

// Object with computed property and method
const obj = {
  [_$ + 'key']: 'value',
  method() { return this[_$ + 'key']; }
};

// Export statement
export { simpleFn, testFunction };

