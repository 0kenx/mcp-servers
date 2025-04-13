# No indentation
def function_without_body():
pass

# Empty lines between definition and body
def function_with_gap():



    print("There are empty lines above")
    
# Function with just pass
def empty_function():
    pass
    
# One-liner functions (Python supports)
def one_liner(): return "One line"

# Nested function with same name as outer
def outer():
    print("Outer")
    def inner():
        print("Inner")
    def outer():
        print("Inner function with same name as outer")
    return inner