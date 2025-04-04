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