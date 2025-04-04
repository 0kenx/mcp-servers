/**
 * Point structure to represent a 2D point.
 */
struct Point {
    int x;
    int y;
    
    // Method
    double distance(const Point& other) const {
        int dx = x - other.x;
        int dy = y - other.y;
        return sqrt(dx*dx + dy*dy);
    }
};