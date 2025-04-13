def process_data(data):
    # Simple assignment expression
    if (n := len(data)) > 10:
        print(f"Processing {n} items")

    # In comprehension
    results = [y for x in data if (y := process(x))]

    # In while loop
    while chunk := read_chunk():
        process_chunk(chunk)

    # Multiple assignments
    if (a := 1) and (b := 2) and (c := a + b) == 3:
        print("Math works!")

    return results


# Function referenced in the walrus examples
def process(item):
    return item * 2


def read_chunk():
    return None  # Just a stub


def process_chunk(chunk):
    pass  # Just a stub
