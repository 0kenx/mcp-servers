# Version of the package
__version__ = "0.1.0"

# Make modules accessible directly through the src package
try:
    from . import grammar
except ImportError:
    pass
