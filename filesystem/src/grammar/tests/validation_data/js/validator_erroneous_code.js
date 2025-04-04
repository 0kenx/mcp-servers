/**
 * JavaScript validation file with syntax errors to test parser robustness
 */

// Syntax error: missing semicolon in a context where it matters
const x = 5
const y = 10;

// Syntax error: using undefined variable
console.log(undefinedVariable);

// Syntax error: mismatched brackets
function brokenFunction() {
  return {
    name: "test",
    value: 42
  ];
}

// Syntax error: invalid property name
const obj = {
  @invalid: true,
  'valid': true
};

// Syntax error: reserved word as variable
const class = "some value";

// Syntax error: assignment in conditional
if (x = 5) {
  console.log("This will always be true");
}

// Syntax error: using var after declaration
const z = 10;
var z = 20;

// Syntax error: unexpected token
const arr = [1, 2, 3,];,

// Syntax error: double comma in array
const badArray = [1, 2,, 3];

// Syntax error: missing closing quote
const stringError = "Unclosed string;

// Syntax error: invalid escape sequence
const escapeError = "Invalid escape: \z";

// Syntax error: octal literals not allowed in strict mode
"use strict";
const octalError = 0765;

// Syntax error: duplicate parameter names
function duplicateParams(a, a) {
  return a;
}

// Syntax error: unexpected line break in string
const multilineString = "This string has
a line break";

// Syntax error: invalid regular expression
const regex = /[a-z/;

// Syntax error: invalid hex number
const hex = 0xZ123;

// Syntax error: with statement in strict mode
"use strict";
with (Math) {
  console.log(PI);
}

// Syntax error: invalid labeled statement
test: const labelVar = 5;

// Syntax error: invalid use of await outside async function
function notAsync() {
  const data = await fetch('/api/data');
  return data;
}

// Syntax error: illegal break statement
function illegalBreak() {
  if (true) {
    break;
  }
}

// Syntax error: invalid delete
delete x;

// Syntax error: invalid for-loop initialization
for (var i = 0, j = 10; i < j i++) {
  console.log(i);
}

// Syntax error: missing colon in object
const missingColon = {
  prop1 "value",
  prop2: "value2"
};

// Syntax error: function declaration without name
function() {
  return "anonymous";
}

// Syntax error: trailing comma in object literal (in older JS)
const oldStyleObject = {
  prop1: "value1",
  prop2: "value2",
};

// Syntax error: calling with wrong this context
console.log.call();

// Multiple errors in one block
function multipleErrors() {
  const x = {;
  return [1, 2,;
  if true {
    console.log("error");
  }
} 