"""
Complex Python program demonstrating advanced language features
for parser robustness testing
"""

import abc
import asyncio
import contextlib
import copy
import dataclasses
import enum
import functools
import logging
import random
import re
import time
import typing
from typing import (  #  -> DETECTION ERROR: import: typing (lines 27-27)
    Any,
    Callable,
    Dict,
    Generic,
    Iterable,
    List,
    Optional,
    Protocol,
    Tuple,
    Type,
    TypeVar,
    Union,
    overload,
    runtime_checkable,
)

# Configure logging  #  -> NOT DETECTED
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Type variables
T = TypeVar("T")
U = TypeVar("U")
V = TypeVar("V", bound="Serializable")
K = TypeVar("K", str, int)
R = TypeVar("R", covariant=True)
C = TypeVar("C", contravariant=True)


# Enum with complex inheritance
class Status(enum.IntEnum):
    """Status enum with documentation"""

    PENDING = 0
    RUNNING = 1
    COMPLETED = 2
    FAILED = 3

    @property
    def is_active(self) -> bool:
        return self in (Status.PENDING, Status.RUNNING)

    @classmethod
    def from_string(cls, status_str: str) -> "Status":
        return getattr(cls, status_str.upper())


# Protocol definition
@runtime_checkable
class Serializable(Protocol):
    """Protocol for objects that can be serialized to JSON"""

    def to_json(self) -> str: ...

    @classmethod
    def from_json(cls, json_str: str) -> "Serializable": ...


# Abstract base class
class BaseProcessor(abc.ABC):
    """Abstract base class for processors"""

    def __init__(self, name: str):
        self.name = name
        self._status = Status.PENDING

    @property
    def status(self) -> Status:
        return self._status

    @status.setter
    def status(self, value: Status) -> None:
        self._status = value

    @abc.abstractmethod
    def process(self, data: Any) -> Any:
        """Process the input data"""
        pass

    def __repr__(self) -> str:
        return (
            f"{self.__class__.__name__}(name='{self.name}', status={self.status.name})"
        )


# Dataclass with complex features
@dataclasses.dataclass(frozen=True)
class Configuration:
    """Configuration dataclass"""

    name: str
    version: str
    debug: bool = False
    max_retries: int = 3
    timeout: float = 30.0
    tags: List[str] = dataclasses.field(default_factory=list)
    options: Dict[str, Any] = dataclasses.field(default_factory=dict)

    def __post_init__(self) -> None:
        # Can't directly assign to fields due to frozen=True
        # This is a workaround using object.__setattr__
        if not self.name:
            object.__setattr__(self, "name", "default")

        if not self.version:
            object.__setattr__(self, "version", "1.0.0")

    @property
    def is_production(self) -> bool:
        return "production" in self.tags

    def clone(self) -> "Configuration":
        return copy.deepcopy(self)


# Named tuple with typing
class Point(typing.NamedTuple):
    x: float
    y: float
    label: Optional[str] = None

    def distance_to_origin(self) -> float:
        return (self.x**2 + self.y**2) ** 0.5

    def __str__(self) -> str:
        if self.label:
            return f"{self.label}: ({self.x}, {self.y})"
        return f"({self.x}, {self.y})"


# Context manager using decorator
@contextlib.contextmanager
def timing(label: str) -> typing.Iterator[None]:
    """Context manager for timing code blocks"""
    start = time.time()
    try:
        yield
    finally:
        end = time.time()
        logger.info(f"{label}: {end - start:.4f} seconds")


# Context manager using class
class ResourceManager:
    """Context manager for handling resources"""

    def __init__(self, resource_id: str):
        self.resource_id = resource_id
        self.resource = None

    def __enter__(self) -> "ResourceManager":
        logger.info(f"Acquiring resource: {self.resource_id}")
        self.resource = f"Resource-{self.resource_id}"
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> Optional[bool]:
        logger.info(f"Releasing resource: {self.resource_id}")
        self.resource = None
        if exc_type is not None:
            logger.error(f"Exception during resource use: {exc_val}")
            return False
        return True

    def use(self) -> None:
        """Use the managed resource"""
        if self.resource is None:
            raise ValueError("Resource not acquired")
        logger.info(f"Using {self.resource}")


# Descriptor protocol
class ValidatedField:
    """Descriptor for validated fields"""

    def __init__(
        self, field_type: Type, validator: Optional[Callable[[Any], bool]] = None
    ):
        self.field_type = field_type
        self.validator = validator
        self.name = None

    def __set_name__(self, owner: Type, name: str) -> None:
        self.name = name

    def __get__(self, instance: Any, owner: Type) -> Any:
        if instance is None:
            return self
        return instance.__dict__.get(self.name)

    def __set__(self, instance: Any, value: Any) -> None:
        if not isinstance(value, self.field_type):
            raise TypeError(f"{self.name} must be of type {self.field_type.__name__}")

        if self.validator and not self.validator(value):
            raise ValueError(f"{value} failed validation for {self.name}")

        instance.__dict__[self.name] = value


# Class using descriptors
class Person:
    """Class with validated fields using descriptors"""

    name = ValidatedField(str, lambda x: len(x) > 0)
    age = ValidatedField(int, lambda x: 0 <= x <= 150)
    email = ValidatedField(str, lambda x: re.match(r"[^@]+@[^@]+\.[^@]+", x))

    def __init__(self, name: str, age: int, email: str):
        self.name = name
        self.age = age
        self.email = email

    def __str__(self) -> str:
        return f"{self.name} ({self.age}) - {self.email}"


# Metaclass example
class SingletonMeta(type):
    """Metaclass for creating singleton classes"""

    _instances: Dict[Type, Any] = {}

    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super().__call__(*args, **kwargs)
        return cls._instances[cls]


# Class using metaclass
class ConfigurationManager(metaclass=SingletonMeta):
    """Singleton configuration manager"""

    def __init__(self):
        self.configs: Dict[str, Configuration] = {}

    def add_config(self, config: Configuration) -> None:
        self.configs[config.name] = config

    def get_config(self, name: str) -> Optional[Configuration]:
        return self.configs.get(name)

    def __len__(self) -> int:
        return len(self.configs)


# Generic class
class Result(Generic[T]):
    """Generic result container"""

    def __init__(self, value: Optional[T] = None, error: Optional[Exception] = None):
        self.value = value
        self.error = error

    @property
    def is_success(self) -> bool:
        return self.error is None

    @property
    def is_failure(self) -> bool:
        return not self.is_success

    def __str__(self) -> str:
        if self.is_success:
            return f"Success: {self.value}"
        return f"Failure: {self.error}"

    # Static factory methods
    @classmethod
    def success(cls, value: T) -> "Result[T]":
        return cls(value=value)

    @classmethod
    def failure(cls, error: Exception) -> "Result[T]":
        return cls(error=error)

    # Monadic operations
    def map(self, func: Callable[[T], U]) -> "Result[U]":
        if self.is_failure:
            return Result(error=self.error)
        try:
            return Result.success(func(self.value))
        except Exception as e:
            return Result.failure(e)

    def flat_map(self, func: Callable[[T], "Result[U]"]) -> "Result[U]":
        if self.is_failure:
            return Result(error=self.error)
        try:
            return func(self.value)
        except Exception as e:
            return Result.failure(e)


# Classes with complex inheritance hierarchy
class DataContainer:
    """Base data container class"""

    def __init__(self, data: Any = None):
        self.data = data if data is not None else []

    def __len__(self) -> int:
        return len(self.data)

    def __getitem__(self, index: Union[int, slice]) -> Any:
        return self.data[index]

    def __iter__(self) -> Iterable:
        return iter(self.data)

    def __str__(self) -> str:
        return f"{self.__class__.__name__}({self.data!r})"


class FilterableContainer(DataContainer):
    """Container that supports filtering"""

    def filter(self, predicate: Callable[[Any], bool]) -> "FilterableContainer":
        filtered_data = [item for item in self.data if predicate(item)]
        return type(self)(filtered_data)


class SortableContainer(DataContainer):
    """Container that supports sorting"""

    def sort(
        self, key: Optional[Callable[[Any], Any]] = None, reverse: bool = False
    ) -> "SortableContainer":
        sorted_data = sorted(self.data, key=key, reverse=reverse)
        return type(self)(sorted_data)


class AdvancedContainer(FilterableContainer, SortableContainer):
    """Advanced container with multiple features"""

    def map(self, transform: Callable[[Any], Any]) -> "AdvancedContainer":
        transformed_data = [transform(item) for item in self.data]
        return type(self)(transformed_data)

    def reduce(
        self, func: Callable[[Any, Any], Any], initial: Optional[Any] = None
    ) -> Any:
        if not self.data:
            return initial

        if initial is None:
            result = self.data[0]
            data_slice = self.data[1:]
        else:
            result = initial
            data_slice = self.data

        for item in data_slice:
            result = func(result, item)

        return result


# Processor implementation
class DataProcessor(BaseProcessor):
    """Concrete processor implementation"""

    def __init__(self, name: str, transform: Optional[Callable[[Any], Any]] = None):
        super().__init__(name)
        self.transform = transform or (lambda x: x)
        self.results: List[Any] = []

    def process(self, data: Any) -> Any:
        try:
            self.status = Status.RUNNING
            result = self.transform(data)
            self.results.append(result)
            self.status = Status.COMPLETED
            return result
        except Exception as e:
            self.status = Status.FAILED
            logger.error(f"Processing error: {e}")
            raise


# Async functions and classes
async def fetch_data(url: str, timeout: float = 10.0) -> str:
    """Async function to fetch data from URL"""
    logger.info(f"Fetching data from {url}")
    await asyncio.sleep(random.uniform(0.1, 0.5))  # Simulate network delay
    return f"Data from {url}"


async def process_urls(urls: List[str]) -> List[str]:
    """Process multiple URLs concurrently"""
    tasks = [fetch_data(url) for url in urls]
    return await asyncio.gather(*tasks)


class AsyncProcessor:
    """Class with async methods"""

    def __init__(self, max_concurrency: int = 5):
        self.max_concurrency = max_concurrency
        self.semaphore = asyncio.Semaphore(max_concurrency)

    async def process_item(self, item: Any) -> Any:
        """Process a single item with concurrency limiting"""
        async with self.semaphore:
            logger.info(f"Processing {item}")
            await asyncio.sleep(random.uniform(0.1, 0.3))
            return f"Processed: {item}"

    async def process_batch(self, items: List[Any]) -> List[Any]:
        """Process a batch of items"""
        tasks = [self.process_item(item) for item in items]
        return await asyncio.gather(*tasks)


# Function and method overloading
@overload
def parse_value(value: str) -> str: ...


@overload
def parse_value(value: int) -> int: ...


@overload
def parse_value(value: List[Any]) -> List[Any]: ...


def parse_value(value: Union[str, int, List[Any]]) -> Union[str, int, List[Any]]:
    """Parse a value based on its type"""
    if isinstance(value, str):
        return value.strip()
    elif isinstance(value, int):
        return value
    elif isinstance(value, list):
        return [parse_value(item) for item in value]
    else:
        raise TypeError(f"Unsupported type: {type(value)}")


# Complex decorators
def retry(
    max_attempts: int = 3,
    delay: float = 1.0,
    backoff: float = 2.0,
    exceptions: Tuple[Type[Exception], ...] = (Exception,),
):
    """Retry decorator with backoff"""

    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            attempt = 0
            current_delay = delay

            while attempt < max_attempts:
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    attempt += 1
                    last_exception = e

                    if attempt < max_attempts:
                        logger.warning(
                            f"Attempt {attempt} failed: {e}. Retrying in {current_delay:.2f} seconds..."
                        )
                        time.sleep(current_delay)
                        current_delay *= backoff

            logger.error(
                f"All {max_attempts} attempts failed. Last error: {last_exception}"
            )
            raise last_exception

        return wrapper

    return decorator


def measure_performance(func: Callable) -> Callable:
    """Decorator to measure function performance"""

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.time()
        result = func(*args, **kwargs)
        end_time = time.time()
        elapsed = end_time - start_time
        logger.info(f"{func.__name__} took {elapsed:.4f} seconds")
        return result

    return wrapper


# Function composition utility
def compose(*functions: Callable) -> Callable:
    """Compose multiple functions: compose(f, g, h)(x) = f(g(h(x)))"""

    def compose_two(f: Callable, g: Callable) -> Callable:
        return lambda x: f(g(x))

    if not functions:
        return lambda x: x

    return functools.reduce(compose_two, functions)


# Class decorator
def add_repr(cls: Type) -> Type:
    """Class decorator to add __repr__ method"""

    def __repr__(self):
        attrs = ", ".join(f"{key}={value!r}" for key, value in self.__dict__.items())
        return f"{self.__class__.__name__}({attrs})"

    # Don't override existing __repr__
    if "__repr__" not in cls.__dict__:
        cls.__repr__ = __repr__

    return cls


# Complex list comprehensions and generator expressions
def complex_list_operations(data: List[Any]) -> Tuple[List[Any], List[Any], List[Any]]:
    """Perform complex list operations"""

    # Nested list comprehension
    matrix = [[1, 2, 3], [4, 5, 6], [7, 8, 9]]
    flattened = [x for row in matrix for x in row]

    # Conditional list comprehension
    evens = [x for x in data if isinstance(x, int) and x % 2 == 0]

    # Complex list comprehension with conditional
    transformed = [
        x * 2 if isinstance(x, int) else x.upper() if isinstance(x, str) else str(x)
        for x in data
    ]

    return flattened, evens, transformed


# Main execution with complex features
def main():
    # Using dataclass
    config = Configuration(
        name="parser-test",
        version="1.0.0",
        debug=True,
        tags=["test", "development"],
        options={"timeout": 60, "retry": True},
    )

    # Using singleton manager
    manager = ConfigurationManager()
    manager.add_config(config)

    # Using generic class
    result: Result[int] = Result.success(42)
    mapped_result = result.map(lambda x: x * 2)

    # Using advanced container
    container = AdvancedContainer([1, 5, 3, 7, 2, 8])
    processed = container.filter(lambda x: x > 2).sort().map(lambda x: x * 2)

    # Using context manager
    with timing("resource operation"):
        with ResourceManager("db-connection") as rm:
            rm.use()
            time.sleep(0.1)

    # Using decorators
    @retry(max_attempts=3, exceptions=(ValueError, KeyError))
    @measure_performance
    def risky_operation(value: Any) -> Any:
        if random.random() < 0.7:
            raise ValueError("Random failure")
        return value

    try:
        result = risky_operation("test")
    except ValueError:
        logger.error("Risky operation failed after retries")

    # Using processor
    processor = DataProcessor(
        "test-processor", lambda x: x.upper() if isinstance(x, str) else x
    )
    processed_data = processor.process("hello world")

    # Using overloaded function
    parsed_str = parse_value("  hello  ")
    parsed_int = parse_value(42)
    parsed_list = parse_value([1, "  test  ", 3])

    # Using function composition
    double = lambda x: x * 2
    increment = lambda x: x + 1
    square = lambda x: x**2

    pipeline = compose(square, increment, double)
    result = pipeline(5)  # (5 * 2 + 1) ^ 2

    logger.info(f"Final result: {result}")


# Entry point with async execution
if __name__ == "__main__":
    # Run synchronous main
    main()

    # Run async code
    async def async_main():
        urls = ["https://example.com", "https://example.org", "https://example.net"]
        results = await process_urls(urls)

        processor = AsyncProcessor(max_concurrency=2)
        items = ["item1", "item2", "item3", "item4", "item5"]
        processed = await processor.process_batch(items)

        return results, processed

    # Run async main on event loop
    loop = asyncio.get_event_loop()
    async_results, async_processed = loop.run_until_complete(async_main())

    logger.info(f"Async results: {async_results}")
    logger.info(f"Async processed: {async_processed}")
