/**
 * A simple C++ program demonstrating language features
 * with some edge cases for parser testing
 */

#include <iostream>
#include <vector>
#include <string>
#include <memory>
#include <algorithm>

// Class declaration with template
template <typename T>
class Container {
private:
    std::vector<T> data;

public:
    // Constructor with initializer list
    Container(std::initializer_list<T> items) : data(items) {}
    
    // Method with reference parameter
    void add(const T& item) {
        data.push_back(item);
    }
    
    // Method with rvalue reference
    void add(T&& item) {
        data.push_back(std::move(item));
    }
    
    // Overloaded operators
    const T& operator[](size_t index) const {
        return data[index];
    }
    
    // Friend function declaration
    friend std::ostream& operator<<(std::ostream& os, const Container<T>& container) {
        os << \"Container with \" << container.data.size() << \" items: \";
        for (const auto& item : container.data) {
            os << item << \" \";
        }
        return os;
    }
    
    // Method with auto return type
    auto size() const -> size_t {
        return data.size();
    }
};

// Function template
template <typename T>
T max_value(T a, T b) {
    return (a > b) ? a : b;
}

// Lambda function example
auto main() -> int {
    // Smart pointer
    auto ptr = std::make_shared<std::string>(\"Hello parser test\");
    
    // Container with template argument deduction
    Container values = {1, 2, 3, 4, 5};
    values.add(6);
    
    std::cout << values << std::endl;
    
    // Lambda function with capture
    int multiplier = 3;
    auto multiply = [multiplier](int value) -> int {
        return value * multiplier;
    };
    
    // Range-based for loop
    for (const auto& val : {\"a\", \"b\", \"c\"}) {
        std::cout << val << \" \";
    }
    std::cout << std::endl;
    
    return 0;
}

