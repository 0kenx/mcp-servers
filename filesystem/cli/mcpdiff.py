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
import fcntl  # For simple file locking on Unix-like systems
import shutil
import time
from pathlib import Path
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional, Tuple, Set

# --- Configuration Constants ---
HISTORY_DIR_NAME = "edit_history"
LOGS_DIR = "logs"
DIFFS_DIR = "diffs"
CHECKPOINTS_DIR = "checkpoints"
LOCK_TIMEOUT = 10  # seconds for file locks

# --- Logging Setup ---
# Initialize logger basic config - level will be set in main()
logging.basicConfig(
    level=logging.WARNING,  # Default level
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
log = logging.getLogger("mcpdiff")

# --- ANSI Color Codes ---
COLOR_RESET = "\033[0m"
COLOR_RED = "\033[91m"
COLOR_GREEN = "\033[92m"
COLOR_YELLOW = "\033[93m"
COLOR_BLUE = "\033[94m"
COLOR_CYAN = "\033[96m"


# --- Custom Exceptions ---
class HistoryError(Exception):
    """Custom exception for history-related errors."""

    pass


class ExternalModificationError(HistoryError):
    """Indicates a file was modified outside the expected history sequence."""

    pass


class AmbiguousIDError(HistoryError):
    """Indicates a partial ID matched multiple entries."""

    pass


# --- Path Normalization and Expansion (from mcp_edit_utils.py) ---
def normalize_path(p: str) -> str:
    """Normalizes a path string."""
    return os.path.normpath(p)


def expand_home(filepath: str) -> str:
    """Expands ~ and ~user constructs in a path."""
    # Simplified version for CLI context, assumes user's home primarily
    if filepath.startswith("~/") or filepath == "~":
        expanded = os.path.join(
            os.path.expanduser("~"), filepath[2:] if filepath.startswith("~/") else ""
        )
        return expanded
    # Add expansion for other users if strictly needed, but often not for CLI tools
    return filepath


# --- Workspace Root Finding ---
def find_workspace_root(start_path: Optional[str] = None) -> Optional[Path]:
    """
    Find the workspace root (directory containing .mcp/edit_history) by walking up from start_path.
    If start_path is None, uses current directory.
    """
    current = Path(start_path if start_path else os.getcwd()).resolve()
    log.debug(f"Starting workspace search from: {current}")
    while True:
        # Look for <workspace>/.mcp/edit_history
        check_dir = current / ".mcp" / HISTORY_DIR_NAME
        if check_dir.is_dir():
            log.debug(f"Found workspace root marker at: {current}")
            return current
        if current.parent == current:  # Stop at filesystem root
            log.debug("Reached filesystem root without finding workspace marker.")
            return None
        current = current.parent
    # This part should not be reachable due to the root check
    return None


def get_workspace_path(relative_path: str, workspace_root: Path) -> Path:
    """
    Convert a path relative to workspace root to an absolute path.
    """
    return (workspace_root / relative_path).resolve()


def get_relative_path(absolute_path: Path, workspace_root: Path) -> str:
    """
    Convert an absolute path to a path relative to workspace root.
    If not relative, returns the original absolute path string.
    """
    try:
        # Ensure absolute_path is actually absolute before making relative
        if not absolute_path.is_absolute():
            # This case might occur if log stores relative paths unexpectedly
            log.debug(
                f"Path '{absolute_path}' provided to get_relative_path is not absolute. Returning as is."
            )
            return str(absolute_path)
        return str(absolute_path.relative_to(workspace_root))
    except ValueError:
        # Log as DEBUG now instead of WARNING
        log.debug(
            f"Path {absolute_path} not relative to workspace {workspace_root}. Using absolute path string."
        )
        return str(absolute_path)


def is_path_within_directory(path: Path, directory: Path) -> bool:
    """
    Check if a path is within a directory (or is the directory itself).
    Both paths must be absolute and resolved.
    """
    try:
        # Resolve any symlinks and normalize paths
        path = path.resolve()
        directory = directory.resolve()

        # Check if path is the directory or is under it
        return str(path).startswith(str(directory))
    except Exception:
        return False


def verify_path_is_safe(path: Path, workspace_root: Path) -> bool:
    """
    Verify that a path is safe to modify:
    - Must be absolute
    - Must be within workspace_root
    - Must not contain symlinks that point outside workspace_root
    """
    try:
        # Convert to absolute path if not already
        abs_path = path if path.is_absolute() else (workspace_root / path).resolve()

        # Check each component for symlinks that might escape
        current = abs_path
        while current != current.parent:  # Stop at root
            if current.is_symlink():
                # If any component is a symlink, verify its target is within workspace
                if not is_path_within_directory(current.resolve(), workspace_root):
                    log.error(
                        f"Security: Symlink '{current}' points outside workspace: {current.resolve()}"
                    )
                    return False
            current = current.parent

        # Final check that resolved path is within workspace
        return is_path_within_directory(abs_path, workspace_root)
    except Exception as e:
        log.error(f"Security: Path verification failed for '{path}': {e}")
        return False


# --- Filesystem Info Helpers (Simplified for CLI) ---
def calculate_hash(file_path: str) -> Optional[str]:
    """Calculates the SHA256 hash of a file's content."""
    try:
        hasher = hashlib.sha256()
        with open(file_path, "rb") as f:
            while chunk := f.read(8192):
                hasher.update(chunk)
        return hasher.hexdigest()
    except FileNotFoundError:
        return None
    except IOError as e:
        log.error(f"Error reading file {file_path} for hashing: {e}")
        return None  # Indicate error or inability to hash


# --- Locking Mechanism (fcntl-based, from original mcpdiff.py) ---
class FileLock:
    """A simple file locking mechanism using fcntl (Unix-like)."""

    def __init__(self, path: str):
        # Use a directory for locks associated with a file/log to avoid locking the file itself
        self.lock_dir = Path(f"{path}.lockdir")
        self.lock_file_path = self.lock_dir / "pid.lock"
        self.lock_file_handle = None
        self.is_locked = False

    def acquire(self, timeout=LOCK_TIMEOUT):
        """Acquire the lock with timeout."""
        start_time = time.time()
        self.lock_dir.mkdir(parents=True, exist_ok=True)  # Ensure lock directory exists

        while True:
            try:
                # Open the lock file within the directory. 'x' mode fails if exists. Use 'w'.
                # Opening with 'w' creates or truncates. We rely on flock for atomicity.
                self.lock_file_handle = open(self.lock_file_path, "w")
                fcntl.flock(
                    self.lock_file_handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB
                )
                # Write PID for debugging purposes (optional)
                self.lock_file_handle.write(str(os.getpid()))
                self.lock_file_handle.flush()
                self.is_locked = True
                log.debug(f"Acquired lock via directory: {self.lock_dir}")
                return  # Success
            except (
                IOError,
                OSError,
            ) as e:  # flock fails with BlockingIOError (subclass of OSError) if locked
                if self.lock_file_handle:
                    self.lock_file_handle.close()  # Close if open failed flock
                    self.lock_file_handle = None

                if time.time() - start_time >= timeout:
                    # Attempt to read PID from lock file if it exists
                    locker_pid = "unknown"
                    try:
                        if self.lock_file_path.exists():
                            locker_pid = self.lock_file_path.read_text().strip()
                    except Exception:
                        pass  # Ignore errors reading PID
                    log.error(
                        f"Timeout acquiring lock {self.lock_dir} after {timeout}s. Locked by PID: {locker_pid}."
                    )
                    raise TimeoutError(
                        f"Could not acquire lock for {self.lock_dir} (locked by PID {locker_pid})"
                    ) from e
                # Wait briefly before retrying
                time.sleep(0.1)
            except Exception as e:  # Catch other potential errors during open/mkdir
                if self.lock_file_handle:
                    self.lock_file_handle.close()
                log.error(f"Unexpected error acquiring lock {self.lock_dir}: {e}")
                raise  # Re-raise unexpected errors

    def release(self):
        """Release the lock and cleanup."""
        if self.is_locked and self.lock_file_handle:
            try:
                fcntl.flock(self.lock_file_handle.fileno(), fcntl.LOCK_UN)
                self.is_locked = False
                log.debug(f"Released lock: {self.lock_dir}")
            except Exception as e:
                log.error(f"Error releasing lock {self.lock_dir}: {e}")
            finally:
                if self.lock_file_handle:
                    self.lock_file_handle.close()
                    self.lock_file_handle = None
                # Clean up the lock file and directory
                try:
                    if self.lock_file_path.exists():
                        self.lock_file_path.unlink()
                        log.debug(f"Removed lock file: {self.lock_file_path}")
                    # Attempt to remove the directory - might fail if another process recreated it
                    try:
                        self.lock_dir.rmdir()
                        log.debug(f"Removed lock directory: {self.lock_dir}")
                    except OSError:
                        log.debug(
                            f"Lock directory {self.lock_dir} not empty or removed by another process."
                        )
                        pass  # Ignore if directory isn't empty or already gone
                except OSError as e:
                    log.warning(f"Could not cleanup lock file/dir {self.lock_dir}: {e}")

    def __enter__(self):
        self.acquire()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.release()


# --- Log File Handling (from mcp_edit_utils.py) ---
def read_log_file(log_file_path: Path) -> List[Dict[str, Any]]:
    """Reads a JSON Lines log file safely."""
    entries = []
    if not log_file_path.is_file():
        return entries
    lock = FileLock(str(log_file_path))  # Use lock for reading consistency
    try:
        with lock:
            with open(log_file_path, "r", encoding="utf-8") as f:
                for i, line in enumerate(f):
                    line = line.strip()
                    if line:
                        try:
                            entries.append(json.loads(line))
                        except json.JSONDecodeError:
                            log.warning(
                                f"Skipping invalid JSON line {i + 1} in {log_file_path}: {line[:100]}..."
                            )
            return entries
    except (IOError, TimeoutError) as e:
        log.error(f"Error reading log file {log_file_path}: {e}")
        raise HistoryError(f"Could not read log file: {log_file_path}") from e


def write_log_file(log_file_path: Path, entries: List[Dict[str, Any]]):
    """Writes a list of entries to a JSON Lines log file atomically."""
    # Sort entries by index before writing to maintain order if modified
    entries.sort(key=lambda x: x.get("tool_call_index", float("inf")))

    temp_path = log_file_path.with_suffix(
        log_file_path.suffix + ".tmp" + str(os.getpid())
    )
    lock = FileLock(str(log_file_path))
    try:
        with lock:  # Acquire lock for the log file itself during write
            log_file_path.parent.mkdir(parents=True, exist_ok=True)
            with open(temp_path, "w", encoding="utf-8") as f:
                for entry in entries:
                    json.dump(entry, f, separators=(",", ":"))
                    f.write("\n")
            # Atomic rename/replace (should work on Unix)
            os.replace(temp_path, log_file_path)
            log.debug(f"Successfully wrote log file: {log_file_path}")
    except (IOError, TimeoutError) as e:
        log.error(f"Error writing log file {log_file_path}: {e}")
        if temp_path.exists():
            try:
                os.remove(temp_path)
            except OSError:
                pass
        raise HistoryError(f"Could not write log file: {log_file_path}") from e
    except Exception as e:
        if temp_path.exists():
            try:
                os.remove(temp_path)
            except OSError:
                pass
        log.exception(f"Unexpected error writing log file {log_file_path}: {e}")
        raise HistoryError(f"Unexpected error writing log file: {log_file_path}") from e


# --- Patch Application (from mcp_edit_utils.py) ---
def apply_patch(
    diff_content: str,
    target_file_rel_path: str,  # Path relative to workspace root
    workspace_root: Path,
    reverse: bool = False,
) -> bool:
    """Applies a diff using the patch command. Runs from workspace root."""
    target_abs_path = workspace_root / target_file_rel_path

    # Security check for target path
    if not verify_path_is_safe(target_abs_path, workspace_root):
        log.error(f"Security: Cannot patch file outside workspace: {target_abs_path}")
        return False

    patch_cmd = shutil.which("patch")
    if not patch_cmd:
        log.error(
            "`patch` command not found. Please install patch (usually in diffutils package)."
        )
        raise HistoryError("`patch` command not found.")

    cmd_args = [patch_cmd, "--no-backup-if-mismatch", "-p1"]
    if reverse:
        cmd_args.append("-R")  # Apply in reverse

    # Important: Provide the target file to patch via standard input as well if possible,
    # or ensure the diff headers `--- a/path` and `+++ b/path` are correct relative to CWD.
    # Running from workspace_root and using -p1 assumes paths in diff are relative to root.

    # Ensure target directory exists before patching
    target_abs_path = workspace_root / target_file_rel_path
    target_abs_path.parent.mkdir(parents=True, exist_ok=True)

    log.debug(
        f"Applying patch {'(Reverse)' if reverse else ''} to '{target_file_rel_path}' within '{workspace_root}'"
    )
    # log.debug(f"Patch command: {' '.join(cmd_args)}") # Debug command
    # log.debug(f"Patch input:\n---\n{diff_content[:500]}...\n---") # Log beginning of diff

    try:
        # Use Popen for better control over stdin/stdout/stderr
        process = subprocess.Popen(
            cmd_args,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=workspace_root,  # Run from workspace root for -p1 to work correctly
            encoding="utf-8",  # Specify encoding
        )
        # Write diff content to stdin and close it
        stdout, stderr = process.communicate(
            input=diff_content, timeout=20
        )  # Increased timeout slightly
        returncode = process.returncode

        if returncode == 0:
            log.info(
                f"Patch {'(Reverse)' if reverse else ''} applied successfully to '{target_file_rel_path}'."
            )
            if stdout:
                log.debug(f"Patch STDOUT:\n{stdout}")
            if stderr:
                log.debug(
                    f"Patch STDERR:\n{stderr}"
                )  # Often patch prints info to stderr even on success
            return True
        # Patch returns 1 if some hunks failed, 2 for serious trouble.
        elif returncode == 1:
            log.warning(
                f"Patch command reported fuzz or failed hunks for '{target_file_rel_path}' {'(Reverse)' if reverse else ''} (RC={returncode})"
            )
            log.warning(f"Patch STDOUT:\n{stdout}")
            log.warning(f"Patch STDERR:\n{stderr}")
            # Consider this a failure for robust replay
            return False
        else:  # returncode >= 2
            log.error(
                f"Patch command failed seriously for '{target_file_rel_path}' {'(Reverse)' if reverse else ''} (RC={returncode})"
            )
            log.error(f"Patch STDOUT:\n{stdout}")
            log.error(f"Patch STDERR:\n{stderr}")  # Crucial for diagnosing failures
            return False
    except subprocess.TimeoutExpired:
        log.error(
            f"Patch command timed out for '{target_file_rel_path}'. Process killed."
        )
        process.kill()
        try:
            # Try to get output after kill, might be empty
            stdout, stderr = process.communicate()
            log.error(f"Patch STDOUT (before timeout):\n{stdout}")
            log.error(f"Patch STDERR (before timeout):\n{stderr}")
        except Exception:
            log.error("Failed to get output after patch timeout.")
        return False
    except FileNotFoundError:  # Should be caught by shutil.which, but as fallback
        log.error("`patch` command not found during execution.")
        raise HistoryError("`patch` command not found.")
    except Exception as e:
        log.exception(
            f"Unexpected error applying patch to '{target_file_rel_path}': {e}"
        )
        return False


# --- Core Re-apply Logic (New/Enhanced) ---


def reapply_conversation_state(
    conversation_id: str, history_root: Path, workspace_root: Path
) -> bool:
    """
    Reconstructs the state of all files affected by a conversation
    by re-applying accepted/pending edits from their checkpoints.
    This is typically called after one or more edits are marked 'rejected'.
    """
    if not is_path_within_directory(history_root, workspace_root):
        log.error(
            f"Security: History directory '{history_root}' must be within workspace '{workspace_root}'"
        )
        return False

    log.info(
        f"Re-applying state for conversation '{conversation_id}' in workspace '{workspace_root}'"
    )
    log_file_path = history_root / LOGS_DIR / f"{conversation_id}.log"

    # --- Load and Group Log Entries by File History ---
    try:
        all_conv_entries = read_log_file(log_file_path)
        if not all_conv_entries:
            log.warning(
                f"No log entries found for conversation {conversation_id}. Nothing to re-apply."
            )
            return True  # No error, just nothing to do
    except HistoryError as e:
        log.error(f"Failed to read log file for re-apply: {e}")
        return False

    # Group entries by the initial file path they affected in this conversation
    file_histories: Dict[str, List[Dict[str, Any]]] = {}
    final_paths: Dict[str, str] = {}
    checkpointed_paths: Set[str] = set()

    # Sort all entries first to process in order
    all_conv_entries.sort(key=lambda x: x.get("tool_call_index", 0))

    path_trace: Dict[
        str, str
    ] = {}  # Tracks current_abs_path -> original_abs_path for move tracing

    for entry in all_conv_entries:
        op = entry.get("operation")
        # Consistently use resolved absolute paths internally for tracking
        try:
            target_abs_str = str(Path(entry["file_path"]).resolve())
        except Exception as e:
            log.error(
                f"Invalid target path '{entry['file_path']}' in edit {entry['edit_id']}: {e}"
            )
            continue  # Skip malformed entry

        source_abs_str = None
        if entry.get("source_path"):
            try:
                source_abs_str = str(Path(entry["source_path"]).resolve())
            except Exception as e:
                log.error(
                    f"Invalid source path '{entry['source_path']}' in edit {entry['edit_id']}: {e}"
                )
                # Allow continuing if target is valid, but log error
                pass  # Continue processing target if possible

        original_path_abs = None

        if op == "move":
            if source_abs_str is None:
                log.error(
                    f"Invalid 'move' entry {entry['edit_id']}: missing or invalid source_path."
                )
                continue  # Skip invalid entry
            # Find the original path this source file corresponds to
            original_path_abs = path_trace.get(source_abs_str, source_abs_str)
            # Update trace: the new target now points back to the same original path
            path_trace[target_abs_str] = original_path_abs
            # Remove the old source from the trace if it exists
            if source_abs_str in path_trace:
                del path_trace[source_abs_str]
            final_paths[original_path_abs] = target_abs_str  # Update final path mapping
        else:
            # Find the original path this target file corresponds to
            original_path_abs = path_trace.get(target_abs_str, target_abs_str)
            # Ensure final_paths is initialized/updated
            final_paths[original_path_abs] = target_abs_str

        # Add the entry to the history for its original path
        if original_path_abs not in file_histories:
            file_histories[original_path_abs] = []
        # Store entry with resolved paths for easier use later
        entry["_resolved_target_abs"] = target_abs_str
        entry["_resolved_source_abs"] = source_abs_str
        file_histories[original_path_abs].append(entry)

        # Record if a checkpoint was made (using original path as key)
        if entry.get("checkpoint_file"):
            checkpointed_paths.add(original_path_abs)

    # --- Process Each File History ---
    overall_success = True
    processed_final_paths = (
        set()
    )  # Avoid processing same final file path multiple times

    # Iterate through the *original* paths found
    for original_path_abs_str, edits in file_histories.items():
        # Determine the FINAL absolute path for this original file after all moves in this conv
        final_target_abs_str = final_paths.get(
            original_path_abs_str, original_path_abs_str
        )
        final_target_abs = Path(final_target_abs_str)

        # Security check for target path
        if not verify_path_is_safe(final_target_abs, workspace_root):
            log.error(
                f"Security: Cannot modify file outside workspace: {final_target_abs}"
            )
            overall_success = False
            continue

        # Get relative path for logging/display purposes
        try:
            final_target_rel = get_relative_path(final_target_abs, workspace_root)
            original_path_rel = get_relative_path(
                Path(original_path_abs_str), workspace_root
            )
        except Exception:
            final_target_rel = final_target_abs_str  # Fallback
            original_path_rel = original_path_abs_str  # Fallback

        log.info(
            f"Processing history for original path '{original_path_rel}' (final: '{final_target_rel}')"
        )

        if final_target_abs_str in processed_final_paths:
            log.debug(f"Skipping already processed final path: {final_target_rel}")
            continue
        processed_final_paths.add(final_target_abs_str)

        # --- Find Checkpoint ---
        first_relevant_edit = edits[0]
        checkpoint_rel_path_str = first_relevant_edit.get("checkpoint_file")
        initial_hash_from_log = first_relevant_edit.get(
            "hash_before"
        )  # Hash when checkpoint taken

        # Add special handling for rejected 'create' operations
        first_op_is_rejected_create = (
            first_relevant_edit["operation"] == "create"
            and first_relevant_edit.get("status") == "rejected"
            and not original_path_abs_str in checkpointed_paths  # Add this check
        )

        # Determine the absolute path *at the time the checkpoint was relevant* (start of sequence)
        # This is the source of a move if the first op is move, otherwise the target.
        checkpoint_origin_path_abs_str = (
            first_relevant_edit.get("_resolved_source_abs")
            if first_relevant_edit["operation"] == "move"
            else first_relevant_edit.get("_resolved_target_abs")
        )

        if not checkpoint_origin_path_abs_str:
            log.error(
                f"Could not determine checkpoint origin path for {original_path_rel} in {conversation_id}"
            )
            overall_success = False
            continue  # Cannot proceed without knowing where to restore/check

        checkpoint_path: Optional[Path] = None
        if checkpoint_rel_path_str:
            checkpoint_path = history_root / checkpoint_rel_path_str

        # Check if checkpoint is required but missing
        checkpoint_available = checkpoint_path and checkpoint_path.exists()
        if not checkpoint_available:
            # If this is a rejected create operation, we don't need a checkpoint
            if first_op_is_rejected_create:
                log.info(
                    f"No checkpoint needed for rejected 'create' operation on '{original_path_rel}'"
                )
            # If a checkpoint was logged for the original path but isn't found now
            elif original_path_abs_str in checkpointed_paths:
                log.error(
                    f"Checkpoint file '{checkpoint_rel_path_str}' not found for '{original_path_rel}' in conv '{conversation_id}', but history indicates one was created."
                )
                overall_success = False
                continue
            # If no checkpoint was ever logged, AND the first operation isn't 'create'
            elif first_relevant_edit["operation"] != "create":
                log.warning(
                    f"No checkpoint found or expected for non-'create' start of '{original_path_rel}' in conv '{conversation_id}'. Will proceed assuming file existed or state is recoverable from first hash."
                )

        # --- Acquire Lock and Restore Checkpoint ---
        target_lock = None
        current_file_path_abs = Path(final_target_abs_str)  # Use Path object
        try:
            # Lock the *final* expected path of the file for this conversation
            log.debug(f"Acquiring lock for final path: {final_target_abs_str}")
            target_lock = FileLock(
                str(final_target_abs)
            )  # Lock based on final path str
            target_lock.acquire()
            log.debug(f"Lock acquired for {final_target_abs_str}")

            current_expected_hash: Optional[str] = None
            file_exists_in_state: bool = False

            # Special handling for rejected create operations
            if first_op_is_rejected_create:
                log.info(
                    f"Handling rejected 'create' operation for '{original_path_rel}' - ensuring file is removed"
                )
                if current_file_path_abs.exists():
                    try:
                        if (
                            current_file_path_abs.is_dir()
                            and not current_file_path_abs.is_symlink()
                        ):
                            shutil.rmtree(current_file_path_abs)
                        else:
                            current_file_path_abs.unlink()
                        log.info(
                            f"Removed file '{current_file_path_abs}' for rejected create operation"
                        )
                    except OSError as e:
                        log.error(
                            f"Failed to remove file for rejected create operation: {e}"
                        )
                        raise HistoryError(
                            "Failed to remove file for rejected create"
                        ) from e
                file_exists_in_state = False
                current_expected_hash = None
                current_file_path_abs = Path(checkpoint_origin_path_abs_str)
            # Regular checkpoint restoration for other cases
            elif checkpoint_available:
                log.info(
                    f"Restoring checkpoint '{checkpoint_path.name}' to '{get_relative_path(Path(checkpoint_origin_path_abs_str), workspace_root)}'"
                )
                try:
                    # Convert string to Path
                    checkpoint_origin_path = Path(checkpoint_origin_path_abs_str)
                    checkpoint_origin_path.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(checkpoint_path, checkpoint_origin_path)
                    current_file_path_abs = (
                        checkpoint_origin_path  # File now exists at the origin path
                    )
                    file_exists_in_state = True
                    current_expected_hash = calculate_hash(str(checkpoint_origin_path))
                    # Verify checkpoint hash if available in log
                    if (
                        initial_hash_from_log
                        and current_expected_hash != initial_hash_from_log
                    ):
                        log.warning(
                            f"Restored checkpoint hash mismatch for '{checkpoint_origin_path}'. Expected {initial_hash_from_log[:8]}, got {current_expected_hash[:8]}. Overriding expected hash."
                        )
                        current_expected_hash = (
                            initial_hash_from_log  # Trust the log's record for sequence
                        )
                    elif not initial_hash_from_log:
                        log.warning(
                            f"No initial hash recorded alongside checkpoint '{checkpoint_path.name}'. Cannot verify integrity."
                        )

                except Exception as e:
                    log.exception(
                        f"Checkpoint restore failed for {checkpoint_path} to {checkpoint_origin_path}: {e}"
                    )
                    raise HistoryError(
                        f"Checkpoint restore failed for {original_path_rel}"
                    ) from e

            elif first_relevant_edit["operation"] == "create":
                # The first operation creates the file, state *before* it is non-existent.
                # Ensure the file *at the path expected by the create op* does not exist.
                create_op_target_abs = Path(first_relevant_edit["_resolved_target_abs"])
                log.info(
                    f"Initializing state from 'create' for '{get_relative_path(create_op_target_abs, workspace_root)}'. Ensuring file is removed."
                )
                if (
                    create_op_target_abs.is_symlink()
                ):  # Handle potential symlinks created outside
                    create_op_target_abs.unlink()
                elif create_op_target_abs.exists():
                    log.warning(
                        f"File '{create_op_target_abs}' existed before 'create' op replay. Deleting."
                    )
                    try:
                        if create_op_target_abs.is_dir():
                            shutil.rmtree(create_op_target_abs)
                        else:
                            create_op_target_abs.unlink()
                    except OSError as e:
                        log.error(
                            f"Failed to delete existing file/dir before create replay: {e}"
                        )
                        raise HistoryError("Failed to reset state for create")
                current_file_path_abs = (
                    create_op_target_abs  # File path expected by the first (create) op
                )
                current_expected_hash = None  # No hash for non-existent file
                file_exists_in_state = False
            else:
                # No checkpoint, not a create. Assume file exists at the path expected by the first op.
                current_file_path_abs = checkpoint_origin_path_abs_str
                if not current_file_path_abs.exists():
                    log.error(
                        f"File '{current_file_path_abs}' expected to exist (no checkpoint, not create) but not found."
                    )
                    raise HistoryError(
                        f"Missing pre-existing file for {original_path_rel}"
                    )
                log.info(
                    f"Starting state from existing file '{get_relative_path(current_file_path_abs, workspace_root)}' (no checkpoint, not create)."
                )
                file_exists_in_state = True
                current_expected_hash = calculate_hash(str(current_file_path_abs))
                # Verify against first op's hash_before
                if (
                    initial_hash_from_log
                    and current_expected_hash != initial_hash_from_log
                ):
                    log.error(
                        f"External modification detected for '{current_file_path_abs}' before first recorded op. Expected {initial_hash_from_log[:8]}, found {current_expected_hash[:8]}."
                    )
                    raise ExternalModificationError(
                        f"External modification detected for {original_path_rel} before conversation start."
                    )
                elif not initial_hash_from_log:
                    log.warning(
                        f"No hash_before recorded for first operation on existing file '{current_file_path_abs}'. Cannot verify initial state."
                    )

            # --- Iterate and Apply/Skip Edits ---
            log.info(f"Applying/Skipping edits for '{original_path_rel}'...")
            for entry_index, entry in enumerate(edits):
                edit_id = entry["edit_id"]
                op = entry["operation"]
                status = entry[
                    "status"
                ]  # This reflects the LATEST status after user actions
                hash_before_entry = entry["hash_before"]
                hash_after_entry = entry["hash_after"]
                # Get resolved paths stored earlier
                entry_target_abs = Path(entry["_resolved_target_abs"])
                entry_target_rel = get_relative_path(entry_target_abs, workspace_root)
                entry_source_abs = (
                    Path(entry["_resolved_source_abs"])
                    if entry["_resolved_source_abs"]
                    else None
                )
                entry_source_rel = (
                    get_relative_path(entry_source_abs, workspace_root)
                    if entry_source_abs
                    else None
                )
                diff_file_rel_path = entry.get("diff_file")  # Relative to history_root

                log.debug(
                    f"  Processing {edit_id[-8:]} (Idx:{entry.get('tool_call_index')}) Op={op}, Status={status}, Target='{entry_target_rel}', Exists={file_exists_in_state}, ExpectedHash={current_expected_hash[:8] if current_expected_hash else 'None'}"
                )

                # --- Pre-condition Check (Hash Verification) ---
                actual_current_hash = (
                    calculate_hash(str(current_file_path_abs))
                    if file_exists_in_state and current_file_path_abs.is_file()
                    else None
                )
                if actual_current_hash != current_expected_hash:
                    # Allow None == None (e.g. start of create)
                    # Allow if hash_before_entry is None (create op, hash comparison not possible)
                    if (
                        not (
                            actual_current_hash is None
                            and current_expected_hash is None
                        )
                        and hash_before_entry is not None
                    ):
                        msg = (
                            f"External modification detected for '{get_relative_path(current_file_path_abs, workspace_root)}' "
                            f"before applying edit {edit_id[-8:]} (Op: {op}). "
                            f"Expected hash: {current_expected_hash[:8] if current_expected_hash else 'None'}, "
                            f"Found hash: {actual_current_hash[:8] if actual_current_hash else 'None'}."
                        )
                        log.error(msg)
                        raise ExternalModificationError(msg)
                    else:
                        log.debug(
                            "  Hash check skipped (Create operation or both hashes are None)"
                        )

                # --- Path Consistency Check --- (Ensure the operation targets the file we're tracking)
                if op == "move":
                    if not entry_source_abs:
                        msg = f"Internal error: Move op {edit_id[-8:]} missing resolved source path."
                        log.error(msg)
                        raise HistoryError(msg)
                    if entry_source_abs != current_file_path_abs:
                        msg = f"Path mismatch error during move {edit_id[-8:]}. Expected source '{current_file_path_abs}', log has '{entry_source_abs}'."
                        log.error(msg)
                        raise HistoryError(msg)
                # For non-move ops, the target path should match the currently tracked path *unless* the file currently doesn't exist (e.g., after a delete or before create)
                elif entry_target_abs != current_file_path_abs:
                    if file_exists_in_state:  # If file exists, paths must match
                        msg = f"Path mismatch error during {op} {edit_id[-8:]}. Expected target '{current_file_path_abs}', log has '{entry_target_abs}'."
                        log.error(msg)
                        raise HistoryError(msg)
                    elif (
                        op != "create"
                    ):  # If file doesn't exist, only allow 'create' to mismatch
                        msg = f"Path mismatch error during {op} {edit_id[-8:]}. File doesn't exist at '{current_file_path_abs}', but op targets '{entry_target_abs}'."
                        log.error(msg)
                        raise HistoryError(msg)

                # --- Apply or Skip based on Status ---
                applied_change_to_disk = False
                if status in ["pending", "accepted"]:
                    log.debug(f"    Applying {op} for edit {edit_id[-8:]}...")
                    if op in ["edit", "replace", "create"]:
                        if not diff_file_rel_path:
                            raise HistoryError(
                                f"Missing diff path for {op} edit {edit_id[-8:]}"
                            )
                        diff_file_abs = history_root / diff_file_rel_path
                        if not diff_file_abs.is_file():  # Check if it's a file
                            raise HistoryError(
                                f"Diff artifact '{diff_file_abs}' not found or not a file for edit {edit_id[-8:]}"
                            )
                        try:
                            diff_content = diff_file_abs.read_text(encoding="utf-8")
                        except IOError as e:
                            raise HistoryError(
                                f"Cannot read diff file for {edit_id[-8:]}: {e}"
                            ) from e

                        # Ensure parent dir exists for the target
                        entry_target_abs.parent.mkdir(parents=True, exist_ok=True)
                        # Apply patch using relative path from workspace root
                        if not apply_patch(
                            diff_content,
                            entry_target_rel,
                            workspace_root,
                            reverse=False,
                        ):
                            log.error(
                                f"Patch application failed for {edit_id[-8:]}. Aborting replay for this file."
                            )
                            raise HistoryError(
                                f"Patch application failed for {edit_id[-8:]}"
                            )
                        # After successful patch: file exists, path is target path
                        file_exists_in_state = True
                        current_file_path_abs = entry_target_abs
                        applied_change_to_disk = True
                        log.debug(f"    Applied patch successfully.")

                    elif op == "delete":
                        if file_exists_in_state:
                            try:
                                if current_file_path_abs.is_symlink():
                                    current_file_path_abs.unlink()  # Unlink symlink
                                    log.debug(
                                        f"    Unlinked symlink '{current_file_path_abs}'"
                                    )
                                elif current_file_path_abs.is_file():
                                    current_file_path_abs.unlink()
                                    log.debug(
                                        f"    Deleted file '{current_file_path_abs}'"
                                    )
                                elif current_file_path_abs.is_dir():
                                    shutil.rmtree(current_file_path_abs)
                                    log.debug(
                                        f"    Deleted directory '{current_file_path_abs}'"
                                    )
                                else:  # Path exists but is not file/dir/symlink?
                                    log.warning(
                                        f"    Path '{current_file_path_abs}' exists but is not file/dir/symlink. Cannot delete."
                                    )
                                    raise HistoryError(
                                        f"Cannot delete unknown file type at {current_file_path_abs}"
                                    )

                                applied_change_to_disk = True
                            except OSError as e:
                                log.error(
                                    f"Failed to delete path '{current_file_path_abs}' for {edit_id[-8:]}: {e}"
                                )
                                raise HistoryError(
                                    f"Failed to delete file/dir for {edit_id[-8:]}"
                                ) from e
                        else:
                            log.warning(
                                f"    Attempted to delete non-existent path '{current_file_path_abs}' for {edit_id[-8:]}. Skipping delete action."
                            )
                        # After delete: file doesn't exist, path remains the target path (conceptually)
                        file_exists_in_state = False
                        current_file_path_abs = entry_target_abs  # Path still represents the target location
                        # applied_change_to_disk = True # Set above if actual delete happened

                    elif op == "move":
                        source_path_abs = entry_source_abs
                        dest_path_abs = entry_target_abs
                        if not source_path_abs:  # Should have been caught earlier
                            raise HistoryError(
                                f"Move operation {edit_id[-8:]} missing source path."
                            )

                        # Check if source exists *according to our state*
                        if file_exists_in_state:
                            # Double check if source exists on disk *now*
                            if (
                                source_path_abs.exists()
                            ):  # or source_path_abs.is_symlink(): # Check links too
                                try:
                                    dest_path_abs.parent.mkdir(
                                        parents=True, exist_ok=True
                                    )
                                    # Check if destination exists - overwrite cautiously
                                    if dest_path_abs.exists():
                                        log.warning(
                                            f"    Destination '{dest_path_abs}' exists. Overwriting during move replay for {edit_id[-8:]}."
                                        )
                                        if (
                                            dest_path_abs.is_dir()
                                            and not dest_path_abs.is_symlink()
                                        ):
                                            shutil.rmtree(dest_path_abs)
                                        else:
                                            dest_path_abs.unlink()  # Remove file or symlink
                                    source_path_abs.rename(dest_path_abs)
                                    log.debug(
                                        f"    Moved '{source_path_abs}' to '{dest_path_abs}'"
                                    )
                                    # After move: file exists, path is the destination path
                                    file_exists_in_state = True
                                    current_file_path_abs = dest_path_abs
                                    applied_change_to_disk = True
                                except OSError as e:
                                    log.error(
                                        f"Failed to move from '{source_path_abs}' to '{dest_path_abs}' for {edit_id[-8:]}: {e}"
                                    )
                                    raise HistoryError(
                                        f"Failed move operation for {edit_id[-8:]}"
                                    ) from e
                            else:  # File should exist based on state, but doesn't on disk now
                                log.warning(
                                    f"    Source path '{source_path_abs}' not found on disk for move {edit_id[-8:]}, though state indicated existence. Skipping move action."
                                )
                                # State becomes non-existent, path becomes the target conceptually
                                file_exists_in_state = False
                                current_file_path_abs = dest_path_abs
                        else:  # File does not exist according to state
                            log.warning(
                                f"    Attempted to move non-existent file state for source '{source_path_abs}' for {edit_id[-8:]}. Skipping move action."
                            )
                            # State remains non-existent, path becomes the target conceptually
                            file_exists_in_state = False
                            current_file_path_abs = dest_path_abs

                else:  # status == 'rejected'
                    log.debug(f"    Skipping rejected {op} for edit {edit_id[-8:]}")
                    # Update logical path/state based on skipping the operation, but BEFORE hash update
                    if op == "move":
                        current_file_path_abs = entry_target_abs
                        # file_exists_in_state reflects source state carried over
                    elif op == "delete":
                        # Logically, the file is now gone for subsequent checks
                        file_exists_in_state = False
                        current_file_path_abs = (
                            entry_target_abs  # Path still represents the deleted target
                        )
                    elif op == "create":
                        # Logically, the file now exists at the target path
                        file_exists_in_state = True
                        current_file_path_abs = entry_target_abs
                    # For edit/replace, path and existence don't change logically if skipped

                # --- Update Expected Hash for Next Iteration ---
                # This uses the hash recorded *in the log* for this operation,
                # representing the state *after* this operation *should* have completed (or been skipped).
                current_expected_hash = hash_after_entry
                log.debug(
                    f"    Intermediate state after {edit_id[-8:]}: Exists={file_exists_in_state}, Path='{get_relative_path(current_file_path_abs, workspace_root)}', NextExpectedHash={current_expected_hash[:8] if current_expected_hash else 'None'}"
                )
                # --- Adjust state specifically for REJECTED operations AFTER initial update ---
                # This ensures the final file_exists_in_state and expected hash reflect the state *as if* the operation never happened.
                if status == "rejected":
                    if op == "delete":
                        # If delete was rejected, file still exists. Expected hash is hash *before* delete.
                        file_exists_in_state = True
                        current_expected_hash = hash_before_entry
                    elif op == "create":
                        # If create was rejected, file doesn't exist. Expected hash is None.
                        file_exists_in_state = False
                        current_expected_hash = None
                    elif op in ["edit", "replace"]:
                        # If edit was rejected, expected hash is hash *before* edit. Existence unchanged.
                        current_expected_hash = hash_before_entry
                    elif op == "move":
                        # If move was rejected, file stays at source. Expected hash is hash *before* move.
                        file_exists_in_state = True  # Assuming it existed at source to begin with for the move op
                        current_file_path_abs = (
                            entry_source_abs  # Path reverts to source
                        )
                        current_expected_hash = hash_before_entry
                    log.debug(
                        f"    *Corrected* state after REJECTED {op}: Exists={file_exists_in_state}, Path='{get_relative_path(current_file_path_abs, workspace_root)}', NextExpectedHash={current_expected_hash[:8] if current_expected_hash else 'None'}"
                    )

            # --- End of Edit Loop ---
            # --- Final Verification for this file history ---
            log.info(
                f"Verifying final state for '{get_relative_path(current_file_path_abs, workspace_root)}'..."
            )
            # Enforce final existence state *before* hash check
            if not file_exists_in_state and current_file_path_abs.exists():
                log.info(
                    f"Final state for '{get_relative_path(current_file_path_abs, workspace_root)}' should be non-existent. Deleting actual file/dir."
                )
                try:
                    if (
                        current_file_path_abs.is_dir()
                        and not current_file_path_abs.is_symlink()
                    ):
                        shutil.rmtree(current_file_path_abs)
                    else:
                        current_file_path_abs.unlink()  # Handles files and symlinks
                except OSError as e:
                    log.error(
                        f"Failed to delete '{current_file_path_abs}' to match final non-existent state: {e}"
                    )
                    overall_success = False  # Mark failure if cleanup fails

            final_actual_hash = (
                calculate_hash(str(current_file_path_abs))
                if file_exists_in_state and current_file_path_abs.is_file()
                else None
            )
            if final_actual_hash != current_expected_hash:
                # Allow None == None (e.g. final state should be deleted)
                if not (final_actual_hash is None and current_expected_hash is None):
                    log.error(
                        f"Final state verification FAILED for '{get_relative_path(current_file_path_abs, workspace_root)}'. "
                        f"Expected hash: {current_expected_hash[:8] if current_expected_hash else 'None'}, "
                        f"Actual hash: {final_actual_hash[:8] if final_actual_hash else 'None'}."
                    )
                    log.error(
                        "The file's final state does not match the expected state after replaying the history."
                    )
                    overall_success = False
                else:
                    log.info(
                        f"Final state verified successfully (both None) for '{get_relative_path(current_file_path_abs, workspace_root)}'."
                    )
            else:
                log.info(
                    f"Final state verified successfully for '{get_relative_path(current_file_path_abs, workspace_root)}'."
                )

        except (
            HistoryError,
            ExternalModificationError,
            FileNotFoundError,
            TimeoutError,
        ) as e:
            log.error(
                f"Failed to re-apply state for original path '{original_path_rel}' (final: '{final_target_rel}'): {e}"
            )
            overall_success = False
            # Continue to next file history if possible
        except Exception as e:
            log.exception(
                f"Unexpected error during re-apply for '{original_path_rel}' (final: '{final_target_rel}'): {e}"
            )
            overall_success = False
            # Continue to next file history if possible
        finally:
            if target_lock:
                target_lock.release()
                log.debug(f"Lock released for {final_target_abs_str}")

    if overall_success:
        log.info(
            f"Successfully finished re-applying state for conversation '{conversation_id}'."
        )
    else:
        log.error(
            f"Finished re-applying state for conversation '{conversation_id}' with one or more errors."
        )

    return overall_success


# --- Helper to find log entries by ID prefix ---


def find_log_entries_by_id(
    identifier: str,
    history_root: Path,
    id_type: str = "edit_id",  # or "conversation_id"
) -> List[Tuple[Path, Dict[str, Any]]]:
    """Find log entries where edit_id or conversation_id starts with the identifier."""
    if not identifier:  # Handle empty identifier case
        return []
    matches = []
    log_dir = history_root / LOGS_DIR
    if not log_dir.is_dir():
        return []

    for log_file in log_dir.glob("*.log"):
        try:
            # Use read_log_file which handles locking
            entries = read_log_file(log_file)
            for entry in entries:
                entry_id_value = entry.get(id_type)
                if (
                    entry_id_value
                    and isinstance(entry_id_value, str)
                    and entry_id_value.startswith(identifier)
                ):
                    matches.append((log_file, entry))
        except HistoryError as e:
            log.warning(f"Could not read or parse log file {log_file}: {e}, skipping.")
            continue
        except Exception as e:
            log.exception(
                f"Unexpected error processing log file {log_file}: {e}, skipping."
            )
            continue

    return matches


# --- CLI Command Functions ---


def handle_status(
    args: argparse.Namespace, workspace_root: Path, history_root: Path
) -> None:
    """Handle the status command."""
    log.info(f"Checking status in: {workspace_root}")
    # Use get_relative_path for display, handle potential errors
    try:
        history_display_path = get_relative_path(history_root, workspace_root)
    except Exception:
        history_display_path = str(history_root)  # Fallback
    print(f"History location: {history_display_path}")

    log_dir = history_root / LOGS_DIR
    if not log_dir.is_dir():
        print("No history logs found.")
        return

    all_entries_with_file = []
    log_files = sorted(
        log_dir.glob("*.log"), key=os.path.getmtime, reverse=True
    )  # Sort by mod time

    for log_file in log_files:
        try:
            entries = read_log_file(log_file)  # Uses locking now
            for entry in entries:
                all_entries_with_file.append((log_file, entry))
        except HistoryError as e:
            print(
                f"{COLOR_YELLOW}Warning: Could not read log file {log_file.name}: {e}{COLOR_RESET}",
                file=sys.stderr,
            )
            continue
        except Exception as e:
            print(
                f"{COLOR_RED}Error processing log file {log_file.name}: {e}{COLOR_RESET}",
                file=sys.stderr,
            )
            continue

    # Filter entries
    filtered_entries = []
    target_conv_prefix = args.conv if args.conv else None
    target_file_rel = args.file  # Assumes user provides relative path or pattern?
    target_status = args.status if args.status else None

    for log_file, entry in all_entries_with_file:
        conv_match = not target_conv_prefix or entry.get(
            "conversation_id", ""
        ).startswith(target_conv_prefix)

        # Get relative path for filtering/display
        try:
            # Resolve path before making relative
            entry_file_abs = Path(entry.get("file_path", "")).resolve()
            entry_file_rel = get_relative_path(entry_file_abs, workspace_root)
        except Exception:  # Catch potential path errors during resolve/relative
            entry_file_rel = entry.get("file_path", "INVALID_PATH")  # Fallback

        # Use simple string matching for file filter for now
        file_match = not target_file_rel or target_file_rel in entry_file_rel
        status_match = not target_status or entry.get("status") == target_status

        if conv_match and file_match and status_match:
            filtered_entries.append(entry)

    # Sort entries by timestamp (descending by default for status)
    filtered_entries.sort(key=lambda x: x.get("timestamp", "0"), reverse=False)

    # Display entries
    count = 0
    if filtered_entries:
        # Header
        print("-" * 110)
        print(
            f"{COLOR_CYAN}{'EDIT_ID':<12} {'TIMESTAMP':<22} {'STATUS':<8} {'OP':<7} {'CONV_ID':<12} {'FILE_PATH'}{COLOR_RESET}"
        )
        print("-" * 110)
        # Data Rows
        for entry in filtered_entries:
            if count >= args.limit:
                print(f"... (limited to {args.limit} entries)")
                break
            # Recalculate relative path safely for display here
            try:
                file_rel_display = get_relative_path(
                    Path(entry.get("file_path", "?")).resolve(), workspace_root
                )
            except Exception:
                file_rel_display = entry.get("file_path", "?")  # Fallback

            # Color-code the status
            status = entry.get("status", "?")
            if status == "pending":
                status_color = COLOR_YELLOW
            elif status == "accepted":
                status_color = COLOR_GREEN
            elif status == "rejected":
                status_color = COLOR_RED
            else:
                status_color = COLOR_RESET

            # Color-code the operation
            op = entry.get("operation", "?")
            if op in ["create", "edit", "replace"]:
                op_color = COLOR_GREEN
            elif op == "delete":
                op_color = COLOR_RED
            elif op == "move":
                op_color = COLOR_BLUE
            else:
                op_color = COLOR_RESET

            print(
                f"{COLOR_CYAN}{entry.get('edit_id', '?')[:10]:<12}{COLOR_RESET} "  # Edit ID in cyan
                f"{entry.get('timestamp', '?'):<22} "  # Timestamp uncolored
                f"{status_color}{status:<8}{COLOR_RESET} "  # Status with dynamic color
                f"{op_color}{op:<7}{COLOR_RESET} "  # Operation with dynamic color
                f"{COLOR_CYAN}{entry.get('conversation_id', '?')[:10]:<12}{COLOR_RESET} "  # Conv ID in cyan
                f"{file_rel_display}"  # File path uncolored
            )
            count += 1
        print("-" * 110)
    else:
        print(f"{COLOR_YELLOW}No matching history entries found.{COLOR_RESET}")


def print_diff_with_color(diff_content: str):
    """Prints unified diff content with basic ANSI colors."""
    lines = diff_content.splitlines()
    for i, line in enumerate(lines):
        if line.startswith("+") and not line.startswith("+++"):
            print(f"{COLOR_GREEN}{line}{COLOR_RESET}")
        elif line.startswith("-") and not line.startswith("---"):
            print(f"{COLOR_RED}{line}{COLOR_RESET}")
        elif line.startswith("@@"):
            print(f"{COLOR_CYAN}{line}{COLOR_RESET}")
        # Print header lines differently?
        elif i < 2 and (line.startswith("---") or line.startswith("+++")):
            print(f"{COLOR_YELLOW}{line}{COLOR_RESET}")
        else:
            print(line)


def handle_show(
    args: argparse.Namespace, workspace_root: Path, history_root: Path
) -> None:
    """Handle the show command."""
    identifier = args.identifier
    log.debug(f"Showing history for identifier prefix: {identifier}")

    # Try finding by edit ID first
    edit_matches = find_log_entries_by_id(identifier, history_root, "edit_id")

    # --- Handle Edit ID Show ---
    if len(edit_matches) == 1:
        log_file, entry = edit_matches[0]
        print(f"Showing diff for Edit ID: {entry['edit_id']}")
        print(f"Conversation ID: {entry['conversation_id']}")
        try:
            file_rel_display = get_relative_path(
                Path(entry["file_path"]).resolve(), workspace_root
            )
        except Exception:
            file_rel_display = entry["file_path"]
        print(f"File: {file_rel_display}")
        print(f"Operation: {entry['operation']}, Status: {entry['status']}")
        print("-" * 30)
        diff_rel_path = entry.get("diff_file")
        if diff_rel_path:
            diff_abs_path = history_root / diff_rel_path
            if diff_abs_path.is_file():
                try:
                    diff_content = diff_abs_path.read_text(encoding="utf-8")
                    print_diff_with_color(diff_content)
                except Exception as e:
                    print(
                        f"{COLOR_RED}Error reading diff file {diff_abs_path}: {e}{COLOR_RESET}",
                        file=sys.stderr,
                    )
            else:
                print(
                    f"{COLOR_YELLOW}Diff file not found: {diff_rel_path}{COLOR_RESET}"
                )
        else:
            print(
                f"No diff file associated with this '{entry['operation']}' operation."
            )
        return  # Done after showing single edit

    elif len(edit_matches) > 1:
        # If prefix matches multiple *edit* IDs, it's ambiguous for 'show edit'
        print(
            f"{COLOR_RED}Ambiguous identifier '{identifier}'. Matched multiple edit IDs:{COLOR_RESET}",
            file=sys.stderr,
        )
        for _, entry in edit_matches:
            print(f"  - {entry['edit_id']}", file=sys.stderr)
        # Suggest trying 'show <conv_id>' if they belong to the same conversation
        conv_ids = {e["conversation_id"] for _, e in edit_matches}
        if len(conv_ids) == 1:
            print(
                f"Did you mean to show the conversation '{list(conv_ids)[0]}'? Try 'mcpdiff show {list(conv_ids)[0][:10]}'.",
                file=sys.stderr,
            )
        raise AmbiguousIDError(f"Identifier '{identifier}' matches multiple edit IDs.")

    # --- Handle Conversation ID Show ---
    # If not found by edit ID (or ambiguous edit ID wasn't intended), try conversation ID
    conv_matches = find_log_entries_by_id(identifier, history_root, "conversation_id")

    if not conv_matches:
        print(
            f"{COLOR_RED}No history entry found matching identifier prefix: {identifier}{COLOR_RESET}",
            file=sys.stderr,
        )
        return

    # Check if the prefix uniquely identifies one conversation
    unique_conv_ids = {entry["conversation_id"] for _, entry in conv_matches}
    if len(unique_conv_ids) > 1:
        print(
            f"{COLOR_RED}Ambiguous identifier '{identifier}'. Matched multiple conversation IDs:{COLOR_RESET}",
            file=sys.stderr,
        )
        for cid in sorted(list(unique_conv_ids)):
            print(f"  - {cid}", file=sys.stderr)
        raise AmbiguousIDError(
            f"Identifier '{identifier}' matches multiple conversation IDs."
        )

    # Show all diffs for the uniquely identified conversation
    target_conv_id = list(unique_conv_ids)[0]
    print(f"Showing all diffs for Conversation ID: {target_conv_id}")

    # Gather and sort entries within the conversation by index
    conv_entries_list = [
        entry for _, entry in conv_matches if entry["conversation_id"] == target_conv_id
    ]
    conv_entries_list.sort(key=lambda x: x.get("tool_call_index", 0))

    for entry in conv_entries_list:
        print("\n" + "=" * 60)
        print(
            f"Edit ID: {entry['edit_id']} (Index: {entry.get('tool_call_index', '?')})"
        )
        try:
            file_rel_display = get_relative_path(
                Path(entry["file_path"]).resolve(), workspace_root
            )
        except Exception:
            file_rel_display = entry["file_path"]
        print(f"File: {file_rel_display}")
        print(f"Operation: {entry['operation']}, Status: {entry['status']}")
        print("-" * 30)
        diff_rel_path = entry.get("diff_file")
        if diff_rel_path:
            diff_abs_path = history_root / diff_rel_path
            if diff_abs_path.is_file():
                try:
                    diff_content = diff_abs_path.read_text(encoding="utf-8")
                    print_diff_with_color(diff_content)
                except Exception as e:
                    print(
                        f"{COLOR_RED}Error reading diff file {diff_abs_path}: {e}{COLOR_RESET}",
                        file=sys.stderr,
                    )
            else:
                print(
                    f"{COLOR_YELLOW}Diff file not found: {diff_rel_path}{COLOR_RESET}"
                )
        else:
            # Only print no diff if it's an op that *should* have one
            if entry["operation"] in ["edit", "replace", "create"]:
                print(
                    f"{COLOR_YELLOW}No diff file associated with this '{entry['operation']}' operation.{COLOR_RESET}"
                )
            else:
                print(f"({entry['operation']} operation - no diff expected)")


def update_entry_status(
    log_file: Path,
    target_edit_id: str,  # Full edit ID
    new_status: str,
) -> bool:
    """Updates the status of a specific edit ID in its log file. Assumes log file lock is held externally if needed."""
    try:
        # Read entries WITHOUT internal lock, assume caller handles locking
        entries = []
        if log_file.is_file():
            with open(log_file, "r", encoding="utf-8") as f:
                for i, line in enumerate(f):
                    line = line.strip()
                    if line:
                        try:
                            entries.append(json.loads(line))
                        except json.JSONDecodeError:
                            log.warning(
                                f"Skipping invalid JSON line {i + 1} in {log_file} during update: {line[:100]}..."
                            )

        updated = False
        found = False
        for entry in entries:
            if entry.get("edit_id") == target_edit_id:
                found = True
                if entry.get("status") == new_status:
                    log.debug(
                        f"Status for {target_edit_id[-8:]} already '{new_status}'."
                    )
                    return True  # No change needed, counts as success
                log.info(
                    f"Updating status of {target_edit_id[-8:]} to '{new_status}' in {log_file.name}"
                )
                entry["status"] = new_status
                updated = True
                break  # Assume edit IDs are unique within a file

        if not found:
            log.warning(
                f"Edit ID {target_edit_id} not found in log file {log_file} during status update attempt."
            )
            return False  # Indicate not found

        if updated:
            # Write back entries WITHOUT internal lock
            temp_path = log_file.with_suffix(
                log_file.suffix + ".tmp_update" + str(os.getpid())
            )
            try:
                log_file.parent.mkdir(parents=True, exist_ok=True)
                # Sort entries by index before writing
                entries.sort(key=lambda x: x.get("tool_call_index", float("inf")))
                with open(temp_path, "w", encoding="utf-8") as f:
                    for entry in entries:
                        json.dump(entry, f, separators=(",", ":"))
                        f.write("\n")
                os.replace(temp_path, log_file)
                log.debug(f"Successfully wrote updated log file: {log_file}")
                return True
            except Exception as e:
                log.error(f"Failed writing updated log file {log_file}: {e}")
                if temp_path.exists():
                    os.remove(temp_path)
                return False  # Write failed
        else:
            # Not updated, but found and status was already correct
            return True

    except Exception as e:  # Catch any other error during read/process
        log.exception(
            f"Unexpected error updating status for {target_edit_id} in {log_file}: {e}"
        )
        return False


def handle_accept_or_reject(
    args: argparse.Namespace,
    workspace_root: Path,
    history_root: Path,
    accept_mode: bool,  # True for accept, False for reject
) -> None:
    """Consolidated handler for accept and reject commands."""
    action = "accept" if accept_mode else "reject"
    new_status = "accepted" if accept_mode else "rejected"
    identifier = args.edit_id if args.edit_id else args.conv
    id_type = "edit_id" if args.edit_id else "conversation_id"
    log.debug(
        f"Processing '{action}' for edits matching {id_type} prefix: {identifier}"
    )

    matches = find_log_entries_by_id(identifier, history_root, id_type)

    if not matches:
        print(
            f"{COLOR_RED}No history entry found matching {id_type} prefix: {identifier}{COLOR_RESET}",
            file=sys.stderr,
        )
        return

    target_conv_ids: Set[str] = set()
    # Use a dictionary mapping log_file -> set of edit_ids to update
    updates_by_file: Dict[Path, Set[str]] = {}

    if id_type == "edit_id":
        # Ensure the prefix matches exactly one edit ID
        unique_edit_ids = {entry["edit_id"] for _, entry in matches}
        if len(unique_edit_ids) > 1:
            print(
                f"{COLOR_RED}Ambiguous identifier '{identifier}'. Matched multiple edit IDs:{COLOR_RESET}",
                file=sys.stderr,
            )
            for eid in sorted(list(unique_edit_ids)):
                print(f"  - {eid}")
            raise AmbiguousIDError(
                f"Identifier '{identifier}' matches multiple edit IDs."
            )
        elif not unique_edit_ids:
            # Should be caught by 'not matches' earlier, but safety check
            print(
                f"{COLOR_RED}No history entry found matching edit ID prefix: {identifier}{COLOR_RESET}",
                file=sys.stderr,
            )
            return

        # Prefix matches exactly one edit ID
        log_file, entry = matches[0]  # Get the single match
        target_edit_id = entry["edit_id"]
        current_status = entry.get("status", "pending")

        # Check if action is valid for current status
        if current_status == new_status:
            print(
                f"Edit {target_edit_id} is already '{current_status}'. No action taken."
            )
            return
        # Cannot accept a rejected edit directly (must reject first, then maybe accept later?) - simplify: allow switching if needed
        # Cannot reject an accepted edit if accept_mode is True (and vice versa) - this logic is handled by new_status

        if log_file not in updates_by_file:
            updates_by_file[log_file] = set()
        updates_by_file[log_file].add(target_edit_id)
        target_conv_ids.add(entry["conversation_id"])

    else:  # conversation_id
        # Ensure the prefix matches exactly one conversation ID
        unique_conv_ids = {entry["conversation_id"] for _, entry in matches}
        if len(unique_conv_ids) > 1:
            print(
                f"{COLOR_RED}Ambiguous identifier '{identifier}'. Matched multiple conversation IDs:{COLOR_RESET}",
                file=sys.stderr,
            )
            for cid in sorted(list(unique_conv_ids)):
                print(f"  - {cid}")
            raise AmbiguousIDError(
                f"Identifier '{identifier}' matches multiple conversation IDs."
            )
        elif not unique_conv_ids:
            print(
                f"{COLOR_RED}No history entry found matching conversation ID prefix: {identifier}{COLOR_RESET}",
                file=sys.stderr,
            )
            return

        target_conv_id = list(unique_conv_ids)[0]
        print(
            f"{action.capitalize()}ing relevant edits for conversation: {target_conv_id}"
        )
        target_conv_ids.add(target_conv_id)

        # Gather all relevant edits for this specific conversation ID
        edits_in_conv = 0
        edits_to_change = 0
        for log_file, entry in matches:
            if entry["conversation_id"] == target_conv_id:
                edits_in_conv += 1
                current_status = entry.get("status", "pending")
                # Apply action based on mode:
                # Accept: Mark 'pending' as 'accepted'.
                # Reject: Mark 'pending' OR 'accepted' as 'rejected'.
                should_update = False
                if accept_mode and current_status == "pending":
                    should_update = True
                elif (
                    not accept_mode and current_status != "rejected"
                ):  # Reject pending or accepted
                    should_update = True

                if should_update:
                    edits_to_change += 1
                    if log_file not in updates_by_file:
                        updates_by_file[log_file] = set()
                    updates_by_file[log_file].add(entry["edit_id"])

        if edits_to_change == 0:
            print(
                f"No edits in conversation {target_conv_id} require status change to '{new_status}'."
            )
            return

    if not updates_by_file:
        print(
            f"No edits found requiring update to '{new_status}' for the given identifier."
        )
        return

    # --- Update Status in Log Files ---
    success_count = 0
    fail_count = 0
    print(
        f"Marking {len([eid for eids in updates_by_file.values() for eid in eids])} edit(s) as '{new_status}'..."
    )

    # Lock each log file once and update all its relevant entries
    for log_file, edit_ids_to_update in updates_by_file.items():
        log_lock = FileLock(str(log_file))
        try:
            with log_lock:
                # Reread entries under lock to ensure we have the latest state before modifying
                current_entries = []
                if log_file.is_file():
                    with open(log_file, "r", encoding="utf-8") as f:
                        for i, line in enumerate(f):
                            line = line.strip()
                            if line:
                                try:
                                    current_entries.append(json.loads(line))
                                except json.JSONDecodeError:
                                    log.warning(
                                        f"Skipping invalid JSON line {i + 1} in {log_file} during update: {line[:100]}..."
                                    )

                updated_in_file = 0
                entries_to_write = []
                processed_ids = set()

                for entry in current_entries:
                    entry_id = entry.get("edit_id")
                    if entry_id in edit_ids_to_update and entry_id not in processed_ids:
                        if entry.get("status") != new_status:
                            entry["status"] = new_status
                            log.info(
                                f"Updated status of {entry_id[-8:]} to '{new_status}' in {log_file.name}"
                            )
                            updated_in_file += 1
                        processed_ids.add(entry_id)
                    entries_to_write.append(entry)  # Keep all entries

                # Check if all requested updates were found
                not_found_ids = edit_ids_to_update - processed_ids
                if not_found_ids:
                    log.warning(
                        f"Could not find edit IDs {list(not_found_ids)} in {log_file} during update."
                    )
                    fail_count += len(not_found_ids)

                # Write back if changes were made
                if updated_in_file > 0:
                    # Use internal write logic (no locking needed as outer lock held)
                    temp_path = log_file.with_suffix(
                        log_file.suffix + ".tmp_atomic_write" + str(os.getpid())
                    )
                    try:
                        log_file.parent.mkdir(parents=True, exist_ok=True)
                        # Sort entries by index before writing
                        entries_to_write.sort(
                            key=lambda x: x.get("tool_call_index", float("inf"))
                        )
                        with open(temp_path, "w", encoding="utf-8") as f:
                            for entry_to_write in entries_to_write:
                                json.dump(entry_to_write, f, separators=(",", ":"))
                                f.write("\n")
                        os.replace(temp_path, log_file)
                        log.debug(f"Successfully wrote updated log file: {log_file}")
                        success_count += updated_in_file
                    except Exception as e_write:
                        log.error(
                            f"Failed writing updated log file {log_file}: {e_write}"
                        )
                        if temp_path.exists():
                            os.remove(temp_path)
                        fail_count += (
                            updated_in_file  # Count as failure if write failed
                        )
                else:
                    # No changes needed in this file for the requested IDs (e.g., status already correct)
                    success_count += len(
                        edit_ids_to_update - not_found_ids
                    )  # Count found IDs as success

        except (TimeoutError, HistoryError, Exception) as e_lock:
            log.error(
                f"Failed to process log file {log_file} due to lock/read error: {e_lock}"
            )
            fail_count += len(edit_ids_to_update)  # Count all as failures for this file
        finally:
            if log_lock:
                log_lock.release()  # Ensure release

    print(f"Successfully updated status for {success_count} edit(s).")
    if fail_count > 0:
        print(
            f"{COLOR_YELLOW}Failed to update status for {fail_count} edit(s). Check logs.{COLOR_RESET}",
            file=sys.stderr,
        )

    # --- Trigger Re-apply ONLY for REJECT ---
    if not accept_mode and target_conv_ids:
        overall_reapply_success = True
        print("Re-applying state based on updated statuses...")
        # Use list to ensure consistent processing order if needed
        sorted_conv_ids = sorted(list(target_conv_ids))
        for conv_id in sorted_conv_ids:
            print(f"Processing conversation: {conv_id}")
            if not reapply_conversation_state(conv_id, history_root, workspace_root):
                overall_reapply_success = False
                print(
                    f"{COLOR_RED}Errors occurred while re-applying state for conversation {conv_id}. Check logs.{COLOR_RESET}",
                    file=sys.stderr,
                )
                # Continue to next conversation

        if overall_reapply_success:
            print("File state reconstruction completed successfully.")
        else:
            print(
                f"{COLOR_YELLOW}File state reconstruction finished with errors. Manual review may be required.{COLOR_RESET}",
                file=sys.stderr,
            )
    elif not accept_mode:
        print("No target conversations identified for re-apply.")


def handle_accept(
    args: argparse.Namespace, workspace_root: Path, history_root: Path
) -> None:
    handle_accept_or_reject(args, workspace_root, history_root, accept_mode=True)


def handle_reject(
    args: argparse.Namespace, workspace_root: Path, history_root: Path
) -> None:
    handle_accept_or_reject(args, workspace_root, history_root, accept_mode=False)


def handle_review(
    args: argparse.Namespace, workspace_root: Path, history_root: Path
) -> None:
    """Handle the interactive review command."""
    log.info("Starting interactive review...")

    log_dir = history_root / LOGS_DIR
    if not log_dir.is_dir():
        print("No history logs found.")
        return

    # Gather all pending edits
    pending_entries = []
    target_conv_prefix = args.conv if args.conv else None

    log_files = sorted(log_dir.glob("*.log"), key=os.path.getmtime, reverse=True)
    processed_log_files = set()  # Track files already read

    for log_file in log_files:
        if log_file in processed_log_files:
            continue
        try:
            # Read log file (uses locking)
            entries = read_log_file(log_file)
            processed_log_files.add(
                log_file
            )  # Mark as read even if no pending found later
            for entry in entries:
                if entry.get("status") == "pending":
                    conv_match = not target_conv_prefix or entry.get(
                        "conversation_id", ""
                    ).startswith(target_conv_prefix)
                    if conv_match:
                        # Add log file path to entry for easier update later
                        entry_with_meta = {"log_file": log_file, **entry}
                        pending_entries.append(entry_with_meta)
        except HistoryError as e:
            print(
                f"{COLOR_YELLOW}Warning: Could not read log file {log_file.name}: {e}{COLOR_RESET}",
                file=sys.stderr,
            )
            continue
        except Exception as e:
            print(
                f"{COLOR_RED}Error processing log file {log_file.name}: {e}{COLOR_RESET}",
                file=sys.stderr,
            )
            continue

    if not pending_entries:
        print(
            "No pending edits found to review"
            + (
                f" for conversation prefix '{target_conv_prefix}'."
                if target_conv_prefix
                else "."
            )
        )
        return

    # Sort by timestamp
    pending_entries.sort(key=lambda x: x.get("timestamp", "0"))
    total_pending = len(pending_entries)
    print(f"Found {total_pending} pending edit(s).")

    # --- Interactive Loop ---
    quit_review = False
    for i, entry in enumerate(pending_entries):
        if quit_review:
            break

        print("\n" + "=" * 70)
        print(f"Reviewing Edit {i + 1}/{total_pending}")
        print(f"Edit ID:         {entry['edit_id']}")
        print(f"Conversation ID: {entry['conversation_id']}")
        print(f"Timestamp:       {entry.get('timestamp', 'N/A')}")
        try:
            file_rel = get_relative_path(
                Path(entry["file_path"]).resolve(), workspace_root
            )
        except Exception:
            file_rel = entry.get("file_path", "N/A")
        print(f"File:            {file_rel}")
        print(f"Operation:       {entry.get('operation', 'N/A')}")
        print("-" * 70)

        # Show Diff
        diff_rel_path = entry.get("diff_file")
        if diff_rel_path:
            diff_abs_path = history_root / diff_rel_path
            if diff_abs_path.is_file():
                try:
                    diff_content = diff_abs_path.read_text(encoding="utf-8")
                    print_diff_with_color(diff_content)
                except Exception as e:
                    print(
                        f"{COLOR_RED}Error reading diff file {diff_abs_path}: {e}{COLOR_RESET}",
                        file=sys.stderr,
                    )
            else:
                print(
                    f"{COLOR_YELLOW}Diff file not found: {diff_rel_path}{COLOR_RESET}"
                )
        else:
            if entry.get("operation") in ["edit", "replace", "create"]:
                print(
                    f"{COLOR_YELLOW}No diff file associated with this '{entry.get('operation')}' operation.{COLOR_RESET}"
                )
            else:
                print(f"({entry.get('operation')} operation - no diff expected)")

        # Prompt User
        while True:
            print("-" * 70)
            prompt = f"Action? ({COLOR_GREEN}[a]{COLOR_RESET}ccept / {COLOR_RED}[r]{COLOR_RESET}eject / {COLOR_BLUE}[s]{COLOR_RESET}kip / {COLOR_YELLOW}[q]{COLOR_RESET}uit): "
            try:
                action = input(prompt).lower().strip()
            except EOFError:  # Handle Ctrl+D as quit
                action = "q"
                print("q")  # Echo 'q' for clarity

            if action in ["a", "accept"]:
                print("Accepting...")
                log_file_to_update = entry["log_file"]
                edit_id_to_update = entry["edit_id"]
                log_lock = FileLock(str(log_file_to_update))
                try:
                    with log_lock:
                        if update_entry_status(
                            log_file_to_update, edit_id_to_update, "accepted"
                        ):
                            print("Marked as accepted.")
                        else:
                            print(
                                f"{COLOR_RED}Failed to mark as accepted. Check logs.{COLOR_RESET}"
                            )
                except (TimeoutError, Exception) as e_lock:
                    print(
                        f"{COLOR_RED}Failed to acquire lock or update log {log_file_to_update}: {e_lock}{COLOR_RESET}"
                    )
                finally:
                    if log_lock:
                        log_lock.release()
                break  # Move to next edit

            elif action in ["r", "reject"]:
                print("Rejecting...")
                log_file_to_update = entry["log_file"]
                edit_id_to_update = entry["edit_id"]
                conv_id_to_reapply = entry["conversation_id"]
                log_lock = FileLock(str(log_file_to_update))
                reapply_needed = False
                try:
                    with log_lock:
                        if update_entry_status(
                            log_file_to_update, edit_id_to_update, "rejected"
                        ):
                            print("Marked as rejected.")
                            reapply_needed = True
                        else:
                            print(
                                f"{COLOR_RED}Failed to mark as rejected. Check logs.{COLOR_RESET}"
                            )
                except (TimeoutError, Exception) as e_lock:
                    print(
                        f"{COLOR_RED}Failed to acquire lock or update log {log_file_to_update}: {e_lock}{COLOR_RESET}"
                    )
                finally:
                    if log_lock:
                        log_lock.release()

                # Perform re-apply *after* releasing log lock
                if reapply_needed:
                    print("Re-applying state for conversation...")
                    if reapply_conversation_state(
                        conv_id_to_reapply, history_root, workspace_root
                    ):
                        print("File state reconstructed successfully.")
                    else:
                        print(
                            f"{COLOR_YELLOW}Errors occurred during state reconstruction. Manual review advised.{COLOR_RESET}"
                        )
                break  # Move to next edit

            elif action in ["s", "skip"]:
                print("Skipping...")
                break  # Move to next edit

            elif action in ["q", "quit"]:
                print("Quitting review.")
                quit_review = True
                break  # Exit inner loop, outer loop will terminate
            else:
                print("Invalid input. Please enter 'a', 'r', 's', or 'q'.")

    if not quit_review:
        print("\nReview complete.")


# --- Main Argparse Setup ---
def main():
    parser = argparse.ArgumentParser(
        description="MCP Diff Tool: Review and manage LLM file edits.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  mcpdiff status                     # Show recent history status
  mcpdiff status --conv 17... --file src/main.py --status pending
  mcpdiff show <edit_id_prefix>      # Show diff for a specific edit
  mcpdiff show <conv_id_prefix>      # Show all diffs for a conversation
  mcpdiff accept -e <edit_id_prefix> # Accept a specific edit
  mcpdiff accept -c <conv_id_prefix> # Accept all pending in a conversation
  mcpdiff reject -e <edit_id_prefix> # Reject an edit (re-applies conversation)
  mcpdiff reject -c <conv_id_prefix> # Reject all in conversation (re-applies)
  mcpdiff review                     # Interactively review pending edits
  mcpdiff review --conv <conv_id_prefix> # Review pending in one conversation
""",
    )
    parser.add_argument(
        "-w",
        "--workspace",
        help="Path to the workspace root (containing .mcp/edit_history). Defaults to searching from CWD upwards.",
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="Enable debug logging."
    )

    subparsers = parser.add_subparsers(
        dest="command", required=True, help="Sub-command help"
    )

    # status
    parser_status = subparsers.add_parser("status", help="Show edit history status.")
    parser_status.add_argument("--conv", help="Filter by conversation ID prefix.")
    parser_status.add_argument("--file", help="Filter by file path substring.")
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
        "show",
        help="Show diff for an edit_id or all diffs for a conversation_id (using prefix).",
    )
    parser_show.add_argument(
        "identifier", help="The edit_id or conversation_id prefix to show."
    )
    parser_show.set_defaults(func=handle_show)

    # accept
    parser_accept = subparsers.add_parser("accept", help="Mark edits as accepted.")
    group_accept = parser_accept.add_mutually_exclusive_group(required=True)
    group_accept.add_argument(
        "-e", "--edit-id", help="The specific edit_id prefix to accept."
    )
    group_accept.add_argument(
        "-c", "--conv", help="Accept all pending edits for a conversation_id prefix."
    )
    parser_accept.set_defaults(func=handle_accept)

    # reject
    parser_reject = subparsers.add_parser(
        "reject", help="Mark edits as rejected and revert/re-apply changes."
    )
    group_reject = parser_reject.add_mutually_exclusive_group(required=True)
    group_reject.add_argument(
        "-e", "--edit-id", help="The specific edit_id prefix to reject."
    )
    group_reject.add_argument(
        "-c",
        "--conv",
        help="Reject all pending/accepted edits for a conversation_id prefix.",
    )
    parser_reject.set_defaults(func=handle_reject)

    # review
    parser_review = subparsers.add_parser(
        "review", help="Interactively review pending edits."
    )
    parser_review.add_argument(
        "--conv", help="Review pending edits only for this conversation ID prefix."
    )
    parser_review.set_defaults(func=handle_review)

    # --- Parse and Execute ---
    args = parser.parse_args()

    # Setup logging level based on -v flag
    if args.verbose:
        # Set logging level for this script's logger and the root logger
        log.setLevel(logging.DEBUG)
        logging.getLogger().setLevel(logging.DEBUG)
        # Update formatter for debug level if desired (e.g., include module name)
        # debug_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(module)s:%(lineno)d - %(message)s')
        # for handler in logging.getLogger().handlers:
        #     handler.setFormatter(debug_formatter)
        log.debug("Debug logging enabled.")
    else:
        log.setLevel(logging.INFO)
        # Keep root logger at WARNING or INFO to avoid overly verbose output from libraries
        logging.getLogger().setLevel(logging.WARNING)

    # --- Find Workspace and History Root ---
    try:
        workspace_root = find_workspace_root(args.workspace)
        if not workspace_root:
            print(
                f"{COLOR_RED}Error: Could not find workspace root (directory containing .mcp/{HISTORY_DIR_NAME}) starting from '{args.workspace or os.getcwd()}'.{COLOR_RESET}",
                file=sys.stderr,
            )
            sys.exit(1)

        # Security: Ensure workspace is current directory or below
        cwd = Path.cwd().resolve()
        if not is_path_within_directory(workspace_root, cwd):
            print(
                f"{COLOR_RED}Error: For security, workspace root must be within current directory: {cwd}{COLOR_RESET}",
                file=sys.stderr,
            )
            sys.exit(1)

        history_root = workspace_root / ".mcp" / HISTORY_DIR_NAME
        # No need to check history_root.is_dir() here, find_workspace_root already does.

        log.debug(f"Using workspace root: {workspace_root}")
        log.debug(f"Using history root: {history_root}")

    except Exception as e:
        print(f"{COLOR_RED}Error finding workspace: {e}{COLOR_RESET}", file=sys.stderr)
        log.exception("Workspace finding error:")  # Log traceback if verbose
        sys.exit(1)

    # --- Execute Command ---
    exit_code = 0
    try:
        args.func(args, workspace_root, history_root)
    except KeyboardInterrupt:
        print("\nOperation cancelled by user.", file=sys.stderr)
        exit_code = 130  # Standard exit code for Ctrl+C
    except (
        HistoryError,
        ExternalModificationError,
        TimeoutError,
        AmbiguousIDError,
    ) as e:
        print(f"{COLOR_RED}Error: {e}{COLOR_RESET}", file=sys.stderr)
        exit_code = 1
    except Exception as e:
        print(
            f"{COLOR_RED}An unexpected error occurred. Use -v for detailed logs.{COLOR_RESET}",
            file=sys.stderr,
        )
        print(f"{COLOR_RED}Error details: {e}{COLOR_RESET}", file=sys.stderr)
        log.exception(
            "Unexpected error during command execution:"
        )  # Log full traceback
        exit_code = 2
    finally:
        # Optional: Cleanup any stray locks if needed, though __exit__ should handle it
        pass

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
