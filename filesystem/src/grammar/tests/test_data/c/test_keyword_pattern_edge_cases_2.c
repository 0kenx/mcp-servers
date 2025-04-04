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