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