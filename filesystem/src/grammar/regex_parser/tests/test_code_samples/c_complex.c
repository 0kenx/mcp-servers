{
  `path`: `complex_c.c`,
  `content`: `/**
 * Complex C program demonstrating advanced language features
 * for parser robustness testing
 */

#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <string.h>
#include <stdarg.h>
#include <stdbool.h>
#include <assert.h>
#include <setjmp.h>
#include <time.h>

/* Macro definitions with various complexities */
#define CONCAT(a, b) a##b
#define STRINGIFY(x) #x
#define MAX(a, b) ((a) > (b) ? (a) : (b))
#define SWAP(a, b, type) do { type temp = a; a = b; b = temp; } while(0)

/* Complex macro with multiple statements and token pasting */
#define DECLARE_LIST(type) \\
    typedef struct CONCAT(List_, type) { \\
        type* data; \\
        size_t size; \\
        size_t capacity; \\
    } CONCAT(List_, type); \\
    \\
    CONCAT(List_, type)* CONCAT(list_create_, type)(size_t initial_capacity) { \\
        CONCAT(List_, type)* list = malloc(sizeof(CONCAT(List_, type))); \\
        if (!list) return NULL; \\
        list->data = malloc(sizeof(type) * initial_capacity); \\
        if (!list->data) { \\
            free(list); \\
            return NULL; \\
        } \\
        list->size = 0; \\
        list->capacity = initial_capacity; \\
        return list; \\
    } \\
    \\
    void CONCAT(list_free_, type)(CONCAT(List_, type)* list) { \\
        if (list) { \\
            free(list->data); \\
            free(list); \\
        } \\
    }

/* Function-like macro with variable arguments */
#define LOG_ERROR(format, ...) \\
    do { \\
        fprintf(stderr, \"[ERROR] %s:%d: \" format \"\
\", \\
                __FILE__, __LINE__, ##__VA_ARGS__); \\
    } while(0)

/* Bit field structure */
typedef struct {
    unsigned int flags : 4;
    unsigned int mode : 2;
    unsigned int : 0;  /* Zero-width field for alignment */
    unsigned int status : 3;
} BitFields;

/* Union with anonymous struct */
typedef union {
    struct {
        uint8_t r;
        uint8_t g;
        uint8_t b;
        uint8_t a;
    };
    uint32_t value;
} Color;

/* Complex enum definition */
typedef enum {
    STATE_INIT = 0,
    STATE_RUNNING = 1,
    STATE_PAUSED = 2,
    STATE_ERROR = -1,
    STATE_COMPLETED = STATE_RUNNING | 0x10,
    STATE_MAX
} State;

/* Typedef for nested function pointer array */
typedef int (*ComplexFuncPtr[5])(void*, size_t);

/* Structure with function pointers */
typedef struct {
    char* name;
    size_t (*size_func)(void*);
    void* (*clone_func)(const void*);
    int (*compare_func)(const void*, const void*);
} TypeInfo;

/* Apply the list macro to create list types */
DECLARE_LIST(int)
DECLARE_LIST(double)

/* Static global variables */
static jmp_buf jump_buffer;
static const char* const error_messages[] = {
    \"No error\",
    \"Out of memory\",
    \"Invalid argument\",
    \"Operation not permitted\",
    \"Resource temporarily unavailable\"
};

/* Global function pointer */
static int (*g_callback)(void*, void*) = NULL;

/* Forward declarations */
struct Node;  /* Forward declaration for self-referential struct */
typedef struct Node Node;

/* Self-referential structure */
struct Node {
    int data;
    Node* next;
    Node* prev;
};

/* Circular linked list function prototypes */
Node* node_create(int data);
void node_insert_after(Node* node, Node* new_node);
Node* node_remove(Node* node);
void node_free_list(Node* head);

/* Function with complex pointer parameters */
void manipulate_data(int** data, size_t* size, int (*transform)(int));

/* Function with variadic arguments */
int sum_values(int count, ...);

/* Inline function */
static inline int square(int x) {
    return x * x;
}

int incomplete(int a, {
    if (a < 0) {
    

/* Function that returns a function pointer */
int (*get_operation(char op))(int, int) {
    switch (op) {
        case '+': return &add;
        case '-': return &subtract;
        case '*': return &multiply;
        case '/': return &divide;
        default:  return NULL;
    }
}

/* Helper arithmetic functions */
int add(int a, int b) { return a + b; }
int subtract(int a, int b) { return a - b; }
int multiply(int a, int b) { return a * b; }
int divide(int a, int b) { return b != 0 ? a / b : 0; }

/* Function with multiple nested conditionals */
int complex_conditional(int a, int b, int c) {
    if (a > 0) {
        if (b > 0) {
            if (c > 0) {
                return a + b + c;
            } else if (c == 0) {
                return a + b;
            } else {
                return a + b - c;
            }
        } else if (b == 0) {
            return a > c ? a : c;
        } else {
            return a - b + (c > 0 ? c : 0);
        }
    } else if (a == 0) {
        return b + c;
    } else {
        if (b < 0 && c < 0) {
            return -(a + b + c);
        } else {
            return b - a + c;
        }
    }
}

/* Function with goto statements */
int process_with_goto(int* array, size_t size) {
    if (!array || size == 0) {
        goto error_invalid_input;
    }
    
    int sum = 0;
    for (size_t i = 0; i < size; i++) {
        if (array[i] < 0) {
            goto error_negative_value;
        }
        sum += array[i];
    }
    
    return sum;

error_negative_value:
    LOG_ERROR(\"Negative value found in array\");
    return -1;

error_invalid_input:
    LOG_ERROR(\"Invalid input parameters\");
    return -2;
}

/* Complex multi-dimensional array handling function */
void process_matrix(int rows, int cols, int matrix[rows][cols]) {
    for (int i = 0; i < rows; i++) {
        for (int j = 0; j < cols; j++) {
            matrix[i][j] = (i + 1) * (j + 1);
        }
    }
    
    /* VLA handling example */
    int transposed[cols][rows];
    for (int i = 0; i < cols; i++) {
        for (int j = 0; j < rows; j++) {
            transposed[i][j] = matrix[j][i];
        }
    }
    
    /* Example with pointer arithmetic */
    int *flat_view = &matrix[0][0];
    for (int i = 0; i < rows * cols; i++) {
        flat_view[i] *= 2;
    }
}

/* Node implementation */
Node* node_create(int data) {
    Node* node = (Node*)malloc(sizeof(Node));
    if (node) {
        node->data = data;
        node->next = node;  /* Points to itself initially */
        node->prev = node;
    }
    return node;
}

void node_insert_after(Node* node, Node* new_node) {
    if (!node || !new_node) return;
    
    new_node->next = node->next;
    new_node->prev = node;
    node->next->prev = new_node;
    node->next = new_node;
}

Node* node_remove(Node* node) {
    if (!node) return NULL;
    
    /* Last node in list */
    if (node->next == node) {
        return node;
    }
    
    node->prev->next = node->next;
    node->next->prev = node->prev;
    Node* next = node->next;
    node->next = node->prev = NULL;
    return next;
}

void node_free_list(Node* head) {
    if (!head) return;
    
    Node* current = head;
    Node* next;
    
    do {
        next = current->next;
        free(current);
        current = next;
    } while (current != head && current != NULL);
}

/* Variadic function implementation */
int sum_values(int count, ...) {
    va_list args;
    va_start(args, count);
    
    int sum = 0;
    for (int i = 0; i < count; i++) {
        sum += va_arg(args, int);
    }
    
    va_end(args);
    return sum;
}

/* Implementation of data manipulation function */
void manipulate_data(int** data, size_t* size, int (*transform)(int)) {
    if (!data || !*data || !size || !transform) return;
    
    for (size_t i = 0; i < *size; i++) {
        (*data)[i] = transform((*data)[i]);
    }
}

/* Function using setjmp/longjmp for error handling */
bool process_with_exceptions(void) {
    if (setjmp(jump_buffer) != 0) {
        /* Error case - jumped here from longjmp */
        LOG_ERROR(\"Exception occurred during processing\");
        return false;
    }
    
    /* Normal processing */
    if (rand() % 10 == 0) {
        /* Simulate an error condition */
        longjmp(jump_buffer, 1);
    }
    
    return true;
}

/* Function with complex pointer arithmetic and casting */
void* memory_operations(void* buffer, size_t size) {
    if (!buffer || size == 0) return NULL;
    
    /* Byte-by-byte access */
    uint8_t* byte_ptr = (uint8_t*)buffer;
    for (size_t i = 0; i < size; i++) {
        byte_ptr[i] = (uint8_t)(i & 0xFF);
    }
    
    /* Word-by-word access (assuming size is multiple of sizeof(int)) */
    if (size % sizeof(int) == 0) {
        int* int_ptr = (int*)buffer;
        for (size_t i = 0; i < size / sizeof(int); i++) {
            int_ptr[i] = (int)i * 100;
        }
    }
    
    /* Double pointer arithmetic */
    if (size >= 2 * sizeof(double)) {
        double* dbl_ptr = (double*)buffer;
        *dbl_ptr = 3.14159;
        *(dbl_ptr + 1) = 2.71828;
    }
    
    return buffer;
}

/* Function with preprocessor conditionals */
void platform_specific(void) {
    #if defined(_WIN32) || defined(_WIN64)
        /* Windows-specific code */
        printf(\"Running on Windows\
\");
        #ifdef _MSC_VER
            /* MSVC-specific code */
            printf(\"Using Microsoft Compiler %d\
\", _MSC_VER);
        #endif
    #elif defined(__APPLE__)
        /* macOS-specific code */
        printf(\"Running on macOS\
\");
        #ifdef __MACH__
            printf(\"Using Mach kernel\
\");
        #endif
    #elif defined(__linux__)
        /* Linux-specific code */
        printf(\"Running on Linux\
\");
    #else
        /* Generic implementation */
        printf(\"Running on unknown platform\
\");
    #endif
}

/* Main function */
int main(int argc, char* argv[]) {
    srand((unsigned int)time(NULL));
    
    /* Parse command line arguments */
    int test_mode = 0;
    for (int i = 1; i < argc; i++) {
        if (strcmp(argv[i], \"--test\") == 0) {
            test_mode = 1;
        } else if (strncmp(argv[i], \"--mode=\", 7) == 0) {
            const char* mode = argv[i] + 7;
            if (strcmp(mode, \"debug\") == 0) {
                printf(\"Debug mode activated\
\");
            }
        }
    }
    
    /* Complex bitwise operations */
    uint32_t flags = 0;
    flags |= (1U << 3) | (1U << 10);
    flags &= ~(1U << 5);
    if (flags & (1U << 3)) {
        printf(\"Bit 3 is set\
\");
    }
    
    /* Array and memory allocation testing */
    int* dynamic_array = (int*)malloc(10 * sizeof(int));
    if (!dynamic_array) {
        LOG_ERROR(\"Memory allocation failed\");
        return EXIT_FAILURE;
    }
    
    for (int i = 0; i < 10; i++) {
        dynamic_array[i] = i * i;
    }
    
    /* Function pointer usage */
    int (*op_func)(int, int) = get_operation('+');
    if (op_func) {
        printf(\"5 + 3 = %d\
\", op_func(5, 3));
    }
    
    /* Free allocated memory */
    free(dynamic_array);
    
    return test_mode ? EXIT_SUCCESS : 0;
}
`
}
