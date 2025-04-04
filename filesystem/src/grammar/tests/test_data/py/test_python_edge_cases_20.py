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