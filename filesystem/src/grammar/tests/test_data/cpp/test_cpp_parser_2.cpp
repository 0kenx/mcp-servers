/**
 * A simple rectangle class.
 */
class Rectangle {
private:
    int width;
    int height;
    
public:
    // Constructor
    Rectangle(int w, int h) : width(w), height(h) {}
    
    // Method to calculate area
    int area() const {
        return width * height;
    }
    
    // Getters and setters
    int getWidth() const { return width; }
    void setWidth(int w) { width = w; }
    
    int getHeight() const { return height; }
    void setHeight(int h) { height = h; }
};