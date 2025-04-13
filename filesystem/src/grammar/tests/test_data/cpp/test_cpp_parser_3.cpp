namespace Utils {
    // Helper function
    int max(int a, int b) {
        return (a > b) ? a : b;
    }
    
    // Nested namespace (C++17)
    namespace Math {
        const double PI = 3.14159265359;
        
        double area(double radius) {
            return PI * radius * radius;
        }
    }
}