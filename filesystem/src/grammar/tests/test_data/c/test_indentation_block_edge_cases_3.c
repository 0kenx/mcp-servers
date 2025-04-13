def simple_function():
    pass

class MyClass:
    def method1(self):
        if True:
            print("Indented")
        else:
            print("Also indented")
            
    def method2(self):
        pass
        
    @property
    def prop(self):
        return 42

def function_with_complex_blocks():
    # Block with empty lines in between
    print("Start")
    
    print("Middle")
    
    print("End")
    
    # Nested blocks with comments
    if True:
        # Comment
        if False:
            print("Nested")
            # Another comment
            for i in range(10):
                # Deep nesting
                print(i)
                
    # Function with docstring and multiple blocks
    def inner_function():