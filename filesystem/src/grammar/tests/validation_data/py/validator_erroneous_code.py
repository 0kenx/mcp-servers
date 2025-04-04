"""
Python validation file with syntax errors to test parser robustness
"""

# Syntax error: mismatched parentheses
def function_with_mismatched_parens():
    return ((5 + 3) * 2))

# Syntax error: invalid indentation
def function_with_bad_indentation():
    if True:
    print("Wrong indentation")
        print("Inconsistent indentation")
          return True

# Syntax error: using a keyword as a variable name
class = "This is a class variable"

# Syntax error: missing colon in if statement
if True
    print("Missing colon")

# Syntax error: using assignment operator in conditional
if x = 5:
    print("Using = instead of ==")

# Mix of tabs and spaces
def mixed_tabs_and_spaces():
	var1 = 10  # Tab
    var2 = 20  # Spaces
	return var1 + var2  # Tab again

# Syntax error: missing commas in list
my_list = [1 2 3 4]

# Syntax error: unclosed string literal
unclosed_string = "This string has no closing quote

# Wrong f-string syntax
f_string_error = f"Value is {value + "

# Syntax error: standalone expression
"This is just a string not assigned to anything"
5 + 3

# Invalid decorator
@not_a_decorator(arg1, arg2)
def decorated_function():
    pass

# Using return outside of function
return "This is outside a function"

# Mixing tabs and spaces in the same line
def mixed_indentation():
    value = 5	  # Mixed tabs and spaces
    return value

# Incorrectly nested blocks
def nested_blocks_error():
    try:
        x = 1 / 0
    except ZeroDivisionError:
        print("Divide by zero")
    finally:
        print("Cleanup")
        finally:  # Double finally
            print("This shouldn't be here")

# Unmatched closing brackets
def unmatched_brackets():
    data = {
        "key1": [
            "value1",
            "value2",
        ],
    }}}  # Extra closing braces

# Using continue outside of loop
continue

# Multiple syntax errors in one function
def multiple_errors(param1,, param2):  # Extra comma
    if param1 == None  # Missing colon
        return None
    elif param1 = param2:  # Assignment instead of comparison
        print("Equal")
    return param1.

# Invalid use of walrus operator
if items := len([1, 2, 3]) > 2  # Missing colon
    print(items)

# Calling method on nothing
.method()

# Invalid augmented assignment
x += * 10 