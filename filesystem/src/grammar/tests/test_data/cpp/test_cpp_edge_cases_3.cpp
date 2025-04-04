class Complex {
private:
    double real;
    double imag;
    
public:
    Complex(double r = 0, double i = 0) : real(r), imag(i) {}
    
    // Unary operators
    Complex operator-() const {
        return Complex(-real, -imag);
    }
    
    Complex& operator++() { // prefix ++
        ++real;
        return *this;
    }
    
    Complex operator++(int) { // postfix ++
        Complex temp(*this);
        ++(*this);
        return temp;
    }
    
    // Binary operators
    Complex operator+(const Complex& other) const {
        return Complex(real + other.real, imag + other.imag);
    }
    
    Complex& operator+=(const Complex& other) {
        real += other.real;
        imag += other.imag;
        return *this;
    }
    
    // Comparison operators
    bool operator==(const Complex& other) const {
        return real == other.real && imag == other.imag;
    }
    
    bool operator!=(const Complex& other) const {
        return !(*this == other);
    }
    
    // Function call operator
    double operator()(double x, double y) const {
        return real * x + imag * y;
    }
    
    // Subscript operator
    double& operator[](int idx) {
        return idx == 0 ? real : imag;
    }
    
    // Type conversion operator
    explicit operator double() const {
        return std::sqrt(real*real + imag*imag);
    }
    
    // Member access operator
    Complex* operator->() {
        return this;
    }
};

// Non-member operator
std::ostream& operator<<(std::ostream& os, const Complex& c) {
    return os << c.real << " + " << c.imag << "i";
}