match command.split():
        case ["quit"]:
            return "Exiting program"
        
        case ["load", filename]:
            return f"Loading file: {filename}"
        
        case ["save", filename]:
            return f"Saving to file: {filename}"
        
        case ["search", *keywords]:
            return f"Searching for: {', '.join(keywords)}"
        
        case ["help"]:
            return "Available commands: quit, load, save, search, help"
        
        case _:
            return "Unknown command"

def process_data(data):