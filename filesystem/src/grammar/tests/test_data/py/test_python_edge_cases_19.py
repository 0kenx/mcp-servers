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