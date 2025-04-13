/**
 * Add two numbers.
 */
function add(a: number, b: number): number {
    return a + b;
}

// Arrow function with type annotations
const multiply = (a: number, b: number): number => a * b;

// Generic function
function identity<T>(value: T): T {
    return value;
}