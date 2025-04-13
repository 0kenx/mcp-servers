// C++ validation file with syntax errors to test parser robustness

#include <iostream>
#include <vector>
#include <string>
#include <memory>

// Error: Extra token
class ExtraToken {
public:
    int value;
};; // Extra semicolon

// Error: Missing semicolon
class MissingSemicolon {
public:
    int value
}; // Missing semicolon after 'value'

// Error: Mismatched brackets
void mismatched_brackets() {
    std::vector<int> values = {1, 2, 3];  // Mismatched brackets
}

// Error: Mismatched parentheses
void mismatched_parentheses(int x, int y {  // Missing closing parenthesis
    return x + y;
}

// Error: Undefined variable
void undefined_variable() {
    int x = 10;
    std::cout << y << std::endl;  // 'y' is not defined
}

// Error: Type mismatch
void type_mismatch() {
    int x = "string";  // Cannot assign string to int
    std::string s = 42;  // Cannot assign int to string
}

// Error: Duplicate variable declaration
void duplicate_variable() {
    int x = 10;
    int x = 20;  // Redeclaration of 'x'
}

// Error: Wrong function call syntax
void wrong_function_call() {
    std::cout.println("Hello");  // No 'println' method in cout
}

// Error: Using class template without template arguments
void missing_template_args() {
    std::vector v;  // Missing template arguments for vector
}

// Error: Wrong template syntax
template <class T, class> class WrongTemplate {  // Missing template parameter name
    T value;
};

// Error: Access control conflict
class AccessConflict {
public:
private:
public:  // Duplicate access specifier
    int value;
};

// Error: Multiple inheritance ambiguity
class Base1 {
public:
    int value = 1;
};

class Base2 {
public:
    int value = 2;
};

class Derived : public Base1, public Base2 {  // Diamond problem
public:
    void printValue() {
        std::cout << value;  // Ambiguous: Base1::value or Base2::value?
    }
};

// Error: Incorrect lambda syntax
auto lambda = [x, y]() {  // x and y not captured or declared
    return x + y;
};

// Error: Missing template keyword
void template_error() {
    std::vector<int> v;
    auto it = v.begin();
    std::vector<int>::iterator::value_type val = *it;  // Missing 'typename'
}

// Error: Duplicate template parameter
template <typename T, typename T>  // Duplicate 'T'
class DuplicateParam {
    T value;
};

// Error: Missing operator in expression
void missing_operator() {
    int x = 5;
    int y = 10;
    int z = x y;  // Missing operator between x and y
}

// Error: Misuse of scope resolution operator
void scope_error() {
    std::cout::endl;  // Incorrect use of scope resolution
}

// Error: Declaring a variable with 'void' type
void type_void_error() {
    void x = 10;  // Cannot declare variable of type 'void'
}

// Error: Multiple unrelated errors in one function
void multiple_errors() {
    int x = "string";  // Type mismatch
    y = 20;  // Undefined variable
    std::vector<> v;  // Missing template argument
    v.non_existent_method();  // Non-existent method
}

// Error: Break outside of loop
void break_outside_loop() {
    if (true) {
        break;  // Break outside of loop
    }
}

// Error: Using non-static member without object
class NonStaticMember {
public:
    void method() {}
};

void call_without_object() {
    NonStaticMember::method();  // Calling non-static method without object
}

// Error: Missing return statement
int missing_return() {
    int x = 10;
    // Missing return statement
}

// Error: Wrong inheritance syntax
class Base {
public:
    virtual void foo() {}
};

class WrongInheritance : Base {  // Missing 'public', 'protected', or 'private'
public:
    void foo() override {}
};

// Error: Invalid delete
void invalid_delete() {
    int x = 10;
    delete x;  // Cannot delete non-pointer
}

// Error: Comparison between pointer and integer
void pointer_integer_comparison(int* ptr) {
    if (ptr == 5) {  // Comparing pointer to integer
        std::cout << "Equal" << std::endl;
    }
}

// Error: Invalid struct initialization
struct Point {
    int x;
    int y;
};

void invalid_initialization() {
    Point p = {1, 2, 3};  // Too many initializers
}

// Error: Incomplete enum value assignment
enum Color {
    RED = ,  // Missing value
    GREEN,
    BLUE
}; 