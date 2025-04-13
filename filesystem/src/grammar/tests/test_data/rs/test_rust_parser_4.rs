/// An enum representing web events.
#[derive(Debug)]
enum WebEvent {
    PageLoad,                       // Variant without data
    KeyPress(char),                 // Tuple variant
    Click { x: i64, y: i64 },       // Struct variant
}