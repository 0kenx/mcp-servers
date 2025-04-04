def function_with_inconsistent_indent():
    print("Normal indentation")
   print("One less space")
     print("One more space")
        print("Much more indentation")
 print("Minimal indentation")

def normal_function():
    if True:
        print("Consistent")
        print("Still consistent")