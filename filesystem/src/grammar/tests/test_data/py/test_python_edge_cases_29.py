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