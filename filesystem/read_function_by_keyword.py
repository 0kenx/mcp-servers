@mcp.tool()
def read_function_by_keyword(
    path: str, keyword: str, include_lines_before: int = 0, use_regex: bool = False
) -> str:
    """
    Read a function definition from a file by keyword or regex pattern.
    
    Args:
        path: Path to the file
        keyword: Keyword to identify the function (usually the function name), or a regex pattern if use_regex is True
        include_lines_before: Number of lines to include before the function definition
        use_regex: Whether to interpret the keyword as a regular expression (default: False)
    
    Returns:
        The function definition with context, or a message if not found
    """
    try:
        resolved_path = _resolve_path(path)
        validated_path = validate_path(resolved_path, SERVER_ALLOWED_DIRECTORIES)
        with open(validated_path, "r", encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()  # Read all lines at once
    except (ValueError, FileNotFoundError, Exception) as e:
        return f"Error accessing file {path}: {str(e)}"

    # Find lines containing the keyword or matching the regex
    matches = []
    if use_regex:
        try:
            pattern = re.compile(keyword)
            matches = [i for i, line in enumerate(lines) if pattern.search(line)]
        except re.error as e:
            return f"Error in regex pattern: {str(e)}"
    else:
        matches = [i for i, line in enumerate(lines) if keyword in line]

    if not matches:
        return (
            f"No matches found for {'pattern' if use_regex else 'keyword'} '{keyword}'."
        )

    for match_idx in matches:
        line_idx = match_idx
        # Get file extension to determine language type
        file_ext = os.path.splitext(validated_path)[1].lower()
        
        # Handle Python-style functions (by indentation)
        if file_ext in ('.py', '.pyx', '.pyw'):
            # Check if this line could be a function definition
            line = lines[line_idx].strip()
            if not (line.startswith('def ') or 'def ' in line):
                continue  # Not a function definition
            
            # Find where function body starts (line with colon)
            func_start = line_idx
            colon_found = ':' in line
            i = line_idx
            
            # Look for colon if not on the same line
            while not colon_found and i < min(line_idx + 5, len(lines) - 1):
                i += 1
                if ':' in lines[i]:
                    colon_found = True
            
            if not colon_found:
                continue  # Not a proper function definition
            
            # Now find the end of the function by tracking indentation
            base_indent = None
            end_idx = len(lines) - 1  # Default to end of file
            
            for i in range(func_start + 1, len(lines)):
                # Skip empty lines or comments at the beginning
                line_content = lines[i].strip()
                if not line_content or line_content.startswith('#'):
                    continue
                    
                # Get indentation of first non-empty line after function definition
                if base_indent is None:
                    base_indent = len(lines[i]) - len(lines[i].lstrip())
                    continue
                
                # Check if we're back to base indentation level or less
                current_indent = len(lines[i]) - len(lines[i].lstrip())
                if current_indent <= base_indent and line_content and not line_content.startswith('#'):
                    # We found a line with same or less indentation - this is the end of the function
                    end_idx = i - 1
                    break
        
        # Handle C-style functions (with braces)
        elif file_ext in ('.c', '.cpp', '.h', '.hpp', '.java', '.js', '.ts', '.php', '.cs'):
            brace_idx = -1
            
            # Look for opening brace on the same line or the next few lines
            for i in range(line_idx, min(line_idx + 3, len(lines))):
                if "{" in lines[i]:
                    brace_idx = i
                    break
            
            if brace_idx == -1:
                continue  # Not a function definition with braces
            
            # Track brace nesting to find the end of the function
            brace_count = 0
            end_idx = -1
            
            for i in range(brace_idx, len(lines)):
                line = lines[i]
                brace_count += line.count("{")
                brace_count -= line.count("}")
                
                if brace_count == 0:
                    end_idx = i
                    break
            
            if end_idx == -1:
                return f"Found function at line {match_idx + 1}, but could not locate matching closing brace."
        
        # For other languages, just try to capture a reasonable chunk of code
        else:
            # Default behavior - capture 20 lines after match
            end_idx = min(line_idx + 20, len(lines) - 1)

        # Include the requested number of lines before the function
        start_idx = max(0, match_idx - include_lines_before)

        # Extract the function with line numbers
        result = []
        for i in range(start_idx, end_idx + 1):
            line_num = i + 1  # 1-indexed line numbers
            line = lines[i].rstrip()
            result.append(f"{line_num}: {line}")

        return "\n".join(result)

    # If we get here, none of the matches were valid function definitions
    return f"Found matches for {'pattern' if use_regex else f\"keyword '{keyword}'\"} but none appeared to be valid function definitions."