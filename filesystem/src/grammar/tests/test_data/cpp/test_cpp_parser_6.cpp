/**
 * Generic maximum function.
 */
template <typename T>
T max(T a, T b) {
    return (a > b) ? a : b;
}

/**
 * Generic container class.
 */
template <typename T, int Size = 10>
class Container {
private:
    T data[Size];
    
public:
    Container() {}
    
    T& get(int index) {
        return data[index];
    }
    
    void set(int index, const T& value) {
        data[index] = value;
    }
};