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