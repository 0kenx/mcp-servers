// C++ validation file with complex but valid language features to test parser robustness

#include <iostream>
#include <vector>
#include <map>
#include <unordered_map>
#include <string>
#include <memory>
#include <functional>
#include <algorithm>
#include <type_traits>
#include <utility>
#include <chrono>
#include <thread>
#include <mutex>
#include <condition_variable>
#include <future>
#include <optional>
#include <variant>
#include <any>
#include <concepts> // C++20 feature

// Template metaprogramming
template<unsigned N>
struct Factorial {
    static constexpr unsigned value = N * Factorial<N-1>::value;
};

template<>
struct Factorial<0> {
    static constexpr unsigned value = 1;
};

// Variadic templates and fold expressions
template<typename... Args>
auto sum(Args... args) {
    return (args + ...); // C++17 fold expression
}

// Concepts and requires (C++20)
template<typename T>
concept Numeric = std::is_arithmetic_v<T>;

template<Numeric T>
T squared(T value) {
    return value * value;
}

// Complex class with CRTP pattern
template<typename Derived>
class Base {
public:
    void interface() {
        static_cast<Derived*>(this)->implementation();
    }
    
protected:
    ~Base() = default;
};

class Derived : public Base<Derived> {
public:
    void implementation() {
        std::cout << "Derived implementation\n";
    }
};

// SFINAE and type traits
template<typename T, typename = void>
struct has_to_string : std::false_type {};

template<typename T>
struct has_to_string<T, std::void_t<decltype(std::declval<T>().to_string())>> : std::true_type {};

// Smart pointer custom deleter
struct FileDeleter {
    void operator()(std::FILE* file) const {
        if (file) {
            std::fclose(file);
            std::cout << "File closed\n";
        }
    }
};

using FilePtr = std::unique_ptr<std::FILE, FileDeleter>;

// Mixin pattern with multiple inheritance
template<typename T>
class Serializable {
public:
    std::string serialize() const {
        return static_cast<const T*>(this)->to_string();
    }
};

template<typename T>
class Loggable {
public:
    void log(const std::string& message) const {
        std::cout << "Log [" << static_cast<const T*>(this)->name() << "]: " << message << "\n";
    }
};

class ComplexObject : public Serializable<ComplexObject>, public Loggable<ComplexObject> {
private:
    std::string name_;
    int value_;
    
public:
    ComplexObject(std::string name, int value) : name_(std::move(name)), value_(value) {}
    
    std::string to_string() const {
        return name_ + ":" + std::to_string(value_);
    }
    
    std::string name() const {
        return name_;
    }
};

// Advanced lambda captures
auto make_logger(std::string prefix) {
    return [prefix = std::move(prefix)](const std::string& message) mutable {
        std::cout << prefix << ": " << message << "\n";
        prefix += "+"; // Mutable state
    };
}

// Perfect forwarding and variadic templates
template<typename T, typename... Args>
std::unique_ptr<T> make_unique_wrapper(Args&&... args) {
    return std::make_unique<T>(std::forward<Args>(args)...);
}

// Custom iterator with iterator_traits support
template<typename T>
class VectorWrapper {
private:
    std::vector<T> data_;
    
public:
    class Iterator {
    public:
        using iterator_category = std::forward_iterator_tag;
        using value_type = T;
        using difference_type = std::ptrdiff_t;
        using pointer = T*;
        using reference = T&;
        
    private:
        typename std::vector<T>::iterator it_;
        
    public:
        explicit Iterator(typename std::vector<T>::iterator it) : it_(it) {}
        
        Iterator& operator++() { ++it_; return *this; }
        Iterator operator++(int) { Iterator tmp = *this; ++(*this); return tmp; }
        
        bool operator==(const Iterator& other) const { return it_ == other.it_; }
        bool operator!=(const Iterator& other) const { return it_ != other.it_; }
        
        reference operator*() const { return *it_; }
        pointer operator->() const { return &(*it_); }
    };
    
    VectorWrapper() = default;
    
    template<typename InputIt>
    VectorWrapper(InputIt first, InputIt last) : data_(first, last) {}
    
    Iterator begin() { return Iterator(data_.begin()); }
    Iterator end() { return Iterator(data_.end()); }
    
    void push_back(const T& value) { data_.push_back(value); }
    size_t size() const { return data_.size(); }
};

// Structured bindings with tuple-like types
struct Point {
    int x;
    int y;
    int z;
    
    template<size_t N>
    decltype(auto) get() const {
        if constexpr (N == 0) return x;
        else if constexpr (N == 1) return y;
        else if constexpr (N == 2) return z;
    }
};

// Support for structured bindings
namespace std {
    template<>
    struct tuple_size<Point> : std::integral_constant<size_t, 3> {};
    
    template<size_t N>
    struct tuple_element<N, Point> {
        using type = decltype(std::declval<Point>().template get<N>());
    };
}

// CRTP with static polymorphism
template<typename T>
class Shape {
public:
    double area() const { return static_cast<const T*>(this)->area_impl(); }
    double perimeter() const { return static_cast<const T*>(this)->perimeter_impl(); }
};

class Circle : public Shape<Circle> {
private:
    double radius_;
    
public:
    explicit Circle(double radius) : radius_(radius) {}
    
    double area_impl() const {
        return 3.14159 * radius_ * radius_;
    }
    
    double perimeter_impl() const {
        return 2 * 3.14159 * radius_;
    }
};

// Multithreading with futures and promises
class AsyncProcessor {
private:
    std::mutex mutex_;
    std::condition_variable cv_;
    bool ready_ = false;
    std::vector<int> results_;
    
public:
    std::future<std::vector<int>> process(std::vector<int> data) {
        std::promise<std::vector<int>> promise;
        std::future<std::vector<int>> future = promise.get_future();
        
        std::thread worker([this, data = std::move(data), promise = std::move(promise)]() mutable {
            std::vector<int> result;
            
            for (int value : data) {
                result.push_back(value * value);
                std::this_thread::sleep_for(std::chrono::milliseconds(10));
            }
            
            std::unique_lock<std::mutex> lock(mutex_);
            results_ = result;
            ready_ = true;
            cv_.notify_all();
            
            promise.set_value(std::move(result));
        });
        
        worker.detach();
        return future;
    }
    
    std::vector<int> wait_for_results() {
        std::unique_lock<std::mutex> lock(mutex_);
        cv_.wait(lock, [this] { return ready_; });
        return results_;
    }
};

// Template template parameters
template<template<typename...> class Container, typename T>
Container<T> create_container(std::initializer_list<T> items) {
    return Container<T>(items);
}

// Type erasure pattern
class Drawable {
private:
    struct Concept {
        virtual ~Concept() = default;
        virtual void draw() const = 0;
        virtual std::unique_ptr<Concept> clone() const = 0;
    };
    
    template<typename T>
    struct Model : Concept {
        T data_;
        
        explicit Model(T data) : data_(std::move(data)) {}
        
        void draw() const override {
            data_.draw();
        }
        
        std::unique_ptr<Concept> clone() const override {
            return std::make_unique<Model>(*this);
        }
    };
    
    std::unique_ptr<Concept> pimpl_;
    
public:
    template<typename T>
    explicit Drawable(T x) : pimpl_(std::make_unique<Model<T>>(std::move(x))) {}
    
    Drawable(const Drawable& other) : pimpl_(other.pimpl_->clone()) {}
    Drawable(Drawable&&) noexcept = default;
    
    Drawable& operator=(const Drawable& other) {
        if (this != &other) {
            pimpl_ = other.pimpl_->clone();
        }
        return *this;
    }
    
    Drawable& operator=(Drawable&&) noexcept = default;
    
    void draw() const {
        pimpl_->draw();
    }
};

// Main function demonstrating usage
int main() {
    // Template metaprogramming
    std::cout << "5! = " << Factorial<5>::value << std::endl;
    
    // Variadic templates
    std::cout << "Sum: " << sum(1, 2, 3, 4, 5) << std::endl;
    
    // CRTP pattern
    Derived d;
    d.interface();
    
    // Mixin pattern
    ComplexObject obj("Object1", 42);
    std::cout << "Serialized: " << obj.serialize() << std::endl;
    obj.log("Initialized");
    
    // Lambdas and captures
    auto logger = make_logger("LOG");
    logger("First message");
    logger("Second message");
    
    // Custom iterator
    VectorWrapper<int> wrapper;
    wrapper.push_back(1);
    wrapper.push_back(2);
    wrapper.push_back(3);
    
    for (auto value : wrapper) {
        std::cout << value << " ";
    }
    std::cout << std::endl;
    
    // Structured bindings
    Point p{10, 20, 30};
    auto [x, y, z] = p;
    std::cout << "Point: " << x << ", " << y << ", " << z << std::endl;
    
    // Static polymorphism
    Circle circle(5.0);
    std::cout << "Circle area: " << circle.area() << std::endl;
    std::cout << "Circle perimeter: " << circle.perimeter() << std::endl;
    
    // Type erasure
    struct Square {
        void draw() const {
            std::cout << "Drawing square\n";
        }
    };
    
    struct Triangle {
        void draw() const {
            std::cout << "Drawing triangle\n";
        }
    };
    
    std::vector<Drawable> shapes;
    shapes.emplace_back(Square{});
    shapes.emplace_back(Triangle{});
    
    for (const auto& shape : shapes) {
        shape.draw();
    }
    
    // Template template parameters
    auto vec = create_container<std::vector>(std::initializer_list<int>{1, 2, 3, 4, 5});
    std::cout << "Container size: " << vec.size() << std::endl;
    
    // Async processing
    AsyncProcessor processor;
    auto future = processor.process({1, 2, 3, 4, 5});
    
    auto status = future.wait_for(std::chrono::milliseconds(100));
    if (status == std::future_status::ready) {
        auto results = future.get();
        std::cout << "Results: ";
        for (int value : results) {
            std::cout << value << " ";
        }
        std::cout << std::endl;
    } else {
        std::cout << "Still processing...\n";
        auto results = future.get(); // Will wait until ready
        std::cout << "Results now ready: ";
        for (int value : results) {
            std::cout << value << " ";
        }
        std::cout << std::endl;
    }
    
    return 0;
} 