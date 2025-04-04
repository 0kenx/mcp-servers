struct Point {
    x: f64,
    y: f64,
}

// Unit struct
struct Unit;

// Tuple struct
struct Color(u8, u8, u8);

pub struct GenericPoint<T> {
    x: T,
    y: T,
}