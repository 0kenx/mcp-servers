// Empty function/class names
function () { }
class { }

// Unusual identifiers
function $special_func() { }
function _private() { }
function func123() { }

// Very long identifier
function thisIsAReallyReallyReallyReallyReallyReallyReallyReallyReallyReallyReallyReallyReallyReallyReallyReallyLongFunctionName() { }

// Non-ASCII identifiers
function áéíóú() { }
function 你好() { }
function λ() { }

// Keywords in comments that look like definitions
// This is not a real function:
// function fake() { }

// Preprocessor directives (in C-like languages)
#define function not_a_real_function() // Shouldn't match