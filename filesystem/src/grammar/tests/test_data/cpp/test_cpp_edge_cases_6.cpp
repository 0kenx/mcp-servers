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