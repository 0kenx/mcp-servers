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