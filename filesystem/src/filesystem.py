import os
import sys
import re
import shutil
import subprocess
import inspect
import uuid
import fnmatch
from pathlib import Path
from typing import List, Dict, Optional, Any, Callable
from datetime import datetime, timezone
from functools import wraps
from mcp.server.fastmcp import FastMCP, Context
import threading
import time
import json
import builtins

try:
    # Try to import from the local module first
    from .mcp_edit_utils import (
        normalize_path,
        expand_home,
        get_file_stats,
        get_metadata,
        get_history_root,
        sanitize_path_for_filename,
        acquire_lock,
        release_lock,
        calculate_hash,
        generate_diff,
        read_log_file,
        write_log_file,
        HistoryError,
        log,
        get_next_tool_call_index,
        validate_path,
        LOGS_DIR,
        DIFFS_DIR,
        CHECKPOINTS_DIR,
    )
except ImportError:
    # This branch is for when running as a module
    from mcp_edit_utils import (
        normalize_path,
        expand_home,
        get_file_stats,
        get_metadata,
        get_history_root,
        sanitize_path_for_filename,
        acquire_lock,
        release_lock,
        calculate_hash,
        generate_diff,
        read_log_file,
        write_log_file,
        HistoryError,
        log,
        get_next_tool_call_index,
        validate_path,
        LOGS_DIR,
        DIFFS_DIR,
        CHECKPOINTS_DIR,
    )

try:
    # Try relative import first
    from .grammar import get_parser_for_file, BaseParser, CodeElement, ElementType
except ImportError:
    # Fall back to direct import for when running as src/filesystem.py
    from src.grammar import get_parser_for_file, ElementType


from src.grammar import get_parser_for_file, ElementType


SYSTEM_PROMPT = """
SYSTEM PROMPT - CODING GUIDELINES
====
You are a powerful agentic AI coding assistant.

You are pair programming with a USER to solve their coding task. The task may require creating a new codebase, modifying or debugging an existing codebase, or simply answering a question. Each time the USER sends a message, he may attach some information about their current state, additional source code files, documentation, linter errors, etc. This information may or may not be relevant to the coding task, it is up for you to decide. Your main goal is to follow the USER's instructions at each message.

1. Be concise and do not repeat yourself.
2. Be conversational but professional. 
3. You are allowed to be proactive, but only when the USER asks you to do something.
4. Refer to the USER in the second person and yourself in the first person. 
5. Format your responses in markdown. Use backticks to format file, directory, function, and class names. 
6. NEVER lie or make things up.
7. Refrain from apologizing all the time when results are unexpected. Instead, just try your best to proceed or explain the circumstances to the USER without apologizing.
8. Strive to strike a balance between doing the right thing when asked, including taking actions and follow-up actions.
9. DO NOT surprise the USER with actions you take without asking. For example, if the USER asks you how to approach something, you should do your best to answer their question first, and not immediately jump into taking actions.
10. DO NOT add additional code explanation summary unless requested by the USER. After working on a file, just stop, rather than providing an explanation of what you did.
11. DO NOT add comments in code highlighting changes or referring to old and new versions of the code.
12. Do add docstrings and function level documentation.
13. When working on a codebase, keep a changelog in CHANGELOG.md located in the same directory as README.md.

IMPORTANT: You should minimize output tokens as much as possible while maintaining helpfulness, quality, and accuracy. Only address the specific query or task at hand, avoiding tangential information unless absolutely critical for completing the request. If you can answer in 1-3 sentences or a short paragraph, please do.

# Following conventions
When making changes to files, first understand the file's code conventions. Mimic code style, use existing libraries and utilities, and follow existing patterns.
- NEVER assume that a given library is available, even if it is well known. Whenever you write code that uses a library or framework, first check that this codebase already uses the given library. For example, you might look at neighboring files, or check the package.json (or cargo.toml, and so on depending on the language).
- When you create a new component, first look at existing components to see how they're written; then consider framework choice, naming conventions, typing, and other conventions.
- When you debug tests, first look at passing tests to see how they're written. NEVER cheat by skipping tests, making mock code to circumvent the code under test, modifying the test case itself, or adding special case branches with the sole purpose of passing tests. ONLY modify the test case if the old test case doesn't conform to the interface specification.
- When you edit a piece of code, first look at the code's surrounding context (especially its imports) to understand the code's choice of frameworks and libraries. Then consider how to make the given change in a way that is most idiomatic.
- Always follow security best practices. Never introduce code that exposes or logs secrets and keys. Never commit secrets or keys to the repository.

# Making code changes
When making code changes, NEVER output code to the USER, unless requested. Instead use one of the code edit tools to implement the change. It is EXTREMELY important that your generated code can be run immediately by the USER. To ensure this, follow these instructions carefully:

Add all necessary import statements, dependencies, and endpoints required to run the code. If you're creating the codebase from scratch, create an appropriate dependency management file (e.g. requirements.txt package.json) with package versions and a helpful README. Keep the architecture simple, design and document the architecture and interface specifications first, and include deployment scripts or instructions. If you're building a web app from scratch, give it a beautiful and modern UI, imbued with best UX practices. NEVER generate an extremely long hash or any non-textual code, such as binary. These are not helpful to the USER and are very expensive. Unless you are appending some small easy to apply edit to a file, or creating a new file, you MUST read the the contents or section of what you're editing before editing it. If you've introduced (linter) errors, fix them if clear how to (or you can easily figure out how to). Do not make uneducated guesses. And DO NOT loop more than 3 times on fixing linter errors on the same file. On the third time, you should stop and ask the USER what to do next. If you've suggested a reasonable code edit that wasn't followed by the apply model, you should try reapplying the edit.

When debugging, only make code changes if you are certain that you can solve the problem. Otherwise, follow debugging best practices: 1. Address the root cause instead of the symptoms. 2. Add descriptive logging statements and error messages to track variable and code state. 3. Add test functions and statements to isolate the problem. 4. Prefer solutions that do not increase structural complexity of the project.

Use test-driven development whenever possible. Look for interface documentation or specifications and make sure tests conform to such specifications. When debugging NEVER cheat by skipping, modifying tests, or creating mock programs. ALWAYS analyze the program under test and fix issues there. Only create new files and implement missing features when you are sure it is the root cause for the failing tests.

# Tool calling
You have MCP tools at your disposal to solve the coding task. Follow these rules regarding tool calls:

ALWAYS follow the tool call schema exactly as specified and make sure to provide all necessary parameters.
The conversation may reference tools that are no longer available. Only calls tools when they are necessary. 
Call the multi version of tools where available, such as read multiple files, list directory tree, make multiple edits, etc. 
If 3 tries to call an editing tool fail, stop and ask the USER for help. NEVER use `sed`, pipe, `rm` or other text processing tools to edit files.
If the USER's task is general or you already know the answer, just respond without calling tools. Before calling each tool, first explain to the USER why you are calling it. 
Answer the USER's request using the relevant tool(s), if they are available. Check that all the required parameters for each tool call are provided or can reasonably be inferred from context. IF there are no relevant tools or there are missing values for required parameters, ask the USER to supply these values; otherwise proceed with the tool calls. If the USER provides a specific value for a parameter (for example provided in quotes), make sure to use that value EXACTLY. DO NOT make up values for or ask about optional parameters. Carefully analyze descriptive terms in the request as they may indicate required parameter values that should be included even if not explicitly quoted.

# Working directory
The working directory of all MCP tools is the directory that is being set with the set_working_directory tool. This does not impact command line operations. You need to cd into the working directory before executing terminal commands.
"""

MCP_INSTRUCTIONS = """
The Filesystem MCP Server is a secure bridge for AI models to interact with your local files and code. This server provides controlled access to filesystem operations, code analysis, and version tracking within explicitly allowed directories.

The server enables reading, writing, analyzing, and managing files and directories through a carefully designed interface that prioritizes security and utility.

Key capabilities:

1. Directory Operations:
   - `set_working_directory`: Establish context for operations
   - `get_working_directory`: Check current working context
   - `directory_tree`: Generate recursive directory listings
   - `list_directory`: Get basic directory listings
   - `create_directory`: Create new directory structures
   - `search_directories`: Find directories matching patterns
   - `search_files`: Locate files matching patterns
   - `list_allowed_directories`: See which directories are accessible
   - `changes_since_last_commit`: View Git repository status

2. File Reading & Analysis:
   - `read_file`: Read whole files or specific line ranges
   - `read_multiple_files`: Process several files at once
   - `read_file_by_keyword`: Find and extract sections containing specific terms
   - `read_function_by_keyword`: Locate functions containing specific keywords
   - `get_symbols`: Extract code structure (functions, classes, methods)
   - `get_function_code`: Extract complete function definitions
   - `get_file_info`: Retrieve detailed metadata about files

3. File Writing & Modification:
   - `write_file`: Create new files or completely overwrite existing ones
   - `edit_file_diff`: Make targeted changes using replacements and insertions
   - `replace_symbol_in_file`: Replace code of a symbol (function, class, method)
   - `replace_lines_in_file`: Replace code by line numbers
   - `move_file`: Rename or relocate files
   - `delete_a_file`: Remove files
   - `finish_edit`: Signal completion of editing operations

Best practices for usage:

- Always call `set_working_directory` first - this is required before performing operations
- For file reading:
  - Use line ranges with `read_file` for efficiency with large files (e.g., ["1-100", "200-300"])
  - Use `read_file_by_keyword` to extract specific sections rather than reading entire files
  - When analyzing code, use specialized tools like `get_symbols` and `get_function_code`

- For file modification:
  - `changes_since_last_commit` should be called before starting to make edits
  - Prefer `edit_file_diff` over `write_file` for smaller changes to save tokens. Make targeted, small changes rather than whole rewrites
  - Use `inserts` and `replacements` parameters to make precise edits, group multiple edits into one tool call
  - Verify the result of edits returned by `edit_file_diff` and check for inconsistencies or unexpected results
  - Call `finish_edit` before finishing your message to the USER

- For exploration:
  - Use `list_directory` for immediate contents, `directory_tree` for deeper exploration
  - Use pattern matching with wildcards in `search_files` (e.g., "*.py" or "config.*")
"""

mcp = FastMCP("secure-filesystem-server", instructions=MCP_INSTRUCTIONS)

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


def _get_or_create_conversation_id(ctx: Optional[Context] = None) -> str:
    """
    Get the current conversation ID or create a new one if needed.
    Uses context.client_id and request_id if available, otherwise generates timestamp-based ID.
    Thread-safe and handles timeouts.
    """
    global _current_conversation_id, _last_tool_call_time

    with _conversation_lock:
        current_time = time.time()

        # If context is provided, try to use client_id and request_id
        if (
            ctx
            and hasattr(ctx, "client_id")
            and hasattr(ctx, "request_id")
            and ctx.client_id is not None
            and ctx.request_id is not None
        ):
            _current_conversation_id = f"{ctx.client_id}_{ctx.request_id}"
            _last_tool_call_time = current_time
            log.info(f"Using context-based conversation ID: {_current_conversation_id}")
            return _current_conversation_id

        # If no conversation exists or timeout occurred, create new one
        if (
            _current_conversation_id is None
            or _last_tool_call_time is None
            or current_time - _last_tool_call_time > _conversation_timeout
        ):
            # Use hex representation of timestamp instead of integer
            _current_conversation_id = format(
                int(current_time), "x"
            )  # Convert to hex without '0x' prefix
            _last_tool_call_time = current_time
            log.info(
                f"Created new hex timestamp-based conversation: {_current_conversation_id}"
            )

        # Update last tool call time
        _last_tool_call_time = current_time
        return _current_conversation_id


def _finish_edit() -> str:
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


def _resolve_path(path: str) -> str:
    """
    Resolve a path relative to the working directory if set.
    Handles '.' and bare filenames to mean working directory when WORKING_DIRECTORY is set.
    """
    # Import the global WORKING_DIRECTORY variable from builtins if available
    try:
        working_dir = globals().get("WORKING_DIRECTORY") or getattr(
            builtins, "WORKING_DIRECTORY", None
        )
    except:
        working_dir = globals().get("WORKING_DIRECTORY")

    if working_dir is not None:
        if os.path.isabs(path):
            # Absolute paths are returned as-is
            return path
        else:
            # All relative paths (including those with . or .. prefixes) get joined with working_dir
            # Using os.path.normpath to resolve . and .. in the path
            result = os.path.normpath(os.path.join(working_dir, path))

            # Make sure we preserve the original path structure when using ./ with hidden files
            # Handle cases where a ".file" becomes just "file" incorrectly
            if path.startswith("./") and len(path) > 2 and path[2] == ".":
                # The path is something like "./.hidden" - ensure the . is preserved
                # Check if the normalized path has lost the dot in the filename
                base_path = os.path.dirname(result)
                filename = os.path.basename(result)
                if not filename.startswith(".") and path[2:].startswith("."):
                    # The dot was lost, restore it
                    result = os.path.join(base_path, "." + filename)

            return result

    return path


# History Tracking Decorator
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
        if "ctx" in bound_args.arguments:
            ctx = bound_args.arguments["ctx"]
            conversation_id = _get_or_create_conversation_id(ctx)
        else:
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
            resolved_file_path = _resolve_path(file_path_str)
            resolved_source_path = (
                _resolve_path(source_path_str) if source_path_str else None
            )
            history_root = get_history_root(resolved_file_path)
            if not history_root:
                os.makedirs(
                    ".mcp", exist_ok=True
                )  # Create the .mcp folder if it doesn't exist
                history_root = get_history_root(resolved_file_path)
                # return f"Error: Cannot track history for path {resolved_file_path}. Make sure '.mcp' folder exists here or in a parent directory."
            # Validate paths using the retrieved allowed_dirs
            validated_path = Path(
                validate_path(resolved_file_path, allowed_dirs)
            ).resolve()
            validated_source_path = (
                Path(validate_path(resolved_source_path, allowed_dirs)).resolve()
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
        elif tool_name == "delete_a_file":
            operation = "delete"
            if not file_existed_before:
                # Fail early if deleting non-existent file
                return f"Error: File to delete not found at {file_path_str}"
        elif tool_name == "write_file":
            operation = "create" if not file_existed_before else "replace"
        elif tool_name in [
            "edit_file_diff",
            "replace_lines_in_file",
            "replace_symbol_in_file",
        ]:
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
            diff_content = ""  # Initialize with empty string to avoid None case
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
                "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H%M%S.%fZ")[
                    :21
                ]
                + "Z",
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

            # For edit and replace operations, always ensure there's a diff file
            if (operation == "edit" or operation == "replace") and not diff_content:
                # Create an empty diff for the edit or replace operation
                empty_diff = generate_diff(
                    content_before or [],
                    content_after or content_before or [],
                    str(relative_file_path),
                    str(relative_file_path),
                )
                diff_file_path.write_text(empty_diff)
                log_entry["diff_file"] = str(relative_diff_path)

            current_log_entries.append(log_entry)
            write_log_file(log_file_path, current_log_entries)

            # Modify the result to include the diff if it's small enough
            # (only for operations that modify files)
            if operation in ["edit", "replace", "create", "delete"] and diff_content:
                # Count the number of lines in the diff
                diff_lines = diff_content.count("\n")
                if diff_lines < 200:  # Check if the diff is less than 200 lines
                    # Add the diff to the result
                    modified_result = result
                    if not modified_result.endswith("\n"):
                        modified_result += "\n"
                    modified_result += f"\nDiff ({diff_lines} lines):\n{diff_content}"
                    return modified_result

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
def read_file(path: str, ranges: Optional[List[str]] = None) -> str:
    """
    Read file by line range. For maximum efficiency, read 100 to 2000 lines at a time. If you want to read the entire file, set range ["1-10000"].

    Args:
        path: The path to the file.
        ranges: Optional list of line ranges (1-based). Examples: ["5", "10-120", "100"].
                If None, reads the first 3000 lines.

    Returns:
        The requested file content with a summary header.
    """
    DEFAULT_MAX_LINES = 3000
    try:
        resolved_path = _resolve_path(path)
        validated_path = validate_path(resolved_path, SERVER_ALLOWED_DIRECTORIES)

        with open(validated_path, "r", encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()
        total_lines = len(lines)

        selected_lines_data = []
        header = ""

        if ranges:
            # Parse the ranges
            line_numbers = set()
            try:
                for r in ranges:
                    if "-" in r:
                        start, end = map(int, r.split("-"))
                        if start < 1 or end < start:
                            return f"Invalid range '{r}': start must be >= 1 and end >= start."
                        line_numbers.update(range(start, end + 1))
                    else:
                        line_num = int(r)
                        if line_num < 1:
                            return f"Invalid line number '{r}': must be >= 1."
                        line_numbers.add(line_num)
            except ValueError:
                return f"Invalid range format in '{r}'. Use numbers or 'start-end'."

            if not line_numbers:
                return f"No valid line numbers specified in ranges for {path}."

            # Filter lines by the requested line numbers (1-indexed)
            selected_lines_data = [
                (i + 1, line) for i, line in enumerate(lines) if i + 1 in line_numbers
            ]

            if not selected_lines_data:
                return f"No matching lines found in specified ranges for {path}."

            # Determine range description for header
            header = f"[TOTAL {total_lines} lines]"

        else:
            # Default: Read first DEFAULT_MAX_LINES
            end_line = min(total_lines, DEFAULT_MAX_LINES)
            selected_lines_data = list(
                enumerate(lines[:end_line], 1)
            )  # Use enumerate for 1-based index
            header = f"[TOTAL {total_lines} lines, showing lines 1-{end_line}]"

        # Format the output with line numbers
        formatted_lines = "\n".join(
            f"{line_num}: {line.rstrip()}" for line_num, line in selected_lines_data
        )

        return f"{header}\n{formatted_lines}"

    except (ValueError, FileNotFoundError, Exception) as e:
        log.warning(f"read_file failed for {path}: {e}")
        return f"Error reading file {path}: {str(e)}"


@mcp.tool()
def read_multiple_files(paths: List[str]) -> str:
    """Read the first 500 lines of multiple files simultaneously."""
    results = []
    for file_path in paths:
        try:
            # Call the refactored read_file with default settings (first 500 lines)
            content = read_file(file_path)
            results.append(f"--- {file_path} ---\n{content}\n")
        except Exception as e:  # Catch potential errors from the called read_file
            log.warning(f"read_multiple_files failed for sub-path {file_path}: {e}")
            # Use the error message returned by read_file if possible
            error_msg = (
                str(e) if isinstance(e, str) else f"Error processing file: {str(e)}"
            )
            results.append(f"--- {file_path} ---\n{error_msg}\n")
    return "\n".join(results)


@mcp.tool()
def read_file_by_keyword(
    path: str,
    keyword: str,
    include_lines_before: int = 2,
    include_lines_after: int = 3,
    use_regex: bool = False,
    ignore_case: bool = False,
) -> str:
    """Read lines containing a keyword or matching a regex pattern, with option to specify the number of lines to include before and after each match."""
    try:
        resolved_path = _resolve_path(path)
        validated_path = validate_path(resolved_path, SERVER_ALLOWED_DIRECTORIES)
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
    Read a function definition from a file by keyword or regex pattern using grammar parsers.

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
            code = f.read()
            lines = code.splitlines()
    except (ValueError, FileNotFoundError, Exception) as e:
        return f"Error accessing file {path}: {str(e)}"

    # Get the appropriate parser for this file type
    parser = get_parser_for_file(validated_path)

    # Try first to find the function using a grammar parser
    found_element = None

    if parser:
        try:
            if use_regex:
                # Parse all elements and then search for regex match in function names
                elements = parser.parse(code)
                pattern = re.compile(keyword)

                for element in elements:
                    if element.element_type in (
                        ElementType.FUNCTION,
                        ElementType.METHOD,
                    ):
                        if pattern.search(element.name):
                            found_element = element
                            break
            else:
                # Try to find the function by exact name
                found_element = parser.find_function(code, keyword)
        except Exception as e:
            log.warning(f"Parser failed: {str(e)}. Falling back to simple search.")

    # If we found a function using the parser, format and return it
    if found_element:
        # Calculate line numbers for including context
        start_line = max(1, found_element.start_line - include_lines_before)
        result_lines = []

        # Add the function code with line numbers
        for i in range(start_line - 1, found_element.end_line):
            line_num = i + 1  # Convert to 1-indexed line numbers
            if i < len(lines):
                line_text = lines[i].rstrip()
                is_match_line = (
                    found_element.start_line <= line_num <= found_element.end_line
                )
                prefix = ">" if is_match_line else " "
                result_lines.append(f"{line_num}{prefix} {line_text}")

        return "\n".join(result_lines)

    # Fall back to the original implementation if no parser is available
    # or if the parser didn't find the function
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
        if file_ext in (".py", ".pyx", ".pyw"):
            # Check if this line could be a function definition
            line = lines[line_idx].strip()
            if not (line.startswith("def ") or "def " in line):
                continue  # Not a function definition

            # Find where function body starts (line with colon)
            func_start = line_idx
            colon_found = ":" in line
            i = line_idx

            # Look for colon if not on the same line
            while not colon_found and i < min(line_idx + 5, len(lines) - 1):
                i += 1
                if ":" in lines[i]:
                    colon_found = True

            if not colon_found:
                continue  # Not a proper function definition

            # Now find the end of the function by tracking indentation
            base_indent = None
            end_idx = len(lines) - 1  # Default to end of file

            for i in range(func_start + 1, len(lines)):
                # Skip empty lines or comments at the beginning
                line_content = lines[i].strip()
                if not line_content or line_content.startswith("#"):
                    continue

                # Get indentation of first non-empty line after function definition
                if base_indent is None:
                    base_indent = len(lines[i]) - len(lines[i].lstrip())
                    continue

                # Check if we're back to base indentation level or less
                current_indent = len(lines[i]) - len(lines[i].lstrip())
                if (
                    current_indent <= base_indent
                    and line_content
                    and not line_content.startswith("#")
                ):
                    # We found a line with same or less indentation - this is the end of the function
                    end_idx = i - 1
                    break

        # Handle C-style functions (with braces)
        elif file_ext in (
            ".c",
            ".cpp",
            ".h",
            ".hpp",
            ".java",
            ".js",
            ".ts",
            ".php",
            ".cs",
        ):
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


@mcp.tool()
def get_symbols(path: str, symbol_type: Optional[str] = None) -> str:
    """
    Get all code symbols (functions, classes, methods, etc.) from a file using grammar parsers.

    Args:
        path: Path to the file
        symbol_type: Optional filter for symbol type (function, class, method, variable, etc.)
                    If None, returns all symbols

    Returns:
        A formatted list of symbols with their types and locations
    """
    try:
        resolved_path = _resolve_path(path)
        validated_path = validate_path(resolved_path, SERVER_ALLOWED_DIRECTORIES)
        with open(validated_path, "r", encoding="utf-8", errors="ignore") as f:
            code = f.read()
    except (ValueError, FileNotFoundError, Exception) as e:
        return f"Error accessing file {path}: {str(e)}"

    # Get the appropriate parser for this file type
    parser = get_parser_for_file(validated_path)
    if not parser:
        return f"No suitable parser available for file type: {path}"

    # Parse the code to get all elements
    try:
        elements = parser.parse(code)
    except Exception as e:
        return f"Error parsing file {path}: {str(e)}"

    # Filter by symbol type if specified
    if symbol_type:
        try:
            # Convert to ElementType if possible
            enum_type = ElementType(symbol_type.lower())
            elements = [e for e in elements if e.element_type == enum_type]
        except (ValueError, Exception):
            # If not a valid ElementType, use string match
            elements = [
                e
                for e in elements
                if symbol_type.lower() in e.element_type.value.lower()
            ]

    # Format the results
    if not elements:
        return f"No symbols found in {path}" + (
            f" with type '{symbol_type}'" if symbol_type else ""
        )

    result = [f"Symbols in {path}:"]
    for elem in sorted(elements, key=lambda e: e.start_line):
        parent_info = f" (in {elem.parent.name})" if elem.parent else ""
        result.append(
            f"{elem.element_type.value}: {elem.name}{parent_info} (lines {elem.start_line}-{elem.end_line})"
        )

    return "\n".join(result)


@mcp.tool()
def get_code_of_symbol(
    path: str, symbol_name: str, symbol_type: Optional[str] = None
) -> str:
    """
    Get the complete code of a specific symbol (function, class, method, etc.) from a file.
    Ensures the symbol name is unique for the given type or returns an error with matches.

    Args:
        path: Path to the file
        symbol_name: Name of the symbol to retrieve
        symbol_type: Optional type to filter by (e.g., 'function', 'class'). If None, searches all types.

    Returns:
        The complete code of the symbol or an error message if not found or ambiguous.
    """
    try:
        resolved_path = _resolve_path(path)
        validated_path = validate_path(resolved_path, SERVER_ALLOWED_DIRECTORIES)
        with open(validated_path, "r", encoding="utf-8", errors="ignore") as f:
            code = f.read()
    except (ValueError, FileNotFoundError, OSError, Exception) as e:
        return f"Error accessing file {path}: {str(e)}"

    # Get the appropriate parser for this file type
    parser = get_parser_for_file(validated_path)
    if not parser:
        return f"No suitable parser available for file type: {path}"

    # Find all symbols and filter
    try:
        all_elements = parser.parse(code)
        matching_elements = []
        for elem in all_elements:
            type_matches = True
            if symbol_type:
                try:
                    enum_type = ElementType(symbol_type.lower())
                    type_matches = elem.element_type == enum_type
                except ValueError:
                    type_matches = (
                        symbol_type.lower() in elem.element_type.value.lower()
                    )

            if elem.name == symbol_name and type_matches:
                matching_elements.append(elem)

    except Exception as e:
        return f"Error parsing symbols in {path}: {str(e)}"

    # Check results
    if not matching_elements:
        type_str = f" of type '{symbol_type}'" if symbol_type else ""
        return f"Symbol '{symbol_name}'{type_str} not found in {path}"
    elif len(matching_elements) > 1:
        error_msg = f"Ambiguous symbol name '{symbol_name}' found in {path}. Multiple matches:\n"
        for elem in matching_elements:
            parent_info = f" (in {elem.parent.name})" if elem.parent else ""
            error_msg += f"- {elem.element_type.value}: {elem.name}{parent_info} (lines {elem.start_line}-{elem.end_line})\n"
        return error_msg.strip()
    else:
        # Exactly one match found
        return matching_elements[0].code


@mcp.tool()
def create_directory(path: str) -> str:
    """Create a new directory or ensure a directory exists. Can create multiple nested directories in one operation. If the directory already exists, this operation will return its listing."""
    try:
        resolved_path = _resolve_path(path)
        validated_path = validate_path(resolved_path, SERVER_ALLOWED_DIRECTORIES)

        # Check if directory already exists
        if os.path.isdir(validated_path):
            # Return the directory listing
            return list_directory(path)

        # Create the directory
        os.makedirs(validated_path, exist_ok=True)
        return f"Successfully created directory {path}"
    except (ValueError, Exception) as e:
        return f"Error creating directory {path}: {str(e)}"


@mcp.tool()
def list_directory(path: str) -> str:
    """Get a detailed listing of all files and directories in a specified path. This tool is similar to the `ls` command. If you need to know the contents of subdirectories, use `directory_tree` instead."""
    try:
        resolved_path = _resolve_path(path)
        validated_path = validate_path(resolved_path, SERVER_ALLOWED_DIRECTORIES)
        if not os.path.isdir(validated_path):
            return f"Error: '{path}' is not a directory."

        entries = os.listdir(validated_path)
        dirs = []
        files = []

        for entry in entries:
            entry_path = os.path.join(validated_path, entry)
            if os.path.isdir(entry_path):
                dirs.append(f"[DIR]  {entry}")
            else:
                files.append(f"[FILE] {entry}")

        # Sort each category separately
        dirs.sort()
        files.sort()

        # Combine sorted categories
        formatted = dirs + files

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
    show_files_ignored_by_git: bool = False,  # Added for compatibility with directory_tree
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
        resolved_path = _resolve_path(path)
        validated_start_path = validate_path(resolved_path, SERVER_ALLOWED_DIRECTORIES)
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
            # For the root directory, show the full path that was requested
            if current_path == Path(validated_start_path):
                display_name = path
            else:
                display_name = str(current_path)

            output_lines.append(
                f"{display_name}/ [{metadata}]" if metadata else f"{display_name}/"
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
    resolved_path = _resolve_path(path)
    validated_path = validate_path(resolved_path, SERVER_ALLOWED_DIRECTORIES)

    # Check if this path is within a git repository by walking up the directory tree
    def find_git_root(start_path: str) -> Optional[str]:
        current = Path(start_path).resolve()
        max_depth = 20
        while current != current.parent and max_depth > 0:  # Stop at root
            if (current / ".git").exists():
                return str(current)
            current = current.parent
            max_depth -= 1
        return None

    # First try to find git root from the working directory
    git_root = None
    if WORKING_DIRECTORY is not None:
        git_root = find_git_root(WORKING_DIRECTORY)

    # If not found, try from the target path
    if git_root is None:
        git_root = find_git_root(validated_path)

    if not git_root or show_files_ignored_by_git:
        return full_directory_tree(
            path,
            show_line_count,
            show_permissions,
            show_owner,
            show_size,
            show_files_ignored_by_git,
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

        os.chdir(validated_path)

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
        # Change to git repository root first
        original_cwd = os.getcwd()
        os.chdir(git_root)
        try:
            result = subprocess.run(
                [git_cmd, "ls-files"], capture_output=True, text=True, check=True
            )
        finally:
            # Restore original working directory
            os.chdir(original_cwd)

        git_files = list(result.stdout.strip().split("\n"))
        if not git_files or (len(git_files) == 1 and not git_files[0]):
            return "No tracked files found in the repository."

        # Get the relative path from git root to the requested directory
        rel_path = os.path.relpath(validated_path, git_root)
        # if rel_path == ".":
        #     rel_path = ""

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
def search_directories(path: str, pattern: str, max_depth: Optional[int] = None) -> str:
    """
    Search for directories matching a pattern within the specified path.

    Args:
        path: Starting directory path
        pattern: Pattern to match directory names against (supports wildcards)
        max_depth: Maximum depth to search (None for unlimited)

    Returns:
        List of matching directory paths
    """
    results = []
    try:
        resolved_path = _resolve_path(path)
        validated_start_path = validate_path(resolved_path, SERVER_ALLOWED_DIRECTORIES)
        if not os.path.isdir(validated_start_path):
            return f"Error: Search path '{path}' is not a directory."

        current_depth = 0
        for root, dirs, _ in os.walk(
            validated_start_path, topdown=True, followlinks=False
        ):
            # Check if we've reached max depth
            if max_depth is not None:
                # Calculate current depth relative to start path
                rel_path = os.path.relpath(root, validated_start_path)
                current_depth = len(rel_path.split(os.sep)) if rel_path != "." else 0
                if current_depth >= max_depth:
                    dirs.clear()  # Don't descend further
                    continue

            # Validate the current root before processing
            try:
                validate_path(root, SERVER_ALLOWED_DIRECTORIES)
            except ValueError:
                log.warning(
                    f"Skipping directory '{root}' during search as it's outside allowed area."
                )
                dirs.clear()  # Don't recurse further
                continue

            # Check directories in current level
            for dir_name in dirs:
                if fnmatch.fnmatch(dir_name, pattern):
                    full_path = os.path.join(root, dir_name)
                    try:
                        # Final validation
                        validate_path(full_path, SERVER_ALLOWED_DIRECTORIES)
                        results.append(full_path)
                    except ValueError:
                        pass  # Skip if validation fails

        return "\n".join(results) if results else "No matching directories found."

    except (ValueError, Exception) as e:
        return f"Error searching directories in {path}: {str(e)}"


@mcp.tool()
def search_files(
    path: str, pattern: str, excludePatterns: Optional[List[str]] = None
) -> str:
    """Recursively search for files and directories matching a pattern."""
    results = []
    excludePatterns = excludePatterns or []
    try:
        resolved_path = _resolve_path(path)
        validated_start_path = validate_path(resolved_path, SERVER_ALLOWED_DIRECTORIES)
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
        resolved_path = _resolve_path(path)
        validated_path = validate_path(resolved_path, SERVER_ALLOWED_DIRECTORIES)
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


@mcp.tool()
def finish_edit() -> str:
    """Call this tool after all edits are done. This is required by the MCP server."""
    return _finish_edit()


@mcp.tool()
def set_working_directory(path: str) -> str:
    """
    THIS TOOL MUST BE CALLED FIRST, once and only once per conversation. If you're continuing a previous conversation, do not call this tool again.
    Set the working directory for file operations. This directory must be within one of the allowed directories.
    Only files within the working directory can be modified.
    The response from this tool should be added to the system prompt and should guide the entire conversation.
    """
    global WORKING_DIRECTORY
    try:
        # First validate the path is within allowed directories
        resolved_path = _resolve_path(path)
        validated_path = validate_path(resolved_path, SERVER_ALLOWED_DIRECTORIES)

        # Check if it's a directory
        if not os.path.isdir(validated_path):
            return f"Error: '{path}' is not a directory. ABORT THIS CONVERSATION IMMEDIATELY."

        # Check if we have write permissions
        if not os.access(validated_path, os.W_OK):
            return f"Error: No write permission for directory '{path}'. ABORT THIS CONVERSATION IMMEDIATELY."

        # Set the working directory
        WORKING_DIRECTORY = validated_path
        return f"{SYSTEM_PROMPT}\n\nWorking directory set to: {validated_path}"
    except ValueError as e:
        return f"Error: {str(e)}. ABORT THIS CONVERSATION IMMEDIATELY."
    except Exception as e:
        return f"Error setting working directory: {str(e)}. ABORT THIS CONVERSATION IMMEDIATELY."


@mcp.tool()
def get_working_directory() -> str:
    """Get the current working directory for file operations."""
    if WORKING_DIRECTORY is None:
        return "No working directory set"
    return WORKING_DIRECTORY


@mcp.tool()
def changes_since_last_commit(path: str = ".") -> str:
    """
    ALWAYS CALL THIS TOOL TO CHECK FOR CHANGES BEFORE EDITING FILES.
    Show changes in the working directory since the last commit.
    Combines git status and git diff to show both tracked and untracked changes.

    Args:
        path: Path to check changes in (defaults to current working directory)

    Returns:
        A string containing the git status and diff output
    """
    try:
        resolved_path = _resolve_path(path)
        validated_path = validate_path(resolved_path, SERVER_ALLOWED_DIRECTORIES)

        # Find git root
        def find_git_root(start_path: str) -> Optional[str]:
            current = Path(start_path).resolve()
            while current != current.parent:  # Stop at root
                if (current / ".git").exists():
                    return str(current)
                current = current.parent
            return None

        # First try to find git root from the working directory
        git_root = None
        if WORKING_DIRECTORY is not None:
            git_root = find_git_root(WORKING_DIRECTORY)

        # If not found, try from the target path
        if git_root is None:
            git_root = find_git_root(validated_path)

        if not git_root:
            return f"Error: No git repository found in or above {path}"

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

        # Add repository to safe.directory to avoid Git security warnings
        subprocess.run(
            [git_cmd, "config", "--global", "--add", "safe.directory", git_root],
            capture_output=False,
            text=False,
            check=False,
        )

        # Get relative path from git root to target path
        rel_path = os.path.relpath(validated_path, git_root)

        # Change to git root directory for git commands
        original_cwd = os.getcwd()
        os.chdir(git_root)

        try:
            # Get git status
            status_result = subprocess.run(
                [git_cmd, "status", "-s", rel_path],
                capture_output=True,
                text=True,
                check=True,
            )

            # Get git diff
            diff_result = subprocess.run(
                [git_cmd, "diff", "HEAD", rel_path],
                capture_output=True,
                text=True,
                check=True,
            )

            # Get untracked files diff
            untracked_diff = ""
            if status_result.stdout:
                # Get list of untracked files from status
                untracked = []
                for line in status_result.stdout.splitlines():
                    if line.startswith("??"):
                        untracked.append(line[3:])

                # Get diff for untracked files
                if untracked:
                    for file in untracked:
                        try:
                            # Check if it's a file before attempting to read
                            if os.path.isfile(file):
                                with open(
                                    file, "r", encoding="utf-8", errors="ignore"
                                ) as f:
                                    content = f.read()
                                untracked_diff += (
                                    f"\n=== Untracked file: {file} ===\n{content}\n"
                                )
                            else:
                                untracked_diff += (
                                    f"\n=== Untracked directory: {file} ===\n"
                                )
                        except Exception as e:
                            untracked_diff += (
                                f"\n=== Error reading untracked file {file}: {e} ===\n"
                            )

            # Combine outputs
            output = []
            if status_result.stdout:
                output.append("=== Git Status ===")
                output.append(status_result.stdout)

            if diff_result.stdout:
                output.append("\n=== Git Diff (tracked files) ===")
                output.append(diff_result.stdout)

            if untracked_diff:
                output.append("\n=== Untracked Files Content ===")
                output.append(untracked_diff)

            return "\n".join(output) if output else "No changes found"

        finally:
            # Restore original working directory
            os.chdir(original_cwd)

    except subprocess.CalledProcessError as e:
        return f"Error executing git command: {e.stderr}"
    except Exception as e:
        return f"Error checking changes: {str(e)}"


# === Modifying Tools (Tracked) ===


@mcp.tool()
@track_edit_history
def write_file(ctx: Context, path: str, content: str) -> str:
    """Create a new file or completely overwrite an existing file with new content. Use with caution as it will overwrite existing files without warning. Prefer using edit_file_diff if the lines changed account for less than 25% of the file. If you need to write more than 700 lines at a time write it in chunks."""
    try:
        resolved_path = _resolve_path(path)
        validated_path = validate_path(resolved_path, WORKING_DIRECTORY)
        # Ensure parent directory exists
        Path(validated_path).parent.mkdir(parents=True, exist_ok=True)

        # Handle content that might be a dictionary string
        try:
            # Try to parse the string as JSON
            json_obj = json.loads(content)
            content_to_write = json.dumps(json_obj, indent=2)
        except json.JSONDecodeError:
            # If parsing fails, try cleaning up the string
            cleaned_content = content.strip().strip("\"'")
            cleaned_content = cleaned_content.replace('\\"', '"')
            try:
                json_obj = json.loads(cleaned_content)
                content_to_write = json.dumps(json_obj, indent=2)
            except json.JSONDecodeError:
                # If all attempts fail, write the original string content
                content_to_write = content

        with open(validated_path, "w", encoding="utf-8") as f:
            f.write(content_to_write)
        return f"Successfully wrote to {path}"
    except Exception as e:
        return f"Error writing file: {str(e)}"


@mcp.tool()
@track_edit_history
def edit_file_diff(
    ctx: Context,
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
        resolved_path = _resolve_path(path)
        validated_path = validate_path(resolved_path, WORKING_DIRECTORY)
        replacements = replacements or {}
        inserts = inserts or {}
        operations = {"replace": 0, "insert": 0, "errors": []}

        # Read current content
        with open(validated_path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
        new_content = content

        # --- Process Replacements ---
        for old_text, new_text in replacements.items():
            if not isinstance(old_text, str):
                continue
            if not old_text:
                operations["errors"].append("Err: Empty replace key")
                continue

            # Try to parse and format JSON if new_text is str or dict
            content_to_replace_with = new_text
            if isinstance(new_text, dict):
                content_to_replace_with = json.dumps(new_text, indent=2)
            elif isinstance(new_text, str):
                try:
                    json_obj = json.loads(new_text)
                    content_to_replace_with = json.dumps(json_obj, indent=2)
                except json.JSONDecodeError:
                    cleaned_content = new_text.strip().strip("\"'")
                    cleaned_content = cleaned_content.replace('\\"', '"')
                    try:
                        json_obj = json.loads(cleaned_content)
                        content_to_replace_with = json.dumps(json_obj, indent=2)
                    except json.JSONDecodeError:
                        pass

            count = new_content.count(old_text)
            if count == 0:
                operations["errors"].append(
                    f"Err: Replace text not found: {old_text[:20]}..."
                )
                continue
            replace_count = -1 if replace_all else 1
            new_content = new_content.replace(
                old_text, content_to_replace_with, replace_count
            )
            operations["replace"] += count if replace_all else (1 if count > 0 else 0)

        # --- Process Insertions ---
        for anchor_text, insert_text in inserts.items():
            if not isinstance(anchor_text, str):
                continue

            # Try to parse and format JSON if insert_text is str or dict
            content_to_insert = insert_text
            if isinstance(insert_text, dict):
                content_to_insert = json.dumps(insert_text, indent=2)
            elif isinstance(insert_text, str):
                try:
                    json_obj = json.loads(insert_text)
                    content_to_insert = json.dumps(json_obj, indent=2)
                except json.JSONDecodeError:
                    cleaned_content = insert_text.strip().strip("\"'")
                    cleaned_content = cleaned_content.replace('\\"', '"')
                    try:
                        json_obj = json.loads(cleaned_content)
                        content_to_insert = json.dumps(json_obj, indent=2)
                    except json.JSONDecodeError:
                        pass

            if anchor_text == "":
                new_content = content_to_insert + new_content
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
                    [anchor_text + content_to_insert + part for part in parts[1:]]
                )
                operations["insert"] += len(parts) - 1
            else:
                pos = new_content.find(anchor_text)
                if pos != -1:
                    new_content = (
                        new_content[: pos + len(anchor_text)]
                        + content_to_insert
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
def replace_lines_in_file(
    ctx: Context, path: str, line_start: int, line_end: int, new_content: str
) -> str:
    """
    Replace a specific range of lines in a file with new content.
    Line numbers are 1-based and inclusive.

    Args:
        path: Path to the file to edit.
        line_start: The starting line number to replace (1-based).
        line_end: The ending line number to replace (1-based).
        new_content: The new text content to insert in place of the specified lines.

    Returns:
        A message indicating success or failure.
    """
    try:
        resolved_path = _resolve_path(path)
        validated_path = validate_path(resolved_path, WORKING_DIRECTORY)

        # Validate line numbers
        if not isinstance(line_start, int) or not isinstance(line_end, int):
            return "Error: line_start and line_end must be integers."
        if line_start < 1:
            return "Error: line_start must be 1 or greater."
        if line_end < line_start:
            return "Error: line_end must be greater than or equal to line_start."

        # Read current lines
        with open(validated_path, "r", encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()  # Readlines keeps trailing newlines

        total_lines = len(lines)
        if line_start > total_lines:
            return f"Error: line_start ({line_start}) is beyond the end of the file ({total_lines} lines)."
        # Allow line_end to be beyond the end, effectively replacing until the end
        line_end_actual = min(line_end, total_lines)

        # Prepare new content lines (ensure they end with newline)
        new_lines = new_content.splitlines(keepends=True)
        if not new_content.endswith("\n") and new_lines:
            # Add newline to last line if original content didn't end with one
            # and the replacement content isn't empty
            new_lines[-1] += "\n"
        elif not new_lines and new_content:
            # Handle case where new_content is a single line without newline
            new_lines = [new_content + "\n"]

        # Construct the new file content
        # Lines before the start (0-based index: line_start - 1)
        content_before = lines[: line_start - 1]
        # Lines after the end (0-based index: line_end_actual)
        content_after = lines[line_end_actual:]

        final_content_lines = content_before + new_lines + content_after
        final_content = "".join(final_content_lines)

        # Write the modified content back
        with open(validated_path, "w", encoding="utf-8") as f:
            f.write(final_content)

        return f"Successfully replaced lines {line_start}-{line_end} in {path}."

    except FileNotFoundError:
        return f"Error: File not found at {path}"
    except ValueError as ve:  # Catch specific validation errors
        return f"Error: {str(ve)}"
    except Exception as e:
        log.error(f"replace_lines_in_file failed for {path}: {e}", exc_info=True)
        return f"Error replacing lines in file {path}: {str(e)}"


@mcp.tool()
@track_edit_history
def replace_symbol_in_file(
    ctx: Context,
    path: str,
    new_content: str,
    symbol_name: str,
    symbol_type: Optional[str] = None,
    parent_name: Optional[str] = None,
) -> str:
    """
    Replace the code of a uniquely identified symbol (function, class, etc.) in a file.
    Uses get_symbols to find the symbol's location first.

    Args:
        path: Path to the file.
        new_content: The new code content for the symbol.
        symbol_name: Name of the symbol to replace.
        symbol_type: Optional type to filter by (e.g., 'function', 'class').
        parent_name: Optional name of the parent symbol (e.g., class name for a method) for a more precise match.

    Returns:
        Success message or error if the symbol is not found or ambiguous.
    """
    # 1. Find the unique symbol using logic similar to get_code_of_symbol
    try:
        resolved_path = _resolve_path(path)
        validated_path = validate_path(
            resolved_path, WORKING_DIRECTORY
        )  # Validate against working dir for modification
        with open(validated_path, "r", encoding="utf-8", errors="ignore") as f:
            code = f.read()
            # Reread as lines for precise manipulation later
            f.seek(0)
            lines = f.readlines()
    except (ValueError, FileNotFoundError, OSError, Exception) as e:
        return f"Error accessing file {path} for symbol replacement: {str(e)}"

    parser = get_parser_for_file(validated_path)
    if not parser:
        return f"No suitable parser available for file type: {path}"

    try:
        all_elements = parser.parse(code)
        matching_elements = []
        for elem in all_elements:
            name_matches = elem.name == symbol_name
            type_matches = True
            if symbol_type:
                try:
                    enum_type = ElementType(symbol_type.lower())
                    type_matches = elem.element_type == enum_type
                except ValueError:
                    type_matches = (
                        symbol_type.lower() in elem.element_type.value.lower()
                    )

            parent_matches = True
            if parent_name:
                parent_matches = (
                    elem.parent is not None and elem.parent.name == parent_name
                )

            if name_matches and type_matches and parent_matches:
                matching_elements.append(elem)

    except Exception as e:
        return f"Error parsing symbols in {path} for replacement: {str(e)}"

    # Create context string for messages
    context_str = ""
    if symbol_type:
        context_str += f" of type '{symbol_type}'"
    if parent_name:
        context_str += f" within parent '{parent_name}'"

    # Check results
    if not matching_elements:
        type_str = f" of type '{symbol_type}'" if symbol_type else ""
        return f"Error replacing symbol: Symbol '{symbol_name}'{type_str} not found in {path}"
    elif len(matching_elements) > 1:
        error_msg = f"Error replacing symbol: Ambiguous symbol name '{symbol_name}' found in {path}. Multiple matches:\n"
        for elem in matching_elements:
            parent_info = f" (in {elem.parent.name})" if elem.parent else ""
            error_msg += f"- {elem.element_type.value}: {elem.name}{parent_info} (lines {elem.start_line}-{elem.end_line})\n"
        return error_msg.strip()
    else:
        # Exactly one match found - get line numbers
        symbol_to_replace = matching_elements[0]
        line_start = symbol_to_replace.start_line
        line_end = symbol_to_replace.end_line

        # 2. Extract original symbol text precisely from lines
        # Lines are 0-indexed, line numbers are 1-based
        original_symbol_lines = lines[line_start - 1 : line_end]
        if not original_symbol_lines:
            return f"Error: Symbol '{symbol_name}'{context_str} found by parser but corresponds to empty line range ({line_start}-{line_end})."
        original_symbol_text = "".join(original_symbol_lines)

        # 3. Extract leading and trailing whitespace from original text
        leading_whitespace_match = re.match(r"^\s*", original_symbol_text, re.DOTALL)
        leading_whitespace = (
            leading_whitespace_match.group(0) if leading_whitespace_match else ""
        )

        trailing_whitespace_match = re.search(r"\s*$", original_symbol_text, re.DOTALL)
        trailing_whitespace = (
            trailing_whitespace_match.group(0) if trailing_whitespace_match else ""
        )

        # 4. Trim the new content
        trimmed_new_content = new_content.strip()

        # 5. Construct the final replacement block
        final_symbol_content = (
            leading_whitespace + trimmed_new_content + trailing_whitespace
        )

        # 6. Split the new block into lines, preserving line endings
        final_symbol_lines = final_symbol_content.splitlines(keepends=True)
        # Handle case where content becomes empty or has no newline
        if final_symbol_content and not final_symbol_content.endswith("\n"):
            if final_symbol_lines:
                final_symbol_lines[-1] += "\n"  # Add newline if missing from last line
            else:
                # If splitlines resulted in empty list but content exists (e.g. "abc"), make it a line
                final_symbol_lines = [final_symbol_content + "\n"]
        # Ensure empty replacement results in empty list
        elif not final_symbol_content:
            final_symbol_lines = []

        # 7. Reconstruct the entire file content
        try:
            content_before = lines[: line_start - 1]
            content_after = lines[line_end:]  # Use original line_end from symbol

            final_content_lines = content_before + final_symbol_lines + content_after
            final_content = "".join(final_content_lines)

            # 8. Write the modified content back
            with open(validated_path, "w", encoding="utf-8") as f:
                f.write(final_content)

            type_str = f" ({symbol_to_replace.element_type.value})"
            parent_str = f" in parent '{parent_name}'" if parent_name else ""
            return f"Successfully replaced symbol '{symbol_name}'{type_str}{parent_str} in {path} (original lines {line_start}-{line_end})."

        except Exception as e:
            # Catch errors during the file modification phase
            log.error(
                f"replace_symbol_in_file modification failed for {path}: {e}",
                exc_info=True,
            )
            return f"Error writing replaced symbol content to {path}: {str(e)}"


@mcp.tool()
@track_edit_history
def move_file(ctx: Context, source: str, destination: str) -> str:
    """Move/rename a file."""
    try:
        # Decorator validates both source and dest using SERVER_ALLOWED_DIRECTORIES
        resolved_source_path = _resolve_path(source)
        resolved_dest_path = _resolve_path(destination)
        validated_source_path = validate_path(resolved_source_path, WORKING_DIRECTORY)
        validated_dest_path = validate_path(resolved_dest_path, WORKING_DIRECTORY)
        if os.path.exists(validated_dest_path):
            return f"Error: Destination path {destination} already exists."
        Path(validated_dest_path).parent.mkdir(parents=True, exist_ok=True)

        # Using shutil.move instead of os.rename to better handle cross-device moves
        shutil.move(validated_source_path, validated_dest_path)

        # Verify the operation succeeded
        if not os.path.exists(validated_dest_path):
            return f"Error: Move operation failed. Destination file {destination} does not exist."
        if os.path.exists(validated_source_path):
            return (
                f"Error: Move operation incomplete. Source file {source} still exists."
            )

        return f"Successfully moved {source} to {destination}"
    except (ValueError, Exception) as e:
        return f"Error moving file: {str(e)}"


@mcp.tool()
@track_edit_history
def delete_a_file(ctx: Context, path: str) -> str:
    """Delete a file"""
    try:
        resolved_path = _resolve_path(path)
        validated_path = validate_path(resolved_path, WORKING_DIRECTORY)
        # Existence/type checks happen within decorator now before op
        if os.path.isdir(validated_path):
            return f"Error: Path {path} is a directory."
        if not os.path.exists(validated_path):
            return f"Error: File {path} does not exist."
        # Decorator ensures file exists before calling this core logic if op is delete
        try:
            os.remove(validated_path)
            return f"Successfully deleted {path}"
        except PermissionError:
            # If we can't delete due to permissions, report this explicitly
            return f"Error: Permission denied when trying to delete {path}"
        except Exception as specific_error:
            # Be more explicit about other errors
            return f"Error deleting {path}: {specific_error}"
    except (ValueError, FileNotFoundError, Exception) as e:
        return f"Error deleting file: {str(e)}"


<<<<<<< HEAD
<<<<<<< HEAD
=======

>>>>>>> 0c75f30 (fix: delete_a_file)
=======
>>>>>>> 2760161 (fix: filesystem path)
@mcp.prompt("echo")
def echo_prompt(text: str) -> str:
    return text

<<<<<<< HEAD
<<<<<<< HEAD

=======
>>>>>>> 0c75f30 (fix: delete_a_file)
=======

>>>>>>> 2760161 (fix: filesystem path)
if __name__ == "__main__":
    print("Secure MCP Filesystem Server running", file=sys.stderr)
    mcp.run()
