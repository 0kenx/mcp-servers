// Rust validation file with syntax errors to test parser robustness

// Error: Missing semicolon
fn missing_semicolon() -> i32 {
    let x = 5
    x + 1
}

// Error: Using a mutable variable without declaring it as mutable
fn mutability_error() {
    let x = 5;
    x = 10; // Error: cannot assign twice to immutable variable
}

// Error: Mismatched types
fn type_mismatch() -> i32 {
    "not an integer" // Error: expected i32, found &str
}

// Error: Undefined variable
fn undefined_variable() {
    println!("{}", nonexistent_variable);
}

// Error: Missing return type
fn missing_return_type() {
    42 // Error: missing return type for function
}

// Error: Extra token
struct ExtraToken {
    field: i32,
}; // Error: extra semicolon

// Error: Mismatched brackets
fn mismatched_brackets() {
    let values = vec![1, 2, 3); // Error: mismatched brackets
}

// Error: Incorrect lifetime usage
fn incorrect_lifetime<'a, 'b>(x: &'a str, y: &'b str) -> &'c str { // Error: undeclared lifetime
    x
}

// Error: Broken match pattern
fn broken_match(option: Option<i32>) -> i32 {
    match option {
        Some => 42, // Error: expected pattern, found identifier
        None => 0,
    }
}

// Error: Invalid struct field
struct InvalidField {
    let value: i32, // Error: expected identifier, found keyword
}

// Error: Comparing incomparable types
fn compare_error() -> bool {
    "string" == 42 // Error: can't compare &str and i32
}

// Error: Invalid method call
fn invalid_method() {
    let x = 5;
    x.nonexistent_method(); // Error: no method named `nonexistent_method`
}

// Error: Private field access
mod privacy_error {
    struct Private {
        private_field: i32,
    }
    
    fn access_outside() {
        let p = Private { private_field: 42 };
    }
}

fn access_error() {
    let p = privacy_error::Private { private_field: 42 }; // Error: private field
}

// Error: Missing trait implementation
trait Required {
    fn required_method(&self);
}

struct MissingImpl;

impl Required for MissingImpl {
    // Error: missing implementation for required method
}

// Error: Out of bounds array access with const
fn array_bounds() {
    let arr = [1, 2, 3];
    let value = arr[5]; // Error: index out of bounds
}

// Error: Invalid loop label
fn invalid_label() {
    'outer: for i in 0..5 {
        for j in 0..5 {
            break 'nonexistent; // Error: use of undeclared label
        }
    }
}

// Error: Type parameter used in function without being declared
fn undefined_type_param(value: T) -> T { // Error: use of undeclared type name
    value
}

// Error: Multiple incompatible trait bounds
fn incompatible_bounds<T: Clone + Copy + AsRef<str>>(value: T) { // Error: incompatible bounds
    // Can't be both str and have copy semantics
}

// Error: Invalid use of mut in parameter
fn invalid_mut(mut self) { // Error: invalid `mut` in function parameter
    // Only valid in impl methods
}

// Error: Reserved keyword as identifier
fn let() { // Error: expected identifier, found keyword
    println!("Can't use keywords as identifiers");
}

// Error: Invalid binary operation
fn invalid_operation() {
    let result = "string" + "concatenation"; // Error: cannot add two &str values
}

// Error: Missing generic parameter
struct GenericStruct<T> {
    field: T,
}

fn generic_error() {
    let value = GenericStruct { field: 42 }; // Error: missing type parameters
}

// Error: Multiple definition errors in one function
fn multiple_errors() {
    let x: i32 = "string"; // Type mismatch
    let y = z; // Undefined variable
    if (x = 5) { // Assignment in condition
        break; // Break outside of loop
    }
} 