filename = "temp.txt"
    with open(filename, "w") as f:
        f.write(content)
    try:
        yield filename
    finally:
        # Clean up
        import os
        os.remove(filename)

# Nested context managers
def process_files():
    with open("input.txt", "r") as input_file, open("output.txt", "w") as output_file:
        for line in input_file:
            output_file.write(line.upper())
    
    # With context manager expressions
    with FileManager("data.txt", mode="r") as f:
        data = f.read()
    
    # With temporary file context manager
    with temp_file("sample content") as temp:
        with open(temp, "r") as f:
            content = f.read()
    
    return content