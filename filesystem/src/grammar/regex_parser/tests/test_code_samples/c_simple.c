/**
 * A simple C program demonstrating language features
 * with some edge cases for parser testing
 */

#include <stdio.h>
#include <stdlib.h>

// Macro with variadic arguments
#define DEBUG_PRINT(fmt, ...) printf(\"[DEBUG] \" fmt \"\
\", ##__VA_ARGS__)

// Function prototype with array parameter
void process_array(int arr[], size_t size);

// Typedef for function pointer
typedef int (*operation_func)(int, int);

// Global variable
static const char* const PROGRAM_NAME = \"parser_test\";

int main(int argc, char *argv[]) {
    // Variable declarations with initializations
    int a = 10, *p_a = &a;
    float f = 12.34f;
    char c = 'X';
    
    // Array initialization
    int numbers[] = {1, 2, 3, 4, 5};
    
    // Preprocessor conditional
    #ifdef DEBUG
    DEBUG_PRINT(\"Debug mode enabled\");
    #else
    printf(\"Running in normal mode\
\");
    #endif
    
    // Function call
    process_array(numbers, sizeof(numbers) / sizeof(numbers[0]));
    
    // Pointer arithmetic
    printf(\"Value at p_a: %d\
\", *p_a);
    p_a++;
    
    // Cast operation
    double d = (double)a / 3;
    
    // Bitwise operations
    int flags = 0x01 | 0x04;
    flags &= ~0x04;
    
    return EXIT_SUCCESS;
}

// Function implementation
void process_array(int arr[], size_t size) {
    for (size_t i = 0; i < size; i++) {
        printf(\"arr[%zu] = %d\
\", i, arr[i]);
    }
}

