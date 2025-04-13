from typing import List, Dict, Tuple, Optional, Union, Callable, TypeVar, Generic, Any

T = TypeVar("T")
K = TypeVar("K")
V = TypeVar("V")


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
    e: Callable[[int, str], bool],
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
