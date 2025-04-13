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