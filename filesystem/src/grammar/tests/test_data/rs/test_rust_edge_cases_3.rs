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