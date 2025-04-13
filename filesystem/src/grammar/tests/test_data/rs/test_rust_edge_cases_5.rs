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