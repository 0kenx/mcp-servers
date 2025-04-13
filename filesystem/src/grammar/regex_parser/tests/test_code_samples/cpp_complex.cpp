/**
 * Complex C++ program demonstrating advanced language features
 * for parser robustness testing
 */

#include <iostream>
#include <string>
#include <vector>
#include <map>
#include <unordered_map>
#include <set>
#include <algorithm>
#include <functional>
#include <memory>
#include <chrono>
#include <thread>
#include <mutex>
#include <condition_variable>
#include <atomic>
#include <future>
#include <type_traits>
#include <optional>
#include <variant>
#include <any>
#include <tuple>
#include <initializer_list>
#include <regex>
#include <cassert>
#include <stdexcept>

// Preprocessor macro with complex expansion
#define CONCATENATE_IMPL(s1, s2) s1##s2
#define CONCATENATE(s1, s2) CONCATENATE_IMPL(s1, s2)
#define ANONYMOUS_VARIABLE(str) CONCATENATE(str, __LINE__)

// Macro for static assertions with string concat
#define ENSURE_TYPE(T, U) \
    static_assert(std::is_same_v<T, U>, \
    "Type mismatch: " #T " is not the same as " #U)

// Generic constexpr if helper for templates
#define REQUIRES(...) typename std::enable_if_t<(__VA_ARGS__), int> = 0

// Forward declarations
template<typename T> class SharedState;
template<typename T> class Observable;

// Namespace for utility functions
namespace Utils {
    // Enum class with explicit underlying type
    enum class LogLevel : uint8_t {
        Debug = 0,
        Info = 1,
        Warning = 2,
        Error = 3,
        Critical = 4
    };
    
    // Overloaded operator for enum
    inline std::ostream& operator<<(std::ostream& os, LogLevel level) {
        switch (level) {
            case LogLevel::Debug: return os << "DEBUG";
            case LogLevel::Info: return os << "INFO";
            case LogLevel::Warning: return os << "WARNING";
            case LogLevel::Error: return os << "ERROR";
            case LogLevel::Critical: return os << "CRITICAL";
            default: return os << "UNKNOWN";
        }
    }
    
    // Template variable
    template<typename T>
    constexpr bool is_numeric_v = std::is_arithmetic_v<T> && !std::is_same_v<T, bool>;
    
    // Variadic template function
    template<typename... Args>
    void log(LogLevel level, const std::string& format, Args&&... args) {
        // Implementation omitted
        std::cout << "[" << level << "] ";
        // In a real implementation, this would format the string with args
        std::cout << format << std::endl;
    }
    
    // SFINAE example with std::enable_if
    template<typename T>
    typename std::enable_if_t<is_numeric_v<T>, T>
    square(T value) {
        return value * value;
    }
    
    // Specialization for strings
    template<typename T>
    typename std::enable_if_t<std::is_same_v<T, std::string>, T>
    square(T value) {
        return value + value;
    }
    
    // Concept-like constraint using C++17 techniques
    template<typename T, REQUIRES(is_numeric_v<T> && sizeof(T) <= sizeof(long))>
    auto safe_cast(double value) {
        return static_cast<T>(value);
    }
} // namespace Utils

// Mixin template for adding observable behavior
template<typename Derived>
class ObservableMixin {
public:
    using ObserverFunc = std::function<void(const Derived&)>;
    
private:
    std::vector<ObserverFunc> observers_;
    
protected:
    void notify_observers() const {
        auto& derived = static_cast<const Derived&>(*this);
        for (const auto& observer : observers_) {
            observer(derived);
        }
    }
    
public:
    void add_observer(ObserverFunc observer) {
        observers_.push_back(std::move(observer));
    }
};

// CRTP with multiple inheritance
template<typename T>
class Singleton : public ObservableMixin<T> {
protected:
    Singleton() = default;
    ~Singleton() = default;
    
public:
    Singleton(const Singleton&) = delete;
    Singleton& operator=(const Singleton&) = delete;
    
    static T& instance() {
        static T instance;
        return instance;
    }
};

// Complex template with multiple parameters and defaults
template<
    typename T,
    typename Allocator = std::allocator<T>,
    typename Compare = std::less<T>,
    typename Hash = std::hash<T>,
    bool ThreadSafe = false
>
class Container {
private:
    // Type aliases
    using value_type = T;
    using reference = value_type&;
    using const_reference = const value_type&;
    using pointer = typename std::allocator_traits<Allocator>::pointer;
    
    std::vector<T, Allocator> data_;
    mutable std::conditional_t<ThreadSafe, std::mutex, std::monostate> mutex_;
    
    // SFINAE for thread-safe methods
    template<bool IsSafe = ThreadSafe>
    std::enable_if_t<IsSafe, void> lock() const {
        std::get<std::mutex>(mutex_).lock();
    }
    
    template<bool IsSafe = ThreadSafe>
    std::enable_if_t<IsSafe, void> unlock() const {
        std::get<std::mutex>(mutex_).unlock();
    }
    
    template<bool IsSafe = ThreadSafe>
    std::enable_if_t<!IsSafe, void> lock() const {}
    
    template<bool IsSafe = ThreadSafe>
    std::enable_if_t<!IsSafe, void> unlock() const {}
    
public:
    // Constructor with forwarding references
    template<typename... Args>
    explicit Container(Args&&... args) : data_(std::forward<Args>(args)...) {}
    
    // Constructor with initializer list
    Container(std::initializer_list<T> init) : data_(init) {}
    
    // Method with auto return type and trailing return type
    auto size() const -> size_t {
        lock();
        auto result = data_.size();
        unlock();
        return result;
    }
    
    // Method template with constraints
    template<typename U, REQUIRES(std::is_constructible_v<T, U>)>
    void add(U&& value) {
        lock();
        data_.push_back(std::forward<U>(value));
        unlock();
    }
    
    // Iterator support
    auto begin() { return data_.begin(); }
    auto end() { return data_.end(); }
    auto begin() const { return data_.begin(); }
    auto end() const { return data_.end(); }
    
    // Operator overloading with reference qualifiers
    Container& operator+=(const Container& other) & {
        lock();
        data_.insert(data_.end(), other.data_.begin(), other.data_.end());
        unlock();
        return *this;
    }
    
    // Rvalue qualified operator
    Container operator+(const Container& other) && {
        lock();
        data_.insert(data_.end(), other.data_.begin(), other.data_.end());
        unlock();
        return std::move(*this);
    }
    
    // Nested class
    class Iterator {
    private:
        typename std::vector<T>::iterator it_;
        
    public:
        explicit Iterator(typename std::vector<T>::iterator it) : it_(it) {}
        
        T& operator*() { return *it_; }
        Iterator& operator++() { ++it_; return *this; }
        bool operator!=(const Iterator& other) const { return it_ != other.it_; }
    };
};

// Class template partial specialization
template<typename T, typename Allocator, typename Compare>
class Container<T*, Allocator, Compare, std::hash<T*>, true> {
public:
    Container() {
        std::cerr << "Pointer specialization not implemented" << std::endl;
    }
};

// Fold expressions and variadic templates
template<typename... Args>
auto sum(Args... args) {
    return (... + args);
}

template<typename... Args>
auto product(Args... args) {
    return (... * args);
}

// Complex lambda expressions
auto create_counter() {
    std::atomic<int> counter{0};
    return [counter = std::move(counter)] () mutable {
        return ++counter;
    };
}

// Function with complex return type
auto create_transformation_pipeline() {
    return [](auto input) {
        return [input = std::move(input)](auto... transforms) {
            auto result = input;
            (result = transforms(result), ...);
            return result;
        };
    };
}

// Function template with if constexpr
template<typename T>
auto process(T&& input) {
    if constexpr (std::is_integral_v<std::decay_t<T>>) {
        return input * 2;
    } else if constexpr (std::is_floating_point_v<std::decay_t<T>>) {
        return input * 3.14;
    } else if constexpr (std::is_same_v<std::decay_t<T>, std::string>) {
        return input + input;
    } else {
        static_assert(std::is_default_constructible_v<std::decay_t<T>>,
                      "Unsupported type for process function");
        return std::decay_t<T>{};
    }
}

// Complex template metaprogramming
template<typename T, typename = void>
struct has_serialize : std::false_type {};

template<typename T>
struct has_serialize<T, std::void_t<decltype(std::declval<T>().serialize())>> : std::true_type {};

// Recursive template
template<size_t N>
struct Factorial {
    static constexpr size_t value = N * Factorial<N - 1>::value;
};

template<>
struct Factorial<0> {
    static constexpr size_t value = 1;
};

// Template with non-type template parameters
template<typename T, size_t Size>
class FixedArray {
private:
    T data_[Size];
    
public:
    constexpr T& operator[](size_t index) {
        if (index >= Size) throw std::out_of_range("Index out of bounds");
        return data_[index];
    }
    
    constexpr const T& operator[](size_t index) const {
        if (index >= Size) throw std::out_of_range("Index out of bounds");
        return data_[index];
    }
    
    constexpr size_t size() const { return Size; }
    
    // Iterator methods
    constexpr T* begin() { return data_; }
    constexpr T* end() { return data_ + Size; }
    constexpr const T* begin() const { return data_; }
    constexpr const T* end() const { return data_ + Size; }
};

// Variadic class template
template<typename... Ts>
class Tuple {};

template<typename T, typename... Ts>
class Tuple<T, Ts...> : private Tuple<Ts...> {
private:
    T value;
    
public:
    constexpr Tuple(T&& head, Ts&&... tail)
        : Tuple<Ts...>(std::forward<Ts>(tail)...), value(std::forward<T>(head)) {}
    
    constexpr T& head() { return value; }
    constexpr const T& head() const { return value; }
    
    constexpr Tuple<Ts...>& tail() { return *this; }
    constexpr const Tuple<Ts...>& tail() const { return *this; }
};

// Deduction guide for tuple
template<typename... Ts>
Tuple(Ts... args) -> Tuple<Ts...>;

// Async helper with complex return type
template<typename Func, typename... Args>
auto run_async(Func&& func, Args&&... args) {
    using ReturnType = std::invoke_result_t<Func, Args...>;
    using FutureType = std::future<ReturnType>;
    
    auto shared_func = std::make_shared<std::packaged_task<ReturnType()>>(
        [f = std::forward<Func>(func), ... params = std::forward<Args>(args)]() mutable {
            return std::invoke(f, params...);
        }
    );
    
    FutureType future = shared_func->get_future();
    
    std::thread([shared_func]() {
        (*shared_func)();
    }).detach();
    
    return future;
}

class IncompleteClass {
public:
    virtual void init() =
    
private:
    std::
    

// Complex inheritance with virtual functions
class BaseComponent {
public:
    virtual ~BaseComponent() = default;
    virtual void update() = 0;
};

class Component : public BaseComponent {
private:
    std::string name_;
    
public:
    explicit Component(std::string name) : name_(std::move(name)) {}
    
    void update() override {
        std::cout << "Component " << name_ << " updated" << std::endl;
    }
};

template<typename... Components>
class CompositeComponent : public BaseComponent, public Components... {
private:
    std::vector<std::unique_ptr<BaseComponent>> children_;
    
public:
    template<typename T, typename... Args>
    T& add_child(Args&&... args) {
        auto child = std::make_unique<T>(std::forward<Args>(args)...);
        T& ref = *child;
        children_.push_back(std::move(child));
        return ref;
    }
    
    void update() override {
        for (auto& child : children_) {
            child->update();
        }
        (Components::update(), ...);  // Call update on all inherited Components
    }
};

// Main function with complex C++17/20 features
int main() {
    // Structured bindings
    std::map<std::string, int> scores = {{"Alice", 95}, {"Bob", 87}, {"Charlie", 92}};
    for (const auto& [name, score] : scores) {
        std::cout << name << ": " << score << std::endl;
    }
    
    // Optional and variant
    std::optional<std::string> maybe_string = "Hello";
    std::variant<int, std::string, double> var = 42;
    
    // std::visit with variant
    std::visit([](auto&& arg) {
        using T = std::decay_t<decltype(arg)>;
        if constexpr (std::is_same_v<T, int>) {
            std::cout << "int: " << arg << std::endl;
        } else if constexpr (std::is_same_v<T, std::string>) {
            std::cout << "string: " << arg << std::endl;
        } else if constexpr (std::is_same_v<T, double>) {
            std::cout << "double: " << arg << std::endl;
        }
    }, var);
    
    // Any type
    std::any value = 3.14;
    try {
        std::cout << std::any_cast<double>(value) << std::endl;
        value = std::string("Hello");
        std::cout << std::any_cast<std::string>(value) << std::endl;
    } catch (const std::bad_any_cast& e) {
        std::cerr << "Bad any cast: " << e.what() << std::endl;
    }
    
    // Tuple and structured bindings
    auto person = std::make_tuple("John", 30, true);
    auto [name, age, active] = person;
    std::cout << name << " is " << age << " years old" << std::endl;
    
    // Template variables and compile-time evaluation
    constexpr auto factorial_10 = Factorial<10>::value;
    std::cout << "10! = " << factorial_10 << std::endl;
    
    // Fixed size array with constexpr
    constexpr FixedArray<int, 5> fixed_array = {1, 2, 3, 4, 5};
    for (auto value : fixed_array) {
        std::cout << value << " ";
    }
    std::cout << std::endl;
    
    // Lambda capture with initialization
    auto generator = [base = 10]() mutable {
        return base++;
    };
    
    // Thread with lambda
    std::mutex mtx;
    std::condition_variable cv;
    bool ready = false;
    
    std::thread worker([&]() {
        std::unique_lock<std::mutex> lock(mtx);
        cv.wait(lock, [&]{ return ready; });
        
        std::cout << "Worker thread running" << std::endl;
    });
    
    {
        std::lock_guard<std::mutex> lock(mtx);
        ready = true;
    }
    
    cv.notify_one();
    worker.join();
    
    // Async execution with future
    auto future = run_async([](int a, int b) {
        std::this_thread::sleep_for(std::chrono::milliseconds(100));
        return a + b;
    }, 5, 10);
    
    std::cout << "Async result: " << future.get() << std::endl;
    
    // Container with complex template parameters
    Container<std::string> strings = {"Hello", "World"};
    strings.add("Parser");
    strings.add("Test");
    
    for (const auto& str : strings) {
        std::cout << str << " ";
    }
    std::cout << std::endl;
    
    // Fold expressions
    std::cout << "Sum: " << sum(1, 2, 3, 4, 5) << std::endl;
    std::cout << "Product: " << product(1, 2, 3, 4, 5) << std::endl;
    
    // if constexpr example
    std::cout << "Process int: " << process(10) << std::endl;
    std::cout << "Process double: " << process(3.14) << std::endl;
    std::cout << "Process string: " << process(std::string("Test")) << std::endl;
    
    // Counter with lambda capture
    auto counter = create_counter();
    std::cout << "Count: " << counter() << std::endl;
    std::cout << "Count: " << counter() << std::endl;
    
    // Transformation pipeline
    auto pipeline = create_transformation_pipeline()("Hello");
    auto result = pipeline(
        [](auto s) { return s + " World"; },
        [](auto s) { return s + "!"; },
        [](auto s) { return s + " (transformed)"; }
    );
    
    std::cout << "Pipeline result: " << result << std::endl;
    
    // Template metaprogramming
    class Serializable {
    public:
        std::string serialize() const { return "serialized"; }
    };
    
    std::cout << "Has serialize: " << has_serialize<Serializable>::value << std::endl;
    std::cout << "Has serialize (int): " << has_serialize<int>::value << std::endl;
    
    return 0;
}
