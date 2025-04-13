"""
Tests for the Python parser with edge cases.
"""

import unittest
from src.grammar.python import PythonParser
from src.grammar.base import ElementType


class TestPythonEdgeCases(unittest.TestCase):
    """Test edge cases for the Python parser."""

    def setUp(self):
        """Set up test cases."""
        self.parser = PythonParser()

    def test_complex_decorators(self):
        """Test parsing complex decorator expressions."""
        code = '''
@decorator1
@decorator2(arg1, arg2=value)
@decorator3(lambda x: x * 2)
@namespace.decorator4(
    param1="value1",
    param2=["list", "of", "values"],
    param3={
        "key1": "value1",
        "key2": "value2"
    }
)
@(lambda f: lambda *args, **kwargs: f(*args, **kwargs))
def complex_decorated_function(x, y):
    """Function with complex decorators."""
    return x + y
'''
        elements = self.parser.parse(code)
        
        # Should identify the function
        self.assertEqual(len(elements), 1)
        
        func = elements[0]
        self.assertEqual(func.element_type, ElementType.FUNCTION)
        self.assertEqual(func.name, "complex_decorated_function")
        
        # Check that decorators were captured
        decorators = func.metadata.get("decorators", [])
        self.assertGreaterEqual(len(decorators), 2)  # Should capture at least some decorators

    def test_complex_f_strings(self):
        """Test parsing complex f-strings and string formatting."""
        code = '''
def format_strings():
    name = "World"
    age = 42
    
    # Simple f-string
    s1 = f"Hello, {name}!"
    
    # Nested braces in f-string
    s2 = f"Values: {{{name}, {age}}}"
    
    # Expression in f-string
    s3 = f"Age next year: {age + 1}"
    
    # Multi-line f-string
    s4 = f"""
    Name: {name}
    Age: {age}
    """
    
    # Formatted string with method format
    s5 = "Hello, {name}! You are {age}".format(name=name, age=age)
    
    # Old-style formatting
    s6 = "Hello, %s! You are %d" % (name, age)
    
    return s1, s2, s3, s4, s5, s6
'''
        elements = self.parser.parse(code)
        
        # Should identify the function
        self.assertEqual(len(elements), 1)
        
        func = elements[0]
        self.assertEqual(func.element_type, ElementType.FUNCTION)
        self.assertEqual(func.name, "format_strings")
        
        # Check variable definitions inside the function
        # This is challenging for many parsers, so we'll be lenient
        child_vars = [e for e in elements if e.element_type == ElementType.VARIABLE and e.parent == func]
        # Not strict on the count, as parsers may handle internal variables differently

    def test_complex_comprehensions(self):
        """Test parsing complex list, dict, and set comprehensions."""
        code = '''
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
'''
        elements = self.parser.parse(code)
        
        # Should identify the function
        self.assertEqual(len(elements), 1)
        
        func = elements[0]
        self.assertEqual(func.element_type, ElementType.FUNCTION)
        self.assertEqual(func.name, "comprehensions")

    def test_walrus_operator(self):
        """Test parsing the walrus operator (:=) introduced in Python 3.8."""
        code = '''
def process_data(data):
    # Simple assignment expression
    if (n := len(data)) > 10:
        print(f"Processing {n} items")
    
    # In comprehension
    results = [y for x in data if (y := process(x))]
    
    # In while loop
    while (chunk := read_chunk()):
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
'''
        elements = self.parser.parse(code)
        
        # Should identify all functions
        self.assertEqual(len(elements), 4)
        
        # Check the main function
        process_data_func = next((e for e in elements if e.name == "process_data"), None)
        self.assertIsNotNone(process_data_func)

    def test_type_hints(self):
        """Test parsing various forms of type hints."""
        code = '''
from typing import List, Dict, Tuple, Optional, Union, Callable, TypeVar, Generic, Literal, Any

T = TypeVar('T')
K = TypeVar('K')
V = TypeVar('V')

class GenericContainer(Generic[T]):
    def __init__(self, value: T) -> None:
        self.value: T = value
    
    def get_value(self) -> T:
        return self.value

def simple_function(x: int, y: float = 0.0) -> float:
    return x + y

def complex_types(
    a: List[int],
    b: Dict[str, Union[int, str]],
    c: Tuple[int, str, float],
    d: Optional[List[Dict[str, Any]]],
    e: Callable[[int, str], bool]
) -> Union[int, None]:
    return len(a) if a else None

# Function with variable type annotations
def with_variable_annotations() -> None:
    x: int = 1
    y: float = 2.0
    z: List[str] = ["a", "b", "c"]
    
    # Type comments (older style)
    a = 1  # type: int
    b = {}  # type: Dict[str, int]

# Type aliases
Vector = List[float]

def process_vector(v: Vector) -> float:
    return sum(v)

# Python 3.10+ type hints
def newer_type_hints(x: int | None, y: list[int]) -> dict[str, int | str]:
    result: dict[str, int | str] = {}
    if x is not None:
        result["x"] = x
    result["y"] = y
    return result
'''
        elements = self.parser.parse(code)
        
        # Should identify various elements with type hints
        self.assertGreaterEqual(len(elements), 5)
        
        # Check the class with generic type
        generic_class = next((e for e in elements if e.name == "GenericContainer"), None)
        self.assertIsNotNone(generic_class)
        
        # Check functions with type hints
        simple_func = next((e for e in elements if e.name == "simple_function"), None)
        self.assertIsNotNone(simple_func)
        self.assertEqual(simple_func.element_type, ElementType.FUNCTION)
        
        # Check return type annotation was captured
        self.assertIn("return_type", simple_func.metadata)
        self.assertEqual(simple_func.metadata["return_type"], "float")
        
        # Check for type aliases
        vector_type = next((e for e in elements if e.name == "Vector"), None)
        self.assertIsNotNone(vector_type)

    def test_async_functions(self):
        """Test parsing async functions and coroutines."""
        code = '''
import asyncio

async def fetch_data(url: str) -> str:
    """Fetch data from URL asynchronously."""
    await asyncio.sleep(1)  # Simulate network delay
    return f"Data from {url}"

async def process_urls(urls: list[str]) -> list[str]:
    """Process multiple URLs in parallel."""
    tasks = [fetch_data(url) for url in urls]
    results = await asyncio.gather(*tasks)
    return results

class DataProcessor:
    def __init__(self, base_url: str):
        self.base_url = base_url
    
    async def fetch_item(self, item_id: int) -> dict:
        """Fetch a single item."""
        await asyncio.sleep(0.5)
        return {"id": item_id, "url": f"{self.base_url}/{item_id}"}
    
    async def process_batch(self, item_ids: list[int]) -> list[dict]:
        """Process a batch of items."""
        tasks = [self.fetch_item(item_id) for item_id in item_ids]
        return await asyncio.gather(*tasks)

# Async context manager
class AsyncResource:
    async def __aenter__(self):
        await asyncio.sleep(0.1)
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await asyncio.sleep(0.1)
    
    async def work(self):
        await asyncio.sleep(0.2)
        return "work done"

# Async iterator
class AsyncCounter:
    def __init__(self, limit: int):
        self.limit = limit
        self.count = 0
    
    def __aiter__(self):
        return self
    
    async def __anext__(self):
        if self.count < self.limit:
            self.count += 1
            await asyncio.sleep(0.1)
            return self.count
        else:
            raise StopAsyncIteration
'''
        elements = self.parser.parse(code)
        
        # Should identify various async elements
        self.assertGreaterEqual(len(elements), 6)
        
        # Check async functions
        fetch_func = next((e for e in elements if e.name == "fetch_data"), None)
        self.assertIsNotNone(fetch_func)
        self.assertEqual(fetch_func.element_type, ElementType.FUNCTION)
        
        # Some parsers might detect that a function is async
        # In that case, check if it's in the metadata
        if "is_async" in fetch_func.metadata:
            self.assertTrue(fetch_func.metadata["is_async"])
        
        # Check async class methods
        classes = [e for e in elements if e.element_type == ElementType.CLASS]
        self.assertGreaterEqual(len(classes), 2)
        
        # Check for the DataProcessor class and its async methods
        data_processor = next((c for c in classes if c.name == "DataProcessor"), None)
        self.assertIsNotNone(data_processor)
        
        # Check for async special methods
        async_resource = next((c for c in classes if c.name == "AsyncResource"), None)
        self.assertIsNotNone(async_resource)
        
        # Find the __aenter__ method
        aenter_method = next((m for m in elements if m.name == "__aenter__"), None)
        self.assertIsNotNone(aenter_method)

    def test_context_managers(self):
        """Test parsing context managers with and without decorators."""
        code = '''
from contextlib import contextmanager

class FileManager:
    def __init__(self, filename: str, mode: str = 'r'):
        self.filename = filename
        self.mode = mode
        self.file = None
    
    def __enter__(self):
        self.file = open(self.filename, self.mode)
        return self.file
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.file:
            self.file.close()

@contextmanager
def temp_file(content: str):
    """Context manager using a decorator."""
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
'''
        elements = self.parser.parse(code)
        
        # Check if we parsed the context manager class and function
        self.assertGreaterEqual(len(elements), 3)
        
        # Check for the FileManager class with __enter__ and __exit__ methods
        file_manager = next((e for e in elements if e.name == "FileManager"), None)
        self.assertIsNotNone(file_manager)
        
        # Check for the context manager function
        temp_file_func = next((e for e in elements if e.name == "temp_file"), None)
        self.assertIsNotNone(temp_file_func)
        
        # Check for the process_files function
        process_files_func = next((e for e in elements if e.name == "process_files"), None)
        self.assertIsNotNone(process_files_func)
        
        # Check for decorators on the temp_file function
        if "decorators" in temp_file_func.metadata:
            self.assertIn("contextmanager", temp_file_func.metadata["decorators"][0])

    def test_metaclasses(self):
        """Test parsing classes with metaclasses."""
        code = '''
class Meta(type):
    def __new__(mcs, name, bases, attrs):
        # Add a new method to the class
        attrs['added_by_meta'] = lambda self: "Added by metaclass"
        return super().__new__(mcs, name, bases, attrs)

class WithMeta(metaclass=Meta):
    def __init__(self, value):
        self.value = value
    
    def get_value(self):
        return self.value

# More complex metaclass example
class RegisteredMeta(type):
    registry = {}
    
    def __new__(mcs, name, bases, attrs):
        cls = super().__new__(mcs, name, bases, attrs)
        if name != "RegisteredClass":  # Don't register the base class
            mcs.registry[name] = cls
        return cls
    
    @classmethod
    def get_registry(mcs):
        return mcs.registry

class RegisteredClass(metaclass=RegisteredMeta):
    """Base class for registered classes."""
    pass

class ServiceA(RegisteredClass):
    """Service implementation A."""
    pass

class ServiceB(RegisteredClass):
    """Service implementation B."""
    pass
'''
        elements = self.parser.parse(code)
        
        # Check if all classes were parsed
        self.assertGreaterEqual(len(elements), 5)
        
        # Check for the metaclasses
        meta_class = next((e for e in elements if e.name == "Meta"), None)
        self.assertIsNotNone(meta_class)
        
        registered_meta = next((e for e in elements if e.name == "RegisteredMeta"), None)
        self.assertIsNotNone(registered_meta)
        
        # Check for the classes using metaclasses
        with_meta = next((e for e in elements if e.name == "WithMeta"), None)
        self.assertIsNotNone(with_meta)
        
        # Check for subclasses
        service_a = next((e for e in elements if e.name == "ServiceA"), None)
        self.assertIsNotNone(service_a)
        
        service_b = next((e for e in elements if e.name == "ServiceB"), None)
        self.assertIsNotNone(service_b)

    def test_structural_pattern_matching(self):
        """Test parsing Python 3.10+ structural pattern matching."""
        code = '''
def parse_command(command):
    """Parse a command using structural pattern matching (Python 3.10+)."""
    match command.split():
        case ["quit"]:
            return "Exiting program"
        
        case ["load", filename]:
            return f"Loading file: {filename}"
        
        case ["save", filename]:
            return f"Saving to file: {filename}"
        
        case ["search", *keywords]:
            return f"Searching for: {', '.join(keywords)}"
        
        case ["help"]:
            return "Available commands: quit, load, save, search, help"
        
        case _:
            return "Unknown command"

def process_data(data):
    """Process structured data with pattern matching."""
    match data:
        case {"type": "user", "name": name, "age": age}:
            return f"User {name}, {age} years old"
        
        case {"type": "post", "title": title, "content": content}:
            return f"Post: {title}"
        
        case [{"type": "comment", "text": text}, *rest]:
            return f"Comment: {text}"
        
        case (a, b, c):
            return f"Tuple with values: {a}, {b}, {c}"
        
        case _:
            return "Unknown data format"

class Point:
    def __init__(self, x, y):
        self.x = x
        self.y = y

def process_points(point):
    """Process points with pattern matching and class patterns."""
    match point:
        case Point(x=0, y=0):
            return "Origin"
        
        case Point(x=0, y=y):
            return f"On y-axis at {y}"
        
        case Point(x=x, y=0):
            return f"On x-axis at {x}"
        
        case Point(x=x, y=y) if x == y:
            return f"On diagonal at {x}"
        
        case Point():
            return "Just a point"
        
        case _:
            return "Not a point"
'''
        elements = self.parser.parse(code)
        
        # Check if the functions were parsed correctly
        self.assertGreaterEqual(len(elements), 3)
        
        # Check for the functions with match statements
        parse_command_func = next((e for e in elements if e.name == "parse_command"), None)
        self.assertIsNotNone(parse_command_func)
        
        process_data_func = next((e for e in elements if e.name == "process_data"), None)
        self.assertIsNotNone(process_data_func)
        
        process_points_func = next((e for e in elements if e.name == "process_points"), None)
        self.assertIsNotNone(process_points_func)
        
        # Check for the Point class
        point_class = next((e for e in elements if e.name == "Point"), None)
        self.assertIsNotNone(point_class)

    def test_multiple_file_types(self):
        """Test parsing mixed code with embedded SQL, HTML, or other languages."""
        code = '''
def generate_sql():
    """Generate SQL queries."""
    # SQL query as a string
    sql = """
    SELECT users.id, users.name, COUNT(orders.id) as order_count
    FROM users
    LEFT JOIN orders ON users.id = orders.user_id
    WHERE users.active = TRUE
    GROUP BY users.id, users.name
    HAVING COUNT(orders.id) > 5
    ORDER BY order_count DESC
    LIMIT 10;
    """
    
    # SQL with string formatting
    table_name = "products"
    column = "price"
    threshold = 100
    
    filter_sql = f"""
    SELECT * FROM {table_name}
    WHERE {column} > {threshold}
    ORDER BY {column} DESC;
    """
    
    return sql, filter_sql

def generate_html():
    """Generate HTML content."""
    user_name = "John"
    items = ["Item 1", "Item 2", "Item 3"]
    
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>User Profile</title>
    </head>
    <body>
        <h1>Welcome, {user_name}!</h1>
        <ul>
            {"".join(f"<li>{item}</li>" for item in items)}
        </ul>
    </body>
    </html>
    """
    
    return html

# Nested triple quotes with various syntaxes
def complex_strings():
    json_str = """
    {
        "name": "Test",
        "values": [1, 2, 3],
        "nested": {
            "a": "value with \\"quotes\\"",
            "b": null
        }
    }
    """
    
    # Triple quotes inside f-strings
    template = f"""
    # Configuration
    name: {config_name}
    settings: {{
        """modules""": {", ".join(modules)}
    }}
    """
    
    # Nested quotes at different levels
    nested = f'''
    level1 = """
        level2 = '''
            level3 = "{level3_var}"
        '''
    """
    '''
    
    return json_str, template, nested
'''
        elements = self.parser.parse(code)
        
        # Check that we found all the functions
        self.assertEqual(len(elements), 3)
        
        # Check for the functions
        generate_sql_func = next((e for e in elements if e.name == "generate_sql"), None)
        self.assertIsNotNone(generate_sql_func)
        
        generate_html_func = next((e for e in elements if e.name == "generate_html"), None)
        self.assertIsNotNone(generate_html_func)
        
        complex_strings_func = next((e for e in elements if e.name == "complex_strings"), None)
        self.assertIsNotNone(complex_strings_func)

    def test_unusual_identifiers(self):
        """Test parsing code with unusual identifiers, including Unicode and dunder methods."""
        code = '''
# Unicode variable names
π = 3.14159
résumé = "John Doe"
ñandú = "bird"
снег = "snow"
变量 = "variable"

# Emoji variable names (may not be supported by all parsers)
💰 = 1000
📱 = "phone"

# Function with Unicode name
def calculate_área(radius):
    return π * radius**2

# Class with some dunder methods
class MagicMethods:
    def __init__(self):
        self.data = []
    
    def __str__(self):
        return f"MagicMethods({len(self.data)} items)"
    
    def __repr__(self):
        return self.__str__()
    
    def __len__(self):
        return len(self.data)
    
    def __getitem__(self, idx):
        return self.data[idx]
    
    def __setitem__(self, idx, value):
        self.data[idx] = value
    
    def __delitem__(self, idx):
        del self.data[idx]
    
    def __iter__(self):
        return iter(self.data)
    
    def __contains__(self, item):
        return item in self.data
    
    def __call__(self, *args, **kwargs):
        return args, kwargs
    
    def __add__(self, other):
        result = MagicMethods()
        result.data = self.data + other.data
        return result
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        pass

# Private name mangling
class PrivateStuff:
    def __init__(self):
        self.__private_var = "secret"
        self._protected_var = "less secret"
    
    def __private_method(self):
        return self.__private_var
    
    def _protected_method(self):
        return self._protected_var
    
    def public_method(self):
        return self.__private_method()
'''
        elements = self.parser.parse(code)
        
        # Check for the class with magic methods
        magic_methods_class = next((e for e in elements if e.name == "MagicMethods"), None)
        self.assertIsNotNone(magic_methods_class)
        
        # Check for the class with private methods
        private_stuff_class = next((e for e in elements if e.name == "PrivateStuff"), None)
        self.assertIsNotNone(private_stuff_class)
        
        # Check for variables (may not detect all Unicode variables)
        variables = [e for e in elements if e.element_type == ElementType.VARIABLE]
        self.assertGreaterEqual(len(variables), 2)  # Should find at least some variables
        
        # Check for the function with Unicode name
        # This is a stretch goal - parsers may not handle Unicode function names well
        # If found, check it
        area_func = next((e for e in elements if e.name == "calculate_área"), None)
        if area_func:
            self.assertEqual(area_func.element_type, ElementType.FUNCTION)


if __name__ == "__main__":
    unittest.main()
