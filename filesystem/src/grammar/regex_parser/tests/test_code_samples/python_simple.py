"""
A simple Python program demonstrating language features
with some edge cases for parser testing
"""

from typing import List, Callable, TypeVar

# Type variables for generics
T = TypeVar("T")
U = TypeVar("U")


# Class with inheritance
class Base:
    """Base class with docstring"""

    def __init__(self, name: str):
        self.name = name
        self._private_value = 0

    def display(self) -> str:
        return f"Base: {self.name}"

    @property  #  -> NOT DETECTED (decorator not included)
    def value(self) -> int:
        return self._private_value

    @value.setter  #  -> NOT DETECTED (decorator not included)
    def value(self, val: int) -> None:
        self._private_value = val


class Derived(Base):
    """Derived class demonstrating inheritance"""

    def __init__(self, name: str, extra: str):
        super().__init__(name)
        self.extra = extra

    def display(self) -> str:
        return f"Derived: {self.name} ({self.extra})"

    # Method with type annotations and default values
    def calculate(self, x: int, y: int = 10) -> int:
        return x * y + self.value


# Function with type hints and docstring
def process_data(items: List[T], transform: Callable[[T], U]) -> List[U]:
    """
    Process a list of items using a transformation function.

    Args:
        items: List of items to process
        transform: Function to apply to each item

    Returns:
        List of transformed items
    """
    return [transform(item) for item in items]


# Function with default arguments and *args, **kwargs
def format_string(template: str, *args, **kwargs) -> str:
    for i, arg in enumerate(args):
        template = template.replace(f"{{{i}}}", str(arg))

    for key, value in kwargs.items():
        template = template.replace(f"{{{key}}}", str(value))

    return template


# Decorator function
def log_call(func: Callable) -> Callable:
    def wrapper(*args, **kwargs):
        print(f"Calling {func.__name__} with {args} and {kwargs}")
        result = func(*args, **kwargs)
        print(f"Result: {result}")
        return result

    return wrapper


# Using decorator
@log_call  #  -> NOT DETECTED (decorator not included)
def add(a: int, b: int) -> int:
    return a + b


# Lambda function
multiply = lambda x, y: x * y


# Main execution block #  -> NOT DETECTED
if __name__ == "__main__":
    # List comprehension
    squares = [x**2 for x in range(5)]

    # Dictionary comprehension
    name_lengths = {name: len(name) for name in ["Alice", "Bob", "Charlie"]}

    # Using class
    obj = Derived("Test", "extra info")
    obj.value = 5
    print(obj.display())

    # Using functions
    processed = process_data([1, 2, 3], lambda x: x * 2)
    formatted = format_string("Hello, {0}! Your score is {score}.", "World", score=95)

    # Function call with decorator
    result = add(5, 7)

    # f-strings with expressions
    print(f"The answer is {6 * 7}, processed: {processed}")
