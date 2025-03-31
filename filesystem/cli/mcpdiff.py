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
from datetime import datetime, timezone, timedelta
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

    def _check_stale_lock(self) -> bool:
        """Check if the lock appears to be stale and clean it up if necessary.
        Returns True if a stale lock was found and cleaned up."""
        
        if not self.lock_dir.exists():
            return False
            
        # Check if the lock file exists
        if not self.lock_file_path.exists():
            # Directory exists but no lock file - clean up
            try:
                log.debug(f"Found stale lock directory without lock file: {self.lock_dir}")
                self.lock_dir.rmdir()
                return True
            except OSError:
                log.warning(f"Failed to remove stale lock directory: {self.lock_dir}")
                return False
                
        # Try to read PID from lock file
        try:
            pid_str = self.lock_file_path.read_text().strip()
            if not pid_str:
                log.debug(f"Found empty PID in lock file: {self.lock_file_path}")
                # Empty PID - likely stale
                self._force_cleanup()
                return True
                
            # Check if PID exists
            pid = int(pid_str)
            if pid <= 0:
                log.debug(f"Invalid PID in lock file: {pid}")
                self._force_cleanup()
                return True
                
            # On Unix-like systems, check if process exists
            try:
                os.kill(pid, 0)  # Signal 0 doesn't kill but checks if process exists
                # Process exists, lock may be valid
                log.debug(f"Process with PID {pid} exists, lock may be valid")
                return False
            except OSError:
                # Process doesn't exist
                log.debug(f"Process with PID {pid} does not exist, cleaning up stale lock")
                self._force_cleanup()
                return True
                
        except (ValueError, IOError) as e:
            # Error reading or parsing PID
            log.debug(f"Error checking stale lock: {e}")
            self._force_cleanup()
            return True
            
        return False
        
    def _force_cleanup(self):
        """Force cleanup of lock file and directory"""
        try:
            if self.lock_file_path.exists():
                self.lock_file_path.unlink()
                log.debug(f"Removed stale lock file: {self.lock_file_path}")
            if self.lock_dir.exists():
                self.lock_dir.rmdir()
                log.debug(f"Removed stale lock directory: {self.lock_dir}")
        except OSError as e:
            log.warning(f"Failed to force cleanup lock: {e}")

    def acquire(self, timeout=LOCK_TIMEOUT):
        """Acquire the lock with timeout."""
        start_time = time.time()
        
        # First check for and clean up stale locks
        self._check_stale_lock()
        
        # Now try to acquire the lock
        self.lock_dir.mkdir(parents=True, exist_ok=True)  # Ensure lock directory exists

        while True:
            try:
                # Open the lock file within the directory
                self.lock_file_handle = open(self.lock_file_path, "w")
                fcntl.flock(
                    self.lock_file_handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB
                )
                # Write PID for debugging purposes (important: ensure it's written and flushed)
                self.lock_file_handle.write(str(os.getpid()))
                self.lock_file_handle.flush()
                os.fsync(self.lock_file_handle.fileno())  # Ensure data is written to disk
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
                    # Check again for stale locks that might have appeared during waiting
                    if self._check_stale_lock():
                        # If we cleaned up a stale lock, try one more time quickly
                        try:
                            self.lock_file_handle = open(self.lock_file_path, "w")
                            fcntl.flock(
                                self.lock_file_handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB
                            )
                            self.lock_file_handle.write(str(os.getpid()))
                            self.lock_file_handle.flush()
                            os.fsync(self.lock_file_handle.fileno())
                            self.is_locked = True
                            log.debug(f"Acquired lock via directory after cleaning stale lock: {self.lock_dir}")
                            return  # Success after cleanup
                        except (IOError, OSError):
                            if self.lock_file_handle:
                                self.lock_file_handle.close()
                                self.lock_file_handle = None
                
                    # Attempt to read PID from lock file if it exists
                    locker_pid = "unknown"
                    try:
                        if self.lock_file_path.exists():
                            locker_pid = self.lock_file_path.read_text().strip()
                            if not locker_pid:
                                locker_pid = "empty PID"
                    except Exception:
                        locker_pid = "unreadable"
                    
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
                    if self.lock_dir.exists():
                        try:
                            self.lock_dir.rmdir()
                            log.debug(f"Removed lock directory: {self.lock_dir}")
                        except OSError:
                            log.debug(
                                f"Lock directory {self.lock_dir} not empty or removed by another process."
                            )
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

    # For tracking the original path affected by each edit
    path_trace: Dict[str, str] = {}

    # --- Build File Histories ---
    # Trace the history of each path affected by the conversation
    for entry in all_conv_entries:
        # Skip entries referring to files we can't find or have no paths
        entry_file_path = entry.get("file_path")
        entry_source_path = entry.get("source_path")
        if not entry_file_path:
            log.warning(
                f"No file_path in entry {entry.get('edit_id')}, skipping. This should not happen."
            )
            continue

        # Convert paths to absolute using workspace as base
        target_abs_str = (
            get_workspace_path(entry_file_path, workspace_root)
            if not os.path.isabs(entry_file_path)
            else entry_file_path
        )
        source_abs_str = (
            get_workspace_path(entry_source_path, workspace_root)
            if entry_source_path and not os.path.isabs(entry_source_path)
            else entry_source_path
        )

        # Get the operation from the entry
        op = entry.get("operation", "unknown")
        if op == "unknown":
            log.warning(
                f"Unknown operation in entry {entry.get('edit_id')}, skipping. This should not happen."
            )
            continue

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
    # Track which final paths we've processed to avoid duplicates
    processed_final_paths = set()

    # Iterate through each path affected by the conversation
    for original_path_abs_str, edits in file_histories.items():
        # Skip if we've already processed the final path (can happen with multiple moves)
        final_target_abs_str = final_paths.get(original_path_abs_str, original_path_abs_str)
        if final_target_abs_str in processed_final_paths:
            log.debug(
                f"Skipping duplicate processing of final path '{final_target_abs_str}'"
            )
            continue
        processed_final_paths.add(final_target_abs_str)

        # Get relative paths for display
        try:
            original_path_rel = get_relative_path(
                Path(original_path_abs_str), workspace_root
            )
            final_target_rel = get_relative_path(Path(final_target_abs_str), workspace_root)
        except Exception as e:
            log.error(f"Error determining relative paths: {e}")
            overall_success = False
            continue  # Skip if paths are problematic

        log.info(f"Processing history for original path '{original_path_rel}' (final: '{final_target_rel}')")

        # Lock the target file during processing
        target_lock = None
        try:
            target_lock = FileLock(final_target_abs_str)
            target_lock.acquire()
            log.debug(f"Lock acquired for {final_target_abs_str}")

            # Get checkpoint path for this history
            checkpoint_rel_path_str = None
            first_relevant_edit = edits[0]
            checkpoint_rel_path_str = first_relevant_edit.get("checkpoint_file")

            # Look up hash recorded when checkpoint was taken
            initial_hash_from_log = first_relevant_edit.get("hash_before")
            if not initial_hash_from_log and checkpoint_rel_path_str:
                log.warning(
                    f"No hash recorded with checkpoint '{checkpoint_rel_path_str}'. This is unexpected."
                )

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
            final_target_abs = Path(final_target_abs_str)

            # Variables to track state during replay
            file_exists_in_state = False  # Does the file exist during current replay step?
            current_file_path_abs = None  # Current filename/path during replay
            current_expected_hash = None  # Expected hash after applying the current step

            # --- Initialize Starting State ---
            if first_op_is_rejected_create:
                # If first op is a rejected create, start with no file
                log.info(
                    f"Skipping state initialization for rejected create of '{final_target_rel}'"
                )
                current_file_path_abs = Path(final_target_abs_str)
                file_exists_in_state = False
                current_expected_hash = None
            # If checkpoint available, use it
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
                except (FileNotFoundError, IOError, OSError) as e:
                    log.error(f"Failed to restore checkpoint: {e}")
                    raise HistoryError(f"Failed to restore checkpoint: {e}") from e
            elif first_relevant_edit["operation"] == "create" and not checkpoint_rel_path_str:
                # Handle creation: No checkpoint but file was created (normal case)
                current_file_path_abs = Path(final_target_abs_str)
                log.info(
                    f"Starting with empty state for '{final_target_rel}' (no checkpoint, create operation)"
                )
                file_exists_in_state = False
                current_expected_hash = None
            else:
                # No checkpoint, not a create. Assume file exists at the path expected by the first op.
                current_file_path_abs = Path(checkpoint_origin_path_abs_str)
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

                # Check if any previous edit for this file was rejected
                previous_rejected = False
                for prev_entry in edits[:entry_index]:
                    if prev_entry.get("status") == "rejected":
                        previous_rejected = True
                        break

                if file_exists_in_state and op not in ["move", "delete"]:
                    # Skip hash check for move/delete as source path may no longer exist
                    # Also skip hash check after a previous rejected edit (which may have
                    # changed file content/hash)
                    if (
                        actual_current_hash != current_expected_hash
                        and current_expected_hash is not None
                        and actual_current_hash is not None
                        and not previous_rejected  # Skip hash check if previous edit was rejected
                    ):
                        log.error(
                            f"Unexpected file state before {op} operation {edit_id[-8:]}. "
                            f"Expected hash: {current_expected_hash[:8]}, "
                            f"Actual hash: {actual_current_hash[:8]}. "
                            f"The file may have been modified externally or history is inconsistent."
                        )
                        # Continue but note overall failure
                        overall_success = False
                        # Update our expectation to match reality for subsequent operations
                        current_expected_hash = actual_current_hash

                # --- Apply or Skip Based on Status ---
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
                        # Update hash expectation after successful patch
                        current_expected_hash = (
                            hash_after_entry or calculate_hash(str(entry_target_abs))
                        )
                    elif op == "move":
                        if not entry_source_abs or not entry_target_abs:
                            log.error(
                                f"Move operation {edit_id[-8:]} missing source or target path."
                            )
                            raise HistoryError(
                                f"Move operation {edit_id[-8:]} missing source or target path."
                            )
                        # Check if source exists where expected during replay
                        if (
                            current_file_path_abs is not None
                            and entry_source_abs != current_file_path_abs
                        ):
                            log.warning(
                                f"Move source '{entry_source_rel}' doesn't match current path '{get_relative_path(current_file_path_abs, workspace_root)}'"
                            )
                        # Ensure the source file exists
                        if not file_exists_in_state:
                            log.error(
                                f"Move operation {edit_id[-8:]} source file doesn't exist in replay."
                            )
                            raise HistoryError(
                                f"Move operation {edit_id[-8:]} source file doesn't exist in replay."
                            )
                        # Ensure parent directory exists
                        entry_target_abs.parent.mkdir(parents=True, exist_ok=True)
                        # Handle destination file existence
                        if entry_target_abs.exists():
                            log.warning(
                                f"    Destination '{entry_target_rel}' exists. Overwriting during move replay for {edit_id[-8:]}."
                            )
                            try:
                                entry_target_abs.unlink()
                            except Exception as e:
                                log.error(
                                    f"Failed to remove existing destination during move: {e}"
                                )
                                raise HistoryError(
                                    f"Failed move operation for {edit_id[-8:]}: {e}"
                                ) from e
                        # Perform the move
                        try:
                            if current_file_path_abs and current_file_path_abs.is_file():
                                shutil.move(str(current_file_path_abs), str(entry_target_abs))
                                log.debug(
                                    f"    Moved '{get_relative_path(current_file_path_abs, workspace_root)}' to '{entry_target_rel}'"
                                )
                            else:
                                log.error(
                                    f"Invalid current state for move: {current_file_path_abs}"
                                )
                                raise HistoryError(
                                    f"Failed move operation for {edit_id[-8:]}: Invalid current state"
                                )
                        except (shutil.Error, OSError) as e:
                            log.error(f"Move operation failed: {e}")
                            raise HistoryError(
                                f"Failed move operation for {edit_id[-8:]}"
                            ) from e
                        # Update state after successful move
                        file_exists_in_state = True
                        current_file_path_abs = entry_target_abs
                        # Hash shouldn't change for move, but still verify if log recorded a different after hash
                        if hash_after_entry and hash_after_entry != current_expected_hash:
                            log.warning(
                                f"Hash changed during move op {edit_id[-8:]}? Before: {current_expected_hash[:8]}, After: {hash_after_entry[:8]}"
                            )
                            current_expected_hash = hash_after_entry
                    elif op == "delete":
                        # Check if file exists as expected
                        if not file_exists_in_state:
                            log.warning(
                                f"Delete operation {edit_id[-8:]} target doesn't exist in replay (already deleted?)"
                            )
                        elif (
                            current_file_path_abs is not None
                            and entry_target_abs != current_file_path_abs
                        ):
                            log.warning(
                                f"Delete target '{entry_target_rel}' doesn't match current path '{get_relative_path(current_file_path_abs, workspace_root)}'"
                            )
                        # Perform the delete
                        try:
                            if entry_target_abs.is_file():
                                entry_target_abs.unlink()
                                log.debug(f"    Deleted '{entry_target_rel}'")
                            else:
                                log.warning(
                                    f"Delete target '{entry_target_rel}' already gone in replay."
                                )
                        except (FileNotFoundError, OSError) as e:
                            log.error(f"Delete operation failed: {e}")
                            raise HistoryError(
                                f"Failed delete operation for {edit_id[-8:]}"
                            ) from e
                        # Update state after successful delete
                        file_exists_in_state = False
                        current_file_path_abs = entry_target_abs  # Keep track of path even though deleted
                        current_expected_hash = None  # No hash for deleted file
                    else:
                        log.warning(f"Unknown operation '{op}' in edit {edit_id[-8:]}. Skipping.")
                elif status == "rejected":
                    log.debug(f"    Skipping (rejected) {op} for edit {edit_id[-8:]}...")
                    # For rejected ops, we don't apply the change, but we still need to update state
                    # tracking vars to maintain our expectation of where files should be
                    if op == "create":
                        # For rejected create: file should not exist
                        file_exists_in_state = False
                        current_file_path_abs = entry_target_abs  # Keep path for tracking
                        current_expected_hash = None  # No hash for non-existent file
                    elif op == "delete":
                        # For rejected delete: file should still exist where it was
                        # No change to tracking vars needed
                        pass
                    elif op == "move":
                        # For rejected move: file should still be at source, not at target
                        if entry_source_abs:
                            # Keep current path at source
                            current_file_path_abs = entry_source_abs
                        else:
                            log.warning(
                                f"Rejected move {edit_id[-8:]} missing source path. Can't track properly."
                            )
                        # Hash shouldn't change for rejected move
                    elif op in ["edit", "replace"]:
                        # For rejected edit: file content should be what it was before
                        # For edits, the "after" state in the log entry is the one we're rejecting
                        # So hash should remain at hash_before
                        if hash_before_entry and current_expected_hash != hash_before_entry:
                            log.debug(
                                f"    After rejecting edit {edit_id[-8:]}, hash should be {hash_before_entry[:8]}"
                            )
                            current_expected_hash = hash_before_entry
                    else:
                        log.warning(f"Unknown rejected op '{op}' in edit {edit_id[-8:]}. Skipping.")
                else:
                    log.warning(
                        f"    Unknown status '{status}' for edit {edit_id[-8:]}. Skipping."
                    )

            # --- Verify Final State ---
            # Only check if a final file should exist based on last operation status
            final_should_exist = file_exists_in_state
            final_actual_exists = final_target_abs.is_file()
            final_actual_hash = calculate_hash(str(final_target_abs)) if final_actual_exists else None

            if final_should_exist != final_actual_exists:
                log.error(
                    f"Final state mismatch for '{get_relative_path(final_target_abs, workspace_root)}'. "
                    f"Should exist: {final_should_exist}, Actually exists: {final_actual_exists}"
                )
                overall_success = False
            elif final_actual_exists:
                # Only compare hashes if file exists (and should exist)
                if final_actual_hash != current_expected_hash:
                    # Allow None == None (e.g. final state should be deleted)
                    if not (final_actual_hash is None and current_expected_hash is None):
                        log.error(
                            f"Final state verification FAILED for '{get_relative_path(current_file_path_abs, workspace_root)}'. "
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


def update_entry_status(log_file_path: Path, edit_id_prefix: str, new_status: str) -> bool:
    """
    Updates the status of one or more log entries that match the edit_id prefix.
    Returns True if all matching entries were updated successfully, False otherwise.
    """
    if not log_file_path.is_file():
        log.error(f"Log file does not exist: {log_file_path}")
        return False
    
    # Read the log file
    try:
        entries = read_log_file(log_file_path)
    except HistoryError as e:
        log.error(f"Error reading log file {log_file_path}: {e}")
        return False
    
    # Find entries matching the edit_id prefix
    found = False
    for entry in entries:
        if entry.get("edit_id", "").startswith(edit_id_prefix):
            log.debug(f"Updating status of edit {entry['edit_id']} from {entry.get('status', 'unknown')} to {new_status}")
            entry["status"] = new_status
            found = True
    
    if not found:
        log.error(f"No entries found matching edit_id prefix '{edit_id_prefix}' in {log_file_path}")
        return False
    
    # Write updated entries back to the log file
    try:
        write_log_file(log_file_path, entries)
        return True
    except HistoryError as e:
        log.error(f"Error writing updated log file {log_file_path}: {e}")
        return False


def handle_accept_or_reject(
    args: argparse.Namespace, workspace_root: Path, history_root: Path, accept_mode: bool
) -> None:
    """Shared implementation for accept and reject commands."""
    action_name = "accept" if accept_mode else "reject"
    log.info(f"Starting {action_name} operation...")
    
    # Determine target: edit ID or conversation ID
    target_edit_id = getattr(args, "edit_id", None)
    target_conv_id = getattr(args, "conv", None)
    
    if not target_edit_id and not target_conv_id:
        print(f"Error: Must specify either --edit-id or --conv for {action_name} command.")
        return
    
    log_dir = history_root / LOGS_DIR
    if not log_dir.is_dir():
        print("No history logs found.")
        return
    
    # Track success and failures
    success_count = 0
    fail_count = 0
    
    # Track which conversations need re-apply (for reject)
    target_conv_ids = set()
    
    # Process by edit_id if specified
    if target_edit_id:
        log.info(f"Looking for edits matching ID prefix: {target_edit_id}")
        found_matches = False
        
        # Check all log files for matching edit_id
        log_files = list(log_dir.glob("*.log"))
        for log_file in log_files:
            log_lock = None
            try:
                log_lock = FileLock(str(log_file))
                with log_lock:
                    # Read log file and find matching entries
                    try:
                        entries = read_log_file(log_file)
                    except HistoryError as e:
                        log.error(f"Failed to read log file {log_file}: {e}")
                        fail_count += 1
                        continue
                    
                    # Check all entries for matching edit_id
                    for entry in entries:
                        edit_id = entry.get("edit_id", "")
                        # Match if edit_id starts with target
                        if edit_id.startswith(target_edit_id):
                            found_matches = True
                            # Track conversation ID for re-apply if rejecting
                            if not accept_mode:
                                conv_id = entry.get("conversation_id")
                                if conv_id:
                                    target_conv_ids.add(conv_id)
                            
                            # Only update if different from current status
                            current_status = entry.get("status", "unknown")
                            new_status = "accepted" if accept_mode else "rejected"
                            if current_status != new_status:
                                entry["status"] = new_status
                                log.info(f"Marking edit {edit_id} as {new_status}")
                                try:
                                    write_log_file(log_file, entries)
                                    success_count += 1
                                    print(f"Updated edit {edit_id} status to {new_status}")
                                except HistoryError as e:
                                    log.error(f"Failed to write log file {log_file}: {e}")
                                    fail_count += 1
                            else:
                                log.info(f"Edit {edit_id} already has status {current_status}, skipping")
                                print(f"Edit {edit_id} already has status {current_status}, skipping")
                                success_count += 1  # Count as success since it's already in the desired state
                            
                            # We've handled this entry, can break out of this log file's entries
                            break
            except (TimeoutError, Exception) as e_lock:
                log.error(f"Failed to process log file {log_file} due to lock/read error: {e_lock}")
                fail_count += 1
            finally:
                if log_lock:
                    log_lock.release()
        
        if not found_matches:
            print(f"No edits found matching ID prefix: {target_edit_id}")
            return
    
    # Process by conversation ID if specified
    elif target_conv_id:
        log.info(f"Looking for edits in conversation matching: {target_conv_id}")
        found_matches = False
        
        # Check all log files for matching conversation_id
        log_files = list(log_dir.glob("*.log"))
        for log_file in log_files:
            log_lock = None
            edit_ids_to_update = []
            try:
                log_lock = FileLock(str(log_file))
                with log_lock:
                    # Read log file and find matching entries
                    try:
                        entries = read_log_file(log_file)
                    except HistoryError as e:
                        log.error(f"Failed to read log file {log_file}: {e}")
                        fail_count += 1
                        continue
                    
                    # First pass: identify entries to update and track their conversation IDs
                    updates_needed = False
                    for entry in entries:
                        conv_id = entry.get("conversation_id", "")
                        # Match conversation ID (start with, end with, or contain)
                        if (conv_id.startswith(target_conv_id) or 
                            conv_id.endswith(target_conv_id) or 
                            target_conv_id.lower() in conv_id.lower()):
                            found_matches = True
                            
                            # Skip if already in the desired state
                            current_status = entry.get("status", "unknown")
                            new_status = "accepted" if accept_mode else "rejected"
                            
                            # For accept, update only pending edits
                            # For reject, update both pending and accepted edits
                            if (accept_mode and current_status == "pending") or \
                               (not accept_mode and current_status in ["pending", "accepted"]):
                                if current_status != new_status:
                                    edit_ids_to_update.append(entry.get("edit_id"))
                                    updates_needed = True
                            
                            # Always track conversation ID for reject
                            if not accept_mode and conv_id:
                                target_conv_ids.add(conv_id)
                    
                    # Second pass: update all matching entries in this log file
                    if updates_needed:
                        for entry in entries:
                            if entry.get("edit_id") in edit_ids_to_update:
                                new_status = "accepted" if accept_mode else "rejected"
                                entry["status"] = new_status
                                log.debug(f"Marking edit {entry.get('edit_id')} as {new_status}")
                        
                        try:
                            write_log_file(log_file, entries)
                            success_count += len(edit_ids_to_update)
                            for edit_id in edit_ids_to_update:
                                print(f"Updated edit {edit_id} status to {'accepted' if accept_mode else 'rejected'}")
                        except HistoryError as e:
                            log.error(f"Failed to write log file {log_file}: {e}")
                            fail_count += len(edit_ids_to_update)
            except (TimeoutError, Exception) as e_lock:
                log.error(f"Failed to process log file {log_file} due to lock/read error: {e_lock}")
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


def handle_show(
    args: argparse.Namespace, workspace_root: Path, history_root: Path
) -> None:
    """Handle the show command to display diffs for an edit or conversation."""
    log.info("Starting show operation...")
    
    # Get the identifier (edit_id or conversation_id) from args
    identifier = args.identifier
    if not identifier:
        print("Error: Must specify an edit ID or conversation ID.")
        return
    
    log_dir = history_root / LOGS_DIR
    if not log_dir.is_dir():
        print("No history logs found.")
        return
    
    # Variables to track what we find
    found_entries = []
    
    # Check all log files for matching entries
    log_files = sorted(log_dir.glob("*.log"), key=os.path.getmtime, reverse=True)
    for log_file in log_files:
        try:
            # Read the log file
            entries = read_log_file(log_file)
            
            # Look for matches in two ways:
            # 1. If identifier matches start of an edit_id, it's a specific edit request
            # 2. If identifier matches part of a conversation_id, show all edits in that conversation
            
            edit_match = False
            for entry in entries:
                edit_id = entry.get("edit_id", "")
                conv_id = entry.get("conversation_id", "")
                
                # Check if this is an edit_id match
                if edit_id.startswith(identifier):
                    edit_match = True
                    found_entries.append((entry, log_file))
                    break  # Only need the first matching edit
                
                # Check if this is a conversation_id match
                if not edit_match and (
                    conv_id.startswith(identifier) or 
                    conv_id.endswith(identifier) or
                    identifier.lower() in conv_id.lower()
                ):
                    found_entries.append((entry, log_file))
        
        except Exception as e:
            print(f"{COLOR_YELLOW}Warning: Could not read log file {log_file.name}: {e}{COLOR_RESET}", file=sys.stderr)
            continue
    
    if not found_entries:
        print(f"No entries found matching identifier: {identifier}")
        return
    
    # Sort entries by timestamp if multiple found (e.g., for conversation)
    found_entries.sort(key=lambda x: x[0].get("timestamp", "0"))
    
    # Display the diffs for all found entries
    count = len(found_entries)
    is_conversation = count > 1
    
    if is_conversation:
        print(f"Found {count} edits matching conversation {identifier}:\n")
    else:
        print(f"Found edit matching ID {identifier}:\n")
    
    for i, (entry, log_file) in enumerate(found_entries):
        print("=" * 70)
        if is_conversation:
            print(f"Edit {i+1}/{count}:")
        
        # Display edit info
        print(f"Edit ID:         {entry['edit_id']}")
        print(f"Conversation ID: {entry['conversation_id']}")
        print(f"Timestamp:       {entry.get('timestamp', 'N/A')}")
        try:
            file_rel = get_relative_path(Path(entry["file_path"]).resolve(), workspace_root)
        except Exception:
            file_rel = entry.get("file_path", "N/A")
        print(f"File:            {file_rel}")
        print(f"Operation:       {entry.get('operation', 'N/A')}")
        print(f"Status:          {entry.get('status', 'N/A')}")
        print("-" * 70)
        
        # Show diff if available
        diff_rel_path = entry.get("diff_file")
        if diff_rel_path:
            diff_abs_path = history_root / diff_rel_path
            if diff_abs_path.is_file():
                try:
                    diff_content = diff_abs_path.read_text(encoding="utf-8")
                    print_diff_with_color(diff_content)
                except Exception as e:
                    print(f"{COLOR_RED}Error reading diff file {diff_abs_path}: {e}{COLOR_RESET}", file=sys.stderr)
            else:
                print(f"{COLOR_YELLOW}Diff file not found: {diff_rel_path}{COLOR_RESET}")
        else:
            if entry.get("operation") in ["edit", "replace", "create"]:
                print(f"{COLOR_YELLOW}No diff file associated with this '{entry.get('operation')}' operation.{COLOR_RESET}")
            else:
                print(f"({entry.get('operation')} operation - no diff expected)")
    
    print("\n" + "=" * 70)
    if is_conversation:
        print(f"End of {count} edits for conversation {identifier}")
    else:
        print(f"End of edit {identifier}")


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
                    conv_match = True
                    if target_conv_prefix:
                        conv_id = entry.get("conversation_id", "")
                        conv_match = conv_id.startswith(target_conv_prefix) or conv_id.endswith(target_conv_prefix)
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
                conversation_id = entry["conversation_id"]
                log_lock = FileLock(str(log_file_to_update))
                try:
                    with log_lock:
                        if update_entry_status(
                            log_file_to_update, edit_id_to_update, "rejected"
                        ):
                            print("Marked as rejected.")
                        else:
                            print(
                                f"{COLOR_RED}Failed to mark as rejected. Check logs.{COLOR_RESET}"
                            )
                            break  # Skip re-apply if update failed
                except (TimeoutError, Exception) as e_lock:
                    print(
                        f"{COLOR_RED}Failed to acquire lock or update log {log_file_to_update}: {e_lock}{COLOR_RESET}"
                    )
                    break  # Skip re-apply if update failed
                finally:
                    if log_lock:
                        log_lock.release()

                # Trigger re-apply for the conversation
                print("Re-applying state for conversation...")
                if reapply_conversation_state(conversation_id, history_root, workspace_root):
                    print("State re-applied successfully.")
                else:
                    print(
                        f"{COLOR_RED}Errors occurred during state reconstruction. Manual review advised.{COLOR_RESET}"
                    )
                break  # Move to next edit
            elif action in ["s", "skip"]:
                print("Skipping to next edit.")
                break  # Move to next edit without changes
            elif action in ["q", "quit"]:
                print("Quitting review.")
                quit_review = True
                break  # Exit inner loop, outer loop will terminate
            else:
                print("Invalid input. Please enter 'a', 'r', 's', or 'q'.")

    if not quit_review:
        print("\nReview complete.")


def print_diff_with_color(diff_content: str) -> None:
    """Print a diff with colored output for additions, deletions, etc."""
    if not diff_content:
        print(f"{COLOR_YELLOW}(Empty diff){COLOR_RESET}")
        return
    
    for line in diff_content.splitlines():
        if line.startswith('+') and not line.startswith('+++'):
            print(f"{COLOR_GREEN}{line}{COLOR_RESET}")
        elif line.startswith('-') and not line.startswith('---'):
            print(f"{COLOR_RED}{line}{COLOR_RESET}")
        elif line.startswith('@@ '):
            print(f"{COLOR_CYAN}{line}{COLOR_RESET}")
        elif line.startswith('diff ') or line.startswith('index ') or \
             line.startswith('--- ') or line.startswith('+++ '):
            print(f"{COLOR_BLUE}{line}{COLOR_RESET}")
        else:
            print(line)


def handle_status(
    args: argparse.Namespace, workspace_root: Path, history_root: Path
) -> None:
    """Handle the status command to show edit history status."""
    log.info("Getting edit history status...")

    log_dir = history_root / LOGS_DIR
    if not log_dir.is_dir():
        print("No history logs found.")
        return

    # Parse time filter if provided
    time_filter_seconds = 0
    if args.time:
        try:
            time_str = args.time.lower()
            # Parse format like "3d1h30m15s" into seconds
            total_seconds = 0
            current_num = ""
            for char in time_str:
                if char.isdigit():
                    current_num += char
                elif char == 'd' and current_num:
                    total_seconds += int(current_num) * 86400  # days to seconds
                    current_num = ""
                elif char == 'h' and current_num:
                    total_seconds += int(current_num) * 3600  # hours to seconds
                    current_num = ""
                elif char == 'm' and current_num:
                    total_seconds += int(current_num) * 60  # minutes to seconds
                    current_num = ""
                elif char == 's' and current_num:
                    total_seconds += int(current_num)  # seconds
                    current_num = ""
            # If there's a number without a unit, assume seconds
            if current_num:
                total_seconds += int(current_num)
            time_filter_seconds = total_seconds
        except ValueError as e:
            print(f"{COLOR_YELLOW}Warning: Invalid time filter format: {e}. Ignoring time filter.{COLOR_RESET}")
    
    # Calculate cutoff time if time filter is active
    cutoff_time = None
    if time_filter_seconds > 0:
        cutoff_time = datetime.now(timezone.utc) - timedelta(seconds=time_filter_seconds)
    
    # Get all log files, sort by modification time (newest first)
    log_files = sorted(log_dir.glob("*.log"), key=os.path.getmtime, reverse=True)
    
    # Extract and collect entries
    all_entries = []
    for log_file in log_files:
        try:
            entries = read_log_file(log_file)
            for entry in entries:
                # Apply filters
                include_entry = True
                
                # Filter by conversation ID if specified
                if args.conv and include_entry:
                    conv_id = entry.get("conversation_id", "")
                    include_entry = args.conv.lower() in conv_id.lower() or conv_id.startswith(args.conv) or conv_id.endswith(args.conv)
                
                # Filter by file path if specified
                if args.file and include_entry:
                    file_path = entry.get("file_path", "")
                    include_entry = args.file.lower() in file_path.lower()
                
                # Filter by status if specified
                if args.status and include_entry:
                    entry_status = entry.get("status", "")
                    include_entry = entry_status == args.status
                
                # Filter by operation if specified
                if args.op and include_entry:
                    operation = entry.get("operation", "")
                    include_entry = operation.lower() == args.op.lower()
                
                # Filter by time if specified
                if cutoff_time and include_entry:
                    entry_time_str = entry.get("timestamp", "")
                    try:
                        # Parse ISO format timestamp
                        entry_time = datetime.fromisoformat(entry_time_str.replace('Z', '+00:00'))
                        include_entry = entry_time > cutoff_time
                    except ValueError:
                        # If timestamp can't be parsed, include anyway
                        log.warning(f"Could not parse timestamp: {entry_time_str}")
                
                if include_entry:
                    # Add log file path to entry for reference
                    entry["_log_file"] = log_file
                    all_entries.append(entry)
        
        except Exception as e:
            print(f"{COLOR_YELLOW}Warning: Could not read log file {log_file.name}: {e}{COLOR_RESET}", file=sys.stderr)
            continue
    
    # Sort entries by timestamp (oldest first)
    all_entries.sort(key=lambda x: x.get("timestamp", "0"), reverse=False)
    
    # Limit number of entries to display
    entries_to_show = all_entries[:args.limit]
    
    if not entries_to_show:
        print("No matching edit history entries found.")
        return
    
    # Display entries
    print(f"Found {len(all_entries)} edits{f' (showing {min(args.limit, len(all_entries))})' if len(all_entries) > args.limit else ''}:\n")
    print(f"{'ID':<11} {'Operation':<10} {'Status':<10} {'File':<30} {'Conv ID':<12} {'Time':<19}")
    print("-" * 98)
    
    for entry in entries_to_show:
        # Format each field
        edit_id = entry.get("edit_id", "")[:8]
        operation = entry.get("operation", "N/A")
        status = entry.get("status", "N/A")
        # Format status with color
        if status == "pending":
            status_str = f"{COLOR_YELLOW}{status}{COLOR_RESET}"
        elif status == "accepted":
            status_str = f"{COLOR_GREEN}{status}{COLOR_RESET}"
        elif status == "rejected":
            status_str = f"{COLOR_RED}{status}{COLOR_RESET}"
        else:
            status_str = status
        
        # Get relative file path for display
        try:
            file_path = entry.get("file_path", "N/A")
            if file_path != "N/A":
                file_rel = get_relative_path(Path(file_path).resolve(), workspace_root)
                # Truncate if too long
                if len(file_rel) > 30:
                    file_rel = "..." + file_rel[-27:]
            else:
                file_rel = "N/A"
        except Exception:
            file_rel = entry.get("file_path", "N/A")
            if len(file_rel) > 30:
                file_rel = "..." + file_rel[-27:]
        
        conv_id = entry.get("conversation_id", "N/A")
        if len(conv_id) > 10:
            conv_id = conv_id[:8] + ".."
        
        # Format timestamp
        timestamp = entry.get("timestamp", "N/A")
        if timestamp != "N/A":
            try:
                # Parse ISO format and make it more readable
                dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                timestamp = dt.strftime('%Y-%m-%d %H:%M:%S')
            except ValueError:
                pass  # Keep original if parsing fails
        
        print(f"{edit_id:<11} {operation:<10} {status_str:<19} {file_rel:<30} {conv_id:<12} {timestamp}")
    
    print("\nUse 'mcpdiff show <edit_id>' or 'mcpdiff show <conv_id>' to see details.")


# --- Main Argparse Setup ---
def main():
    parser = argparse.ArgumentParser(
        description="MCP Diff Tool: Review and manage LLM file edits.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  mcpdiff status                     # Show recent history status
  mcpdiff st                         # Shorthand for status
  mcpdiff status --conv 17... --file src/main.py --status pending
  mcpdiff status -c 17... -f src/main.py
  mcpdiff show <edit_id_prefix>      # Show diff for a specific edit
  mcpdiff show <conv_id_prefix>      # Show all diffs for a conversation
  mcpdiff accept -e <edit_id_prefix> # Accept a specific edit
  mcpdiff a -e <edit_id_prefix>      # Shorthand for accept
  mcpdiff accept -c <conv_id_prefix> # Accept all pending edits for a conversation
  mcpdiff reject -e <edit_id_prefix> # Reject an edit (re-applies conversation)
  mcpdiff r -c <conv_id_prefix>      # Shorthand for reject conversation
  mcpdiff review                     # Interactively review pending edits
  mcpdiff v                          # Shorthand for review
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
    parser_status = subparsers.add_parser(
        "status", aliases=["st"], help="Show edit history status."
    )
    parser_status.add_argument("--conv", "-c", help="Filter by conversation ID prefix or suffix.")
    parser_status.add_argument("--file", "-f", help="Filter by file path substring.")
    parser_status.add_argument(
        "--status",
        choices=["pending", "accepted", "rejected"],
        help="Filter by status.",
    )
    parser_status.add_argument(
        "-n", "--limit", type=int, default=50, help="Limit entries shown (default: 50)"
    )
    # Add time filter options
    parser_status.add_argument(
        "--time", 
        help="Filter by time (e.g., 30s, 5m, 1h, 3d1h for edits made in the last X time)"
    )
    # Add operation filter
    parser_status.add_argument(
        "--op", 
        help="Filter by operation type (e.g., edit, create, delete, move, replace)"
    )
    parser_status.set_defaults(func=handle_status)

    # show
    parser_show = subparsers.add_parser(
        "show", aliases=["sh", "s"],
        help="Show diff for an edit_id or all diffs for a conversation_id (using prefix).",
    )
    parser_show.add_argument(
        "identifier", help="The edit_id or conversation_id prefix to show."
    )
    parser_show.set_defaults(func=handle_show)

    # accept
    parser_accept = subparsers.add_parser("accept", aliases=["a"], help="Mark edits as accepted.")
    group_accept = parser_accept.add_mutually_exclusive_group(required=True)
    group_accept.add_argument(
        "-e", "--edit-id", help="The specific edit_id prefix to accept."
    )
    group_accept.add_argument(
        "-c", "--conv", help="Accept all pending edits for a conversation_id prefix or suffix."
    )
    parser_accept.set_defaults(func=handle_accept)

    # reject
    parser_reject = subparsers.add_parser(
        "reject", aliases=["r"], help="Mark edits as rejected and revert/re-apply changes."
    )
    group_reject = parser_reject.add_mutually_exclusive_group(required=True)
    group_reject.add_argument(
        "-e", "--edit-id", help="The specific edit_id prefix to reject."
    )
    group_reject.add_argument(
        "-c",
        "--conv",
        help="Reject all pending/accepted edits for a conversation_id prefix or suffix.",
    )
    parser_reject.set_defaults(func=handle_reject)

    # review
    parser_review = subparsers.add_parser(
        "review", aliases=["v"], help="Interactively review pending edits."
    )
    parser_review.add_argument(
        "--conv", "-c", help="Review pending edits only for this conversation ID prefix or suffix."
    )
    parser_review.set_defaults(func=handle_review)
    
    # help
    parser_help = subparsers.add_parser(
        "help", aliases=["h"], help="Show help information."
    )
    parser_help.set_defaults(func=lambda *args, **kwargs: parser.print_help())

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
        # MODIFIED: Allow working in a subdirectory of a directory containing .mcp
        if not is_path_within_directory(cwd, workspace_root):
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


# Add this new function before main()
def generate_hex_timestamp() -> str:
    """Generate a conversation ID as hexadecimal representation of the current Unix epoch time."""
    epoch_time = int(time.time())
    return format(epoch_time, 'x')  # Convert to hex without '0x' prefix


if __name__ == "__main__":
    main()
