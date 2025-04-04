class Complex;  // Forward declaration

class ComplexHelper {
public:
    static void reset(Complex& c);
};

class Complex {
private:
    double real;
    double imag;
    
public:
    Complex(double r = 0, double i = 0) : real(r), imag(i) {}
    
    // Friend function declaration
    friend Complex operator*(const Complex& a, const Complex& b);
    
    // Friend function definition
    friend std::ostream& operator<<(std::ostream& os, const Complex& c) {
        return os << c.real << " + " << c.imag << "i";
    }
    
    // Friend class
    friend class ComplexHelper;
    
    // Friend member function from another class
    friend void OtherClass::processComplex(Complex&);
};

// Implementation of friend function
Complex operator*(const Complex& a, const Complex& b) {
    return Complex(a.real * b.real - a.imag * b.imag,
                  a.real * b.imag + a.imag * b.real);
}

// Implementation of friend class method
void ComplexHelper::reset(Complex& c) {
    c.real = 0;
    c.imag = 0;
}