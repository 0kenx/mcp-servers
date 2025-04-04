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