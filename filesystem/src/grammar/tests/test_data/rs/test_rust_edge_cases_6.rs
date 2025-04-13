// Attribute macros
#[derive(Debug, Clone, PartialEq)]
#[repr(C)]
struct Point {
    x: f64,
    y: f64,
}

// Custom attribute
#[inline(always)]
fn optimized_function() -> i32 {
    42
}

// Conditional compilation
#[cfg(target_os = "linux")]
fn linux_only() {
    println!("Running on Linux");
}

#[cfg(not(target_os = "linux"))]
fn linux_only() {
    println!("Not running on Linux");
}

// Feature gates
#[cfg(feature = "advanced")]
mod advanced_features {
    pub fn advanced_function() {
        println!("Advanced feature enabled");
    }
}

// Existential types (impl Trait)
fn returns_closure() -> impl Fn(i32) -> i32 {
    |x| x + 1
}

// RAII guards
struct MutexGuard<'a, T: 'a> {
    lock: &'a mut T,
}

impl<'a, T> Drop for MutexGuard<'a, T> {
    fn drop(&mut self) {
        println!("Releasing lock");
    }
}

struct Mutex<T> {
    data: T,
}

impl<T> Mutex<T> {
    fn new(data: T) -> Self {
        Mutex { data }
    }
    
    fn lock(&mut self) -> MutexGuard<T> {
        println!("Acquiring lock");
        MutexGuard { lock: &mut self.data }
    }
}

// Associated type constructors
trait Container {
    type Item;
    
    fn get(&self) -> Option<&Self::Item>;
    fn insert(&mut self, item: Self::Item);
}

struct Queue<T> {
    items: Vec<T>,
}

impl<T> Container for Queue<T> {
    type Item = T;
    
    fn get(&self) -> Option<&Self::Item> {
        self.items.first()
    }
    
    fn insert(&mut self, item: Self::Item) {
        self.items.push(item);
    }
}

// Const generics
struct Array<T, const N: usize> {
    data: [T; N],
}

impl<T: Default + Copy, const N: usize> Default for Array<T, N> {
    fn default() -> Self {
        Self {
            data: [T::default(); N],
        }
    }
}

// Never type
fn never_returns() -> ! {
    panic!("This function never returns");
}

// Async/await
async fn fetch_data(url: &str) -> Result<String, Box<dyn std::error::Error>> {
    // Simulated async operation
    std::future::pending::<()>().await;
    Ok(format!("Data from {}", url))
}

async fn process_url(url: &str) {
    match fetch_data(url).await {
        Ok(data) => println!("Received: {}", data),
        Err(e) => eprintln!("Error: {}", e),
    }
}

// Pin and structural pinning
use std::marker::PhantomPinned;
use std::pin::Pin;

struct SelfReferential {
    data: String,
    ptr_to_data: *const String,
    _pin: PhantomPinned,
}

impl SelfReferential {
    fn new(data: String) -> Pin<Box<Self>> {
        let mut boxed = Box::new(SelfReferential {
            data,
            ptr_to_data: std::ptr::null(),
            _pin: PhantomPinned,
        });
        
        let ptr = &boxed.data as *const String;
        boxed.ptr_to_data = ptr;
        
        Pin::new(boxed)
    }
}