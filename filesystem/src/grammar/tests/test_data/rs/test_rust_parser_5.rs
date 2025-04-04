/// A summary trait.
pub trait Summary {
    /// Get the author summary.
    fn author_summary(&self) -> String;

    /// Get the full summary.
    fn summarize(&self) -> String {
        format!("(Read more from {}...)", self.author_summary())
    }
}