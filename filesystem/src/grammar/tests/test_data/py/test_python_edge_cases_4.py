def comprehensions():
    # List comprehension
    squares = [x**2 for x in range(10)]
    
    # Nested list comprehension
    matrix = [[i*j for j in range(5)] for i in range(5)]
    
    # List comprehension with condition
    even_squares = [x**2 for x in range(10) if x % 2 == 0]
    
    # Dict comprehension
    square_dict = {x: x**2 for x in range(10)}
    
    # Dict comprehension with condition
    even_square_dict = {x: x**2 for x in range(10) if x % 2 == 0}
    
    # Set comprehension
    unique_letters = {char for char in "mississippi"}
    
    # Generator expression
    gen = (x**2 for x in range(10))
    
    # Nested comprehension with complex conditions
    complex_comp = [
        (x, y) 
        for x in range(10) 
        if x % 2 == 0 
        for y in range(10) 
        if y % 2 == 1 and x < y
    ]
    
    return squares, matrix, even_squares, square_dict, even_square_dict, unique_letters, gen, complex_comp