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
from typing import List, Dict, Any, Optional, Tuple, Set, Union

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
            # Read and hash file in chunks to handle large files efficiently
            while chunk := f.read(8192):
                hasher.update(chunk)
        return hasher.hexdigest()
    except FileNotFoundError:
        log.debug(f"File not found for hashing: {file_path}")
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
                self._force_cleanup()
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
            # First try using standard file operations
            if self.lock_file_path.exists():
                try:
                    self.lock_file_path.unlink()
                    log.debug(f"Removed stale lock file: {self.lock_file_path}")
                except (OSError, PermissionError) as e:
                    log.warning(f"Could not remove lock file {self.lock_file_path}: {e}")
                    # Try more aggressive cleanup with rm command if available
                    try:
                        subprocess.run(["rm", "-f", str(self.lock_file_path)], check=False)
                        log.debug(f"Forcibly removed lock file using rm: {self.lock_file_path}")
                    except Exception as e2:
                        log.warning(f"Failed forcible removal of lock file: {e2}")
                        
            if self.lock_dir.exists():
                try:
                    self.lock_dir.rmdir()
                    log.debug(f"Removed stale lock directory: {self.lock_dir}")
                except (OSError, PermissionError) as e:
                    log.warning(f"Could not remove lock directory {self.lock_dir}: {e}")
                    # Try more aggressive cleanup with rm command if available
                    try:
                        subprocess.run(["rm", "-rf", str(self.lock_dir)], check=False)
                        log.debug(f"Forcibly removed lock directory using rm -rf: {self.lock_dir}")
                    except Exception as e2:
                        log.warning(f"Failed forcible removal of lock directory: {e2}")
        except Exception as e:
            log.warning(f"Failed to force cleanup lock: {e}")

    def acquire(self, timeout=None):
        """Acquire the lock with timeout."""
        if timeout is None:
            timeout = LOCK_TIMEOUT  # Use global timeout if none specified
        
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
def read_log_file(log_file_path: Path, lock_timeout=None) -> List[Dict[str, Any]]:
    """Reads a JSON Lines log file safely."""
    entries = []
    if not log_file_path.is_file():
        log.debug(f"Log file does not exist: {log_file_path}")
        return entries
    lock = FileLock(str(log_file_path))  # Use lock for reading consistency
    try:
        lock.acquire(timeout=lock_timeout)  # Use provided timeout
        with open(log_file_path, "r", encoding="utf-8") as f:
            log_content = f.read()
            log.debug(f"Raw log file content ({len(log_content)} bytes): {log_content[:200]}...")
            
            for i, line in enumerate(log_content.splitlines()):
                line = line.strip()
                if not line:
                    continue
                try:
                    log.debug(f"Processing line {i+1}: {line[:100]}...")
                    entry = json.loads(line)
                    entries.append(entry)
                except json.JSONDecodeError as e:
                    log.warning(f"Invalid JSON on line {i + 1} in {log_file_path}: {e}")
                    log.warning(f"Problematic line: {line[:200]}...")
        lock.release()
        log.debug(f"Successfully read {len(entries)} entries from {log_file_path}")
        return entries
    except (IOError, TimeoutError) as e:
        log.error(f"Error reading log file {log_file_path}: {e}")
        if lock.is_locked:
            lock.release()
        raise HistoryError(f"Could not read log file: {log_file_path}") from e


def write_log_file(log_file_path: Path, entries: List[Dict[str, Any]], lock_timeout=None):
    """Writes a list of entries to a JSON Lines log file atomically."""
    # Sort entries by index before writing to maintain order if modified
    entries.sort(key=lambda x: x.get("tool_call_index", float("inf")))

    temp_path = log_file_path.with_suffix(
        log_file_path.suffix + ".tmp" + str(os.getpid())
    )
    lock = FileLock(str(log_file_path))
    try:
        lock.acquire(timeout=lock_timeout)  # Use provided timeout
        log_file_path.parent.mkdir(parents=True, exist_ok=True)
        with open(temp_path, "w", encoding="utf-8") as f:
            for entry in entries:
                json.dump(entry, f, separators=(",", ":"))
                f.write("\n")
        # Atomic rename/replace (should work on Unix)
        os.replace(temp_path, log_file_path)
        log.debug(f"Successfully wrote log file: {log_file_path}")
        lock.release()
    except (IOError, TimeoutError) as e:
        log.error(f"Error writing log file {log_file_path}: {e}")
        if temp_path.exists():
            try:
                os.remove(temp_path)
            except OSError:
                pass
        if lock.is_locked:
            lock.release()
        raise HistoryError(f"Could not write log file: {log_file_path}") from e
    except Exception as e:
        if temp_path.exists():
            try:
                os.remove(temp_path)
            except OSError:
                pass
        if lock.is_locked:
            lock.release()
        log.exception(f"Unexpected error writing log file {log_file_path}: {e}")
        raise HistoryError(f"Unexpected error writing log file: {log_file_path}") from e


def cleanup_stale_locks(history_root: Path) -> int:
    """Clean up any stale lock files and directories under the history directory.
    Returns the number of locks cleaned up."""
    
    cleaned_count = 0
    
    # Find all .lockdir directories
    for lockdir in history_root.glob("**/*.lockdir"):
        try:
            lock_file = lockdir / "pid.lock"
            
            # Check if the lock file exists
            if not lock_file.exists():
                # Empty lock directory - clean up
                log.debug(f"Cleaning up orphaned lock directory: {lockdir}")
                try:
                    lockdir.rmdir()
                    cleaned_count += 1
                except OSError:
                    try:
                        # Try with rm -rf if available
                        subprocess.run(["rm", "-rf", str(lockdir)], check=False)
                        cleaned_count += 1
                    except Exception:
                        pass
                continue
                
            # Try to read PID from lock file
            try:
                pid_str = lock_file.read_text().strip()
                if not pid_str:
                    # Empty PID - clean up
                    log.debug(f"Cleaning up lock with empty PID: {lockdir}")
                    lock_file.unlink(missing_ok=True)
                    lockdir.rmdir()
                    cleaned_count += 1
                    continue
                    
                # Check if process exists
                pid = int(pid_str)
                try:
                    os.kill(pid, 0)  # Signal 0 doesn't kill but checks if process exists
                    # Process exists, lock may be valid
                    log.debug(f"Process with PID {pid} exists for lock {lockdir}, leaving alone")
                except OSError:
                    # Process doesn't exist - clean up
                    log.debug(f"Cleaning up stale lock for PID {pid}: {lockdir}")
                    lock_file.unlink(missing_ok=True)
                    lockdir.rmdir()
                    cleaned_count += 1
            except (ValueError, IOError, OSError) as e:
                # Error reading or parsing PID - clean up
                log.debug(f"Error checking lock {lockdir}, cleaning up: {e}")
                try:
                    lock_file.unlink(missing_ok=True)
                    lockdir.rmdir()
                    cleaned_count += 1
                except OSError:
                    try:
                        # Try with rm -rf if available
                        subprocess.run(["rm", "-rf", str(lockdir)], check=False)
                        cleaned_count += 1
                    except Exception:
                        pass
        except Exception as e:
            log.warning(f"Failed to check/clean lock {lockdir}: {e}")
            
    return cleaned_count


# --- Utility Functions for Commands ---
def find_all_entries(history_root: Path, lock_timeout: int = LOCK_TIMEOUT) -> List[Dict[str, Any]]:
    """Find all edit history entries from log files."""
    all_entries = []
    
    # Find all log files in the logs directory
    logs_dir = history_root / LOGS_DIR
    if not logs_dir.is_dir():
        return []
    
    log_files = list(logs_dir.glob("*.log"))
    log.debug(f"Found {len(log_files)} log files in {logs_dir}")
    
    for log_file in log_files:
        try:
            log.debug(f"Reading log file: {log_file}")
            entries = read_log_file(log_file, lock_timeout=lock_timeout)
            log.debug(f"Found {len(entries)} entries in {log_file}")
            all_entries.extend(entries)
        except Exception as e:
            log.warning(f"Error reading log file {log_file}: {e}")
            
    # Sort entries by timestamp (newest first)
    def sort_key(entry):
        """Return a sortable key from the entry timestamp."""
        timestamp = entry.get("timestamp", 0)
        if not timestamp:
            return 0
            
        try:
            if isinstance(timestamp, str):
                if 'T' in timestamp and 'Z' in timestamp:
                    # Parse ISO-like timestamp: "2025-03-31T154939.993Z"
                    # Convert to a comparable string format: "20250331154939.993"
                    date_part, time_part = timestamp.split('T')
                    time_part = time_part.rstrip('Z')
                    date_str = date_part.replace('-', '')
                    return date_str + time_part
                else:
                    return float(timestamp)
            else:
                return float(timestamp)
        except (ValueError, TypeError):
            return 0
                
    try:
        all_entries.sort(key=sort_key, reverse=False)  # Sort from oldest to latest
    except Exception as e:
        log.warning(f"Error sorting entries by timestamp: {e}")
        # Fall back to unsorted if we can't sort by timestamp
        
    log.debug(f"Total entries found: {len(all_entries)}")
    return all_entries
    
def filter_entries(
    entries: List[Dict[str, Any]],
    conv_id: Optional[str] = None,
    file_path: Optional[str] = None,
    status: Optional[str] = None,
    time_filter: Optional[str] = None,
    op_type: Optional[str] = None,
    limit: int = 50,
) -> List[Dict[str, Any]]:
    """Filter entries based on criteria."""
    filtered = entries.copy()
    
    # Filter by conversation ID (prefix or suffix match)
    if conv_id:
        filtered = [
            entry for entry in filtered 
            if entry.get("conversation_id") and 
            (entry["conversation_id"].startswith(conv_id) or entry["conversation_id"].endswith(conv_id))
        ]
        
    # Filter by file path substring
    if file_path:
        filtered = [
            entry for entry in filtered
            if entry.get("file_path") and file_path in entry["file_path"]
        ]
        
    # Filter by status
    if status:
        filtered = [
            entry for entry in filtered
            if entry.get("status") == status
        ]
        
    # Filter by operation type
    if op_type:
        filtered = [
            entry for entry in filtered
            if entry.get("operation") == op_type
        ]
        
    # Filter by time (e.g., 30s, 5m, 1h, 3d1h)
    if time_filter:
        current_time = datetime.now(timezone.utc).timestamp()
        seconds = parse_time_filter(time_filter)
        if seconds:
            filtered = [
                entry for entry in filtered
                if entry.get("timestamp") and current_time - entry["timestamp"] <= seconds
            ]
            
    # Apply limit
    return filtered[:limit]
    
def parse_time_filter(time_str: str) -> Optional[int]:
    """Parse a time filter string like 30s, 5m, 1h, 3d1h into seconds."""
    pattern = r'(\d+)([smhd])'
    matches = re.findall(pattern, time_str)
    
    if not matches:
        log.warning(f"Invalid time filter format: {time_str}")
        return None
        
    seconds = 0
    for value, unit in matches:
        value = int(value)
        if unit == 's':
            seconds += value
        elif unit == 'm':
            seconds += value * 60
        elif unit == 'h':
            seconds += value * 3600
        elif unit == 'd':
            seconds += value * 86400
            
    return seconds
    
def format_timestamp(timestamp: Union[float, str]) -> str:
    """Format a timestamp in a human-readable way."""
    try:
        # Convert string timestamp to float if needed
        if isinstance(timestamp, str):
            if 'T' in timestamp and 'Z' in timestamp:
                # Parse ISO-like timestamp format: "2025-03-31T154939.993Z"
                date_part, time_part = timestamp.split('T')
                time_part = time_part.rstrip('Z')
                year, month, day = int(date_part[:4]), int(date_part[5:7]), int(date_part[8:10])
                
                # Handle time part with potential decimal seconds
                if '.' in time_part:
                    hour_min_sec, ms = time_part.split('.')
                else:
                    hour_min_sec, ms = time_part, '0'
                    
                hour = int(hour_min_sec[:2])
                minute = int(hour_min_sec[2:4])
                second = int(hour_min_sec[4:6]) if len(hour_min_sec) >= 6 else 0
                
                dt = datetime(year, month, day, hour, minute, second)
                return dt.strftime("%Y-%m-%d %H:%M:%S")
            else:
                # Try to convert to float if it's not in our special format
                timestamp = float(timestamp)
                dt = datetime.fromtimestamp(timestamp, timezone.utc).astimezone()
                now = datetime.now(timezone.utc).astimezone()
                diff = now - dt
                
                if diff.days == 0:
                    if diff.seconds < 60:
                        return "just now"
                    elif diff.seconds < 3600:
                        minutes = diff.seconds // 60
                        return f"{minutes}m ago"
                    else:
                        hours = diff.seconds // 3600
                        return f"{hours}h ago"
                elif diff.days == 1:
                    return "yesterday"
                elif diff.days < 7:
                    return f"{diff.days}d ago"
                else:
                    return dt.strftime("%Y-%m-%d")
    except (ValueError, TypeError, OSError):
        # Handle any conversion errors gracefully
        if isinstance(timestamp, str) and timestamp:
            # If it's a string that we couldn't convert, return it as is
            return timestamp
        return "unknown time"
        
def find_entry_by_id(entries: List[Dict[str, Any]], id_prefix: str) -> Optional[Dict[str, Any]]:
    """Find an entry by its ID prefix."""
    matching = [
        entry for entry in entries
        if entry.get("edit_id") and entry["edit_id"].startswith(id_prefix)
    ]
    
    if not matching:
        return None
    if len(matching) > 1:
        # Check if any match exactly
        exact_matches = [entry for entry in matching if entry["edit_id"] == id_prefix]
        if len(exact_matches) == 1:
            return exact_matches[0]
            
        # Display all matching entries and let the user select one
        print(f"{COLOR_RED}Ambiguous ID prefix '{id_prefix}' matches multiple entries:{COLOR_RESET}")
        print(f"{COLOR_CYAN}{'No.  Time':24}  {'Edit ID':8}  {'Conv ID':8}  {'Operation':9}  {'Status':8}  {'File Path'}{COLOR_RESET}")
        print("-" * 100)
        
        for i, entry in enumerate(matching):
            print(f"{COLOR_CYAN}[{i+1:2d}]{COLOR_RESET} {format_entry_summary(entry)}")
            
        # Ask the user to choose an entry
        try:
            choice = input(f"\n{COLOR_YELLOW}Enter number to select an entry (or 'q' to quit): {COLOR_RESET}")
            if choice.lower() in ['q', 'quit']:
                raise KeyboardInterrupt("Operation cancelled by user")
                
            choice_idx = int(choice) - 1
            if 0 <= choice_idx < len(matching):
                return matching[choice_idx]
            else:
                print(f"{COLOR_RED}Invalid selection.{COLOR_RESET}")
                raise IndexError("Invalid selection index")
        except (ValueError, IndexError):
            raise AmbiguousIDError(f"Could not determine which entry to use")
    
    return matching[0]
    
def find_entries_by_conversation(entries: List[Dict[str, Any]], conv_id_prefix: str) -> List[Dict[str, Any]]:
    """Find all entries for a conversation by ID prefix or suffix."""
    log.debug(f"Searching for entries with conversation ID matching: {conv_id_prefix}")
    # First try prefix match
    matching = [
        entry for entry in entries
        if entry.get("conversation_id") and entry["conversation_id"].startswith(conv_id_prefix)
    ]
    
    # If no prefix matches, try suffix match
    if not matching:
        log.debug(f"No prefix matches found, trying suffix match for: {conv_id_prefix}")
        matching = [
            entry for entry in entries
            if entry.get("conversation_id") and entry["conversation_id"].endswith(conv_id_prefix)
        ]
        
    log.debug(f"Found {len(matching)} entries for conversation ID matching: {conv_id_prefix}")
    # Sort by timestamp (oldest first) for proper ordering of operations
    matching.sort(key=lambda x: x.get("timestamp", 0))
    return matching
    
def update_entry_status(
    entry: Dict[str, Any], 
    status: str,
    history_root: Path,
    lock_timeout: int = LOCK_TIMEOUT
) -> bool:
    """Update the status of an entry in its log file."""
    if not entry or "edit_id" not in entry or "log_file" not in entry:
        log.error("Invalid entry data, missing edit_id or log_file")
        return False
        
    log_file_path = history_root / LOGS_DIR / entry["log_file"]
    if not log_file_path.exists():
        log.error(f"Log file not found: {log_file_path}")
        return False
        
    try:
        # Read all entries from the log file
        entries = read_log_file(log_file_path, lock_timeout=lock_timeout)
        
        # Find and update the specific entry
        updated = False
        for e in entries:
            if e.get("edit_id") == entry["edit_id"]:
                e["status"] = status
                e["updated_at"] = datetime.now(timezone.utc).timestamp()
                updated = True
                break
                
        if not updated:
            log.error(f"Entry {entry['edit_id']} not found in log file {log_file_path}")
            return False
            
        # Write back all entries
        write_log_file(log_file_path, entries, lock_timeout=lock_timeout)
        log.debug(f"Updated entry {entry['edit_id']} status to {status}")
        return True
        
    except Exception as e:
        log.error(f"Error updating entry status: {e}")
        return False
        
def get_diff_for_entry(entry: Dict[str, Any], history_root: Path) -> Optional[str]:
    """Get the diff content for an entry."""
    # Special case for MOVE operations, which often don't have a diff file
    if entry.get("operation", "").upper() == "MOVE":
        source = entry.get("source_path", "unknown")
        destination = entry.get("file_path", "unknown")
        return f"MOVE: {source} -> {destination}"
        
    if not entry or "edit_id" not in entry:
        log.debug(f"Missing edit_id in entry: {entry}")
        return None
    
    # Try direct path with edit_id first (most reliable)
    if "conversation_id" in entry:
        direct_path = history_root / DIFFS_DIR / entry["conversation_id"] / f"{entry['edit_id']}.diff"
        if direct_path.exists():
            try:
                with open(direct_path, "r", encoding="utf-8") as f:
                    return f.read()
            except Exception as e:
                log.error(f"Error reading direct diff file {direct_path}: {e}")
    
    # If no diff_file field or it's None, we've already tried the best option above
    if "diff_file" not in entry or entry["diff_file"] is None:
        log.debug(f"Missing or None diff_file in entry: {entry}")
        # Additional fallback - try searching for the diff file by edit_id
        for diff_dir in (history_root / DIFFS_DIR).glob("*"):
            if diff_dir.is_dir():
                potential_path = diff_dir / f"{entry['edit_id']}.diff"
                if potential_path.exists():
                    try:
                        with open(potential_path, "r", encoding="utf-8") as f:
                            return f.read()
                    except Exception as e:
                        log.error(f"Error reading found diff file {potential_path}: {e}")
                        
        return None
        
    # If we have the diff_file path in the entry, try several possible arrangements
    
    # 1. Try path with conversation_id directory
    if "conversation_id" in entry:
        try:
            conv_path = history_root / DIFFS_DIR / entry["conversation_id"] / entry["diff_file"]
            if conv_path.exists():
                try:
                    with open(conv_path, "r", encoding="utf-8") as f:
                        return f.read()
                except Exception as e:
                    log.error(f"Error reading conv_path diff file {conv_path}: {e}")
        except Exception as e:
            log.error(f"Error constructing path with conversation_id: {e}")
    
    # 2. Try direct path using diff_file
    try:
        direct_path = history_root / DIFFS_DIR / entry["diff_file"]
        if direct_path.exists():
            try:
                with open(direct_path, "r", encoding="utf-8") as f:
                    return f.read()
            except Exception as e:
                log.error(f"Error reading direct diff file {direct_path}: {e}")
    except Exception as e:
        log.error(f"Error constructing direct path: {e}")
    
    # 3. One last attempt - try assuming diff_file is the same as edit_id
    if "conversation_id" in entry:
        try:
            edit_id_path = history_root / DIFFS_DIR / entry["conversation_id"] / f"{entry['edit_id']}.diff"
            if edit_id_path.exists():
                try:
                    with open(edit_id_path, "r", encoding="utf-8") as f:
                        return f.read()
                except Exception as e:
                    log.error(f"Error reading edit_id diff file {edit_id_path}: {e}")
        except Exception as e:
            log.error(f"Error constructing edit_id path: {e}")
                
    log.debug(f"Could not find diff file for entry {entry.get('edit_id')}, tried multiple paths")
    return None

def print_diff_with_color(diff_content: str) -> None:
    """Print a diff with color highlighting."""
    if not diff_content:
        print("No diff content available.")
        return
        
    for line in diff_content.splitlines():
        if line.startswith("+") and not line.startswith("+++"):
            print(f"{COLOR_GREEN}{line}{COLOR_RESET}")
        elif line.startswith("-") and not line.startswith("---"):
            print(f"{COLOR_RED}{line}{COLOR_RESET}")
        elif line.startswith("@@"):
            print(f"{COLOR_CYAN}{line}{COLOR_RESET}")
        elif line.startswith("diff ") or line.startswith("--- ") or line.startswith("+++ "):
            print(f"{COLOR_BLUE}{line}{COLOR_RESET}")
        else:
            print(line)
            
def format_entry_summary(entry: Dict[str, Any], detailed: bool = False) -> str:
    """Format an entry for display in summaries."""
    if not entry:
        return "Invalid entry"
        
    # Use edit_id for ID field if present, limited to first 8 chars
    id_short = entry.get("edit_id", "")[:8] if entry.get("edit_id") else "no-id"
    conv_id = entry.get("conversation_id", "")
    conv_id_short = conv_id[:8] if conv_id else "N/A"
    
    # Get operation in lowercase
    op = entry.get("operation", "unknown").lower()
    file_path = entry.get("file_path", "unknown")
    
    # Get status in lowercase
    status = entry.get("status", "unknown").lower()
    timestamp = entry.get("timestamp", 0)
    time_str = format_timestamp(timestamp) if timestamp else "unknown"
    
    # Apply colors to status
    if status == "pending":
        status_colored = f"{COLOR_YELLOW}{status}{COLOR_RESET}"
    elif status == "accepted":
        status_colored = f"{COLOR_GREEN}{status}{COLOR_RESET}"
    elif status == "rejected":
        status_colored = f"{COLOR_RED}{status}{COLOR_RESET}"
    else:
        status_colored = status
    
    # Apply colors to operations
    if op == "edit":
        op_colored = f"{COLOR_BLUE}{op}{COLOR_RESET}"
    elif op == "create":
        op_colored = f"{COLOR_GREEN}{op}{COLOR_RESET}"
    elif op == "replace":
        op_colored = f"{COLOR_YELLOW}{op}{COLOR_RESET}"
    elif op == "delete":
        op_colored = f"{COLOR_RED}{op}{COLOR_RESET}"
    elif op == "move" or op == "rename":
        op_colored = f"{COLOR_CYAN}{op}{COLOR_RESET}"
        file_path = f"{entry.get('source_path', '')} -> {file_path}"
    else:
        op_colored = op
        
    # Calculate the length of the operation string without ANSI color codes
    op_length = len(op)
    status_length = len(status)
    
    # Fixed width columns for alignment: Time  Edit ID  Conv ID  Operation  Status  File path
    # Pad the operation field to ensure consistent column width
    op_padding = max(9 - op_length, 0)  # Ensure at least 10 chars for op column
    status_padding = max(8 - status_length, 0)  # Ensure at least 10 chars for status column
    
    summary = f"{time_str:19}  {id_short:8}  {conv_id_short:8}  {op_colored}{' ' * op_padding}  {status_colored}{' ' * status_padding}  {file_path}"
    
    if detailed:
        # Add additional details for detailed view
        tool = entry.get("tool_name", entry.get("tool", ""))
        source_path = entry.get("source_path", "")
        tool_call_index = entry.get("tool_call_index", "")
        
        summary += f"\nTool: {tool}\n"

    return summary
    
def apply_or_revert_edit(
    entry: Dict[str, Any],
    workspace_root: Path,
    history_root: Path,
    is_revert: bool = False
) -> bool:
    """Apply or revert an edit based on its diff."""
    if not entry or "edit_id" not in entry:
        log.error("Invalid entry data, missing edit_id")
        return False
        
    operation = entry.get("operation", "").lower()
    file_path_str = entry.get("file_path", "")
    
    if not file_path_str:
        log.error(f"Missing file_path in entry {entry['edit_id']}")
        return False
        
    file_path = workspace_root / file_path_str
    
    # For operations requiring a diff file, check that it exists
    if "diff_file" not in entry or entry["diff_file"] is None:
        log.warning(f"No diff file for entry {entry['edit_id']}, checking if we can proceed")
        # We can still handle some operations without a diff file
        if not (
            (operation == "create" and is_revert) or  # Reverting a create (just delete)
            (operation == "delete" and is_revert) or  # Reverting a delete (restore from checkpoint)
            (operation == "move")                     # Move operations don't strictly need a diff
        ):
            log.error(f"Cannot {('revert' if is_revert else 'apply')} {operation} without a diff file")
            return False
    else:
        # Only try to access the diff file if it exists
        diff_file_path = history_root / DIFFS_DIR / entry["diff_file"]
        if not diff_file_path.exists():
            log.error(f"Diff file not found: {diff_file_path}")
            if not (
                (operation == "create" and is_revert) or 
                (operation == "delete" and is_revert) or 
                (operation == "move")
            ):
                return False
    
    try:
        # For 'create' operations, ensure diff exists or we have enough information
        if operation == "create" and is_revert:
            # Handle reverting a create (just delete the file)
            if file_path.exists():
                os.remove(file_path)
                log.debug(f"Deleted file {file_path}")
            else:
                log.warning(f"File already doesn't exist: {file_path}")
            return True
            
        # For 'delete' operations, we should have a checkpoint file
        elif operation == "delete" and is_revert:
            # Handle reverting a delete (restore from checkpoint)
            if "checkpoint_file" not in entry or not entry["checkpoint_file"]:
                log.error(f"Missing checkpoint file for delete operation in entry {entry['edit_id']}")
                return False
                
            checkpoint_path = history_root / entry["checkpoint_file"]
            if not checkpoint_path.exists():
                log.error(f"Checkpoint file not found: {checkpoint_path}")
                return False
                
            # Ensure target directory exists
            if not file_path.parent.exists():
                file_path.parent.mkdir(parents=True, exist_ok=True)
                
            # Copy content from checkpoint to target file
            shutil.copy2(checkpoint_path, file_path)
            log.debug(f"Restored file from checkpoint: {file_path}")
            return True
            
        # For move/rename operations
        elif operation == "move":
            if is_revert:
                # Reverting a move/rename
                if not file_path.exists():
                    log.error(f"Move destination not found: {file_path}")
                    return False
                    
                if not entry.get("source_path"):
                    log.error(f"Missing source_path for move operation in entry {entry['edit_id']}")
                    return False
                    
                source_path = workspace_root / entry["source_path"]
                # Ensure the parent directory exists
                if not source_path.parent.exists():
                    source_path.parent.mkdir(parents=True, exist_ok=True)
                    
                # Move file back to original location
                shutil.move(str(file_path), str(source_path))
                log.debug(f"Moved {file_path} back to {source_path}")
                return True
            else:
                # Re-applying a move (files will be in their original location)
                if not entry.get("source_path"):
                    log.error(f"Missing source_path for move operation in entry {entry['edit_id']}")
                    return False
                    
                source_path = workspace_root / entry["source_path"]
                if not source_path.exists():
                    log.error(f"Source file for move does not exist: {source_path}")
                    return False
                    
                # Ensure the parent directory exists
                if not file_path.parent.exists():
                    file_path.parent.mkdir(parents=True, exist_ok=True)
                    
                # Move file to the specified destination
                shutil.move(str(source_path), str(file_path))
                log.debug(f"Moved {source_path} to {file_path}")
                return True
        
        # For replace operations without diff, we need to handle specially
        elif operation == "replace" and ("diff_file" not in entry or entry["diff_file"] is None):
            log.warning(f"No diff file for replace operation {entry['edit_id']}")
            if is_revert:
                log.error("Cannot revert a replace operation without a diff or checkpoint")
                return False
            else:
                log.error("Cannot apply a replace operation without a diff")
                return False
                
        # For edits and other operations where we need to apply a patch
        elif "diff_file" in entry and entry["diff_file"] is not None:
            diff_file_path = history_root / DIFFS_DIR / entry["diff_file"]
            if not diff_file_path.exists():
                log.error(f"Diff file not found: {diff_file_path}")
                return False
                
            # Use git apply to apply/revert the diff
            git_command = ["git", "apply"]
            
            if is_revert:
                git_command.append("-R")  # Reverse the patch for revert
                
            git_command.extend(["-v", "--unsafe-paths", "--directory", str(workspace_root), str(diff_file_path)])
            
            log.debug(f"Running: {' '.join(git_command)}")
            result = subprocess.run(
                git_command, 
                capture_output=True, 
                text=True, 
                cwd=str(workspace_root)
            )
            
            if result.returncode != 0:
                log.error(f"Error {'reverting' if is_revert else 'applying'} diff: {result.stderr}")
                return False
                
            log.debug(f"Successfully {'reverted' if is_revert else 'applied'} diff for {entry['edit_id']}")
            return True
        else:
            log.error(f"Cannot handle operation {operation} for entry {entry['edit_id']}")
            return False
            
        return True
        
    except Exception as e:
        log.error(f"Error {'reverting' if is_revert else 'applying'} edit {entry['edit_id']}: {e}")
        return False

def handle_status(
    args: argparse.Namespace, workspace_root: Path, history_root: Path
) -> None:
    """Handle the status command to show recent history entries."""
    log.debug("Processing status command")
    
    # Find all entries
    all_entries = find_all_entries(history_root)
    
    if not all_entries:
        print(f"{COLOR_YELLOW}No edit history entries found.{COLOR_RESET}")
        return
        
    # Apply filters
    filtered_entries = filter_entries(
        all_entries,
        conv_id=args.conv,
        file_path=args.file,
        status=args.status,
        time_filter=args.time,
        op_type=args.op,
        limit=args.limit
    )
    
    if not filtered_entries:
        print(f"{COLOR_YELLOW}No entries match the specified filters.{COLOR_RESET}")
        print(f"Workspace root: {workspace_root}")
        print(f"History root: {history_root}")
        print(f"{COLOR_CYAN}Filter criteria:{COLOR_RESET}")
        if args.conv:
            print(f"  Conversation ID containing: {args.conv}")
        if args.file:
            print(f"  File path containing: {args.file}")
        if args.status:
            print(f"  Status: {args.status}")
        if args.time:
            print(f"  Time filter: {args.time}")
        if args.op:
            print(f"  Operation type: {args.op}")
        print(f"  Limit: {args.limit}")
        return
    
    # Print header
    print(f"{COLOR_CYAN}{'Time':19}  {'Edit ID':8}  {'Conv ID':8}  {'Operation':9}  {'Status':8}  {'File Path'}{COLOR_RESET}")
    print("-" * 100)
    
    # Print entries
    for entry in filtered_entries:
        print(format_entry_summary(entry))
        
    # Print summary
    print(f"\nShowing {len(filtered_entries)} of {len(all_entries)} entries")
    
    # Show filter info
    if args.conv or args.file or args.status or args.time or args.op:
        print(f"\n{COLOR_CYAN}Applied filters:{COLOR_RESET}")
        if args.conv:
            print(f"  Conversation ID containing: {args.conv}")
        if args.file:
            print(f"  File path containing: {args.file}")
        if args.status:
            print(f"  Status: {args.status}")
        if args.time:
            print(f"  Time filter: {args.time}")
        if args.op:
            print(f"  Operation type: {args.op}")


def handle_show(
    args: argparse.Namespace, workspace_root: Path, history_root: Path
) -> None:
    """Handle the show command to display diffs."""
    identifier = args.identifier
    if not identifier:
        print(f"{COLOR_RED}Error: No identifier provided.{COLOR_RESET}")
        return
        
    log.debug(f"Processing show command for identifier: {identifier}")
    
    # Find all entries
    all_entries = find_all_entries(history_root)
    
    if not all_entries:
        print(f"{COLOR_YELLOW}No edit history entries found.{COLOR_RESET}")
        return
        
    # Try to find a specific entry by ID first
    try:
        entry = find_entry_by_id(all_entries, identifier)
        if entry:
            # Found a specific entry
            print(f"\n{COLOR_CYAN}Details for edit {entry.get('edit_id', 'unknown')}{COLOR_RESET}")
            print(format_entry_summary(entry, detailed=True))
            
            # Show the diff
            diff_content = get_diff_for_entry(entry, history_root)
            print_diff_with_color(diff_content)
            return
    except AmbiguousIDError:
        # Fall through to conversation search
        pass
        
    # If no specific entry found or ambiguous, try as conversation ID
    conversation_entries = find_entries_by_conversation(all_entries, identifier)
    
    if not conversation_entries:
        print(f"{COLOR_RED}No entries found matching identifier: {identifier}{COLOR_RESET}")
        return
        
    print(f"\n{COLOR_CYAN}Showing {len(conversation_entries)} edits for conversation {conversation_entries[0].get('conversation_id', 'unknown')}{COLOR_RESET}")
    
    # Show details and diffs for each entry
    for i, entry in enumerate(conversation_entries):
        print(f"\n{COLOR_CYAN}Edit {i+1}/{len(conversation_entries)} - {entry.get('edit_id', 'unknown')}{COLOR_RESET}")
        print(format_entry_summary(entry, detailed=True))
        
        # Show the diff
        diff_content = get_diff_for_entry(entry, history_root)
        print_diff_with_color(diff_content)
        
        # Add separator between entries
        if i < len(conversation_entries) - 1:
            print("\n" + "=" * 80)


def handle_accept(
    args: argparse.Namespace, workspace_root: Path, history_root: Path
) -> None:
    """Handle the accept command to accept edits."""
    log.debug("Processing accept command")
    
    # Find all entries
    all_entries = find_all_entries(history_root)
    
    if not all_entries:
        print(f"{COLOR_YELLOW}No edit history entries found.{COLOR_RESET}")
        return
        
    successful = 0
    failed = 0
    
    if args.edit_id:
        # Accept a specific edit
        try:
            entry = find_entry_by_id(all_entries, args.edit_id)
            if not entry:
                print(f"{COLOR_RED}No entry found with ID prefix: {args.edit_id}{COLOR_RESET}")
                return
                
            # Check if already accepted
            if entry.get("status") == "accepted":
                print(f"{COLOR_YELLOW}Edit {entry.get('edit_id')} is already accepted.{COLOR_RESET}")
                return
                
            # Get the file path
            file_path_str = entry.get("file_path")
            if not file_path_str:
                print(f"{COLOR_RED}Missing file path in entry {entry.get('edit_id')}{COLOR_RESET}")
                return
                
            file_path = workspace_root / file_path_str
            
            # Hash verification - check if the file has been modified since the last edit
            last_edit = get_last_edit_for_file(all_entries, file_path_str)
            if last_edit and "hash_after" in last_edit and last_edit["hash_after"]:
                expected_hash = last_edit["hash_after"]
                if not verify_file_hash(file_path, expected_hash):
                    # Hash mismatch detected - show diff and prompt user
                    diff_content = generate_file_diff(file_path, expected_hash, history_root)
                    if diff_content:
                        if not prompt_for_hash_mismatch(file_path, diff_content):
                            print(f"{COLOR_YELLOW}Operation aborted by user.{COLOR_RESET}")
                            return
                    else:
                        print(f"{COLOR_YELLOW}Warning: File has been modified but could not generate diff.{COLOR_RESET}")
                        proceed = input(f"{COLOR_YELLOW}Continue anyway? (y/n): {COLOR_RESET}").lower()
                        if proceed not in ['y', 'yes']:
                            print(f"{COLOR_YELLOW}Operation aborted by user.{COLOR_RESET}")
                            return
            
            # Ensure edit is applied
            if entry.get("status") != "pending":
                print(f"{COLOR_YELLOW}Warning: Edit {entry.get('edit_id')} has status: {entry.get('status')}{COLOR_RESET}")
                
            # Apply the edit if needed
            if entry.get("status") == "rejected":
                print(f"Re-applying previously rejected edit...")
                if not apply_or_revert_edit(entry, workspace_root, history_root, is_revert=False):
                    print(f"{COLOR_RED}Failed to apply edit {entry.get('edit_id')}{COLOR_RESET}")
                    return
            
            # Reconstruct the file state to ensure consistency
            result = reconstruct_file_from_edits(file_path, all_entries, workspace_root, history_root)
            if result["error"]:
                print(f"{COLOR_RED}Error reconstructing file: {result['error']}{COLOR_RESET}")
                return
                
            # Make sure log_file is populated if missing
            if "log_file" not in entry and "conversation_id" in entry:
                entry["log_file"] = f"{entry['conversation_id']}.log"
            
            # Update entry with new hash
            entry["hash_after"] = result["hash"]
            
            # Update status
            if update_entry_status(entry, "accepted", history_root):
                print(f"{COLOR_GREEN}Successfully accepted edit: {entry.get('edit_id')}{COLOR_RESET}")
                successful += 1
            else:
                print(f"{COLOR_RED}Failed to update status for edit: {entry.get('edit_id')}{COLOR_RESET}")
                failed += 1
                
        except AmbiguousIDError as e:
            print(f"{COLOR_RED}Error: {e}{COLOR_RESET}")
            return
            
    elif args.conv:
        # Accept all pending edits for a conversation
        conversation_entries = find_entries_by_conversation(all_entries, args.conv)
        
        if not conversation_entries:
            print(f"{COLOR_RED}No entries found for conversation with ID: {args.conv}{COLOR_RESET}")
            return
            
        # Filter to only pending edits
        pending_entries = [e for e in conversation_entries if e.get("status") == "pending"]
        
        if not pending_entries:
            print(f"{COLOR_YELLOW}No pending edits found for conversation with ID: {args.conv}{COLOR_RESET}")
            return
            
        print(f"Found {len(pending_entries)} pending edits for conversation {conversation_entries[0].get('conversation_id')}.")
        print(f"Accepting all pending edits...")
        
        # Group entries by file path for more efficient processing
        entries_by_file = {}
        for entry in pending_entries:
            file_path = entry.get("file_path")
            if file_path:
                if file_path not in entries_by_file:
                    entries_by_file[file_path] = []
                entries_by_file[file_path].append(entry)
        
        # Process each file separately
        for file_path_str, file_entries in entries_by_file.items():
            file_path = workspace_root / file_path_str
            
            # Hash verification for the file
            last_edit = get_last_edit_for_file(all_entries, file_path_str)
            if last_edit and "hash_after" in last_edit and last_edit["hash_after"]:
                expected_hash = last_edit["hash_after"]
                if not verify_file_hash(file_path, expected_hash):
                    # Hash mismatch detected
                    diff_content = generate_file_diff(file_path, expected_hash, history_root)
                    if diff_content:
                        if not prompt_for_hash_mismatch(file_path, diff_content):
                            print(f"{COLOR_YELLOW}Skipping edits for file {file_path_str}.{COLOR_RESET}")
                            continue
                    else:
                        print(f"{COLOR_YELLOW}Warning: File {file_path_str} has been modified but could not generate diff.{COLOR_RESET}")
                        proceed = input(f"{COLOR_YELLOW}Continue with this file anyway? (y/n): {COLOR_RESET}").lower()
                        if proceed not in ['y', 'yes']:
                            print(f"{COLOR_YELLOW}Skipping edits for file {file_path_str}.{COLOR_RESET}")
                            continue
            
            # Reconstruct the file state
            result = reconstruct_file_from_edits(file_path, all_entries, workspace_root, history_root)
            if result["error"]:
                print(f"{COLOR_RED}Error reconstructing file {file_path_str}: {result['error']}{COLOR_RESET}")
                continue
                
            # Update all entries for this file
            final_hash = result["hash"]
            for entry in file_entries:
                # Make sure log_file is populated if missing
                if "log_file" not in entry and "conversation_id" in entry:
                    entry["log_file"] = f"{entry['conversation_id']}.log"
                
                # Update entry with new hash
                entry["hash_after"] = final_hash
                
                # Update status
                if update_entry_status(entry, "accepted", history_root):
                    print(f"{COLOR_GREEN}Successfully accepted edit: {entry.get('edit_id')}{COLOR_RESET}")
                    successful += 1
                else:
                    print(f"{COLOR_RED}Failed to update status for edit: {entry.get('edit_id')}{COLOR_RESET}")
                    failed += 1
                
    # Print summary
    if successful > 0 or failed > 0:
        print(f"\nAccept operation completed: {successful} successful, {failed} failed")


def handle_reject(
    args: argparse.Namespace, workspace_root: Path, history_root: Path
) -> None:
    """Handle the reject command to reject edits."""
    log.debug("Processing reject command")
    
    # Find all entries
    all_entries = find_all_entries(history_root)
    
    if not all_entries:
        print(f"{COLOR_YELLOW}No edit history entries found.{COLOR_RESET}")
        return
        
    successful = 0
    failed = 0
    
    if args.edit_id:
        # Reject a specific edit
        try:
            entry = find_entry_by_id(all_entries, args.edit_id)
            if not entry:
                print(f"{COLOR_RED}No entry found with ID prefix: {args.edit_id}{COLOR_RESET}")
                return
                
            # Check if already rejected
            if entry.get("status") == "rejected":
                print(f"{COLOR_YELLOW}Edit {entry.get('edit_id')} is already rejected.{COLOR_RESET}")
                return
                
            # Get the file path
            file_path_str = entry.get("file_path")
            if not file_path_str:
                print(f"{COLOR_RED}Missing file path in entry {entry.get('edit_id')}{COLOR_RESET}")
                return
                
            file_path = workspace_root / file_path_str
            
            # Hash verification - check if the file has been modified since the last edit
            last_edit = get_last_edit_for_file(all_entries, file_path_str)
            if last_edit and "hash_after" in last_edit and last_edit["hash_after"]:
                expected_hash = last_edit["hash_after"]
                if not verify_file_hash(file_path, expected_hash):
                    # Hash mismatch detected - show diff and prompt user
                    diff_content = generate_file_diff(file_path, expected_hash, history_root)
                    if diff_content:
                        if not prompt_for_hash_mismatch(file_path, diff_content):
                            print(f"{COLOR_YELLOW}Operation aborted by user.{COLOR_RESET}")
                            return
                    else:
                        print(f"{COLOR_YELLOW}Warning: File has been modified but could not generate diff.{COLOR_RESET}")
                        proceed = input(f"{COLOR_YELLOW}Continue anyway? (y/n): {COLOR_RESET}").lower()
                        if proceed not in ['y', 'yes']:
                            print(f"{COLOR_YELLOW}Operation aborted by user.{COLOR_RESET}")
                            return
                
            # Revert the edit if it was applied (pending or accepted)
            if entry.get("status") in ["pending", "accepted"]:
                print(f"Reverting edit...")
                if not apply_or_revert_edit(entry, workspace_root, history_root, is_revert=True):
                    print(f"{COLOR_RED}Failed to revert edit {entry.get('edit_id')}{COLOR_RESET}")
                    return
            
            # Reconstruct the file state to ensure consistency
            result = reconstruct_file_from_edits(file_path, all_entries, workspace_root, history_root)
            if result["error"]:
                print(f"{COLOR_RED}Error reconstructing file: {result['error']}{COLOR_RESET}")
                return
                
            # Make sure log_file is populated if missing
            if "log_file" not in entry and "conversation_id" in entry:
                entry["log_file"] = f"{entry['conversation_id']}.log"
                
            # Update entry with new hash
            entry["hash_after"] = result["hash"]
                
            # Update status
            if update_entry_status(entry, "rejected", history_root):
                print(f"{COLOR_GREEN}Successfully rejected edit: {entry.get('edit_id')}{COLOR_RESET}")
                successful += 1
            else:
                print(f"{COLOR_RED}Failed to update status for edit: {entry.get('edit_id')}{COLOR_RESET}")
                failed += 1
                
        except AmbiguousIDError as e:
            print(f"{COLOR_RED}Error: {e}{COLOR_RESET}")
            return
            
    elif args.conv:
        # Reject all pending/accepted edits for a conversation
        conversation_entries = find_entries_by_conversation(all_entries, args.conv)
        
        if not conversation_entries:
            print(f"{COLOR_RED}No entries found for conversation with ID: {args.conv}{COLOR_RESET}")
            return
            
        # Filter to only pending or accepted edits
        applicable_entries = [e for e in conversation_entries if e.get("status") in ["pending", "accepted"]]
        
        if not applicable_entries:
            print(f"{COLOR_YELLOW}No pending or accepted edits found for conversation with ID: {args.conv}{COLOR_RESET}")
            return
            
        print(f"Found {len(applicable_entries)} applicable edits for conversation {conversation_entries[0].get('conversation_id')}.")
        print(f"Rejecting all applicable edits...")
        
        # Group entries by file path for more efficient processing
        entries_by_file = {}
        for entry in applicable_entries:
            file_path = entry.get("file_path")
            if file_path:
                if file_path not in entries_by_file:
                    entries_by_file[file_path] = []
                entries_by_file[file_path].append(entry)
                
        # Process each file separately
        for file_path_str, file_entries in entries_by_file.items():
            file_path = workspace_root / file_path_str
            
            # Hash verification for the file
            last_edit = get_last_edit_for_file(all_entries, file_path_str)
            if last_edit and "hash_after" in last_edit and last_edit["hash_after"]:
                expected_hash = last_edit["hash_after"]
                if not verify_file_hash(file_path, expected_hash):
                    # Hash mismatch detected
                    diff_content = generate_file_diff(file_path, expected_hash, history_root)
                    if diff_content:
                        if not prompt_for_hash_mismatch(file_path, diff_content):
                            print(f"{COLOR_YELLOW}Skipping edits for file {file_path_str}.{COLOR_RESET}")
                            continue
                    else:
                        print(f"{COLOR_YELLOW}Warning: File {file_path_str} has been modified but could not generate diff.{COLOR_RESET}")
                        proceed = input(f"{COLOR_YELLOW}Continue with this file anyway? (y/n): {COLOR_RESET}").lower()
                        if proceed not in ['y', 'yes']:
                            print(f"{COLOR_YELLOW}Skipping edits for file {file_path_str}.{COLOR_RESET}")
                            continue
            
            # Process in reverse order to avoid conflicts
            sorted_entries = sorted(file_entries, key=lambda e: e.get("tool_call_index", 0), reverse=True)
            for entry in sorted_entries:
                # Revert the edit
                reverted = apply_or_revert_edit(entry, workspace_root, history_root, is_revert=True)
                if not reverted:
                    print(f"{COLOR_RED}Failed to revert edit: {entry.get('edit_id')}{COLOR_RESET}")
                    failed += 1
                    continue
                    
                # Make sure log_file is populated if missing
                if "log_file" not in entry and "conversation_id" in entry:
                    entry["log_file"] = f"{entry['conversation_id']}.log"
                    
                # Update status
                if update_entry_status(entry, "rejected", history_root):
                    print(f"{COLOR_GREEN}Successfully rejected edit: {entry.get('edit_id')}{COLOR_RESET}")
                    successful += 1
                else:
                    print(f"{COLOR_RED}Failed to update status for edit: {entry.get('edit_id')}{COLOR_RESET}")
                    failed += 1
            
            # Reconstruct the file state after all edits in this file are processed
            result = reconstruct_file_from_edits(file_path, all_entries, workspace_root, history_root)
            if result["error"]:
                print(f"{COLOR_RED}Error reconstructing file {file_path_str}: {result['error']}{COLOR_RESET}")
                
    # Print summary
    if successful > 0 or failed > 0:
        print(f"\nReject operation completed: {successful} successful, {failed} failed")


def handle_review(
    args: argparse.Namespace, workspace_root: Path, history_root: Path
) -> None:
    """Handle the review command to interactively review edits."""
    log.debug("Processing review command")
    
    # Find all entries
    all_entries = find_all_entries(history_root)
    
    if not all_entries:
        print(f"{COLOR_YELLOW}No edit history entries found.{COLOR_RESET}")
        return
        
    # Filter to only pending edits
    pending_entries = [e for e in all_entries if e.get("status") == "pending"]
    
    if not pending_entries:
        print(f"{COLOR_YELLOW}No pending edits found to review.{COLOR_RESET}")
        return
        
    # Further filter by conversation if specified
    if args.conv:
        pending_entries = [
            e for e in pending_entries
            if e.get("conversation_id") and (
                e["conversation_id"].startswith(args.conv) or 
                e["conversation_id"].endswith(args.conv)
            )
        ]
        
        if not pending_entries:
            print(f"{COLOR_YELLOW}No pending edits found for conversation with ID: {args.conv}{COLOR_RESET}")
            return
            
    print(f"Found {len(pending_entries)} pending edits to review.")
    
    # Group by conversation for better organization
    by_conversation = {}
    for entry in pending_entries:
        conv_id = entry.get("conversation_id", "unknown")
        if conv_id not in by_conversation:
            by_conversation[conv_id] = []
        by_conversation[conv_id].append(entry)
        
    # Process each conversation
    for conv_id, entries in by_conversation.items():
        print(f"\n{COLOR_CYAN}Reviewing {len(entries)} edits for conversation {conv_id}{COLOR_RESET}")
        
        # Process each entry in the conversation
        for i, entry in enumerate(entries):
            print(f"\n{COLOR_CYAN}Edit {i+1}/{len(entries)} - {entry.get('edit_id', 'unknown')}{COLOR_RESET}")
            print(format_entry_summary(entry, detailed=True))
            
            # Show the diff
            diff_content = get_diff_for_entry(entry, history_root)
            print_diff_with_color(diff_content)
            
            # Prompt for action
            while True:
                choice = input(f"\n{COLOR_RESET}Action? ({COLOR_GREEN}[a]{COLOR_RESET}ccept {COLOR_RED}[r]{COLOR_RESET}eject {COLOR_CYAN}[s]{COLOR_RESET}kip {COLOR_BLUE}[q]{COLOR_RESET}uit):{COLOR_RESET}").lower()
                
                if choice in ['a', 'accept']:
                    # Accept the edit
                    if update_entry_status(entry, "accepted", history_root):
                        print(f"{COLOR_GREEN}Edit accepted.{COLOR_RESET}")
                    else:
                        print(f"{COLOR_RED}Failed to accept edit.{COLOR_RESET}")
                    break
                elif choice in ['r', 'reject']:
                    # Revert and reject the edit
                    reverted = apply_or_revert_edit(entry, workspace_root, history_root, is_revert=True)
                    if not reverted:
                        print(f"{COLOR_RED}Failed to revert edit.{COLOR_RESET}")
                        continue
                        
                    if update_entry_status(entry, "rejected", history_root):
                        print(f"{COLOR_GREEN}Edit rejected and reverted.{COLOR_RESET}")
                    else:
                        print(f"{COLOR_RED}Failed to reject edit (but it was reverted).{COLOR_RESET}")
                    break
                elif choice in ['s', 'skip']:
                    print(f"{COLOR_YELLOW}Edit skipped.{COLOR_RESET}")
                    break
                elif choice in ['q', 'quit']:
                    print(f"{COLOR_YELLOW}Review session ended.{COLOR_RESET}")
                    return
                else:
                    print(f"{COLOR_RED}Invalid choice. Please try again.{COLOR_RESET}")
                    
    print(f"\n{COLOR_GREEN}Review completed. All pending edits processed.{COLOR_RESET}")


def handle_cleanup(
    args: argparse.Namespace, workspace_root: Path, history_root: Path
) -> None:
    """Handle the cleanup command to remove stale locks."""
    log.info("Starting cleanup of stale locks...")
    
    count = cleanup_stale_locks(history_root)
    
    if count > 0:
        print(f"Cleaned up {count} stale lock(s).")
    else:
        print("No stale locks found to clean up.")


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
  mcpdiff cleanup                    # Clean up stale locks
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
    parser.add_argument(
        "--timeout", 
        type=int, 
        default=LOCK_TIMEOUT,
        help=f"Timeout in seconds for acquiring locks (default: {LOCK_TIMEOUT})."
    )
    parser.add_argument(
        "--force-cleanup",
        action="store_true",
        help="Force cleanup of stale locks before running any command."
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
    
    # cleanup
    parser_cleanup = subparsers.add_parser(
        "cleanup", aliases=["clean"], help="Clean up stale locks."
    )
    parser_cleanup.set_defaults(func=handle_cleanup)
    
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

    # Get lock timeout from arguments - use the value directly, not modifying the global
    lock_timeout = args.timeout
    log.debug(f"Using lock timeout: {lock_timeout}s")

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
        
        # Force cleanup of stale locks if requested
        if args.force_cleanup or args.command == "cleanup":
            log.debug("Performing cleanup of stale locks")
            cleaned = cleanup_stale_locks(history_root)
            if cleaned > 0:
                log.info(f"Cleaned up {cleaned} stale lock(s) before main operation")

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


def verify_file_hash(file_path: Path, expected_hash: str) -> bool:
    """Verify if the file's current hash matches the expected hash."""
    current_hash = calculate_hash(str(file_path))
    return current_hash == expected_hash


def get_last_edit_for_file(entries: List[Dict[str, Any]], file_path: str) -> Optional[Dict[str, Any]]:
    """Get the last edit entry for a specific file path."""
    relevant_entries = [e for e in entries if e.get("file_path") == file_path]
    if not relevant_entries:
        return None
    # Sort by timestamp, newest first
    relevant_entries.sort(key=lambda e: e.get("timestamp", 0), reverse=True)
    return relevant_entries[0]


def generate_file_diff(file_path: Path, expected_hash: str, history_root: Path) -> Optional[str]:
    """Generate a diff between the current file state and the expected state based on hash."""
    # First, we need to find the last known checkpoint and replay edits
    # to create the expected file state
    # For simplicity in this implementation, we'll create a temp file with the expected content
    
    # Get current content
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            current_content = f.readlines()
    except Exception as e:
        log.error(f"Error reading current file {file_path}: {e}")
        return None
        
    # Find the reference file with the expected hash
    # This is a simplified implementation - in practice you would reconstruct from checkpoints and edits
    expected_file = None
    for root, _, files in os.walk(history_root / CHECKPOINTS_DIR):
        for file in files:
            checkpoint_path = Path(root) / file
            if checkpoint_path.is_file():
                checkpoint_hash = calculate_hash(str(checkpoint_path))
                if checkpoint_hash == expected_hash:
                    expected_file = checkpoint_path
                    break
        if expected_file:
            break
            
    if not expected_file:
        log.error(f"Could not find file with expected hash: {expected_hash}")
        return None
        
    # Get expected content
    try:
        with open(expected_file, "r", encoding="utf-8") as f:
            expected_content = f.readlines()
    except Exception as e:
        log.error(f"Error reading expected file {expected_file}: {e}")
        return None
        
    # Generate diff
    return generate_diff(expected_content, current_content, str(file_path), str(file_path))


def prompt_for_hash_mismatch(file_path: Path, diff_content: str) -> bool:
    """Show diff and prompt user to continue or abort when hash mismatch is detected."""
    print(f"\n{COLOR_YELLOW}Warning: File has been modified since the last edit:{COLOR_RESET} {file_path}")
    print(f"\n{COLOR_CYAN}Diff between expected and current state:{COLOR_RESET}")
    print_diff_with_color(diff_content)
    
    while True:
        choice = input(f"\n{COLOR_YELLOW}Continue and discard these changes? (y/n): {COLOR_RESET}").lower()
        if choice in ['y', 'yes']:
            return True
        elif choice in ['n', 'no']:
            return False
        print(f"{COLOR_RED}Invalid choice. Please enter 'y' or 'n'.{COLOR_RESET}")


def reconstruct_file_from_edits(file_path: Path, entries: List[Dict[str, Any]], 
                                workspace_root: Path, history_root: Path) -> Dict[str, Any]:
    """
    Reconstruct a file by applying all accepted and pending edits from the nearest snapshot.
    Returns the final hash of the file and any error messages.
    """
    if not file_path.exists():
        return {
            "hash": None,
            "error": f"File does not exist: {file_path}"
        }
    
    try:
        # Get all entries for this file, sorted chronologically
        file_path_str = str(file_path.relative_to(workspace_root))
        file_entries = [e for e in entries if e.get("file_path") == file_path_str]
        
        if not file_entries:
            # No entries for this file, just return current hash
            current_hash = calculate_hash(str(file_path))
            return {
                "hash": current_hash,
                "error": None
            }
        
        # Sort by timestamp (oldest first)
        file_entries.sort(key=lambda e: e.get("timestamp", 0))
        
        # The first entry should have a checkpoint if this isn't a brand new file
        first_entry = file_entries[0]
        if first_entry.get("operation") != "create" and not first_entry.get("checkpoint_file"):
            return {
                "hash": None,
                "error": f"Missing checkpoint for first edit of {file_path_str}"
            }
        
        # Find all accepted and pending edits
        applicable_edits = [e for e in file_entries if e.get("status") in ["accepted", "pending"]]
        
        # Calculate the current expected hash based on the entries
        expected_hash = None
        for entry in applicable_edits:
            expected_hash = entry.get("hash_after")
        
        # If expected hash matches current, we're good
        current_hash = calculate_hash(str(file_path))
        if expected_hash and current_hash == expected_hash:
            return {
                "hash": current_hash,
                "error": None
            }
        
        # Otherwise, we need to reconstruct the file
        # Start with the checkpoint or create a new file
        if first_entry.get("operation") == "create":
            # For a create operation, we'd start with an empty file
            log.debug(f"Starting reconstruction with empty file for {file_path_str}")
        elif first_entry.get("checkpoint_file"):
            # Get checkpoint path and verify it exists
            checkpoint_path = history_root / first_entry["checkpoint_file"]
            if not checkpoint_path.exists():
                return {
                    "hash": None,
                    "error": f"Checkpoint file not found: {checkpoint_path}"
                }
            
            # Copy checkpoint to a temporary file
            temp_file = tempfile.NamedTemporaryFile(delete=False)
            temp_file.close()
            shutil.copy2(checkpoint_path, temp_file.name)
            
            # Apply all edits to the temporary file
            for entry in applicable_edits:
                if entry.get("operation") == "edit" and entry.get("diff_file"):
                    diff_path = history_root / entry["diff_file"]
                    if not diff_path.exists():
                        # Try alternative paths
                        if "conversation_id" in entry:
                            alt_diff_path = history_root / DIFFS_DIR / entry["conversation_id"] / f"{entry['edit_id']}.diff"
                            if alt_diff_path.exists():
                                diff_path = alt_diff_path
                            else:
                                log.warning(f"Could not find diff file for entry {entry.get('edit_id')}")
                                continue
                    
                    # Apply the diff to the temporary file
                    git_command = ["git", "apply", "-v", "--unsafe-paths", diff_path]
                    result = subprocess.run(
                        git_command,
                        capture_output=True,
                        text=True,
                        cwd=os.path.dirname(temp_file.name)
                    )
                    
                    if result.returncode != 0:
                        log.warning(f"Error applying diff for {entry.get('edit_id')}: {result.stderr}")
            
            # Copy the reconstructed file back to the original location
            shutil.copy2(temp_file.name, file_path)
            
            # Clean up
            os.unlink(temp_file.name)
        
        # Calculate and return the new hash
        reconstructed_hash = calculate_hash(str(file_path))
        return {
            "hash": reconstructed_hash,
            "error": None
        }
        
    except Exception as e:
        log.error(f"Error reconstructing file {file_path}: {e}")
        return {
            "hash": None,
            "error": str(e)
        }


if __name__ == "__main__":
    main()
