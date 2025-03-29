import os
import sys
import re
import shutil
import subprocess
import inspect
import uuid
import fnmatch
from pathlib import Path
from typing import List, Dict, Optional, Any, Callable, Union
from datetime import datetime, timezone
from functools import wraps
from mcp.server.fastmcp import FastMCP
import threading
import time
import json

from mcp_edit_utils import (
    normalize_path,
    expand_home,  # Keep path utils if used directly elsewhere
    get_file_stats,
    get_metadata,  # File info helpers
    get_history_root,
    sanitize_path_for_filename,
    acquire_lock,
    release_lock,
    calculate_hash,
    generate_diff,
    read_log_file,
    write_log_file,
    HistoryError,
    log,  # Use the shared logger
    get_next_tool_call_index,  # Use the shared counter
    validate_path,
    LOGS_DIR,
    DIFFS_DIR,
    CHECKPOINTS_DIR,  # Use constants
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

    # Initialize working directory as None
    WORKING_DIRECTORY = None

    # Validate that all directories exist and are accessible
    for i, dir_arg in enumerate(sys.argv[1:]):
        dir_path = SERVER_ALLOWED_DIRECTORIES[i]  # Use the already processed path
        if not os.path.isdir(dir_path):
            print(
                f"Error: Allowed directory '{dir_arg}' resolved to '{dir_path}' which is not a directory.",
                file=sys.stderr,
            )
            sys.exit(1)
        if not os.access(dir_path, os.R_OK):
            print(
                f"Error: Insufficient permissions (need read access) for allowed directory '{dir_path}'.",
                file=sys.stderr,
            )
            sys.exit(1)

    log.info(
        f"Server configured with allowed directories: {SERVER_ALLOWED_DIRECTORIES}"
    )

except Exception as e:
    print(f"Error processing allowed directories: {e}", file=sys.stderr)
    sys.exit(1)

# --- Global Conversation Tracking ---
_current_conversation_id: Optional[str] = None
_last_tool_call_time: Optional[float] = None
_conversation_timeout: float = 120.0  # seconds
_conversation_lock = threading.Lock()


def _get_or_create_conversation_id() -> str:
    """
    Get the current conversation ID or create a new one if needed.
    Thread-safe and handles timeouts.
    """
    global _current_conversation_id, _last_tool_call_time

    with _conversation_lock:
        current_time = time.time()

        # If no conversation exists or timeout occurred, create new one
        if (
            _current_conversation_id is None
            or _last_tool_call_time is None
            or current_time - _last_tool_call_time > _conversation_timeout
        ):
            _current_conversation_id = str(int(current_time))
            _last_tool_call_time = current_time
            log.info(f"Created new conversation: {_current_conversation_id}")

        # Update last tool call time
        _last_tool_call_time = current_time
        return _current_conversation_id


def finish_edit() -> str:
    """
    End the current conversation and return its ID.
    The next tool call will start a new conversation.
    """
    global _current_conversation_id, _last_tool_call_time

    with _conversation_lock:
        if _current_conversation_id is None:
            return "No active conversation to finish"

        conversation_id = _current_conversation_id
        _current_conversation_id = None
        _last_tool_call_time = None
        log.info(f"Finished conversation: {conversation_id}")
        return f"Finished conversation: {conversation_id}"


# --- History Tracking Decorator ---
def track_edit_history(func: Callable) -> Callable:
    """
    Decorator for MCP tools that modify files to track their history.
    Handles locking, checkpointing, diff generation, and logging.
    Skips history tracking if the operation is a dry run.
    """

    @wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        # Check if this is a dry run
        is_dry_run = kwargs.get("dry_run", False)
        if is_dry_run:
            # Skip history tracking for dry runs
            return func(*args, **kwargs)

        wrapper_args = list(args)
        wrapper_kwargs = kwargs.copy()

        # Use inspect.signature
        try:
            sig = inspect.signature(func)
        except ValueError as e:
            log.error(f"Could not determine signature for {func.__name__}: {e}")
            return f"Internal Server Error: Cannot inspect tool signature for {func.__name__}."

        # Bind arguments for the *original decorated function*
        try:
            bound_args = sig.bind(*wrapper_args, **wrapper_kwargs)
            bound_args.apply_defaults()
        except TypeError as e:
            log.error(f"Bind failed for {func.__name__}: {e}.")
            return f"Error: Missing required arguments for {func.__name__}."

        # Get or create conversation ID
        conversation_id = _get_or_create_conversation_id()
        current_index = get_next_tool_call_index(conversation_id)
        tool_name = func.__name__
        log.info(
            f"Tracking call {current_index} for {tool_name} in conv {conversation_id}"
        )

        # Determine paths
        file_path_str: Optional[str] = None
        source_path_str: Optional[str] = None
        if "path" in bound_args.arguments:
            file_path_str = bound_args.arguments["path"]
        elif "destination" in bound_args.arguments:
            file_path_str = bound_args.arguments["destination"]
        if func.__name__ == "move_file":
            source_path_str = bound_args.arguments.get("source")

        if not file_path_str:
            return "Internal Server Error: Path argument missing."

        # Retrieve allowed_directories
        if "SERVER_ALLOWED_DIRECTORIES" not in globals():
            log.critical(
                "SERVER_ALLOWED_DIRECTORIES not found in global scope. Cannot validate path."
            )
            return "Internal Server Error: Server configuration for allowed directories not found."
        allowed_dirs = globals()["SERVER_ALLOWED_DIRECTORIES"]

        # Prepare history tracking structure
        try:
            history_root = get_history_root(file_path_str)
            if not history_root:
                return f"Error: Cannot track history for path {file_path_str}."
            # Validate paths using the retrieved allowed_dirs
            validated_path = Path(validate_path(file_path_str, allowed_dirs)).resolve()
            validated_source_path = (
                Path(validate_path(source_path_str, allowed_dirs)).resolve()
                if source_path_str
                else None
            )
        except (ValueError, Exception) as e:
            log.error(f"Path validation/prep failed: {e}")
            return f"Error: Path validation failed - {e}"

        # Determine operation based on tool name and existence check
        operation: Optional[str] = None
        file_existed_before = validated_path.exists()  # Check before locks

        if tool_name == "move_file":
            operation = "move"
        elif tool_name == "delete_file":
            operation = "delete"
            if not file_existed_before:
                # Fail early if deleting non-existent file
                return f"Error: File to delete not found at {file_path_str}"
        elif tool_name == "write_file":
            operation = "create" if not file_existed_before else "replace"
        elif tool_name == "edit_file_diff":
            operation = "edit"
            if not file_existed_before:
                # Fail early if editing non-existent file
                return f"Error editing file: File not found at {file_path_str}"
        else:
            # Should not happen if decorator applied correctly
            log.error(f"Decorator applied to untracked tool type? {tool_name}")
            return f"Internal Server Error: Cannot determine operation for {tool_name}"

        if operation in ["delete", "edit"] and not file_existed_before:
            return f"Error: File not found at {file_path_str}"

        # --- Initialize Variables ---
        workspace_root = history_root.parent.parent
        edit_id = str(uuid.uuid4())
        log_file_path = history_root / LOGS_DIR / f"{conversation_id}.log"
        diff_dir = history_root / DIFFS_DIR / conversation_id
        diff_dir.mkdir(exist_ok=True)
        checkpoint_dir = history_root / CHECKPOINTS_DIR / conversation_id
        checkpoint_dir.mkdir(exist_ok=True)
        relative_diff_path = Path(DIFFS_DIR) / conversation_id / f"{edit_id}.diff"
        diff_file_path = history_root / relative_diff_path

        # Convert absolute paths to relative paths from workspace root
        relative_file_path = validated_path.relative_to(workspace_root)
        relative_source_path = (
            validated_source_path.relative_to(workspace_root)
            if validated_source_path
            else None
        )

        content_before: Optional[List[str]] = None
        hash_before: Optional[str] = None
        checkpoint_created = False
        relative_checkpoint_path: Optional[Path] = None
        target_file_lock = None
        source_file_lock = None
        log_file_lock = None

        try:
            # --- Acquire Locks ---
            target_file_lock = acquire_lock(str(validated_path))
            if validated_source_path:
                source_file_lock = acquire_lock(str(validated_source_path))
            log_file_lock = acquire_lock(str(log_file_path))

            # --- Read State Before Operation ---
            path_to_read_before = (
                validated_source_path if operation == "move" else validated_path
            )
            file_existed_before_locked = path_to_read_before.exists()
            if operation in ["delete", "edit"] and not file_existed_before_locked:
                raise FileNotFoundError(
                    f"File vanished before {operation}: {path_to_read_before.name}"
                )

            if file_existed_before_locked:
                hash_before = calculate_hash(str(path_to_read_before))
                try:
                    with open(
                        path_to_read_before, "r", encoding="utf-8", errors="ignore"
                    ) as f:
                        content_before = f.readlines()
                except IOError:
                    content_before = None
            else:
                content_before = []

            # --- Handle Checkpoint ---
            path_to_checkpoint = path_to_read_before
            sanitized_chkpt_fname = (
                sanitize_path_for_filename(str(path_to_checkpoint), workspace_root)
                + ".chkpt"
            )
            checkpoint_file = checkpoint_dir / sanitized_chkpt_fname
            relative_checkpoint_path = (
                Path(CHECKPOINTS_DIR) / conversation_id / sanitized_chkpt_fname
            )
            current_log_entries = read_log_file(log_file_path)
            seen_paths = set(
                e["file_path"] for e in current_log_entries if "file_path" in e
            )

            # Only create checkpoint if this is the first time we're seeing this path
            if str(relative_file_path) not in seen_paths:
                checkpoint_created = True
                if file_existed_before_locked:
                    try:
                        shutil.copy2(path_to_checkpoint, checkpoint_file)
                    except IOError as e:
                        log.error(f"Failed to create checkpoint: {e}")
                        raise HistoryError(f"Failed to create checkpoint: {e}")

            # --- Execute Operation ---
            try:
                result = func(*wrapper_args, **wrapper_kwargs)
            except Exception as e:
                log.error(f"Operation failed: {e}")
                raise

            # --- Read State After Operation ---
            content_after: Optional[List[str]] = None
            hash_after: Optional[str] = None
            if operation != "delete":
                try:
                    with open(
                        validated_path, "r", encoding="utf-8", errors="ignore"
                    ) as f:
                        content_after = f.readlines()
                    hash_after = calculate_hash(str(validated_path))
                except IOError as e:
                    log.error(f"Failed to read file after operation: {e}")
                    content_after = None
                    hash_after = None

            # --- Generate Diff ---
            if content_before is not None and content_after is not None:
                try:
                    diff_content = generate_diff(
                        content_before,
                        content_after,
                        str(relative_file_path),
                        str(relative_file_path),
                    )
                    if diff_content:
                        diff_file_path.write_text(diff_content)
                except Exception as e:
                    log.error(f"Failed to generate diff: {e}")
                    raise HistoryError(f"Failed to generate diff: {e}")

            # --- Log Entry ---
            log_entry = {
                "edit_id": edit_id,
                "conversation_id": conversation_id,
                "tool_call_index": current_index,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "operation": operation,
                "file_path": str(relative_file_path),
                "source_path": str(relative_source_path)
                if relative_source_path
                else None,
                "tool_name": tool_name,
                "status": "pending",
                "diff_file": str(relative_diff_path) if diff_content else None,
                "checkpoint_file": str(relative_checkpoint_path)
                if checkpoint_created
                else None,
                "hash_before": hash_before,
                "hash_after": hash_after,
            }

            current_log_entries.append(log_entry)
            write_log_file(log_file_path, current_log_entries)

            return result

        finally:
            # --- Release Locks ---
            release_lock(target_file_lock)
            release_lock(source_file_lock)
            release_lock(log_file_lock)

    return wrapper


# --- MCP Tool Definitions ---

# === Read-Only Tools (No Tracking Needed) ===


@mcp.tool()
def read_file(path: str) -> str:
    """Read the complete contents of a file. Prefer using `read_multiple_files` if you need to read multiple files."""
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
    include_lines_before: int = 0,
    include_lines_after: int = 0,
    use_regex: bool = False,
    ignore_case: bool = False,
) -> str:
    """Read lines containing a keyword or matching a regex pattern, with option to specify the number of lines to include before and after each match."""
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
        start = max(0, match - include_lines_before)
        end = min(len(lines) - 1, match + include_lines_after)
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
        start_idx = max(0, match_idx - include_lines_before)

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
    """Create a new directory or ensure a directory exists. Can create multiple nested directories in one operation. If the directory already exists, this operation will succeed silently."""
    try:
        validated_path = validate_path(path, SERVER_ALLOWED_DIRECTORIES)
        os.makedirs(validated_path, exist_ok=True)
        return f"Successfully created directory {path}"
    except (ValueError, Exception) as e:
        return f"Error creating directory {path}: {str(e)}"


@mcp.tool()
def list_directory(path: str) -> str:
    """Get a detailed listing of all files and directories in a specified path. This tool is similar to the `ls` command. If you need to know the contents of subdirectories, use `directory_tree` instead."""
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


def full_directory_tree(
    path: str,
    show_line_count: bool = False,
    show_permissions: bool = False,
    show_owner: bool = False,
    show_size: bool = False,
) -> str:
    """
    Get a recursive listing of files and directories with optional metadata.

    Args:
        path: Path to the directory to display
        show_line_count: Whether to include the number of lines for each file (default: False)
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
                        show_line_count,
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
def directory_tree(
    path: str,
    show_line_count: bool = False,
    show_permissions: bool = False,
    show_owner: bool = False,
    show_size: bool = False,
    show_files_ignored_by_git: bool = False,
) -> str:
    """Get a recursive listing of files and directories inclding subdirectoies. By default no extra metadata is shown and gitignored files are not included."""
    validated_path = validate_path(path, SERVER_ALLOWED_DIRECTORIES)

    # Check if this path is within a git repository by walking up the directory tree
    def find_git_root(start_path: str) -> Optional[str]:
        current = Path(start_path).resolve()
        while current != current.parent:  # Stop at root
            if (current / ".git").exists():
                return str(current)
            current = current.parent
        return None

    git_root = find_git_root(validated_path)
    if not git_root or show_files_ignored_by_git:
        return full_directory_tree(
            path, show_line_count, show_permissions, show_owner, show_size
        )

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
        output_lines = []

        # git config --global --add safe.directory /path
        subprocess.run(
            [
                git_cmd,
                "config",
                "--global",
                "--add",
                "safe.directory",
                git_root,
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

        # Get the relative path from git root to the requested directory
        rel_path = os.path.relpath(validated_path, git_root)
        if rel_path == ".":
            rel_path = ""

        # Collect tracked files
        for rel_file in git_files:
            if not rel_file:  # Skip empty lines
                continue

            # Skip .git directory and its contents
            if rel_file.startswith(".git/"):
                continue

            # Skip files not under the requested directory
            if rel_path and not rel_file.startswith(rel_path + os.sep):
                continue

            file_path = os.path.join(git_root, rel_file)

            # Get and add metadata
            if os.path.exists(file_path):
                metadata = get_metadata(
                    file_path,
                    True,
                    show_line_count,
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
def write_file(path: str, content: str) -> str:
    """Create a new file or completely overwrite an existing file with new content. Use with caution as it will overwrite existing files without warning. Prefer using edit_file_diff if the lines changed account for less than 25% of the file."""
    try:
        validated_path = validate_path(path, WORKING_DIRECTORY)
        # Ensure parent directory exists
        Path(validated_path).parent.mkdir(parents=True, exist_ok=True)

        # Try to parse and format JSON if it's valid JSON
        try:
            json_obj = json.loads(content)
            content = json.dumps(json_obj, indent=2)
        except json.JSONDecodeError:
            # Not valid JSON, use content as-is
            pass

        with open(validated_path, "w", encoding="utf-8") as f:
            f.write(content)
        return f"Successfully wrote to {path}"
    except Exception as e:
        return f"Error writing file: {str(e)}"


@mcp.tool()
@track_edit_history
def edit_file_diff(
    path: str,
    replacements: Dict[str, str] = None,
    inserts: Dict[str, str] = None,
    replace_all: bool = True,
    dry_run: bool = False,
) -> str:
    """
    Edit a file using diff logic. Prefer using this over write_file if the lines changed account for less than 25% of the file.

    Args:
        path: Path to the file to edit.
        replacements: Dictionary {existing_content: new_content} for replacements.
        inserts: Dictionary {anchor_content: content_to_insert_after}. Empty string "" for anchor inserts at the beginning.
        replace_all: If True, replace/insert after all occurrences; if False, only the first.
        dry_run: If True, show proposed changes without making them.

    Returns:
        A message indicating the changes applied or validation result.

    Example:
        edit_file_diff(
            "myfile.py",
            replacements={
                "def old_function():\\n    return False\\n": "def new_function():\\n    return True\\n",
                "MAX_RETRIES = 3": "MAX_RETRIES = 5",
                "deleted_function() {}": "",
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
    try:
        validated_path = validate_path(path, WORKING_DIRECTORY)
        replacements = replacements or {}
        inserts = inserts or {}
        operations = {"replace": 0, "insert": 0, "errors": []}

        # Read current content
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

            # Try to parse and format JSON if it's valid JSON
            try:
                json_obj = json.loads(new_text)
                new_text = json.dumps(json_obj, indent=2)
            except json.JSONDecodeError:
                # Not valid JSON, use new_text as-is
                pass

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

            # Try to parse and format JSON if it's valid JSON
            try:
                json_obj = json.loads(insert_text)
                insert_text = json.dumps(json_obj, indent=2)
            except json.JSONDecodeError:
                # Not valid JSON, use insert_text as-is
                pass

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

        # --- Handle Dry Run ---
        if dry_run:
            if operations["errors"]:
                return "Dry run validation failed:\n" + "\n".join(operations["errors"])

            # Generate unified diff showing proposed changes
            try:
                diff_content = generate_diff(
                    content.splitlines(),
                    new_content.splitlines(),
                    str(validated_path),
                    str(validated_path),
                )
                if diff_content:
                    return f"Dry run - proposed changes for {path}:\n\n{diff_content}"
                return f"Dry run - no changes would be made to {path}"
            except Exception as e:
                return f"Error generating dry run diff: {str(e)}"

        # --- Apply Changes ---
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
def move_file(source: str, destination: str) -> str:
    """Move/rename a file."""
    try:
        # Decorator validates both source and dest using SERVER_ALLOWED_DIRECTORIES
        validated_source_path = validate_path(source, WORKING_DIRECTORY)
        validated_dest_path = validate_path(destination, WORKING_DIRECTORY)
        if os.path.exists(validated_dest_path):
            return f"Error: Destination path {destination} already exists."
        Path(validated_dest_path).parent.mkdir(parents=True, exist_ok=True)
        os.rename(validated_source_path, validated_dest_path)
        return f"Successfully moved {source} to {destination}"
    except (ValueError, Exception) as e:
        return f"Error moving file: {str(e)}"


@mcp.tool()
@track_edit_history
def delete_file(path: str) -> str:
    """Delete a file."""
    try:
        validated_path = validate_path(path, WORKING_DIRECTORY)
        # Existence/type checks happen within decorator now before op
        if os.path.isdir(validated_path):
            return f"Error: Path {path} is a directory."
        # Decorator ensures file exists before calling this core logic if op is delete
        os.remove(validated_path)
        return f"Successfully deleted {path}"
    except (ValueError, FileNotFoundError, Exception) as e:
        return f"Error deleting file: {str(e)}"


@mcp.tool()
def finish_edit() -> str:
    """Call this tool after all edits are done. This is required by the MCP server."""
    return finish_edit()


@mcp.tool()
def set_working_directory(path: str) -> str:
    """
    Set the working directory for file operations. This directory must be within one of the allowed directories.
    Only files within the working directory can be modified.
    """
    global WORKING_DIRECTORY
    try:
        # First validate the path is within allowed directories
        validated_path = validate_path(path, SERVER_ALLOWED_DIRECTORIES)

        # Check if it's a directory
        if not os.path.isdir(validated_path):
            return f"Error: '{path}' is not a directory."

        # Check if we have write permissions
        if not os.access(validated_path, os.W_OK):
            return f"Error: No write permission for directory '{path}'."

        # Set the working directory
        WORKING_DIRECTORY = validated_path
        return f"Working directory set to: {validated_path}"
    except ValueError as e:
        return f"Error: {str(e)}"
    except Exception as e:
        return f"Error setting working directory: {str(e)}"


@mcp.tool()
def get_working_directory() -> str:
    """Get the current working directory for file operations."""
    if WORKING_DIRECTORY is None:
        return "No working directory set"
    return WORKING_DIRECTORY


if __name__ == "__main__":
    print("Secure MCP Filesystem Server running", file=sys.stderr)
    mcp.run()
