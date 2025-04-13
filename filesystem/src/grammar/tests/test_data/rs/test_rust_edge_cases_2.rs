// Basic trait
trait Animal {
    fn name(&self) -> &str;
    fn sound(&self) -> &str;
    
    // Default implementation
    fn make_sound(&self) {
        println!("{} says {}", self.name(), self.sound());
    }
}

// Trait with associated types
trait Iterator {
    type Item;
    
    fn next(&mut self) -> Option<Self::Item>;
    
    fn map<B, F>(self, f: F) -> Map<Self, F>
    where
        Self: Sized,
        F: FnMut(Self::Item) -> B,
    {
        Map { iter: self, f }
    }
}

// Trait with associated constants
trait Physics {
    const GRAVITY: f64 = 9.81;
    
    fn calculate_force(&self, mass: f64) -> f64;
}

// Trait bounds
trait Printable: std::fmt::Display + std::fmt::Debug {
    fn print(&self) {
        println!("{}", self);
    }
}

// Implementing a trait
struct Dog {
    name: String,
}

impl Animal for Dog {
    fn name(&self) -> &str {
        &self.name
    }
    
    fn sound(&self) -> &str {
        "woof"
    }
    
    // Override the default implementation
    fn make_sound(&self) {
        println!("{} barks loudly: {}", self.name(), self.sound());
    }
}

// Generic trait implementation
struct Counter<T> {
    count: usize,
    value: T,
}

impl<T: Clone> Iterator for Counter<T> {
    type Item = T;
    
    fn next(&mut self) -> Option<Self::Item> {
        self.count += 1;
        Some(self.value.clone())
    }
}

// Implementing multiple traits
impl<T: std::fmt::Display + std::fmt::Debug> Printable for Counter<T> {}

// Trait objects
fn get_animal() -> Box<dyn Animal> {
    Box::new(Dog { name: String::from("Rex") })
}

// Auto traits and marker traits
unsafe trait Send {}
unsafe trait Sync {}

struct ThreadSafeCounter {
    count: std::sync::atomic::AtomicUsize,
}

unsafe impl Send for ThreadSafeCounter {}
unsafe impl Sync for ThreadSafeCounter {}

// Extension traits
trait StringExt {
    fn is_palindrome(&self) -> bool;
}

impl StringExt for str {
    fn is_palindrome(&self) -> bool {
        let chars: Vec<_> = self.chars().collect();
        chars == chars.into_iter().rev().collect::<Vec<_>>()
    }
}

// Implementing external traits for your types
struct MyType;

impl std::fmt::Display for MyType {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        write!(f, "MyType")
    }
}