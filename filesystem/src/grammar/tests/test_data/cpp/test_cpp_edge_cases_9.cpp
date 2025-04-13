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