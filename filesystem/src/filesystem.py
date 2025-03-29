import os
import sys
import re
import shutil
import subprocess
from pathlib import Path
from typing import List, Dict, Optional
import fnmatch
from datetime import datetime
from mcp.server.fastmcp import FastMCP, Context

from mcp_edit_utils import (
    normalize_path,
    expand_home,
    validate_path,  # Core path utils
    get_file_stats,
    get_metadata,  # File info helpers
    track_edit_history,  # The decorator
    log,  # Use the shared logger
)

# Create MCP server
mcp = FastMCP("secure-filesystem-server")

# Command line argument parsing
if len(sys.argv) < 2:
    print(
        "Usage: python mcp_server_filesystem.py <allowed-directory> [additional-directories...]",
        file=sys.stderr,
    )
    sys.exit(1)

# Store allowed directories globally for validate_path
# THIS IS THE CRITICAL DEPENDENCY for the validate_path function
try:
    # Normalize all paths from arguments
    SERVER_ALLOWED_DIRECTORIES = [
        normalize_path(os.path.abspath(expand_home(d))) for d in sys.argv[1:]
    ]
    if not SERVER_ALLOWED_DIRECTORIES:
        print("Error: No valid allowed directories provided.", file=sys.stderr)
        sys.exit(1)

    # Validate that all directories exist and are accessible
    for i, dir_arg in enumerate(sys.argv[1:]):
        dir_path = SERVER_ALLOWED_DIRECTORIES[i]  # Use the already processed path
        if not os.path.isdir(dir_path):
            print(
                f"Error: Allowed directory '{dir_arg}' resolved to '{dir_path}' which is not a directory.",
                file=sys.stderr,
            )
            sys.exit(1)
        if not os.access(dir_path, os.R_OK | os.W_OK | os.X_OK):
            print(
                f"Error: Insufficient permissions (need rwx) for allowed directory '{dir_path}'.",
                file=sys.stderr,
            )
            sys.exit(1)

    log.info(
        f"Server configured with allowed directories: {SERVER_ALLOWED_DIRECTORIES}"
    )

except Exception as e:
    print(f"Error processing allowed directories: {e}", file=sys.stderr)
    sys.exit(1)


# --- MCP Tool Definitions ---

# === Read-Only Tools (No Tracking Needed) ===


@mcp.tool()
def read_file(path: str) -> str:
    """Read the complete contents of a file."""
    try:
        validated_path = validate_path(path, SERVER_ALLOWED_DIRECTORIES)
        with open(validated_path, "r", encoding="utf-8", errors="ignore") as f:
            return f.read()
    except (ValueError, Exception) as e:
        log.warning(f"read_file failed for {path}: {e}")
        return f"Error reading file: {str(e)}"


@mcp.tool()
def read_multiple_files(paths: List[str]) -> str:
    """Read the contents of multiple files simultaneously."""
    results = []
    for file_path in paths:
        try:
            validated_path = validate_path(file_path, SERVER_ALLOWED_DIRECTORIES)
            with open(validated_path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
            results.append(f"--- {file_path} ---\n{content}\n")
        except (ValueError, Exception) as e:
            log.warning(f"read_multiple_files failed for sub-path {file_path}: {e}")
            results.append(f"--- {file_path} ---\nError: {str(e)}\n")
    return "\n".join(results)


@mcp.tool()
def read_file_by_line(path: str, ranges: List[str]) -> str:
    """Read specific lines or line ranges from a file. Ranges can be specified as single numbers or ranges. Line numbers are 1-based. Example: ["5", "10-20", "100"] will read line 5, lines 10 through 20, and line 100."""
    validated_path = validate_path(path, SERVER_ALLOWED_DIRECTORIES)

    # Parse the ranges
    line_numbers = set()
    for r in ranges:
        if "-" in r:
            start, end = map(int, r.split("-"))
            if start < 1 or end < start:
                return f"Invalid range '{r}': start must be >= 1 and end >= start."
            line_numbers.update(range(start, end + 1))
        else:
            if int(r) < 1:
                return f"Invalid line number '{r}': must be >= 1."
            line_numbers.add(int(r))

    if not line_numbers:
        return "No valid line numbers or ranges specified."

    # Read the file line by line, keeping only requested lines
    try:
        with open(validated_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
    except (ValueError, FileNotFoundError, Exception) as e:
        return f"Error reading file by line: {str(e)}"

    # Filter lines by the requested line numbers (1-indexed)
    selected_lines = [
        (i + 1, line) for i, line in enumerate(lines) if i + 1 in line_numbers
    ]

    if not selected_lines:
        return "No matching lines found."

    # Format the output with line numbers
    return "\n".join(
        f"{line_num}: {line.rstrip()}" for line_num, line in selected_lines
    )


@mcp.tool()
def read_file_by_keyword(
    path: str,
    keyword: str,
    before: int = 0,
    after: int = 0,
    use_regex: bool = False,
    ignore_case: bool = False,
) -> str:
    """
    Read lines containing a keyword or matching a regex pattern, with optional context.
    Overlapping regions are combined.

    Args:
        path: Path to the file
        keyword: The keyword to search for, or a regex pattern if use_regex is True
        before: Number of lines to include before each match (default: 0)
        after: Number of lines to include after each match (default: 0)
        use_regex: Whether to interpret the keyword as a regular expression (default: False)
        ignore_case: Whether to ignore case when matching (default: False)

    Returns:
        Matching lines with context, or a message if no matches are found.
    """
    try:
        validated_path = validate_path(path, SERVER_ALLOWED_DIRECTORIES)
        with open(validated_path, "r", encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()
    except (ValueError, Exception) as e:
        return f"Error accessing file {path}: {str(e)}"

    matches = []  # List of line indices (0-based)
    try:
        if use_regex:
            flags = re.IGNORECASE if ignore_case else 0
            pattern = re.compile(keyword, flags)
            matches = [i for i, line in enumerate(lines) if pattern.search(line)]
        else:
            search_term = keyword.lower() if ignore_case else keyword
            matches = [
                i
                for i, line in enumerate(lines)
                if search_term in (line.lower() if ignore_case else line)
            ]
    except re.error as e:
        return f"Error in regex pattern: {str(e)}"

    if not matches:
        return f"No matches found for '{keyword}'."

    # Determine the ranges of lines to include (with context)
    regions = []
    for match in matches:
        start = max(0, match - before)
        end = min(len(lines) - 1, match + after)
        regions.append((start, end))

    # Combine overlapping regions
    combined_regions = []
    regions.sort()
    current_start, current_end = regions[0]

    for start, end in regions[1:]:
        if start <= current_end + 1:
            # Regions overlap or are adjacent, merge them
            current_end = max(current_end, end)
        else:
            # New non-overlapping region
            combined_regions.append((current_start, current_end))
            current_start, current_end = start, end

    combined_regions.append((current_start, current_end))

    # Extract the lines from the combined regions
    result = []

    # Create pattern for regex mode or None for keyword mode
    if use_regex:
        flags = re.IGNORECASE if ignore_case else 0
        pattern = re.compile(keyword, flags)
    else:
        pattern = None

    for start, end in combined_regions:
        # Add a separator between regions if needed
        if result:
            result.append("---")

        # Add the region with line numbers
        for i in range(start, end + 1):
            line_num = i + 1  # 1-indexed line numbers
            line = lines[i].rstrip()

            # Mark matching lines
            if use_regex:
                is_match = pattern.search(line) is not None
            else:
                if ignore_case:
                    is_match = keyword.lower() in line.lower()
                else:
                    is_match = keyword in line

            prefix = ">" if is_match else " "
            result.append(f"{line_num}{prefix} {line}")

    return "\n".join(result)


@mcp.tool()
def read_function_by_keyword(
    path: str, keyword: str, before: int = 0, use_regex: bool = False
) -> str:
    """
    Read a function definition from a file by keyword or regex pattern.

    Searches for the keyword, then captures the function definition by:
    1. Looking for an opening brace after the keyword
    2. Tracking brace nesting to find the matching closing brace
    3. Including the specified number of lines before the function

    Args:
        path: Path to the file
        keyword: Keyword to identify the function (usually the function name), or a regex pattern if use_regex is True
        before: Number of lines to include before the function definition
        use_regex: Whether to interpret the keyword as a regular expression (default: False)

    Returns:
        The function definition with context, or a message if not found
    """
    try:
        validated_path = validate_path(path, SERVER_ALLOWED_DIRECTORIES)
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
        # Check if this is a function definition by looking for braces
        line_idx = match_idx
        brace_idx = -1

        # Look for opening brace on the same line or the next few lines
        for i in range(line_idx, min(line_idx + 3, len(lines))):
            if "{" in lines[i]:
                brace_idx = i
                break

        if brace_idx == -1:
            continue  # Not a function definition with braces, try next match

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

        # Include the requested number of lines before the function
        start_idx = max(0, match_idx - before)

        # Extract the function with line numbers
        result = []
        for i in range(start_idx, end_idx + 1):
            line_num = i + 1  # 1-indexed line numbers
            line = lines[i].rstrip()
            result.append(f"{line_num}: {line}")

        return "\n".join(result)

    return f"Found {'pattern matches' if use_regex else f"keyword '{keyword}'"} but no valid function definition with braces was identified."


@mcp.tool()
def create_directory(path: str) -> str:
    """
    Create a new directory or ensure a directory exists. Can create multiple nested directories in one operation. If the directory already exists, this operation will succeed silently. Only works within allowed directories.
    """
    try:
        validated_path = validate_path(path, SERVER_ALLOWED_DIRECTORIES)
        os.makedirs(validated_path, exist_ok=True)
        return f"Successfully created directory {path}"
    except (ValueError, Exception) as e:
        return f"Error creating directory {path}: {str(e)}"


@mcp.tool()
def list_directory(path: str) -> str:
    """
    Get a detailed listing of all files and directories in a specified path.
    Results clearly distinguish between files and directories with [FILE] and [DIR]
    prefixes. This tool is essential for understanding directory structure and
    finding specific files within a directory. Only works within allowed directories.
    """
    try:
        validated_path = validate_path(path, SERVER_ALLOWED_DIRECTORIES)
        if not os.path.isdir(validated_path):
            return f"Error: '{path}' is not a directory."
        entries = os.listdir(validated_path)
        formatted = []
        for entry in sorted(entries):
            entry_path = os.path.join(validated_path, entry)
            # Use a safer check for isdir/isfile
            prefix = "[DIR] " if os.path.isdir(entry_path) else "[FILE]"
            formatted.append(f"{prefix} {entry}")
        return (
            f"Contents of {path}:\n" + "\n".join(formatted)
            if formatted
            else f"Directory {path} is empty."
        )
    except (ValueError, Exception) as e:
        return f"Error listing directory {path}: {str(e)}"


@mcp.tool()
def directory_tree(
    path: str,
    count_lines: bool = False,
    show_permissions: bool = False,
    show_owner: bool = False,
    show_size: bool = False,
) -> str:
    """
    Get a recursive listing of files and directories with optional metadata.

    Args:
        path: Path to the directory to display
        count_lines: Whether to include the number of lines for each file (default: False)
        show_permissions: Whether to show file permissions (default: False)
        show_owner: Whether to show file ownership information (default: False)
        show_size: Whether to show file sizes (default: False)

    Returns:
        A text representation of directories and files with full paths and requested metadata
    """
    output_lines = []
    try:
        validated_start_path = validate_path(path, SERVER_ALLOWED_DIRECTORIES)
        if not os.path.isdir(validated_start_path):
            return f"Error: '{path}' is not a directory."

        def process_directory(current_path_str):
            # Re-validate each subdir to prevent following links out of allowed area
            try:
                current_path = Path(
                    validate_path(current_path_str, SERVER_ALLOWED_DIRECTORIES)
                )
                if not current_path.is_dir():
                    return  # Skip if became file/link or invalid
            except ValueError:
                output_lines.append(f"{Path(current_path_str).name} [ACCESS DENIED]")
                return

            # Add the directory itself
            metadata = get_metadata(
                str(current_path), False, False, show_permissions, show_owner, show_size
            )
            output_lines.append(
                f"{current_path.name}/ [{metadata}]"
                if metadata
                else f"{current_path.name}/"
            )

            try:
                entries = sorted(os.listdir(current_path))
            except OSError as e:
                output_lines.append(
                    f"{current_path.name}/ [Error listing dir: {e.strerror}]"
                )
                return

            for i, entry_name in enumerate(entries):
                entry_path = current_path / entry_name

                if entry_path.is_symlink():  # Handle symlinks explicitly
                    try:
                        link_target = os.readlink(entry_path)
                        # Attempt validation of link target path itself
                        metadata = get_metadata(
                            str(entry_path),
                            False,
                            False,
                            show_permissions,
                            show_owner,
                            show_size,
                        )
                        display_text = f"{entry_path} -> {link_target}"
                        if metadata:
                            display_text += f" [{metadata}]"
                        try:
                            validate_path(
                                str(entry_path.resolve()), SERVER_ALLOWED_DIRECTORIES
                            )  # Check resolved target
                        except ValueError:
                            display_text += " [TARGET OUTSIDE ALLOWED DIRECTORIES]"
                        output_lines.append(display_text)
                    except OSError as e:
                        output_lines.append(f"{entry_path} [Broken Link: {e.strerror}]")

                elif entry_path.is_dir():
                    process_directory(str(entry_path))  # Recurse into subdirectory
                elif entry_path.is_file():
                    metadata = get_metadata(
                        str(entry_path),
                        True,
                        count_lines,
                        show_permissions,
                        show_owner,
                        show_size,
                    )
                    output_lines.append(
                        f"{entry_path} [{metadata}]" if metadata else f"{entry_path}"
                    )
                else:
                    output_lines.append(f"{entry_path} [Unknown Type]")

        process_directory(validated_start_path)  # Start recursion
        return "\n".join(output_lines)

    except (ValueError, Exception) as e:
        return f"Error generating directory tree for {path}: {str(e)}"


@mcp.tool()
def git_directory_tree(
    path: str,
    count_lines: bool = False,
    show_permissions: bool = False,
    show_owner: bool = False,
    show_size: bool = False,
) -> str:
    """
    Get a recursive listing of git-tracked files and directories with optional metadata.

    Args:
        path: Path to the git repository directory
        count_lines: Whether to include the number of lines for each file (default: False)
        show_permissions: Whether to show file permissions (default: False)
        show_owner: Whether to show file ownership information (default: False)
        show_size: Whether to show file sizes (default: False)

    Returns:
        A text representation of git-tracked files with full paths and requested metadata
    """
    validated_path = validate_path(path, SERVER_ALLOWED_DIRECTORIES)

    # Check if this is a git repository
    git_dir = os.path.join(validated_path, ".git")
    if not os.path.isdir(git_dir):
        return f"Error: {path} is not a git repository (no .git directory found)."

    # Find git executable
    git_cmd = shutil.which("git")
    if not git_cmd:
        # Try common locations for git if shutil.which fails
        common_git_paths = [
            "/usr/bin/git",
            "/usr/local/bin/git",
            "/opt/homebrew/bin/git",
            "C:\\Program Files\\Git\\bin\\git.exe",
            "C:\\Program Files (x86)\\Git\\bin\\git.exe",
        ]
        for git_path in common_git_paths:
            if os.path.isfile(git_path):
                git_cmd = git_path
                break

        if not git_cmd:
            return "Error: Git executable not found. Please ensure Git is installed and in your PATH."

    try:
        # Change into the repository directory and run git ls-files
        original_dir = os.getcwd()
        os.chdir(validated_path)

        try:
            # git config --global --add safe.directory /path
            subprocess.run(
                [
                    git_cmd,
                    "config",
                    "--global",
                    "--add",
                    "safe.directory",
                    validated_path,
                ],
                capture_output=False,
                text=False,
                check=False,
            )

            # Run git ls-files to get all tracked files
            result = subprocess.run(
                [git_cmd, "ls-files"], capture_output=True, text=True, check=True
            )

            git_files = list(result.stdout.strip().split("\n"))
            if not git_files or (len(git_files) == 1 and not git_files[0]):
                return "No tracked files found in the repository."

            # Add repository root as the first entry
            output_lines = [f"{validated_path}/ [git repository root]"]

            # Collect tracked files
            for rel_file in git_files:
                if not rel_file:  # Skip empty lines
                    continue

                # Skip .git directory and its contents
                if rel_file.startswith(".git/"):
                    continue

                file_path = os.path.join(validated_path, rel_file)

                # Get and add metadata
                if os.path.exists(file_path):
                    metadata = get_metadata(
                        file_path,
                        True,
                        count_lines,
                        show_permissions,
                        show_owner,
                        show_size,
                    )
                    if metadata:
                        output_lines.append(f"{file_path} [{metadata}]")
                    else:
                        output_lines.append(file_path)
                else:
                    # Handle case where file is tracked but doesn't exist locally
                    output_lines.append(f"{file_path} [tracked but missing]")

            return "\n".join(output_lines)

        finally:
            # Ensure we change back to the original directory even if an error occurs
            if os.getcwd() != original_dir:
                os.chdir(original_dir)

    except subprocess.CalledProcessError as e:
        return f"Error executing git command: {e.stderr}"
    except Exception as e:
        return f"Error processing git repository: {str(e)}"


@mcp.tool()
def search_files(
    path: str, pattern: str, excludePatterns: Optional[List[str]] = None
) -> str:
    """Recursively search for files and directories matching a pattern."""
    results = []
    excludePatterns = excludePatterns or []
    try:
        validated_start_path = validate_path(path, SERVER_ALLOWED_DIRECTORIES)
        if not os.path.isdir(validated_start_path):
            return f"Error: Search path '{path}' is not a directory."

        for root, dirs, files in os.walk(
            validated_start_path, topdown=True, followlinks=False
        ):
            # Filter excluded directories *before* recursing into them
            dirs[:] = [
                d
                for d in dirs
                if not any(fnmatch.fnmatch(d, pat) for pat in excludePatterns)
            ]
            files[:] = [
                f
                for f in files
                if not any(fnmatch.fnmatch(f, pat) for pat in excludePatterns)
            ]

            # Validate the current root before processing its contents
            try:
                validate_path(root, SERVER_ALLOWED_DIRECTORIES)
            except ValueError:
                log.warning(
                    f"Skipping directory '{root}' during search as it's outside allowed area (likely due to symlink traversal avoided by followlinks=False, but double checking)."
                )
                dirs[:] = []  # Don't recurse further down this invalid path
                continue  # Skip processing files in this dir

            # Check files and directories in the current validated root
            current_entries = dirs + files
            for name in current_entries:
                if fnmatch.fnmatch(name, pattern):  # Use fnmatch for wildcard support
                    full_path = os.path.join(root, name)
                    # Final check just in case (should be redundant if root is valid)
                    try:
                        validate_path(full_path, SERVER_ALLOWED_DIRECTORIES)
                        results.append(full_path)
                    except ValueError:
                        pass  # Skip adding if final validation fails somehow

        return "\n".join(results) if results else "No matches found."

    except (ValueError, Exception) as e:
        return f"Error searching in {path}: {str(e)}"


@mcp.tool()
def get_file_info(path: str) -> str:
    """Retrieve detailed metadata about a file or directory."""
    try:
        validated_path = validate_path(path, SERVER_ALLOWED_DIRECTORIES)
        info = get_file_stats(validated_path)  # Use the moved helper
        # Format output nicely
        info_str = f"Info for: {path}\n"
        for key, value in info.items():
            if isinstance(value, datetime):
                info_str += (
                    f"  {key.capitalize()}: {value.strftime('%Y-%m-%d %H:%M:%S %Z')}\n"
                )
            else:
                info_str += f"  {key.capitalize()}: {value}\n"
        return info_str.strip()
    except (ValueError, Exception) as e:
        return f"Error getting file info for {path}: {str(e)}"


@mcp.tool()
def list_allowed_directories() -> str:
    """Returns the list of directories that this server is allowed to access."""
    return f"Allowed directories:\n{chr(10).join(SERVER_ALLOWED_DIRECTORIES)}"


# === Modifying Tools (Tracked) ===


@mcp.tool()
@track_edit_history
def write_file(ctx: Context, path: str, content: str, mcp_conversation_id: str) -> str:
    """
    Create a new file or completely overwrite an existing file with new content. Use with caution as it will overwrite existing files without warning. Only works within allowed directories. mcp_conversation_id is required for history tracking, and should be unique for each LLM response and the same across multiple tool calls.
    """
    try:
        validated_path = validate_path(path, SERVER_ALLOWED_DIRECTORIES)
        # Ensure parent directory exists
        Path(validated_path).parent.mkdir(parents=True, exist_ok=True)
        with open(validated_path, "w", encoding="utf-8") as f:
            f.write(content)
        return f"Successfully wrote to {path}"
    except Exception as e:
        return f"Error writing file: {str(e)}"


@mcp.tool()
@track_edit_history
def edit_file_diff(
    ctx: Context,
    path: str,
    mcp_conversation_id: str,
    replacements: Dict[str, str] = None,
    inserts: Dict[str, str] = None,
    replace_all: bool = True,
    dry_run: bool = False,
) -> str:
    """
    Edit a file using diff logic.

    Args:
        ctx: The MCP Context object.
        path: Path to the file to edit.
        mcp_conversation_id: Required for history tracking. Should be unique for each LLM response and the same across multiple tool calls.
        replacements: Dictionary {existing_content: new_content} for replacements.
        inserts: Dictionary {anchor_content: content_to_insert_after}. Empty string "" for anchor inserts at the beginning.
        replace_all: If True, replace/insert after all occurrences; if False, only the first.
        dry_run: If True, simulate changes but don't write to disk or history.

    Returns:
        A message indicating the changes applied or validation result

    Example:
        edit_file_diff(
            ctx,
            "myfile.py",
            replacements={
                "def old_function():\\n    return False\\n": "def new_function():\\n    return True\\n",
                "MAX_RETRIES = 3": "MAX_RETRIES = 5"
            },
            inserts={
                "": "# Insert comment at beginning of file\\n",
                "import os": "import sys\\nimport logging\\n",
                "def main():": "    # Main function follows\\n",
                "return result  # last line": "# End of file\\n"
            },
            replace_all=False
        )
    """
    # --- Dry Run Handling ---
    if dry_run:
        log.info(f"Dry run for edit_file_diff on {path}.")
        try:
            validated_path = validate_path(path, SERVER_ALLOWED_DIRECTORIES)
            if os.path.exists(validated_path):
                # TODO: Add simulation logic here if desired, e.g., read content and check if keys exist
                pass
            return f"Dry run validation successful for {path}"
        except Exception as e:
            return f"Dry run validation failed for {path}: {str(e)}"

    # --- Non-Dry Run Core Logic ---
    try:
        validated_path = validate_path(path, SERVER_ALLOWED_DIRECTORIES)
        replacements = replacements or {}
        inserts = inserts or {}
        operations = {"replace": 0, "insert": 0, "errors": []}

        # Read current content (decorator has snapshot, but edits are sequential)
        with open(validated_path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
        new_content = content

        # --- Process Replacements ---
        for old_text, new_text in replacements.items():
            if not isinstance(old_text, str) or not isinstance(new_text, str):
                continue
            if not old_text:
                operations["errors"].append("Err: Empty replace key")
                continue
            count = new_content.count(old_text)
            if count == 0:
                operations["errors"].append(
                    f"Err: Replace text not found: {old_text[:20]}..."
                )
                continue
            replace_count = -1 if replace_all else 1
            new_content = new_content.replace(old_text, new_text, replace_count)
            operations["replace"] += count if replace_all else (1 if count > 0 else 0)

        # --- Process Insertions ---
        for anchor_text, insert_text in inserts.items():
            if not isinstance(anchor_text, str) or not isinstance(insert_text, str):
                continue
            if anchor_text == "":
                new_content = insert_text + new_content
                operations["insert"] += 1
                continue
            count = new_content.count(anchor_text)
            if count == 0:
                operations["errors"].append(
                    f"Err: Insert anchor not found: {anchor_text[:20]}..."
                )
                continue
            if replace_all:
                parts = new_content.split(anchor_text)
                new_content = parts[0] + "".join(
                    [anchor_text + insert_text + part for part in parts[1:]]
                )
                operations["insert"] += len(parts) - 1
            else:
                pos = new_content.find(anchor_text)
                if pos != -1:
                    new_content = (
                        new_content[: pos + len(anchor_text)]
                        + insert_text
                        + new_content[pos + len(anchor_text) :]
                    )
                    operations["insert"] += 1

        # --- Write Modified Content ---
        if not operations["errors"]:
            with open(validated_path, "w", encoding="utf-8") as f:
                f.write(new_content)
        else:
            log.warning(f"Skipping write for {path} due to edit processing errors.")

        # --- Construct Result Message ---
        if operations["errors"]:
            return "Completed edit with errors:\n" + "\n".join(operations["errors"])
        changes = [f"{v} {k}" for k, v in operations.items() if k != "errors" and v > 0]
        return (
            f"Applied {', '.join(changes)} to {path}"
            if changes
            else f"No changes applied to {path}"
        )

    except (ValueError, FileNotFoundError, Exception) as e:
        log.warning(f"edit_file_diff failed for {path}: {e}")
        return f"Error editing file: {str(e)}"


@mcp.tool()
@track_edit_history
def move_file(
    ctx: Context, source: str, destination: str, mcp_conversation_id: str
) -> str:
    """Move/rename a file. mcp_conversation_id is required for history tracking, and should be unique for each LLM response and the same across multiple tool calls."""
    try:
        # Decorator validates both source and dest using SERVER_ALLOWED_DIRECTORIES
        validated_source_path = validate_path(source, SERVER_ALLOWED_DIRECTORIES)
        validated_dest_path = validate_path(destination, SERVER_ALLOWED_DIRECTORIES)
        if os.path.exists(validated_dest_path):
            return f"Error: Destination path {destination} already exists."
        Path(validated_dest_path).parent.mkdir(parents=True, exist_ok=True)
        os.rename(validated_source_path, validated_dest_path)
        return f"Successfully moved {source} to {destination}"
    except (ValueError, Exception) as e:
        return f"Error moving file: {str(e)}"


@mcp.tool()
@track_edit_history
def delete_file(ctx: Context, path: str, mcp_conversation_id: str) -> str:
    """Delete a file. mcp_conversation_id is required for history tracking, and should be unique for each LLM response and the same across multiple tool calls."""
    try:
        validated_path = validate_path(path, SERVER_ALLOWED_DIRECTORIES)
        # Existence/type checks happen within decorator now before op
        if os.path.isdir(validated_path):
            return f"Error: Path {path} is a directory."  # Should be caught by decorator? Redundant check ok.
        # Decorator ensures file exists before calling this core logic if op is delete
        os.remove(validated_path)
        return f"Successfully deleted {path}"
    except (ValueError, FileNotFoundError, Exception) as e:
        return f"Error deleting file: {str(e)}"


if __name__ == "__main__":
    print("Secure MCP Filesystem Server running", file=sys.stderr)
    mcp.run()
