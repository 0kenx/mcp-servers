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