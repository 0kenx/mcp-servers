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