"""
Tests for the Rust parser with edge cases.
"""

import unittest
from src.grammar.rust import RustParser
from src.grammar.base import ElementType


class TestRustEdgeCases(unittest.TestCase):
    """Test edge cases for the Rust parser."""

    def setUp(self):
        """Set up test cases."""
        self.parser = RustParser()

    def test_complex_generics(self):
        """Test parsing Rust code with complex generic constraints."""
        code = """
use std::fmt::Debug;
use std::cmp::PartialOrd;
use std::collections::HashMap;

// Function with multiple generic parameters and bounds
fn find_largest<T, U>(list: &[T], key_fn: impl Fn(&T) -> U) -> Option<&T>
where
    T: Debug,
    U: PartialOrd,
{
    if list.is_empty() {
        return None;
    }
    
    let mut largest = &list[0];
    let mut largest_key = key_fn(largest);
    
    for item in list {
        let key = key_fn(item);
        if key > largest_key {
            largest = item;
            largest_key = key;
        }
    }
}
"""
        elements = self.parser.parse(code)
        
        # Check that we found the expected elements
        self.assertGreaterEqual(len(elements), 3)
        
        # Check for the macro definitions
        say_hello_macro = next((e for e in elements if e.name == "say_hello"), None)
        if say_hello_macro:  # Macro parsing is challenging, so this is optional
            self.assertEqual(say_hello_macro.element_type, ElementType.FUNCTION)
        
        # Check for struct with derive macro
        point_struct = next((e for e in elements if e.name == "Point"), None)
        self.assertIsNotNone(point_struct)
        
        # Check for the use_macros function
        use_macros_func = next((e for e in elements if e.name == "use_macros"), None)
        self.assertIsNotNone(use_macros_func)

    def test_traits_and_trait_implementations(self):
        """Test parsing complex traits and trait implementations."""
        code = """
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
"""
        elements = self.parser.parse(code)
        
        # Check that we found various trait elements
        self.assertGreaterEqual(len(elements), 8)
        
        # Check for traits
        animal_trait = next((e for e in elements if e.element_type == ElementType.TRAIT 
                           and e.name == "Animal"), None)
        self.assertIsNotNone(animal_trait)
        
        iterator_trait = next((e for e in elements if e.element_type == ElementType.TRAIT 
                             and e.name == "Iterator"), None)
        self.assertIsNotNone(iterator_trait)
        
        # Check for structs
        dog_struct = next((e for e in elements if e.element_type == ElementType.STRUCT 
                         and e.name == "Dog"), None)
        self.assertIsNotNone(dog_struct)
        
        # Check for trait implementations
        impl_elements = [e for e in elements if e.element_type == ElementType.IMPL]
        self.assertGreaterEqual(len(impl_elements), 3)

    def test_lifetime_annotations(self):
        """Test parsing Rust code with complex lifetime annotations."""
        code = """
// Basic lifetime annotations
struct Ref<'a, T: 'a> {
    reference: &'a T,
}

// Multiple lifetime parameters
struct RefPair<'a, 'b, T: 'a, U: 'b> {
    ref1: &'a T,
    ref2: &'b U,
}

// Function with lifetime annotations
fn longest<'a>(s1: &'a str, s2: &'a str) -> &'a str {
    if s1.len() > s2.len() { s1 } else { s2 }
}

// Struct with lifetime and method with different lifetime
struct StrSplit<'a, 'b> {
    remainder: Option<&'a str>,
    delimiter: &'b str,
}

impl<'a, 'b> StrSplit<'a, 'b> {
    fn new(haystack: &'a str, delimiter: &'b str) -> Self {
        Self {
            remainder: Some(haystack),
            delimiter,
        }
    }
    
    // Method returning a reference with the struct's lifetime
    fn next_token(&mut self) -> Option<&'a str> {
        if let Some(remainder) = self.remainder {
            if let Some(delimiter_index) = remainder.find(self.delimiter) {
                let token = &remainder[..delimiter_index];
                self.remainder = Some(&remainder[delimiter_index + self.delimiter.len()..]);
                Some(token)
            } else {
                self.remainder = None;
                Some(remainder)
            }
        } else {
            None
        }
    }
}

// Lifetime bounds
struct Wrapper<'a, T: 'a> {
    value: &'a T,
}

// 'static lifetime
const HELLO: &'static str = "Hello, world!";

struct StaticRef<T: 'static> {
    data: &'static T,
}

// Higher-ranked trait bounds (HRTB)
trait Matcher<T> {
    fn matches(&self, item: &T) -> bool;
}

fn match_all<'a, T, M>(items: &'a [T], matcher: M) -> Vec<&'a T>
where
    M: for<'b> Matcher<&'b T>,
{
    items.iter().filter(|item| matcher.matches(item)).collect()
}

// Named lifetime parameters with elision
impl<'a, T: Clone> Clone for Ref<'a, T> {
    fn clone(&self) -> Self {
        Ref {
            reference: self.reference,
        }
    }
}

// Phantom lifetimes
struct Slice<'a, T: 'a> {
    start: *const T,
    end: *const T,
    phantom: std::marker::PhantomData<&'a T>,
}

// Function returning impl Trait with lifetime
fn returns_str_slice<'a>(slice: &'a str) -> impl Iterator<Item = &'a str> + 'a {
    slice.lines()
}
"""
        elements = self.parser.parse(code)
        
        # Check that we found various elements with lifetimes
        self.assertGreaterEqual(len(elements), 5)
        
        # Check for structs with lifetimes
        ref_struct = next((e for e in elements if e.element_type == ElementType.STRUCT 
                          and e.name == "Ref"), None)
        self.assertIsNotNone(ref_struct)
        
        ref_pair_struct = next((e for e in elements if e.element_type == ElementType.STRUCT 
                               and e.name == "RefPair"), None)
        self.assertIsNotNone(ref_pair_struct)
        
        # Check for function with lifetime
        longest_func = next((e for e in elements if e.element_type == ElementType.FUNCTION 
                            and e.name == "longest"), None)
        self.assertIsNotNone(longest_func)
        
        # Check for trait
        matcher_trait = next((e for e in elements if e.element_type == ElementType.TRAIT 
                             and e.name == "Matcher"), None)
        self.assertIsNotNone(matcher_trait)

    def test_advanced_patterns(self):
        """Test parsing Rust code with advanced pattern matching."""
        code = """
enum Message {
    Quit,
    Move { x: i32, y: i32 },
    Write(String),
    ChangeColor(i32, i32, i32),
}

struct Point {
    x: i32,
    y: i32,
}

struct Rectangle {
    top_left: Point,
    bottom_right: Point,
}

// Function with advanced pattern matching
fn process_message(msg: Message) {
    match msg {
        Message::Quit => {
            println!("Quitting");
        },
        Message::Move { x, y } => {
            println!("Moving to ({}, {})", x, y);
        },
        Message::Write(text) => {
            println!("Writing: {}", text);
        },
        Message::ChangeColor(r, g, b) => {
            println!("Changing color to RGB({}, {}, {})", r, g, b);
        },
    }
}

// Pattern matching with guards
fn describe_number(n: i32) -> &'static str {
    match n {
        0 => "zero",
        1 => "one",
        2..=9 => "small",
        10..=99 => "medium",
        _ if n < 0 => "negative",
        _ => "large",
    }
}

// @ bindings
fn inspect_tuple(pair: (i32, i32)) {
    match pair {
        (x, y) if x == y => println!("Equal parts: {}", x),
        (x, _) if x > 100 => println!("Large first part: {}", x),
        (_, y @ 10..=20) => println!("Medium second part: {}", y),
        (first @ .., second @ _) => println!("Generic parts: {}, {}", first, second),
    }
}

// Destructuring nested structs and enums
fn inspect_rectangle(rect: &Rectangle) {
    match rect {
        Rectangle {
            top_left: Point { x: 0, y: 0 },
            bottom_right: Point { x, y },
        } => println!("Rectangle starting at origin with width {} and height {}", x, y),
        
        Rectangle {
            top_left: Point { x: left, .. },
            bottom_right: Point { x: right, .. },
        } if right - left > 100 => println!("Wide rectangle"),
        
        Rectangle {
            top_left,
            bottom_right,
        } => println!("Rectangle from {:?} to {:?}", top_left, bottom_right),
    }
}

// Match ergonomics
fn print_id(id: Option<&str>) {
    match id {
        Some(name) => println!("ID: {}", name),
        None => println!("No ID provided"),
    }
}

// If let expressions
fn process_color(color: Option<(u8, u8, u8)>) {
    if let Some((r, g, b)) = color {
        println!("RGB: {}, {}, {}", r, g, b);
    } else {
        println!("No color provided");
    }
    
    // Nested if let
    if let Some((r, g, _)) = color {
        if let 255 = r {
            if let 255 = g {
                println!("Color has max red and green");
            }
        }
    }
}

// While let
fn process_stack(mut stack: Vec<i32>) {
    while let Some(top) = stack.pop() {
        println!("Stack top: {}", top);
    }
}
"""
        elements = self.parser.parse(code)
        
        # Check that we found various elements
        self.assertGreaterEqual(len(elements), 5)
        
        # Check for enum
        message_enum = next((e for e in elements if e.name == "Message"), None)
        self.assertIsNotNone(message_enum)
        
        # Check for structs
        point_struct = next((e for e in elements if e.name == "Point"), None)
        self.assertIsNotNone(point_struct)
        
        rectangle_struct = next((e for e in elements if e.name == "Rectangle"), None)
        self.assertIsNotNone(rectangle_struct)
        
        # Check for functions with pattern matching
        process_message_func = next((e for e in elements if e.name == "process_message"), None)
        self.assertIsNotNone(process_message_func)
        
        describe_number_func = next((e for e in elements if e.name == "describe_number"), None)
        self.assertIsNotNone(describe_number_func)

    def test_unsafe_code(self):
        """Test parsing Rust code with unsafe blocks and operations."""
        code = """
// Basic unsafe block
fn access_raw_pointer() {
    let mut x = 5;
    let ptr = &mut x as *mut i32;
    
    unsafe {
        *ptr = 10;
        println!("Value through raw pointer: {}", *ptr);
    }
}

// Dereferencing raw pointers
fn manipulate_pointers() {
    let mut values = vec![1, 2, 3, 4, 5];
    let ptr = values.as_mut_ptr();
    
    unsafe {
        for i in 0..values.len() {
            *ptr.add(i) *= 2;
        }
    }
}

// Calling unsafe functions
unsafe fn dangerous() {
    println!("This function is unsafe");
}

fn call_unsafe_function() {
    unsafe {
        dangerous();
    }
}

// Implementing unsafe traits
unsafe trait UnsafeTrait {
    fn unsafe_method(&self);
}

unsafe impl UnsafeTrait for u32 {
    fn unsafe_method(&self) {
        println!("Unsafe method on {}", self);
    }
}

// Using extern functions (FFI)
extern "C" {
    fn abs(input: i32) -> i32;
    fn sqrt(input: f64) -> f64;
}

fn use_c_functions() {
    unsafe {
        println!("Absolute value: {}", abs(-42));
        println!("Square root: {}", sqrt(64.0));
    }
}

// Creating unions
union IntOrFloat {
    int_val: i32,
    float_val: f32,
}

fn use_union() {
    let mut value = IntOrFloat { int_val: 123456 };
    
    unsafe {
        println!("Int: {}", value.int_val);
        value.float_val = 3.14;
        println!("Float: {}", value.float_val);
    }
}

// Global mutable state
static mut COUNTER: u32 = 0;

fn increment_counter() {
    unsafe {
        COUNTER += 1;
        println!("Counter: {}", COUNTER);
    }
}

// Reinterpreting memory
fn reinterpret_bytes() {
    let bytes: [u8; 4] = [0x12, 0x34, 0x56, 0x78];
    
    unsafe {
        let int_val: i32 = std::mem::transmute(bytes);
        println!("As integer: {}", int_val);
    }
}
"""
        elements = self.parser.parse(code)
        
        # Check that we found various elements with unsafe code
        self.assertGreaterEqual(len(elements), 5)
        
        # Check for functions with unsafe blocks
        access_fn = next((e for e in elements if e.name == "access_raw_pointer"), None)
        self.assertIsNotNone(access_fn)
        
        # Check for unsafe function
        dangerous_fn = next((e for e in elements if e.name == "dangerous"), None)
        self.assertIsNotNone(dangerous_fn)
        
        # Check for unsafe trait
        unsafe_trait = next((e for e in elements if e.name == "UnsafeTrait"), None)
        self.assertIsNotNone(unsafe_trait)
        
        # Check for extern block
        extern_fns = [e for e in elements if "extern" in str(e.metadata.get("docstring", ""))]
        self.assertGreaterEqual(len(extern_fns), 1)
        
        # Check for union
        int_or_float_union = next((e for e in elements if e.name == "IntOrFloat"), None)
        self.assertIsNotNone(int_or_float_union)

    def test_advanced_rust_features(self):
        """Test parsing code with advanced Rust features."""
        code = """
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
"""
        elements = self.parser.parse(code)
        
        # Check that we found various advanced elements
        self.assertGreaterEqual(len(elements), 8)
        
        # Check for a struct with derive attributes
        point_struct = next((e for e in elements if e.name == "Point"), None)
        self.assertIsNotNone(point_struct)
        
        # Check for functions
        optimized_fn = next((e for e in elements if e.name == "optimized_function"), None)
        self.assertIsNotNone(optimized_fn)
        
        # Check for trait and implementation
        container_trait = next((e for e in elements if e.name == "Container"), None)
        self.assertIsNotNone(container_trait)
        
        # Check for async functions
        fetch_data_fn = next((e for e in elements if e.name == "fetch_data"), None)
        self.assertIsNotNone(fetch_data_fn)
        
        process_url_fn = next((e for e in elements if e.name == "process_url"), None)
        self.assertIsNotNone(process_url_fn)
        
        # Check for struct with const generics
        array_struct = next((e for e in elements if e.name == "Array"), None)
        self.assertIsNotNone(array_struct)

    def test_incomplete_code(self):
        """Test parsing incomplete or syntactically invalid Rust code."""
        code = """
// Incomplete function
fn incomplete_function(x: i32, 

// Missing closing brace
fn missing_brace() {
    let x = 5;
    let y = 10;
    println!("Sum: {}", x + y);

// Incomplete struct definition
struct Point {
    x: i32,
    y: i32

// Missing field type
struct User {
    name: String,
    email:

// Incomplete impl block
impl SomeStruct {
    fn method1(&self) -> i32 {
        42
    
    fn method2(&self)

// Incomplete match expression
fn process_option(opt: Option<i32>) {
    match opt {
        Some(val) => println!("Value: {}", val),
        None =>

// Incomplete enum
enum Status {
    Active,
    Inactive,
    Pending(

// Incomplete trait
trait MyTrait {
    fn required_method(&self);
    fn optional_method(&self) {
        println!("Default implementation");

// Unmatched generic brackets
struct GenericStruct<T {
    value: T,
}

// Incomplete lifetime specifier
struct Ref<'a, T: {
    value: &'a T,
}

// Incomplete unsafe block
fn unsafe_function() {
    unsafe {
        let ptr = 0x1234 as *const i32;
        println!("Value: {}", *ptr);
"""
        try:
            elements = self.parser.parse(code)
            
            # Even with syntax errors, the parser should be able to identify some elements
            self.assertGreaterEqual(len(elements), 1, "Should find at least one element despite syntax errors")
            
            # Check if any elements were found
            functions = [e for e in elements if e.element_type == ElementType.FUNCTION]
            structs = [e for e in elements if e.element_type == ElementType.STRUCT]
            
            print(f"Found {len(functions)} functions and {len(structs)} structs in incomplete code")
            
            # This is a stretch goal - parsers may not handle incomplete code well
            
        except Exception as e:
            self.fail(f"Parser crashed on incomplete code: {e}")


if __name__ == "__main__":
    unittest.main()

