struct Vec2 {
    x: f64,
    y: f64,
}

impl Vec2 {
    fn new(x: f64, y: f64) -> Self {
        Vec2 { x, y }
    } // end new

    // Another method
    fn length(&self) -> f64 {
        (self.x.powi(2) + self.y.powi(2)).sqrt()
    }
} // end impl