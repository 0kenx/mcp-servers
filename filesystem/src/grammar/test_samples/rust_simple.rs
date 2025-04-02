/**
 * A simple Rust program demonstrating language features
 * with some edge cases for parser testing
 */

// Module declaration
mod utils {
    // Public function
    pub fn add(a: i32, b: i32) -> i32 {
        a + b
    }
    
    // Private function with pattern matching
    fn check_value(value: Option<i32>) -> i32 {
        match value {
            Some(v) if v > 0 => v,
            Some(_) => 0,
            None => -1,
        }
    }
}

// Struct definition with lifetime parameter
struct Container<'a, T> {
    name: &'a str,
    value: T,
}

// Trait definition
trait Describable {
    fn describe(&self) -> String;
    
    // Default method implementation
    fn summary(&self) -> String {
        format!("Summary of {}", self.describe())
    }
}

// Impl block for struct
impl<'a, T: std::fmt::Debug> Container<'a, T> {
    // Constructor method
    fn new(name: &'a str, value: T) -> Self {
        Container { name, value }
    }
    
    // Method with reference to self
    fn get_value(&self) -> &T {
        &self.value
    }
}

// Implementing trait for struct
impl<'a, T: std::fmt::Debug> Describable for Container<'a, T> {
    fn describe(&self) -> String {
        format!("{}: {:?}", self.name, self.value)
    }
}

// Main function
fn main() {
    // Variable declaration with type inference
    let x = 42;
    let mut y = 10;
    
    // Using imported function
    let sum = utils::add(x, y);
    println!("Sum: {}", sum);
    
    // Using struct
    let container = Container::new("test", vec![1, 2, 3]);
    println!("Description: {}", container.describe());
    
    // Closure
    let multiply = |a, b| a * b;
    println!("Product: {}", multiply(x, y));
    
    // Mutable closure with captured variable
    let mut counter = 0;
    let mut increment = || {
        counter += 1;
        counter
    };
    println!("Counter: {}", increment());
    println!("Counter: {}", increment());
}
