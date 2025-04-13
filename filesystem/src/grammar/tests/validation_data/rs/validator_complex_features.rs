// Rust validation file with complex but valid language features to test parser robustness

#![allow(unused_imports, dead_code, unused_variables)]

use std::collections::{HashMap, HashSet, BTreeMap, VecDeque};
use std::sync::{Arc, Mutex, RwLock};
use std::sync::atomic::{AtomicUsize, Ordering};
use std::fmt::{self, Debug, Display, Formatter};
use std::ops::{Add, Sub, Mul, Div, Deref, DerefMut};
use std::marker::{PhantomData, Unpin};
use std::future::Future;
use std::pin::Pin;
use std::task::{Context, Poll};
use std::time::{Duration, Instant};

// Complex generic type with multiple constraints and where clause
pub trait DataProcessor<T>: Send + Sync + 'static
where
    T: Clone + Debug + PartialEq + Send + 'static,
{
    type Output: Clone + Debug + Send;
    type Error: Debug + Display;
    
    fn process(&self, input: T) -> Result<Self::Output, Self::Error>;
    fn validate(&self, input: &T) -> bool;
}

// Struct with lifetime parameters, generics, and PhantomData
pub struct ComplexData<'a, T, E, F>
where
    T: Clone + Debug,
    E: Debug + Display,
    F: Fn(&T) -> bool,
{
    name: String,
    value: T,
    reference: Option<&'a T>,
    error_type: PhantomData<E>,
    validator: F,
    created_at: Instant,
}

impl<'a, T, E, F> ComplexData<'a, T, E, F>
where
    T: Clone + Debug,
    E: Debug + Display,
    F: Fn(&T) -> bool,
{
    pub fn new(name: impl Into<String>, value: T, reference: Option<&'a T>, validator: F) -> Self {
        Self {
            name: name.into(),
            value,
            reference,
            error_type: PhantomData,
            validator,
            created_at: Instant::now(),
        }
    }
    
    pub fn is_valid(&self) -> bool {
        (self.validator)(&self.value)
    }
    
    pub fn elapsed(&self) -> Duration {
        self.created_at.elapsed()
    }
}

// Advanced enum with variants containing different data types
#[derive(Debug, Clone)]
pub enum ProcessingStage<T, E> {
    NotStarted,
    InProgress {
        progress: f64,
        started_at: Instant,
    },
    Completed(T),
    Failed {
        error: E,
        attempts: usize,
    },
}

impl<T, E> ProcessingStage<T, E> {
    pub fn is_completed(&self) -> bool {
        matches!(self, ProcessingStage::Completed(_))
    }
    
    pub fn is_failed(&self) -> bool {
        matches!(self, ProcessingStage::Failed { .. })
    }
    
    pub fn unwrap(self) -> T
    where
        E: Debug,
    {
        match self {
            ProcessingStage::Completed(value) => value,
            _ => panic!("Called unwrap on a non-completed stage: {:?}", self),
        }
    }
}

// Struct implementing multiple traits with complex derivation
#[derive(Debug, Clone, PartialEq)]
pub struct ProcessingResult<T, E> {
    pub id: String,
    pub data: Option<T>,
    pub error: Option<E>,
    pub duration: Duration,
    pub attempts: usize,
}

impl<T, E> ProcessingResult<T, E> {
    pub fn new(id: impl Into<String>) -> Self {
        Self {
            id: id.into(),
            data: None,
            error: None,
            duration: Duration::default(),
            attempts: 0,
        }
    }
    
    pub fn with_data(mut self, data: T) -> Self {
        self.data = Some(data);
        self
    }
    
    pub fn with_error(mut self, error: E) -> Self {
        self.error = Some(error);
        self
    }
    
    pub fn is_success(&self) -> bool {
        self.data.is_some() && self.error.is_none()
    }
}

// Implementation of Display with complex formatting
impl<T: Debug, E: Debug> Display for ProcessingResult<T, E> {
    fn fmt(&self, f: &mut Formatter<'_>) -> fmt::Result {
        write!(
            f,
            "ProcessingResult {{ id: {}, success: {}, attempts: {}, duration: {:?} }}",
            self.id,
            self.is_success(),
            self.attempts,
            self.duration
        )
    }
}

// Async trait with associated types
#[async_trait::async_trait]
pub trait AsyncProcessor {
    type Input: Send;
    type Output: Send;
    type Error: Send + Debug + Display;
    
    async fn process(&self, input: Self::Input) -> Result<Self::Output, Self::Error>;
    
    async fn process_with_retry(
        &self,
        input: Self::Input,
        max_attempts: usize,
    ) -> Result<Self::Output, Self::Error>
    where
        Self::Input: Clone,
    {
        let mut last_error = None;
        
        for attempt in 1..=max_attempts {
            match self.process(input.clone()).await {
                Ok(output) => return Ok(output),
                Err(e) => {
                    last_error = Some(e);
                    if attempt < max_attempts {
                        tokio::time::sleep(Duration::from_millis(100 * attempt as u64)).await;
                    }
                }
            }
        }
        
        Err(last_error.unwrap())
    }
}

// Implementation of custom async Future
pub struct ComplexFuture<F, T>
where
    F: Future<Output = T>,
{
    inner: F,
    start_time: Option<Instant>,
    poll_count: usize,
}

impl<F, T> ComplexFuture<F, T>
where
    F: Future<Output = T>,
{
    pub fn new(future: F) -> Self {
        Self {
            inner: future,
            start_time: None,
            poll_count: 0,
        }
    }
}

impl<F, T> Future for ComplexFuture<F, T>
where
    F: Future<Output = T>,
{
    type Output = (T, Duration, usize);
    
    fn poll(self: Pin<&mut Self>, cx: &mut Context<'_>) -> Poll<Self::Output> {
        // SAFETY: We're not moving any fields out of self, just accessing them
        let this = unsafe { self.get_unchecked_mut() };
        
        if this.start_time.is_none() {
            this.start_time = Some(Instant::now());
        }
        
        this.poll_count += 1;
        
        // SAFETY: We're not moving inner but we need it pinned
        let inner = unsafe { Pin::new_unchecked(&mut this.inner) };
        
        match inner.poll(cx) {
            Poll::Ready(output) => {
                let duration = this.start_time.unwrap().elapsed();
                Poll::Ready((output, duration, this.poll_count))
            }
            Poll::Pending => Poll::Pending,
        }
    }
}

// Implementation of custom operator overloading with generics
#[derive(Debug, Clone, Copy, PartialEq)]
pub struct Vector2D<T> {
    pub x: T,
    pub y: T,
}

impl<T> Vector2D<T>
where
    T: Add<Output = T> + Sub<Output = T> + Mul<Output = T> + Div<Output = T> + Copy,
{
    pub fn new(x: T, y: T) -> Self {
        Self { x, y }
    }
    
    pub fn dot(&self, other: &Self) -> T {
        self.x * other.x + self.y * other.y
    }
    
    pub fn scale(&self, factor: T) -> Self {
        Self {
            x: self.x * factor,
            y: self.y * factor,
        }
    }
}

impl<T: Add<Output = T>> Add for Vector2D<T> {
    type Output = Self;
    
    fn add(self, other: Self) -> Self::Output {
        Self {
            x: self.x + other.x,
            y: self.y + other.y,
        }
    }
}

// Smart pointer implementation with DerefMut
pub struct SmartBox<T> {
    value: Box<T>,
    access_count: AtomicUsize,
}

impl<T> SmartBox<T> {
    pub fn new(value: T) -> Self {
        Self {
            value: Box::new(value),
            access_count: AtomicUsize::new(0),
        }
    }
    
    pub fn access_count(&self) -> usize {
        self.access_count.load(Ordering::SeqCst)
    }
}

impl<T> Deref for SmartBox<T> {
    type Target = T;
    
    fn deref(&self) -> &Self::Target {
        self.access_count.fetch_add(1, Ordering::SeqCst);
        &self.value
    }
}

impl<T> DerefMut for SmartBox<T> {
    fn deref_mut(&mut self) -> &mut Self::Target {
        self.access_count.fetch_add(1, Ordering::SeqCst);
        &mut self.value
    }
}

// Advanced macro usage
#[macro_export]
macro_rules! complex_map {
    // Empty map
    () => {
        std::collections::HashMap::new()
    };
    
    // Map with entries
    ($(
        $key:expr => $value:expr
    ),* $(,)?) => {
        {
            let mut map = std::collections::HashMap::new();
            $(
                map.insert($key, $value);
            )*
            map
        }
    };
    
    // Map with type annotation
    ($(
        $key:expr => $value:expr
    ),* $(,)?; $k:ty => $v:ty) => {
        {
            let mut map: std::collections::HashMap<$k, $v> = std::collections::HashMap::new();
            $(
                map.insert($key, $value);
            )*
            map
        }
    };
}

// Function with complex pattern matching and guard clauses
pub fn analyze_result<T, E>(result: &ProcessingResult<T, E>) -> &'static str
where
    T: Debug,
    E: Debug,
{
    match result {
        ProcessingResult { data: Some(_), error: None, attempts, .. } if *attempts <= 1 => {
            "Succeeded on first attempt"
        }
        ProcessingResult { data: Some(_), error: None, attempts, .. } => {
            "Succeeded after retries"
        }
        ProcessingResult { data: None, error: Some(_), attempts, .. } if *attempts >= 3 => {
            "Failed after multiple attempts"
        }
        ProcessingResult { duration, .. } if duration.as_secs() > 10 => {
            "Timed out"
        }
        _ => "Unknown state",
    }
}

// Unsafe code block with raw pointers
pub unsafe fn memory_copy<T: Copy>(src: &T, dest: &mut T) {
    let src_ptr: *const T = src;
    let dest_ptr: *mut T = dest;
    
    std::ptr::copy_nonoverlapping(src_ptr, dest_ptr, 1);
}

// Main function demonstrating usage of complex features
pub fn main() {
    // Complex data structure creation and manipulation
    let validator = |value: &i32| -> bool { *value > 0 };
    let data = ComplexData::<i32, String, _>::new("example", 42, None, validator);
    
    // Smart pointer usage
    let mut smart_box = SmartBox::new(Vector2D::new(1.0, 2.0));
    let scaled = smart_box.scale(2.0);
    
    // Macro usage
    let map = complex_map! {
        "key1" => "value1",
        "key2" => "value2",
        "key3" => "value3",
    };
    
    // Pattern matching
    let result = ProcessingResult::new("test-1")
        .with_data(42)
        .with_error("Processing error".to_string());
    
    let analysis = analyze_result(&result);
    println!("Analysis: {}", analysis);
    
    // Enum variants
    let stage = ProcessingStage::InProgress {
        progress: 0.5,
        started_at: Instant::now(),
    };
    
    if let ProcessingStage::InProgress { progress, .. } = stage {
        println!("Progress: {:.1}%", progress * 100.0);
    }
} 