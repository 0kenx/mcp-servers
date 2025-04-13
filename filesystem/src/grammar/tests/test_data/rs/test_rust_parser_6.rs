struct Article { name: String }
impl Summary for Article {
    fn author_summary(&self) -> String {
        format!("Article by {}", self.name)
    }
}

impl Article {
    /// Create a new article.
    pub fn new(name: &str) -> Self {
        Article { name: name.to_string() }
    }
}