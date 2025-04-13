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