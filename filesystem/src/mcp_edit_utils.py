# mcp_edit_utils.py

import os
import re
import hashlib
import json
import logging
import subprocess
import difflib
import filelock
import threading
import uuid
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any, Callable
from functools import wraps
from mcp.server.fastmcp import Context

# --- Configuration Constants ---
HISTORY_DIR_NAME = ".mcp/edit_history"
LOGS_DIR = "logs"
DIFFS_DIR = "diffs"
CHECKPOINTS_DIR = "checkpoints"
LOCK_TIMEOUT = 10  # seconds for file locks

# --- Logging Setup ---
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
log = logging.getLogger("mcp_history_utils")  # Changed logger name


# --- Custom Exceptions ---
class HistoryError(Exception):
    """Custom exception for history-related errors."""

    pass


class ExternalModificationError(HistoryError):
    """Indicates a file was modified outside the expected history sequence."""

    pass


# --- Path Normalization and Expansion ---
def normalize_path(p: str) -> str:
    """Normalizes a path string."""
    return os.path.normpath(p)


def expand_home(filepath: str) -> str:
    """Expands ~ and ~user constructs in a path."""
    if filepath.startswith("~/") or filepath == "~":
        # Handle paths like ~/file.txt or just ~
        expanded = os.path.join(
            os.path.expanduser("~"), filepath[2:] if filepath.startswith("~/") else ""
        )
        # Log the expansion for clarity
        # log.debug(f"Expanded path '{filepath}' to '{expanded}'")
        return expanded
    elif filepath.startswith("~") and "/" not in filepath[1:]:
        # Handle paths like ~user (requires more complex logic, often handled by expanduser)
        try:
            expanded = os.path.expanduser(filepath)
            # log.debug(f"Expanded user path '{filepath}' to '{expanded}'")
            return expanded
        except KeyError:
            # If user doesn't exist, expanduser might raise KeyError or return unchanged
            log.warning(f"Could not expand user for path: {filepath}")
            return filepath  # Return original path if expansion fails
    return filepath


# --- Core Path Validation ---
def validate_path(requested_path: str, allowed_directories: List[str]) -> str:
    """
    Validate that a path is within allowed directories and safe to access.

    Args:
        requested_path: The path to validate.
        allowed_directories: List of absolute, normalized allowed directory paths.

    Returns:
        The normalized, absolute path if valid.

    Raises:
        ValueError: If the path is outside allowed directories or otherwise invalid.
    """
    if not allowed_directories:
        raise ValueError("Configuration error: No allowed directories specified.")

    expanded_path = expand_home(requested_path)
    absolute_req_path = os.path.abspath(expanded_path)
    normalized_requested = normalize_path(absolute_req_path)

    log.debug(
        f"Validating path. Requested: '{requested_path}', Absolute: '{absolute_req_path}', Normalized: '{normalized_requested}'"
    )
    log.debug(f"Allowed directories: {allowed_directories}")

    is_within_allowed = False
    for allowed_dir_path in allowed_directories:
        # Check if the requested path *starts with* an allowed directory path.
        # Ensure matching happens at directory boundaries (append os.sep).
        allowed_prefix = os.path.join(
            allowed_dir_path, ""
        )  # Ensures trailing slash consistency
        if normalized_requested == allowed_dir_path or normalized_requested.startswith(
            allowed_prefix
        ):
            is_within_allowed = True
            log.debug(
                f"Path '{normalized_requested}' is within allowed directory '{allowed_dir_path}'"
            )
            break

    if not is_within_allowed:
        log.warning(
            f"Access denied for path '{normalized_requested}'. Not within allowed: {allowed_directories}"
        )
        raise ValueError(
            f"Access denied - path outside allowed directories: {absolute_req_path}"
        )

    # Handle symlinks carefully for existing paths
    if os.path.exists(
        normalized_requested
    ):  # Check existence using the normalized absolute path
        try:
            # Use os.path.realpath to resolve symlinks
            real_path = os.path.realpath(absolute_req_path)
            normalized_real = normalize_path(real_path)

            # Crucially, re-check if the *resolved* real path is within allowed directories
            is_real_path_allowed = False
            for allowed_dir_path in allowed_directories:
                allowed_prefix = os.path.join(allowed_dir_path, "")
                if normalized_real == allowed_dir_path or normalized_real.startswith(
                    allowed_prefix
                ):
                    is_real_path_allowed = True
                    break

            if not is_real_path_allowed:
                log.warning(
                    f"Access denied for symlink '{normalized_requested}'. Real path '{normalized_real}' is outside allowed directories."
                )
                raise ValueError(
                    "Access denied - symlink target outside allowed directories"
                )

            log.debug(
                f"Path exists. Real path: '{normalized_real}'. Validation successful."
            )
            # Return the resolved, normalized real path for existing items
            return normalized_real

        except OSError as e:
            # Catch potential OS errors during realpath resolution (e.g., broken links, deep recursion)
            if (
                "recursion" in str(e).lower()
                or "maximum recursion depth exceeded" in str(e).lower()
            ):
                log.error(
                    f"Path validation failed due to potential symlink loop: {absolute_req_path}"
                )
                raise ValueError(
                    "Path contains circular symlinks or excessive recursion"
                )
            elif "Too many levels of symbolic links" in str(e):
                log.error(
                    f"Path validation failed due to too many symlink levels: {absolute_req_path}"
                )
                raise ValueError("Path contains too many levels of symbolic links")
            else:
                log.error(f"Error resolving real path for '{absolute_req_path}': {e}")
                raise ValueError(f"Error validating path existence: {str(e)}")
        except Exception as e:
            log.exception(
                f"Unexpected error during real path validation for {absolute_req_path}: {e}"
            )
            raise ValueError(f"Unexpected error validating path: {str(e)}")

    else:
        # For non-existing paths (e.g., creating a new file/dir)
        # Verify the *intended parent directory* exists and is allowed.
        parent_dir = os.path.dirname(absolute_req_path)

        if not os.path.exists(parent_dir):
            log.warning(
                f"Access denied for non-existing path '{normalized_requested}'. Parent directory '{parent_dir}' does not exist."
            )
            raise ValueError(f"Parent directory does not exist: {parent_dir}")

        # Validate the parent directory itself (including resolving its symlinks)
        try:
            # Resolve parent symlinks first
            parent_real_path = os.path.realpath(parent_dir)
            normalized_parent = normalize_path(parent_real_path)

            is_parent_allowed = False
            for allowed_dir_path in allowed_directories:
                allowed_prefix = os.path.join(allowed_dir_path, "")
                if (
                    normalized_parent == allowed_dir_path
                    or normalized_parent.startswith(allowed_prefix)
                ):
                    is_parent_allowed = True
                    break

            if not is_parent_allowed:
                log.warning(
                    f"Access denied for non-existing path '{normalized_requested}'. Parent's real path '{normalized_parent}' is outside allowed directories."
                )
                raise ValueError(
                    "Access denied - parent directory outside allowed directories"
                )

            log.debug(
                f"Path does not exist. Parent '{normalized_parent}' validated. Allowing creation at '{normalized_requested}'."
            )
            # Return the original intended normalized absolute path for creation
            return normalized_requested

        except OSError as e:
            if (
                "recursion" in str(e).lower()
                or "maximum recursion depth exceeded" in str(e).lower()
            ):
                log.error(
                    f"Parent path validation failed due to potential symlink loop: {parent_dir}"
                )
                raise ValueError(
                    "Parent path contains circular symlinks or excessive recursion"
                )
            elif "Too many levels of symbolic links" in str(e):
                log.error(
                    f"Parent path validation failed due to too many symlink levels: {parent_dir}"
                )
                raise ValueError(
                    "Parent path contains too many levels of symbolic links"
                )
            else:
                log.error(
                    f"Error resolving real path for parent directory '{parent_dir}': {e}"
                )
                raise ValueError(
                    f"Error validating parent directory existence: {str(e)}"
                )
        except Exception as e:
            log.exception(
                f"Unexpected error during parent directory validation for {parent_dir}: {e}"
            )
            raise ValueError(f"Unexpected error validating parent directory: {str(e)}")


# --- Filesystem Info Helpers ---
def get_file_stats(file_path: str) -> Dict[str, Any]:
    """Gets file statistics using os.stat."""
    stats = os.stat(file_path)
    return {
        "size": stats.st_size,
        "created": datetime.fromtimestamp(stats.st_ctime, tz=timezone.utc),  # Use UTC
        "modified": datetime.fromtimestamp(stats.st_mtime, tz=timezone.utc),
        "accessed": datetime.fromtimestamp(stats.st_atime, tz=timezone.utc),
        "isDirectory": os.path.isdir(file_path),
        "isFile": os.path.isfile(file_path),
        "permissions": oct(stats.st_mode)[-3:],  # POSIX permissions part
        "uid": stats.st_uid,
        "gid": stats.st_gid,
    }


def get_metadata(
    path: str,
    is_file: bool,
    count_lines: bool = False,
    show_permissions: bool = False,
    show_owner: bool = False,
    show_size: bool = False,
) -> str:
    """
    Get formatted metadata for a file or directory.

    Args:
        path: The path to get metadata for.
        is_file: Whether this is a file (True) or directory (False).
        count_lines: Whether to include line count for files.
        show_permissions: Whether to include permissions.
        show_owner: Whether to include owner/group info.
        show_size: Whether to include size info.

    Returns:
        A comma-separated string of metadata, or empty string if no metadata requested.
    """
    # Import pwd/grp only if needed and available (Unix-specific)
    pwd = grp = None
    if show_owner:
        try:
            import pwd
            import grp
        except ImportError:
            log.warning(
                "pwd/grp modules not available on this system. Owner info will be UID/GID."
            )

    metadata_parts = []
    try:
        stats = os.stat(path)

        if show_size:
            size_bytes = stats.st_size
            if size_bytes < 1024:
                size_str = f"{size_bytes}B"
            elif size_bytes < 1024**2:
                size_str = f"{size_bytes / 1024:.1f}KB"
            elif size_bytes < 1024**3:
                size_str = f"{size_bytes / 1024**2:.1f}MB"
            else:
                size_str = f"{size_bytes / 1024**3:.1f}GB"
            metadata_parts.append(size_str)

        if show_permissions:
            mode = stats.st_mode
            perms = ""
            perms += "d" if os.path.isdir(path) else "-"
            perms += "r" if mode & 0o400 else "-"
            perms += "w" if mode & 0o200 else "-"
            perms += "x" if mode & 0o100 else "-"
            perms += "r" if mode & 0o040 else "-"
            perms += "w" if mode & 0o020 else "-"
            perms += "x" if mode & 0o010 else "-"
            perms += "r" if mode & 0o004 else "-"
            perms += "w" if mode & 0o002 else "-"
            perms += "x" if mode & 0o001 else "-"
            metadata_parts.append(perms)

        if show_owner and pwd and grp:
            try:
                user = pwd.getpwuid(stats.st_uid).pw_name
                group = grp.getgrgid(stats.st_gid).gr_name
                metadata_parts.append(f"{user}:{group}")
            except (KeyError, AttributeError):  # Handle lookup failures
                metadata_parts.append(f"{stats.st_uid}:{stats.st_gid}")
        elif show_owner:  # Fallback if modules not available
            metadata_parts.append(f"{stats.st_uid}:{stats.st_gid}")

        if count_lines and is_file:
            try:
                line_count = 0
                with open(path, "rb") as f:  # Read bytes to count lines robustly
                    for line in f:
                        line_count += 1
                metadata_parts.append(f"{line_count} lines")
            except Exception:
                metadata_parts.append(
                    "binary/unreadable"
                )  # Handle binary files or read errors

    except Exception as e:
        log.warning(f"Could not get metadata for {path}: {e}")
        if show_size or show_permissions or show_owner or count_lines:
            metadata_parts.append("Error: inaccessible")  # Keep it brief

    return ", ".join(metadata_parts)


# --- History Management Utilities ---
def get_mcp_root(path: str) -> Optional[Path]:
    """Find the root directory containing the .mcp directory."""
    p = Path(path).resolve()
    while True:
        if (p / ".mcp").is_dir():
            return p
        if p.parent == p:
            return None
        p = p.parent


def get_history_root(path: str) -> Optional[Path]:
    """Find or create the .mcp/edit_history directory and subdirs."""
    mcp_root = get_mcp_root(path)
    if mcp_root:
        history_root = mcp_root / HISTORY_DIR_NAME
        try:
            history_root.mkdir(parents=True, exist_ok=True)
            (history_root / LOGS_DIR).mkdir(exist_ok=True)
            (history_root / DIFFS_DIR).mkdir(exist_ok=True)
            (history_root / CHECKPOINTS_DIR).mkdir(exist_ok=True)
            return history_root
        except OSError as e:
            log.error(f"Could not create history directories under {history_root}: {e}")
            return None
    return None


def sanitize_path_for_filename(abs_path: str, workspace_root: Path) -> str:
    """Creates a safe filename from an absolute path relative to the workspace."""
    try:
        relative_path = Path(abs_path).relative_to(workspace_root)
        sanitized = (
            str(relative_path)
            .replace(os.sep, "_")
            .replace(":", "_")
            .replace("\\", "_")
            .replace("/", "_")
        )
        sanitized = re.sub(
            r"[^\w\-_\.]", "_", sanitized
        )  # Replace other potentially unsafe chars
        max_len = 200  # Common filesystem limit approximation
        if len(sanitized) > max_len:
            hash_suffix = hashlib.sha1(sanitized.encode()).hexdigest()[:8]
            sanitized = sanitized[: max_len - 9] + "_" + hash_suffix
        return sanitized
    except ValueError:
        log.warning(
            f"Path {abs_path} not relative to workspace {workspace_root}. Using hash."
        )
        return hashlib.sha256(abs_path.encode()).hexdigest()


def acquire_lock(lock_path: str) -> filelock.FileLock:
    """Acquires a file lock, creating parent directory if needed."""
    lock_file = Path(f"{lock_path}.lock")
    try:
        lock_file.parent.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        log.error(f"Could not create directory for lock file {lock_file}: {e}")
        raise TimeoutError(f"Failed to create directory for lock {lock_path}") from e

    lock = filelock.FileLock(str(lock_file), timeout=LOCK_TIMEOUT)
    try:
        lock.acquire()
        log.debug(f"Acquired lock: {lock_file}")
        return lock
    except filelock.Timeout:
        log.error(f"Timeout acquiring lock: {lock_file}")
        raise TimeoutError(f"Could not acquire lock for {lock_path}")


def release_lock(lock: Optional[filelock.FileLock]):
    """Releases a file lock if it's held."""
    if lock and lock.is_locked:
        lock_path = lock.lock_file
        lock.release()
        # Optionally remove the .lock file? FileLock usually handles cleanup.
        # try:
        #     os.remove(lock_path)
        # except OSError: pass # Ignore if already gone
        log.debug(f"Released lock: {lock_path}")


def calculate_hash(file_path: str) -> Optional[str]:
    """Calculates the SHA256 hash of a file's content."""
    try:
        hasher = hashlib.sha256()
        with open(file_path, "rb") as f:
            while chunk := f.read(8192):  # Read in chunks
                hasher.update(chunk)
        return hasher.hexdigest()
    except FileNotFoundError:
        return None
    except IOError as e:
        log.error(f"Error reading file {file_path} for hashing: {e}")
        return None


def generate_diff(
    content_before_lines: List[str],
    content_after_lines: List[str],
    path_a: str,
    path_b: str,
) -> str:
    """Generates a unified diff string."""

    # Ensure lines end with newline for difflib if they don't (except maybe last line)
    def ensure_nl(lines):
        return [(l if l.endswith("\n") else l + "\n") for l in lines]

    # difflib expects lines WITH newlines
    diff_iter = difflib.unified_diff(
        content_before_lines,  # Assume lines read by readlines() have them
        content_after_lines,
        fromfile=f"a/{path_a}",
        tofile=f"b/{path_b}",
        lineterm="\n",
    )
    return "".join(diff_iter)


def apply_patch(
    diff_content: str, target_file: str, workspace_root: Path, reverse: bool = False
) -> bool:
    """Applies a diff using the patch command. Runs from workspace root."""
    patch_cmd = ["patch", "--no-backup-if-mismatch", "-p1"]  # Add --no-backup...
    if reverse:
        patch_cmd.append("-R")

    target_rel_path = Path(target_file).relative_to(workspace_root)

    log.debug(
        f"Applying patch to {target_rel_path} (Reverse: {reverse}) within {workspace_root}"
    )
    try:
        process = subprocess.run(
            patch_cmd,
            input=diff_content.encode("utf-8"),
            # Specify the target file explicitly if patch supports it (GNU patch does)
            # This avoids ambiguity if CWD is not exactly workspace root
            args=patch_cmd + [str(target_rel_path)],  # Pass relative path as final arg
            cwd=workspace_root,  # Run from workspace root
            capture_output=True,
            check=False,
            timeout=15,  # Add a timeout
        )

        if process.returncode == 0:
            log.info(
                f"Patch applied successfully to {target_rel_path} (Reverse: {reverse})"
            )
            return True
        else:
            log.error(
                f"Patch command failed for {target_rel_path} (Reverse: {reverse}) RC={process.returncode}"
            )
            log.error(
                f"Patch STDOUT:\n{process.stdout.decode('utf-8', errors='ignore')}"
            )
            log.error(
                f"Patch STDERR:\n{process.stderr.decode('utf-8', errors='ignore')}"
            )
            return False
    except FileNotFoundError:
        log.error("`patch` command not found. Please install patch.")
        raise HistoryError("`patch` command not found.")
    except subprocess.TimeoutExpired:
        log.error(f"Patch command timed out for {target_rel_path}")
        return False
    except Exception as e:
        log.exception(f"Unexpected error applying patch to {target_rel_path}: {e}")
        return False


def read_log_file(log_file_path: Path) -> List[Dict[str, Any]]:
    """Reads a JSON Lines log file safely."""
    entries = []
    if not log_file_path.is_file():
        return entries
    try:
        with open(log_file_path, "r", encoding="utf-8") as f:
            for i, line in enumerate(f):
                if line.strip():
                    try:
                        entries.append(json.loads(line))
                    except json.JSONDecodeError:
                        log.warning(
                            f"Skipping invalid JSON line {i + 1} in {log_file_path}: {line.strip()}"
                        )
        return entries
    except IOError as e:
        log.error(f"Error reading log file {log_file_path}: {e}")
        # Decide: return empty list or raise? Raising might be safer.
        raise HistoryError(f"Could not read log file: {log_file_path}") from e


def write_log_file(log_file_path: Path, entries: List[Dict[str, Any]]):
    """Writes a list of entries to a JSON Lines log file atomically."""
    temp_path = log_file_path.with_suffix(log_file_path.suffix + ".tmp")
    try:
        log_file_path.parent.mkdir(parents=True, exist_ok=True)  # Ensure dir exists
        with open(temp_path, "w", encoding="utf-8") as f:
            for entry in entries:
                json.dump(entry, f, separators=(",", ":"))  # More compact
                f.write("\n")
        # Atomic rename/replace
        os.replace(temp_path, log_file_path)
    except IOError as e:
        log.error(f"Error writing log file {log_file_path}: {e}")
        if temp_path.exists():
            os.remove(temp_path)  # Clean up temp file
        raise HistoryError(f"Could not write log file: {log_file_path}") from e
    except Exception as e:
        if temp_path.exists():
            os.remove(temp_path)
        log.exception(f"Unexpected error writing log file {log_file_path}: {e}")
        raise HistoryError(f"Unexpected error writing log file: {log_file_path}") from e


# --- Global Counter and Lock for Tool Call Index ---
# Needs to be accessible by the decorator in the server file
_tool_call_counters: Dict[str, int] = {}
_tool_call_counters_lock = threading.Lock()


def get_next_tool_call_index(conversation_id: str) -> int:
    """Gets the next sequential index for a tool call within a conversation."""
    with _tool_call_counters_lock:
        current_index = _tool_call_counters.get(conversation_id, -1) + 1
        _tool_call_counters[conversation_id] = current_index
        # Optional: Add cleanup logic here for old conversation IDs if needed
    return current_index


# --- History Tracking Decorator ---
def track_edit_history(func: Callable) -> Callable:
    """
    Decorator for MCP tools that modify files to track their history.
    Handles locking, checkpointing, diff generation, and logging.
    Requires the decorated function to accept 'mcp_conversation_id' as a
    keyword argument and 'allowed_dirs' list passed via kwargs to the decorator call itself if needed.
    """

    @wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        ctx: Optional[Context] = None
        sig = func.__signature__
        wrapper_args = list(args)
        wrapper_kwargs = kwargs.copy()

        # Extract context
        for i, arg in enumerate(wrapper_args):
            if isinstance(arg, Context):
                ctx = wrapper_args.pop(i)
                break
        if not ctx and "ctx" in wrapper_kwargs:
            ctx = wrapper_kwargs.pop("ctx")

        # Extract allowed_dirs (passed via decorator if needed, or from context/global?)
        # For now, assume validate_path gets it passed directly.
        # If validate_path needs it from here:
        # allowed_dirs = wrapper_kwargs.pop('allowed_dirs', None)
        # if allowed_dirs is None: ... handle error ...

        # Bind arguments for the *original decorated function*
        try:
            bound_args = sig.bind(*wrapper_args, **wrapper_kwargs)
            bound_args.apply_defaults()
        except TypeError as e:
            log.error(f"Bind failed for {func.__name__}: {e}.")
            return f"Error: Missing required arguments for {func.__name__}."

        conversation_id = bound_args.arguments.get("mcp_conversation_id")
        if not conversation_id or not isinstance(conversation_id, str):
            return (
                f"Error: mcp_conversation_id (string) is required for {func.__name__}."
            )

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
        # Retrieve allowed_directories - THIS IS THE KEY DEPENDENCY
        # Assuming it's available globally in the server's scope for now.
        # If not, it MUST be passed somehow (e.g., via func default, context, decorator arg)
        # Let's pretend it's available globally called `SERVER_ALLOWED_DIRECTORIES`
        # You MUST replace this with the actual way you access the list
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
            ) | set(
                e.get("source_path")
                for e in current_log_entries
                if e.get("source_path")
            )
            needs_checkpoint = str(path_to_checkpoint) not in seen_paths

            if (
                needs_checkpoint
                and operation != "create"
                and file_existed_before_locked
            ):
                log.info(f"Creating checkpoint for {path_to_checkpoint}...")
                try:
                    with (
                        open(path_to_checkpoint, "rb") as fr,
                        open(checkpoint_file, "wb") as fw,
                    ):
                        fw.write(fr.read())
                    checkpoint_created = True
                except Exception as e:
                    log.error(f"Checkpoint failed: {e}")
                    relative_checkpoint_path = None

            # --- Execute Original Function ---
            call_args = bound_args.arguments.copy()  # Get dict of args
            if ctx:
                call_args["ctx"] = ctx  # Add context back if needed by func
            original_result = func(**call_args)  # Call original func

            # --- Read State After Operation ---
            hash_after: Optional[str] = None
            content_after: Optional[List[str]] = None
            path_after_op = validated_path
            file_exists_after = path_after_op.exists()
            if operation != "delete" and file_exists_after:
                hash_after = calculate_hash(str(path_after_op))
                if operation != "move":
                    try:
                        with open(
                            path_after_op, "r", encoding="utf-8", errors="ignore"
                        ) as f:
                            content_after = f.readlines()
                    except IOError:
                        content_after = None
            elif operation != "delete" and not file_exists_after:
                log.warning(
                    f"File {path_after_op} gone after non-delete op {tool_name}"
                )
                content_after = []

            # --- Generate and Save Diff ---
            diff_content: Optional[str] = None
            if (
                operation in ["create", "replace", "edit"]
                and content_before is not None
                and content_after is not None
            ):
                rel_path_diff = sanitize_path_for_filename(
                    str(validated_path), workspace_root
                )
                diff_content = generate_diff(
                    content_before, content_after, rel_path_diff, rel_path_diff
                )
                try:
                    with open(diff_file_path, "w", encoding="utf-8") as f:
                        f.write(diff_content)
                except IOError as e:
                    log.error(f"Failed write diff: {e}")

            # --- Create and Append Log Entry ---
            log_entry = {  # Fields as defined before
                "edit_id": edit_id,
                "conversation_id": conversation_id,
                "tool_call_index": current_index,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "operation": operation,
                "file_path": str(validated_path),
                "source_path": str(validated_source_path)
                if validated_source_path
                else None,
                "tool_name": tool_name,
                "status": "pending",
                "diff_file": str(relative_diff_path)
                if diff_content is not None
                else None,
                "checkpoint_file": str(relative_checkpoint_path)
                if checkpoint_created
                else None,
                "hash_before": hash_before,
                "hash_after": hash_after,
            }
            current_log_entries.append(log_entry)
            write_log_file(log_file_path, current_log_entries)

            return original_result  # Success

        except (
            ValueError,
            FileNotFoundError,
            IsADirectoryError,
            HistoryError,
            TimeoutError,
        ) as e:
            log.warning(f"Op failed for {tool_name} on {file_path_str}: {e}")
            # Return error message directly if safe, or use original result if func returned error string
            return (
                str(e)
                if isinstance(
                    e, (FileNotFoundError, IsADirectoryError, TimeoutError, ValueError)
                )
                else f"Error: {e}"
            )
        except Exception as e:
            log.exception(
                f"Unexpected error in track_edit_history for {tool_name}: {e}"
            )
            return f"Internal Server Error during history tracking: {e}"
        finally:
            # --- Release Locks ---
            release_lock(log_file_lock)
            release_lock(target_file_lock)
            release_lock(source_file_lock)

    return wrapper
