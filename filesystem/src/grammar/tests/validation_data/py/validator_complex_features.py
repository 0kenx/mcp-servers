"""
Python validation file with complex but valid language features to test parser robustness
"""
import asyncio
import contextlib
import dataclasses
import functools
import inspect
import itertools
import re
import sys
import types
from typing import (
    Any, Callable, Dict, Generic, List, Optional, Protocol, 
    Tuple, Type, TypeVar, Union, cast, runtime_checkable
)

# Type variables with complex constraints
T = TypeVar('T')
K = TypeVar('K', bound='Serializable')
V = TypeVar('V', str, int, float)

# Complex f-string formatting with nested expressions
def complex_f_string():
    name = "World"
    value = 42
    data = {"key": [1, 2, 3]}
    
    # Complex nested f-string with quotes and expressions
    result = f"""
    Hello, {name}!
    Your value is {value * 2 + {key: val for key, val in {'a': 1, 'b': 2}.items()}['a']}.
    The data is {[f"{x}" for x in data["key"]]} with length {len(data["key"])}.
    Nested quotes: {f'nested {f"double {f\'triple\'} nested"} quotes'}
    Expression: {(lambda x: x**2)(3 + 4)}
    """
    
    return result

# Protocol with multiple inheritance and abstract methods
@runtime_checkable
class Serializable(Protocol):
    """Serializable protocol"""
    
    def to_dict(self) -> Dict[str, Any]:
        ...
    
    def to_json(self) -> str:
        ...

@runtime_checkable
class Validatable(Protocol):
    """Validatable protocol"""
    
    def validate(self) -> bool:
        ...
    
    def validation_errors(self) -> List[str]:
        ...

# Complex class with multiple inheritance, generics, type annotations
class ComplexContainer(Generic[T], Serializable, Validatable):
    """A complex container with multiple features"""
    
    __slots__ = ('_data', '_meta', '_callbacks')
    
    def __init__(self, data: List[T], *, meta: Optional[Dict[str, Any]] = None):
        self._data = data
        self._meta = meta or {}
        self._callbacks: List[Callable[[T], Any]] = []
    
    def __iter__(self):
        return iter(self._data)
    
    def __getitem__(self, index):
        if isinstance(index, slice):
            return ComplexContainer(self._data[index], meta=self._meta)
        return self._data[index]
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self._callbacks.clear()
        return False
    
    def map(self, func: Callable[[T], Any]) -> 'ComplexContainer[Any]':
        return ComplexContainer([func(item) for item in self._data], meta=self._meta)
    
    def filter(self, predicate: Callable[[T], bool]) -> 'ComplexContainer[T]':
        return ComplexContainer([item for item in self._data if predicate(item)], meta=self._meta)
    
    def add_callback(self, callback: Callable[[T], Any]) -> None:
        self._callbacks.append(callback)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "data": self._data,
            "meta": self._meta,
            "callbacks_count": len(self._callbacks)
        }
    
    def to_json(self) -> str:
        import json
        return json.dumps(self.to_dict())
    
    def validate(self) -> bool:
        return len(self._data) > 0
    
    def validation_errors(self) -> List[str]:
        errors = []
        if not self._data:
            errors.append("Container is empty")
        return errors

# Decorator factory with complex arguments and introspection
def validate_types(*, check_return: bool = True, raise_exception: bool = False):
    """Decorator factory for validating function parameter types"""
    
    def decorator(func: Callable) -> Callable:
        sig = inspect.signature(func)
        
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            bound = sig.bind(*args, **kwargs)
            bound.apply_defaults()
            
            errors = []
            for name, param in sig.parameters.items():
                if param.annotation is not inspect.Parameter.empty:
                    value = bound.arguments[name]
                    if not isinstance(value, param.annotation):
                        errors.append(
                            f"Parameter '{name}' expected {param.annotation.__name__}, "
                            f"got {type(value).__name__}"
                        )
            
            if errors and raise_exception:
                raise TypeError("\n".join(errors))
            
            result = func(*args, **kwargs)
            
            if (check_return and sig.return_annotation is not inspect.Signature.empty and
                    not isinstance(result, sig.return_annotation)):
                if raise_exception:
                    raise TypeError(
                        f"Return value expected {sig.return_annotation.__name__}, "
                        f"got {type(result).__name__}"
                    )
            
            return result
        
        return wrapper
    
    return decorator

# Complex context manager with nested error handling
@contextlib.contextmanager
def nested_context(level: int = 1):
    """A complex nested context manager"""
    contexts = []
    
    try:
        print(f"Setting up level {level}")
        contexts.append(level)
        
        if level > 1:
            with nested_context(level - 1) as inner:
                contexts.extend(inner)
                yield contexts
        else:
            yield contexts
            
    except Exception as e:
        print(f"Error at level {level}: {e}")
        raise
    finally:
        if contexts:
            contexts.pop(0)
        print(f"Tearing down level {level}")

# Async generator with complex control flow
async def complex_async_generator(items: List[Any], delay: float = 0.1):
    """An async generator with complex control flow"""
    for i, item in enumerate(items):
        if i > 0:
            await asyncio.sleep(delay)
        
        try:
            if isinstance(item, dict):
                for key, value in item.items():
                    yield key, value
            elif isinstance(item, (list, tuple)):
                yield from item
            else:
                yield item
        except Exception as e:
            yield f"Error: {e}"

# Function with complex unpacking and parameter handling
def complex_unpacking(*args, **kwargs):
    """Function demonstrating complex unpacking and parameter handling"""
    positional = args
    keyword = kwargs
    
    # Dictionary unpacking with complex expressions
    combined = {
        **{str(i): arg for i, arg in enumerate(args)},
        **{k: v for k, v in sorted(kwargs.items(), key=lambda x: x[0])},
        **({f"extra_{i}": i**2 for i in range(3)} if args else {}),
        "function": complex_unpacking.__name__,
        "args_count": len(args),
        "kwargs_count": len(kwargs),
    }
    
    # List and tuple unpacking with complex expressions
    result = [
        *args,
        *(v for k, v in kwargs.items() if k.startswith("a")),
        *[i**2 for i in range(min(3, len(args)))],
        *(kwargs.get(k, k) for k in ["x", "y", "z"]),
    ]
    
    # Nested unpacking
    {a: b for a, *b in [(1, 2, 3), (4, 5, 6)]}
    
    return combined, tuple(result)

# Class for testing decorator stacking and method types
class DecoratorTest:
    """Class for testing various decorators and method types"""
    
    @staticmethod
    @validate_types(check_return=True, raise_exception=False)
    def static_method(a: int, b: int) -> int:
        return a + b
    
    @classmethod
    @validate_types()
    def class_method(cls, data: List[str]) -> Dict[str, int]:
        return {item: len(item) for item in data}
    
    @property
    def prop(self) -> str:
        return "property_value"
    
    @prop.setter
    def prop(self, value: str) -> None:
        print(f"Setting prop to {value}")
    
    @functools.cached_property
    def expensive_calculation(self) -> int:
        print("Computing expensive calculation...")
        return sum(i**2 for i in range(1000))

# Main function demonstrating all features
async def main():
    # Complex container usage
    container = ComplexContainer([1, 2, 3, 4, 5])
    filtered = container.filter(lambda x: x % 2 == 0)
    mapped = container.map(lambda x: x * 10)
    
    # Context manager usage
    with nested_context(3) as contexts:
        print(f"Got contexts: {contexts}")
    
    # Async generator usage
    async for item in complex_async_generator([{"a": 1, "b": 2}, [3, 4, 5], 6]):
        print(f"Generated: {item}")
    
    # Complex unpacking
    result = complex_unpacking(1, 2, 3, a=10, b=20, z=30)
    print(f"Unpacking result: {result}")
    
    # Decorator test
    dt = DecoratorTest()
    print(dt.static_method(5, 10))
    print(dt.class_method(["hello", "world"]))
    print(dt.prop)
    print(dt.expensive_calculation)  # Cached after first access
    print(dt.expensive_calculation)  # Uses cache
    
    # Complex f-string
    print(complex_f_string())

if __name__ == "__main__":
    asyncio.run(main()) 