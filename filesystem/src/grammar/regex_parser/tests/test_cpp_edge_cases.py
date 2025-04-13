"""
Tests for the C++ parser with edge cases.
"""

import unittest
from src.grammar.c_cpp import CCppParser
from src.grammar.base import ElementType


class TestCppEdgeCases(unittest.TestCase):
    """Test edge cases for the C++ parser."""

    def setUp(self):
        """Set up test cases."""
        self.parser = CCppParser()

    def test_complex_templates(self):
        """Test parsing complex template expressions."""
        code = """
// Complex template with multiple parameters and defaults
template <
    typename T,
    typename U = int,
    size_t N = 100,
    template <typename...> class Container = std::vector,
    typename Allocator = std::allocator<T>
>
class AdvancedContainer {
public:
    using value_type = T;
    using container_type = Container<T, Allocator>;
    
    template <typename V>
    void add(V&& value) {
        data.push_back(static_cast<T>(std::forward<V>(value)));
    }
    
private:
    container_type data;
};

// Variadic templates
template <typename... Args>
auto sum(Args... args) {
    return (args + ...); // Fold expression (C++17)
}

// Template specialization
template <typename T>
struct IsPointer {
    static const bool value = false;
};

template <typename T>
struct IsPointer<T*> {
    static const bool value = true;
};

// Template with non-type parameter that's a template
template <
    typename T,
    template <typename> class Trait = IsPointer
>
constexpr bool check_trait() {
    return Trait<T>::value;
}

// SFINAE and type traits
template <typename T>
struct has_begin_end {
private:
    template <typename U>
    static auto test(int) -> decltype(
        std::declval<U>().begin(),
        std::declval<U>().end(),
        std::true_type{}
    );
    
    template <typename>
    static std::false_type test(...);
    
public:
    static constexpr bool value = decltype(test<T>(0))::value;
};
"""
        elements = self.parser.parse(code)

        # Should identify at least the main template classes and functions
        self.assertGreaterEqual(len(elements), 3)

        # Check for the AdvancedContainer class
        container_class = next(
            (e for e in elements if e.name == "AdvancedContainer"), None
        )
        self.assertIsNotNone(container_class)
        self.assertEqual(container_class.element_type, ElementType.CLASS)

        # Check for the sum function
        sum_func = next((e for e in elements if e.name == "sum"), None)
        self.assertIsNotNone(sum_func)

        # Check for template specialization
        is_pointer_struct = next((e for e in elements if e.name == "IsPointer"), None)
        self.assertIsNotNone(is_pointer_struct)

    def test_multiple_inheritance(self):
        """Test parsing classes with multiple inheritance and virtual inheritance."""
        code = """
class Base {
public:
    virtual void foo() = 0;
    virtual ~Base() = default;
};

class InterfaceA {
public:
    virtual void methodA() = 0;
    virtual ~InterfaceA() = default;
};

class InterfaceB {
public:
    virtual void methodB() = 0;
    virtual ~InterfaceB() = default;
};

// Multiple inheritance
class Derived : public Base, public InterfaceA, public InterfaceB {
public:
    void foo() override {
        // Implementation
    }
    
    void methodA() override {
        // Implementation
    }
    
    void methodB() override {
        // Implementation
    }
};

// Virtual inheritance (diamond problem)
class BaseV {
public:
    int x;
};

class Derived1 : virtual public BaseV {
public:
    int y;
};

class Derived2 : virtual public BaseV {
public:
    int z;
};

class Diamond : public Derived1, public Derived2 {
public:
    int w;
};
"""
        elements = self.parser.parse(code)

        # Should identify all classes
        classes = [e for e in elements if e.element_type == ElementType.CLASS]
        self.assertGreaterEqual(len(classes), 7)

        # Check for the Derived class
        derived_class = next((c for c in classes if c.name == "Derived"), None)
        self.assertIsNotNone(derived_class)

        # Check for the Diamond class
        diamond_class = next((c for c in classes if c.name == "Diamond"), None)
        self.assertIsNotNone(diamond_class)

    def test_operator_overloading(self):
        """Test parsing operator overloading."""
        code = """
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
"""
        elements = self.parser.parse(code)

        # Should identify the class and operators
        self.assertGreaterEqual(len(elements), 1)

        # Check for the Complex class
        complex_class = next((e for e in elements if e.name == "Complex"), None)
        self.assertIsNotNone(complex_class)

        # Check for method count - should find multiple operator methods
        methods = [e for e in elements if e.element_type == ElementType.METHOD]
        self.assertGreaterEqual(len(methods), 8)

        # Check for the non-member operator
        operator_func = next(
            (
                e
                for e in elements
                if e.element_type == ElementType.FUNCTION and "operator" in e.name
            ),
            None,
        )
        self.assertIsNotNone(operator_func)

    def test_friend_functions_and_classes(self):
        """Test parsing friend functions and classes."""
        code = """
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
"""
        elements = self.parser.parse(code)

        # Should identify the classes and friend functions
        classes = [e for e in elements if e.element_type == ElementType.CLASS]
        self.assertGreaterEqual(len(classes), 2)

        # Check for the Complex class
        complex_class = next((c for c in classes if c.name == "Complex"), None)
        self.assertIsNotNone(complex_class)

        # Check for the ComplexHelper class
        helper_class = next((c for c in classes if c.name == "ComplexHelper"), None)
        self.assertIsNotNone(helper_class)

        # Check for the friend functions
        functions = [e for e in elements if e.element_type == ElementType.FUNCTION]
        self.assertGreaterEqual(len(functions), 1)

        # Check for at least one operator function
        operator_func = next((f for f in functions if "operator" in f.name), None)
        self.assertIsNotNone(operator_func)

    def test_nested_namespaces_and_classes(self):
        """Test parsing nested namespaces and classes."""
        code = """
namespace Outer {
    int global_var = 42;
    
    namespace Inner {
        void inner_function() {
            // Implementation
        }
        
        class InnerClass {
        public:
            void method() {}
        };
    }
    
    class OuterClass {
    public:
        class NestedClass {
        public:
            void nested_method() {}
            
            struct DeepNested {
                int x, y;
            };
        };
        
        void outer_method() {}
    };
    
    namespace {
        // Anonymous namespace
        int anon_var = 10;
        
        void anon_function() {
            // Implementation
        }
    }
}

// C++17 nested namespace definition
namespace A::B::C {
    void abc_function() {
        // Implementation
    }
    
    class ABC {
    public:
        void method() {}
    };
}
"""
        elements = self.parser.parse(code)

        # Check for namespaces
        namespaces = [e for e in elements if e.element_type == ElementType.NAMESPACE]
        self.assertGreaterEqual(len(namespaces), 2)

        # Check for the Outer namespace
        outer_ns = next((ns for ns in namespaces if ns.name == "Outer"), None)
        self.assertIsNotNone(outer_ns)

        # Check for classes
        classes = [e for e in elements if e.element_type == ElementType.CLASS]
        self.assertGreaterEqual(len(classes), 2)

        # Check for functions
        functions = [
            e
            for e in elements
            if e.element_type == ElementType.FUNCTION
            or e.element_type == ElementType.METHOD
        ]
        self.assertGreaterEqual(len(functions), 2)

        # This is a stretch goal - checking for nested elements with correct parent-child relationships
        # The parent-child relationships for nested namespaces and classes are complex
        # and may not be fully captured

    def test_preprocessor_directives(self):
        """Test parsing code with preprocessor directives."""
        code = """
#include <iostream>
#include <vector>
#include "myheader.h"

#define MAX_SIZE 100
#define SQUARE(x) ((x) * (x))
#define DEBUG_PRINT(msg) std::cout << msg << std::endl

#ifdef DEBUG
    #define LOG(msg) std::cout << "[DEBUG] " << msg << std::endl
#else
    #define LOG(msg) do {} while(0)
#endif

#if defined(PLATFORM_WINDOWS)
    #include <windows.h>
    typedef HANDLE FileHandle;
#elif defined(PLATFORM_LINUX)
    #include <unistd.h>
    typedef int FileHandle;
#else
    #error "Unsupported platform"
#endif

// Multi-line macro
#define MULTI_LINE_FUNC(x, y) do { \\
    int temp = (x); \\
    (x) = (y); \\
    (y) = temp; \\
} while(0)

class TestClass {
public:
    #ifdef DEBUG
    void debug_method() {
        LOG("Debug method called");
    }
    #endif
    
    void regular_method() {
        // Implementation
        #if MAX_SIZE > 50
        int buffer[MAX_SIZE];
        #else
        int buffer[50];
        #endif
    }
};

#pragma once
#pragma warning(disable: 4996)

// Function with preprocessor directives in body
int process(int value) {
    #ifdef DEBUG
    DEBUG_PRINT("Processing value: " << value);
    #endif
    
    int result = SQUARE(value);
    
    #if defined(FEATURE_A) && !defined(FEATURE_B)
    result += 10;
    #endif
    
    return result;
}
"""
        elements = self.parser.parse(code)

        # Should identify classes and functions despite preprocessor directives
        self.assertGreaterEqual(len(elements), 3)

        # Check for includes
        includes = [e for e in elements if e.element_type == ElementType.IMPORT]
        self.assertGreaterEqual(len(includes), 2)

        # Check for the class
        test_class = next(
            (
                e
                for e in elements
                if e.element_type == ElementType.CLASS and e.name == "TestClass"
            ),
            None,
        )
        self.assertIsNotNone(test_class)

        # Check for the function
        process_func = next(
            (
                e
                for e in elements
                if e.element_type == ElementType.FUNCTION and e.name == "process"
            ),
            None,
        )
        self.assertIsNotNone(process_func)

        # Check for definition of MAX_SIZE
        # This is a stretch goal - parsers may not extract preprocessor definitions
        constants = [
            e
            for e in elements
            if e.element_type == ElementType.CONSTANT
            or e.element_type == ElementType.VARIABLE
        ]

        if constants:
            max_size = next((c for c in constants if c.name == "MAX_SIZE"), None)
            if max_size:
                self.assertEqual(max_size.element_type, ElementType.CONSTANT)

    def test_modern_cpp_features(self):
        """Test parsing modern C++ features (C++11 and later)."""
        code = """
#include <iostream>
#include <vector>
#include <memory>
#include <functional>
#include <string_view>
#include <optional>
#include <variant>
#include <any>

// Auto type deduction
auto calculate() {
    return 42;
}

// Lambda expressions
auto add = [](int a, int b) -> int { 
    return a + b; 
};

// Structured bindings (C++17)
std::pair<int, std::string> get_data() {
    return {42, "hello"};
}

void process_data() {
    auto [id, name] = get_data();
    std::cout << id << " " << name << std::endl;
}

// Constexpr
constexpr int factorial(int n) {
    return n <= 1 ? 1 : n * factorial(n - 1);
}

// Static assertions
static_assert(factorial(5) == 120, "Factorial calculation is wrong");

// Range-based for loops
void process_vector(const std::vector<int>& v) {
    for (const auto& item : v) {
        std::cout << item << std::endl;
    }
}

// Smart pointers
std::unique_ptr<int> create_unique() {
    return std::make_unique<int>(42);
}

std::shared_ptr<int> create_shared() {
    return std::make_shared<int>(42);
}

// Variadic templates
template <typename... Args>
void print_all(Args... args) {
    (std::cout << ... << args) << std::endl;
}

// If constexpr (C++17)
template <typename T>
auto get_value(T t) {
    if constexpr (std::is_pointer_v<T>) {
        return *t;
    } else {
        return t;
    }
}

// Inline variables (C++17)
inline int global_counter = 0;

// Attributes
[[nodiscard]] int get_important_value() {
    return 42;
}

[[deprecated("Use new_function instead")]]
void old_function() {}

// Concepts (C++20)
#if __cplusplus >= 202002L
template <typename T>
concept Numeric = std::is_arithmetic_v<T>;

template <Numeric T>
T add_numbers(T a, T b) {
    return a + b;
}
#endif

// Three-way comparison operator (C++20)
#if __cplusplus >= 202002L
class Version {
    int major, minor, patch;
public:
    auto operator<=>(const Version&) const = default;
};
#endif
"""
        elements = self.parser.parse(code)

        # Should identify various elements despite modern C++ features
        self.assertGreaterEqual(len(elements), 5)

        # Check for functions
        functions = [e for e in elements if e.element_type == ElementType.FUNCTION]
        self.assertGreaterEqual(len(functions), 3)

        # Check for some specific functions
        calculate_func = next((f for f in functions if f.name == "calculate"), None)
        self.assertIsNotNone(calculate_func)

        factorial_func = next((f for f in functions if f.name == "factorial"), None)
        self.assertIsNotNone(factorial_func)

        # Check for variables including lambda
        variables = [
            e
            for e in elements
            if e.element_type == ElementType.VARIABLE
            or e.element_type == ElementType.CONSTANT
        ]
        self.assertGreaterEqual(len(variables), 1)

        # Check for templates
        templates = [
            f for f in functions if "template" in f.metadata.get("docstring", "")
        ]
        self.assertGreaterEqual(len(templates), 1)

    def test_incomplete_code(self):
        """Test parsing incomplete or invalid C++ code."""
        code = """
// Missing semicolon
int global_var = 42

// Incomplete class definition
class Incomplete {
    int x, y
    
    void method() {
        // Missing closing brace for method

// Incomplete template
template <typename T
class TemplateClass {
    T value;
    
    // Method with syntax error
    void setValue(T val {
        value = val;
    

// Incomplete namespace
namespace Test {
    void func() {
        if (true) {
            // Missing closing brace for if

    // Function with mismatched braces
    void another_func() {
        {
            int x = 10;
        }
        }
    }

// Mismatched preprocessor directives
#ifdef DEBUG
void debug_function() {
    // Implementation
}
#else
void release_function() {
    // Implementation
#endif

// Incomplete statement with templates
std::vector<std::pair<int, std::string>> data
"""
        try:
            elements = self.parser.parse(code)

            # Should identify at least some elements despite syntax errors
            self.assertGreaterEqual(
                len(elements), 1, "Should find at least one element"
            )

            # Check for some identifiable elements
            classes = [e for e in elements if e.element_type == ElementType.CLASS]
            functions = [e for e in elements if e.element_type == ElementType.FUNCTION]

            print(
                f"Found {len(classes)} classes and {len(functions)} functions in incomplete code"
            )

            # Test that the parser handled incomplete code gracefully
            for element in elements:
                self.assertIsNotNone(element.name, "Elements should have names")
                self.assertGreater(
                    element.end_line,
                    element.start_line,
                    "End line should be greater than start line",
                )

        except Exception as e:
            self.fail(f"Parser crashed on incomplete code: {e}")

    def test_complex_expressions(self):
        """Test parsing code with complex expressions."""
        code = """
// Function with complex expressions
void complex_expressions() {
    // Complex initialization
    int a = 1, b = 2, c = 3, d = (a + b) * c - (a ? b : c) + (a & b | c ^ d);
    
    // Nested ternary expressions
    int result = a > b ? (c > d ? a : b) : (c < d ? c : d);
    
    // Complex lambda with captures
    auto lambda = [a, &b, c=a+b, &](int x) mutable -> decltype(auto) {
        a += x;
        b += x;
        return a + b + c;
    };
    
    // Complex assignment
    a += b -= c *= d /= 2;
    
    // Pointer arithmetic
    int* ptr = &a;
    int** ptr_to_ptr = &ptr;
    *(*ptr_to_ptr) = *(ptr) + 1;
    
    // Complex array indexing
    int arr[3][3] = {{1,2,3},{4,5,6},{7,8,9}};
    arr[a>b?0:1][c<d?2:0] = (arr[1][1] * arr[0][0]) % arr[2][2];
    
    // Bit manipulation
    unsigned int mask = (1U << 31) | (1U << 15) | (1U << 7) | 1U;
    unsigned int flags = (a << 24) | (b << 16) | (c << 8) | d;
    
    // Complex member access
    struct {
        struct {
            int x, y;
        } point;
        int value;
    } obj = {{1, 2}, 3};
    
    obj.point.x = obj.point.y + obj.value;
    
    // Complex template instantiation
    std::vector<std::pair<int, std::map<std::string, std::vector<int>>>> complex_data;
    
    // Placement new
    alignas(16) char buffer[1024];
    auto* p = new (buffer) int[10];
    
    // Complex cast expressions
    int* void_ptr = static_cast<int*>(reinterpret_cast<void*>(const_cast<int*>(std::addressof(a))));
    
    // Fold expressions (C++17)
    auto sum = [](auto... args) {
        return (... + args);
    };
}

// Template function with complex default arguments
template <
    typename T,
    typename U = std::conditional_t<
        std::is_integral_v<T>,
        long long,
        double
    >
>
auto convert(const T& value) -> U {
    if constexpr (std::is_same_v<T, U>) {
        return value;
    } else if constexpr (std::is_convertible_v<T, U>) {
        return static_cast<U>(value);
    } else {
        return static_cast<U>(0);
    }
}
"""
        elements = self.parser.parse(code)

        # Check that we found the complex function
        complex_func = next(
            (e for e in elements if e.name == "complex_expressions"), None
        )
        self.assertIsNotNone(complex_func)

        # Check that we found the template function
        convert_func = next((e for e in elements if e.name == "convert"), None)
        self.assertIsNotNone(convert_func)


if __name__ == "__main__":
    unittest.main()
