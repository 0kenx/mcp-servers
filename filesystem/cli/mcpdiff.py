#!/usr/bin/env python
# mcpdiff.py

import sys
import subprocess
import argparse
import os
import re
import hashlib
import json
import logging
import threading
import tempfile
import fcntl
from pathlib import Path
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional, Tuple

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


class FileLock:
    """A simple file locking mechanism using fcntl."""

    def __init__(self, path: str):
        self.path = path
        self.lock_path = f"{path}.lock"
        self.lock_file = None
        self.is_locked = False

    def acquire(self):
        """Acquire the lock."""
        try:
            # Create lock file if it doesn't exist
            Path(self.lock_path).parent.mkdir(parents=True, exist_ok=True)
            self.lock_file = open(self.lock_path, "w")
            fcntl.flock(self.lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            self.is_locked = True
            log.debug(f"Acquired lock: {self.lock_path}")
        except (IOError, OSError) as e:
            if self.lock_file:
                self.lock_file.close()
            raise TimeoutError(f"Could not acquire lock for {self.path}: {e}")

    def release(self):
        """Release the lock."""
        if self.lock_file:
            try:
                if self.is_locked:
                    fcntl.flock(self.lock_file.fileno(), fcntl.LOCK_UN)
                self.lock_file.close()
                try:
                    os.unlink(self.lock_path)
                except OSError:
                    pass  # Ignore errors removing lock file
            finally:
                self.is_locked = False
                self.lock_file = None

    def __enter__(self):
        self.acquire()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.release()


def acquire_lock(lock_path: str) -> FileLock:
    """Acquires a file lock, creating parent directory if needed."""
    lock = FileLock(lock_path)
    lock.acquire()
    return lock


def release_lock(lock: Optional[FileLock]):
    """Releases a file lock if it's held."""
    if lock:
        lock.release()


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
    """Generates a unified diff string using GNU diff."""
    with (
        tempfile.NamedTemporaryFile(mode="w", suffix="_before") as before_file,
        tempfile.NamedTemporaryFile(mode="w", suffix="_after") as after_file,
    ):
        # Write content to temp files
        before_file.writelines(content_before_lines)
        after_file.writelines(content_after_lines)
        before_file.flush()
        after_file.flush()

        # Run GNU diff
        try:
            result = subprocess.run(
                [
                    "diff",
                    "-u",
                    "--label",
                    f"a/{path_a}",
                    "--label",
                    f"b/{path_b}",
                    before_file.name,
                    after_file.name,
                ],
                capture_output=True,
                text=True,
                check=False,  # Don't raise on non-zero exit (diff returns 1 if files differ)
            )
            return result.stdout if result.stdout else ""
        except FileNotFoundError:
            raise HistoryError("GNU diff command not found. Please install diffutils.")
        except subprocess.SubprocessError as e:
            raise HistoryError(f"Error running diff command: {e}")


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


# --- Core Re-apply Logic ---


def reapply_conversation_state(
    conversation_id: str, target_file_path_str: str, history_root: Path
) -> bool:
    """
    Reconstructs the state of a file by re-applying accepted/pending edits
    from its conversation history, starting from its checkpoint.
    """
    log.info(
        f"Re-applying state for file '{target_file_path_str}' in conversation '{conversation_id}'"
    )
    # Corrected: Removed unused workspace_root assignment
    # workspace_root = history_root.parent.parent
    target_file_path = Path(target_file_path_str).resolve()  # Ensure absolute
    log_file_path = history_root / LOGS_DIR / f"{conversation_id}.log"

    # --- Load and Filter Log Entries ---
    # ... (Load all_conv_entries) ...
    try:
        all_conv_entries = read_log_file(log_file_path)
        if not all_conv_entries:
            log.warning(
                f"No log entries found for conversation {conversation_id}. Cannot re-apply."
            )
            return True  # Nothing to do
    except HistoryError as e:
        log.error(f"Failed to read log file for re-apply: {e}")
        return False

    # ... (Filter relevant_entries based on path history) ...
    relevant_entries: List[Dict[str, Any]] = []
    current_path_in_history = target_file_path_str
    file_ever_existed = False
    for entry in reversed(all_conv_entries):
        entry_target = entry.get("file_path")
        entry_source = entry.get("source_path")
        entry_op = entry.get("operation")
        if entry_target == current_path_in_history:
            relevant_entries.append(entry)
            file_ever_existed = True
            if entry_op == "move" and entry_source:
                current_path_in_history = entry_source
        elif entry_op == "move" and entry_source == current_path_in_history:
            relevant_entries.append(entry)
            file_ever_existed = True
            # Path trace continues from source == current == target of prev step
    if (
        not file_ever_existed
    ):  # Handle case where file was never touched or only deleted
        # ... (logic to delete file if it exists but shouldn't) ...
        log.info(
            f"File {target_file_path_str} no relevant history in {conversation_id}."
        )
        # Check if it exists and delete if it shouldn't (optional strictness)
        return True
    relevant_entries.reverse()  # Sort ascending by tool_call_index

    # --- Find Checkpoint ---
    # ... (Find checkpoint_file_str, initial_hash, first_op_details) ...
    checkpoint_file_str: Optional[str] = None
    initial_hash: Optional[str] = None
    first_op_details: Optional[Dict] = None
    for entry in relevant_entries:
        if entry.get("checkpoint_file"):
            checkpoint_file_str = entry["checkpoint_file"]
            initial_hash = entry.get("hash_before")
            first_op_details = entry
            break
        if not first_op_details:
            first_op_details = entry
    if (
        not checkpoint_file_str
        and first_op_details
        and first_op_details["operation"] != "create"
    ):
        log.error(
            f"Unrecoverable: No checkpoint found for '{target_file_path_str}' in {conversation_id}, not starting with 'create'."
        )
        return False
    elif not first_op_details:
        return True  # No ops found relevant
    checkpoint_path = (
        history_root / checkpoint_file_str if checkpoint_file_str else None
    )

    # --- Acquire Lock and Restore Checkpoint ---
    target_lock = None
    try:
        target_lock = acquire_lock(str(target_file_path))
        current_file_path = target_file_path
        file_exists_in_state = False
        current_expected_hash: Optional[str] = None

        if checkpoint_path and checkpoint_path.exists():
            # ... (Restore checkpoint logic) ...
            log.info(f"Restoring checkpoint {checkpoint_path} to {current_file_path}")
            try:
                current_file_path.parent.mkdir(parents=True, exist_ok=True)
                with (
                    open(checkpoint_path, "rb") as f_read,
                    open(current_file_path, "wb") as f_write,
                ):
                    f_write.write(f_read.read())
                file_exists_in_state = True
                current_expected_hash = calculate_hash(str(current_file_path))
                if initial_hash and current_expected_hash != initial_hash:
                    log.warning("Restored checkpoint hash mismatch.")
            except Exception as e:
                raise HistoryError("Checkpoint restore failed") from e
        elif first_op_details and first_op_details["operation"] == "create":
            # ... (Handle create start state logic) ...
            log.info(f"Starting state from 'create' for {current_file_path}.")
            if current_file_path.exists():
                current_file_path.unlink()
            current_expected_hash = None
            file_exists_in_state = False
        else:
            raise HistoryError("Cannot determine starting state.")

        # --- Iterate and Apply Edits ---
        log.info(f"Applying edits for {target_file_path_str} from checkpoint/create...")
        for entry in relevant_entries:
            edit_id = entry["edit_id"]
            op = entry["operation"]
            status = entry["status"]
            hash_before_entry = entry["hash_before"]
            hash_after_entry = entry["hash_after"]
            entry_target_path_str = entry["file_path"]
            entry_source_path_str = entry["source_path"]
            diff_file_rel_path = entry.get("diff_file")
            log.debug(
                f"Processing {edit_id}: Op={op}, Status={status}, Target={entry_target_path_str}"
            )

            # --- Pre-condition Check ---
            if file_exists_in_state:
                if op != "create":
                    actual_current_hash = calculate_hash(str(current_file_path))
                    if actual_current_hash != current_expected_hash:
                        msg = f"External modification detected for '{current_file_path}' before {edit_id}. Expected {current_expected_hash}, found {actual_current_hash}."
                        raise ExternalModificationError(msg)
            elif op not in ["create", "move"]:
                if hash_before_entry is not None:
                    log.warning(
                        f"Inconsistent: File {current_file_path} non-existent, but {edit_id} ({op}) expected hash {hash_before_entry}."
                    )

            # Path consistency check (optional strictness)
            if op != "move" and entry_target_path_str != str(current_file_path):
                if file_exists_in_state:
                    raise HistoryError(f"Path mismatch at {edit_id}")
            elif op == "move" and entry_source_path_str != str(current_file_path):
                if file_exists_in_state:
                    raise HistoryError(f"Move source mismatch at {edit_id}")

            # --- Apply or Skip based on Status ---
            # Corrected: Removed applied_change assignments
            if status in ["pending", "accepted"]:
                log.debug(f"Applying operation {op} for edit {edit_id}")
                if op in ["edit", "replace", "create"]:
                    # ... (Patch application logic - unchanged) ...
                    if not diff_file_rel_path:
                        raise HistoryError(f"Missing diff path for {edit_id}")
                    diff_file = history_root / diff_file_rel_path
                    if not diff_file.exists():
                        raise HistoryError(f"Diff file not found for {edit_id}")
                    try:
                        with open(diff_file, "r", encoding="utf-8") as f_diff:
                            diff_content = f_diff.read()
                    except IOError as e:
                        raise HistoryError(
                            f"Cannot read diff file for {edit_id}"
                        ) from e
                    Path(entry_target_path_str).parent.mkdir(
                        parents=True, exist_ok=True
                    )
                    # Need workspace_root for apply_patch context
                    # Re-calculate it here if needed by apply_patch
                    ws_root_for_patch = history_root.parent.parent
                    if not apply_patch(
                        diff_content,
                        entry_target_path_str,
                        ws_root_for_patch,
                        reverse=False,
                    ):
                        raise HistoryError(f"Patch application failed for {edit_id}")
                    file_exists_in_state = True
                    # applied_change = True # <- REMOVED

                elif op == "delete":
                    # ... (Delete logic - unchanged) ...
                    if Path(entry_target_path_str).exists():
                        Path(entry_target_path_str).unlink()
                    file_exists_in_state = False
                    # applied_change = True # <- REMOVED

                elif op == "move":
                    # ... (Move logic - unchanged) ...
                    source_path = Path(entry_source_path_str)
                    dest_path = Path(entry_target_path_str)
                    if source_path.exists():
                        dest_path.parent.mkdir(parents=True, exist_ok=True)
                        if dest_path.exists():
                            log.warning(f"Overwriting {dest_path} during move replay.")
                            dest_path.unlink()  # Basic file overwrite
                        source_path.rename(dest_path)
                        current_file_path = dest_path
                        file_exists_in_state = True
                        # applied_change = True # <- REMOVED
                    else:
                        log.warning(
                            f"Source {source_path} not found for move {edit_id}. Skipping."
                        )

            else:  # status == 'rejected'
                log.debug(f"Skipping rejected operation {op} for edit {edit_id}")
                if op == "move":
                    current_file_path = Path(entry_target_path_str)
                elif op == "delete":
                    file_exists_in_state = False

            # --- Update Expected Hash for Next Iteration ---
            current_expected_hash = hash_after_entry
            if op == "move":
                current_file_path = Path(entry_target_path_str)

        # --- Final Verification ---
        # ... (Final hash check - unchanged) ...
        final_actual_hash = (
            calculate_hash(str(current_file_path)) if file_exists_in_state else None
        )
        if final_actual_hash != current_expected_hash:
            log.error(
                f"Final state verification failed for {current_file_path}. Expected {current_expected_hash}, actual {final_actual_hash}."
            )
            return False

        log.info(
            f"Successfully re-applied state for file '{target_file_path_str}' in conversation '{conversation_id}'"
        )
        return True

    except (
        HistoryError,
        ExternalModificationError,
        FileNotFoundError,
        TimeoutError,
    ) as e:
        log.error(f"Failed to re-apply state for {target_file_path_str}: {e}")
        return False
    except Exception as e:
        log.exception(
            f"Unexpected error during re-apply for {target_file_path_str}: {e}"
        )
        return False
    finally:
        release_lock(target_lock)


# --- CLI Command Functions ---


def find_workspace_root(start_path: Optional[str] = None) -> Optional[Path]:
    """
    Find the workspace root (directory containing .mcp) by walking up from start_path.
    If start_path is None, uses current directory.
    """
    current = Path(start_path if start_path else os.getcwd()).resolve()
    while current != current.parent:  # Stop at root
        if (current / ".mcp").exists():
            return current
        current = current.parent
    return None


def get_workspace_path(relative_path: str) -> Path:
    """
    Convert a path relative to workspace root to an absolute path.
    Raises HistoryError if workspace root cannot be found.
    """
    workspace_root = find_workspace_root()
    if not workspace_root:
        raise HistoryError("Could not find workspace root (directory containing .mcp)")
    return workspace_root / relative_path


def get_relative_path(absolute_path: Path) -> str:
    """
    Convert an absolute path to a path relative to workspace root.
    Raises HistoryError if workspace root cannot be found.
    """
    workspace_root = find_workspace_root()
    if not workspace_root:
        raise HistoryError("Could not find workspace root (directory containing .mcp)")
    try:
        return str(absolute_path.relative_to(workspace_root))
    except ValueError:
        raise HistoryError(
            f"Path {absolute_path} is not within workspace root {workspace_root}"
        )


def handle_status(args: argparse.Namespace) -> None:
    """Handle the status command."""
    workspace_root = find_workspace_root()
    if not workspace_root:
        print("Error: Could not find workspace root (directory containing .mcp)")
        return

    history_root = workspace_root / HISTORY_DIR_NAME
    if not history_root.exists():
        print("No history found in this workspace.")
        return

    log.info(f"Checking status in: {workspace_root}/")
    print(f"{HISTORY_DIR_NAME}")
    print(
        "EDIT_ID                              TIMESTAMP                  STATUS   OP       CONV_ID      FILE_PATH"
    )
    print("-" * 100)

    # Get all log files
    log_dir = history_root / LOGS_DIR
    if not log_dir.exists():
        print("No history logs found.")
        return

    log_files = sorted(log_dir.glob("*.log"))
    all_entries = []
    for log_file in log_files:
        entries = read_log_file(log_file)
        all_entries.extend(entries)

    # Filter entries based on command line arguments
    if args.conv:
        all_entries = [e for e in all_entries if e["conversation_id"] == args.conv]
    if args.file:
        all_entries = [e for e in all_entries if e["file_path"] == args.file]
    if args.status:
        all_entries = [e for e in all_entries if e["status"] == args.status]

    # Sort entries by timestamp
    all_entries.sort(key=lambda x: x["timestamp"])

    # Display entries
    for entry in all_entries[: args.limit]:
        print(
            f"{entry['edit_id']}  {entry['timestamp']}  {entry['status']:<8} {entry['operation']:<7} {entry['conversation_id']:<10} {entry['file_path']}"
        )


def handle_show(args: argparse.Namespace) -> None:
    """Handle the show command."""
    workspace_root = find_workspace_root()
    if not workspace_root:
        print("Error: Could not find workspace root (directory containing .mcp)")
        return

    history_root = workspace_root / HISTORY_DIR_NAME
    if not history_root.exists():
        print("No history found in this workspace.")
        return

    # Get all log files
    log_dir = history_root / LOGS_DIR
    if not log_dir.exists():
        print("No history logs found.")
        return

    # Find the entry with matching edit_id or conversation_id
    target_id = args.identifier
    found_entry = None
    found_file = None

    for log_file in log_dir.glob("*.log"):
        entries = read_log_file(log_file)
        for entry in entries:
            if entry["edit_id"] == target_id or entry["conversation_id"] == target_id:
                found_entry = entry
                found_file = log_file
                break
        if found_entry:
            break

    if not found_entry:
        print(f"No history entry found with ID: {target_id}")
        return

    # If it's a conversation_id, show all entries in that conversation
    if found_entry["conversation_id"] == target_id:
        entries = read_log_file(found_file)
        conversation_entries = [e for e in entries if e["conversation_id"] == target_id]
        for entry in conversation_entries:
            if entry.get("diff_file"):
                diff_path = history_root / entry["diff_file"]
                if diff_path.exists():
                    print(f"\nDiff for {entry['file_path']}:")
                    print(diff_path.read_text())
                else:
                    print(f"No diff file found for edit {target_id}")
        # Show single entry's diff
        if found_entry.get("diff_file"):
            diff_path = history_root / found_entry["diff_file"]
            if diff_path.exists():
                print(diff_path.read_text())
            else:
                print(f"No diff file found for edit {target_id}")


def handle_accept(args: argparse.Namespace) -> None:
    """Handle the accept command."""
    workspace_root = find_workspace_root()
    if not workspace_root:
        print("Error: Could not find workspace root (directory containing .mcp)")
        return

    history_root = workspace_root / HISTORY_DIR_NAME
    if not history_root.exists():
        print("No history found in this workspace.")
        return

    # Get all log files
    log_dir = history_root / LOGS_DIR
    if not log_dir.exists():
        print("No history logs found.")
        return

    # Find the entry with matching edit_id or conversation_id
    target_id = args.edit_id if args.edit_id else args.conv
    found_entry = None
    found_file = None

    for log_file in log_dir.glob("*.log"):
        entries = read_log_file(log_file)
        for entry in entries:
            if entry["edit_id"] == target_id or entry["conversation_id"] == target_id:
                found_entry = entry
                found_file = log_file
                break
        if found_entry:
            break

    if not found_entry:
        print(f"No history entry found with ID: {target_id}")
        return

    # Update status to accepted
    entries = read_log_file(found_file)
    for entry in entries:
        if entry["edit_id"] == target_id or entry["conversation_id"] == target_id:
            entry["status"] = "accepted"

    write_log_file(found_file, entries)
    print(f"Marked edit(s) as accepted: {target_id}")


def handle_reject(args: argparse.Namespace) -> None:
    """Handle the reject command."""
    workspace_root = find_workspace_root()
    if not workspace_root:
        print("Error: Could not find workspace root (directory containing .mcp)")
        return

    history_root = workspace_root / HISTORY_DIR_NAME
    if not history_root.exists():
        print("No history found in this workspace.")
        return

    # Get all log files
    log_dir = history_root / LOGS_DIR
    if not log_dir.exists():
        print("No history logs found.")
        return

    # Find the entry with matching edit_id or conversation_id
    target_id = args.edit_id if args.edit_id else args.conv
    found_entry = None
    found_file = None

    for log_file in log_dir.glob("*.log"):
        entries = read_log_file(log_file)
        for entry in entries:
            if entry["edit_id"] == target_id or entry["conversation_id"] == target_id:
                found_entry = entry
                found_file = log_file
                break
        if found_entry:
            break

    if not found_entry:
        print(f"No history entry found with ID: {target_id}")
        return

    # Update status to rejected
    entries = read_log_file(found_file)
    for entry in entries:
        if entry["edit_id"] == target_id or entry["conversation_id"] == target_id:
            entry["status"] = "rejected"

    write_log_file(found_file, entries)
    print(f"Marked edit(s) as rejected: {target_id}")


# --- Main Argparse Setup --- (unchanged)
def main():
    parser = argparse.ArgumentParser(
        description="MCP Diff Tool: Review and manage LLM file edits."
    )
    parser.add_argument(
        "-w",
        "--workspace",
        help="Path to the workspace root (containing .mcp directory). Defaults to searching from CWD upwards.",
    )
    subparsers = parser.add_subparsers(
        dest="command", required=True, help="Sub-command help"
    )
    # status
    parser_status = subparsers.add_parser("status", help="Show edit history status.")
    parser_status.add_argument("--conv", help="Filter by conversation ID.")
    parser_status.add_argument("--file", help="Filter by file path.")
    parser_status.add_argument(
        "--status",
        choices=["pending", "accepted", "rejected"],
        help="Filter by status.",
    )
    parser_status.add_argument(
        "-n", "--limit", type=int, default=50, help="Limit entries shown (default: 50)"
    )
    parser_status.set_defaults(func=handle_status)
    # show
    parser_show = subparsers.add_parser(
        "show", help="Show diff for an edit_id or all diffs for a conversation_id."
    )
    parser_show.add_argument(
        "identifier", help="The edit_id or conversation_id to show."
    )
    parser_show.set_defaults(func=handle_show)
    # accept
    parser_accept = subparsers.add_parser("accept", help="Mark edits as accepted.")
    group_accept = parser_accept.add_mutually_exclusive_group(required=True)
    group_accept.add_argument(
        "-e", "--edit-id", help="The specific edit_id to accept."
    )  # Changed to --edit-id for clarity
    group_accept.add_argument(
        "-c", "--conv", help="Accept all pending edits for a conversation_id."
    )
    parser_accept.set_defaults(func=handle_accept)
    # reject
    parser_reject = subparsers.add_parser(
        "reject", help="Mark edits as rejected and revert changes."
    )
    group_reject = parser_reject.add_mutually_exclusive_group(required=True)
    group_reject.add_argument(
        "-e", "--edit-id", help="The specific edit_id to reject."
    )  # Changed to --edit-id
    group_reject.add_argument(
        "-c", "--conv", help="Reject all pending/accepted edits for a conversation_id."
    )
    parser_reject.set_defaults(func=handle_reject)

    # Parse and execute
    args = parser.parse_args()
    # Adjust arg names if using --edit-id
    if (
        hasattr(args, "edit_id") and args.edit_id is None and not hasattr(args, "conv")
    ):  # Handle case where positional was expected but --edit-id used
        if args.command in ["accept", "reject"]:
            parser.error(
                "argument --edit-id: expected one argument when not using --conv"
            )

    # Map --edit-id back if necessary for handler functions (adjust handlers if they expect positional 'edit_id')
    # Current handlers expect args.edit_id and args.conv, so using flags is fine.

    args.func(args)


if __name__ == "__main__":
    main()
