# mcpdiff_utils.py

import os
import fcntl
import time
import hashlib
import json
import logging
import re
from pathlib import Path
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional, Union

# --- Configuration Constants ---
# These might be better placed in history if purely history-related,
# but keeping them here as they define directory structures used by utils too.
HISTORY_DIR_NAME = "edit_history"
LOGS_DIR = "logs"
DIFFS_DIR = "diffs"
CHECKPOINTS_DIR = "checkpoints"
LOCK_TIMEOUT = 10  # seconds for file locks

# --- Logging Setup ---
# Initialize logger basic config - level will be set in main() of mcpdiff.py
logging.basicConfig(
    level=logging.WARNING,  # Default level
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
log = logging.getLogger("mcpdiff")  # Keep same logger name for consistency

# --- ANSI Color Codes ---
COLOR_RESET = "\033[0m"
COLOR_RED = "\033[91m"
COLOR_GREEN = "\033[92m"
COLOR_YELLOW = "\033[93m"
COLOR_BLUE = "\033[94m"
COLOR_CYAN = "\033[96m"
COLOR_MAGENTA = "\033[95m"


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


# --- Path Normalization and Expansion ---
def normalize_path(p: str) -> str:
    """Normalizes a path string."""
    return os.path.normpath(p)


def expand_home(filepath: str) -> str:
    """Expands ~ and ~user constructs in a path."""
    if filepath.startswith("~/") or filepath == "~":
        expanded = os.path.join(
            os.path.expanduser("~"), filepath[2:] if filepath.startswith("~/") else ""
        )
        return expanded
    return filepath


def is_path_within_directory(path: Path, directory: Path) -> bool:
    """
    Check if a path is within a directory (or is the directory itself).
    Both paths must be absolute and resolved.
    """
    try:
        path = path.resolve()
        directory = directory.resolve()
        return str(path).startswith(str(directory))
    except Exception:
        return False


def verify_path_is_safe(path: Path, workspace_root: Path) -> bool:
    """
    Verify that a path is safe to modify: within workspace, handling symlinks.
    """
    try:
        abs_path = path if path.is_absolute() else (workspace_root / path).resolve()
        current = abs_path
        while current != current.parent:
            if current.is_symlink():
                if not is_path_within_directory(current.resolve(), workspace_root):
                    log.error(
                        f"Security: Symlink '{current}' points outside workspace: {current.resolve()}"
                    )
                    return False
            # Handle potential infinite loop with broken symlinks gracefully
            parent = current.parent
            if parent == current:  # Already at root
                break
            # Check if parent is accessible (avoids errors on weird filesystems)
            try:
                parent.exists()
            except OSError:
                log.error(
                    f"Security: Cannot access parent of '{current}'. Path verification failed."
                )
                return False
            current = parent

        return is_path_within_directory(abs_path, workspace_root)
    except Exception as e:
        log.error(f"Security: Path verification failed for '{path}': {e}")
        return False


# --- Filesystem Info Helpers ---
def calculate_hash(file_path: str) -> Optional[str]:
    """Calculates the SHA256 hash of a file's content."""
    try:
        hasher = hashlib.sha256()
        with open(file_path, "rb") as f:
            while chunk := f.read(8192):
                hasher.update(chunk)
        return hasher.hexdigest()
    except FileNotFoundError:
        log.debug(f"File not found for hashing: {file_path}")
        return None
    except IOError as e:
        log.error(f"Error reading file {file_path} for hashing: {e}")
        return None


# --- Locking Mechanism (fcntl-based) ---
class FileLock:
    """A simple file locking mechanism using fcntl (Unix-like)."""

    def __init__(self, path: str):
        self.lock_dir = Path(f"{path}.lockdir")
        self.lock_file_path = self.lock_dir / "pid.lock"
        self.lock_file_handle = None
        self.is_locked = False

    def _check_stale_lock(self) -> bool:
        """Check if the lock appears to be stale and clean it up if necessary."""
        if not self.lock_dir.exists():
            return False
        if not self.lock_file_path.exists():
            try:
                log.debug(
                    f"Found stale lock directory without lock file: {self.lock_dir}"
                )
                self._force_cleanup()
                return True
            except OSError:
                log.warning(f"Failed to remove stale lock directory: {self.lock_dir}")
                return False
        try:
            pid_str = self.lock_file_path.read_text().strip()
            if not pid_str:
                log.debug(f"Found empty PID in lock file: {self.lock_file_path}")
                self._force_cleanup()
                return True
            pid = int(pid_str)
            if pid <= 0:
                log.debug(f"Invalid PID in lock file: {pid}")
                self._force_cleanup()
                return True
            try:
                os.kill(pid, 0)
                log.debug(f"Process with PID {pid} exists, lock may be valid")
                return False
            except OSError:
                log.debug(
                    f"Process with PID {pid} does not exist, cleaning up stale lock"
                )
                self._force_cleanup()
                return True
        except (ValueError, IOError, OSError) as e:
            log.debug(f"Error checking stale lock: {e}, cleaning up")
            try:
                self._force_cleanup()
            except Exception as cleanup_e:
                log.warning(f"Failed force cleanup during stale check: {cleanup_e}")
            return True  # Indicate cleanup attempt happened
        return False  # Should not be reached

    def _force_cleanup(self):
        """Force cleanup of lock file and directory"""
        # Use shutil.rmtree for potentially non-empty dirs, more robust
        if self.lock_dir.exists():
            try:
                import shutil

                shutil.rmtree(self.lock_dir)
                log.debug(
                    f"Removed stale lock directory (and contents): {self.lock_dir}"
                )
            except OSError as e:
                log.warning(
                    f"Could not remove lock directory {self.lock_dir}: {e}. Manual cleanup might be needed."
                )
                # Avoid subprocess unless absolutely necessary, can hide issues
                # Try removing file first if dir removal failed
                if self.lock_file_path.exists():
                    try:
                        self.lock_file_path.unlink()
                    except OSError:
                        pass  # Already logged dir removal failure

    def acquire(self, timeout: Optional[float] = None):
        """Acquire the lock with timeout."""
        effective_timeout = timeout if timeout is not None else LOCK_TIMEOUT
        start_time = time.time()

        # Initial stale check
        self._check_stale_lock()

        self.lock_dir.mkdir(parents=True, exist_ok=True)

        while True:
            try:
                self.lock_file_handle = open(self.lock_file_path, "w")
                fcntl.flock(
                    self.lock_file_handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB
                )
                self.lock_file_handle.write(str(os.getpid()))
                self.lock_file_handle.flush()
                os.fsync(self.lock_file_handle.fileno())
                self.is_locked = True
                log.debug(f"Acquired lock via directory: {self.lock_dir}")
                return
            except (IOError, OSError) as e:  # Includes BlockingIOError
                if self.lock_file_handle:
                    self.lock_file_handle.close()
                    self.lock_file_handle = None

                if time.time() - start_time >= effective_timeout:
                    # Final stale check before timeout
                    if self._check_stale_lock():
                        # Retry one last time immediately after cleanup
                        try:
                            self.lock_file_handle = open(self.lock_file_path, "w")
                            fcntl.flock(
                                self.lock_file_handle.fileno(),
                                fcntl.LOCK_EX | fcntl.LOCK_NB,
                            )
                            self.lock_file_handle.write(str(os.getpid()))
                            self.lock_file_handle.flush()
                            os.fsync(self.lock_file_handle.fileno())
                            self.is_locked = True
                            log.debug(
                                f"Acquired lock via directory after cleaning stale lock: {self.lock_dir}"
                            )
                            return
                        except (IOError, OSError):
                            if self.lock_file_handle:
                                self.lock_file_handle.close()
                                self.lock_file_handle = None
                            # Fall through to timeout error if retry failed

                    locker_pid = "unknown"
                    try:
                        if self.lock_file_path.exists():
                            locker_pid = (
                                self.lock_file_path.read_text().strip() or "empty PID"
                            )
                    except Exception:
                        locker_pid = "unreadable"

                    log.error(
                        f"Timeout acquiring lock {self.lock_dir} after {effective_timeout}s. Locked by PID: {locker_pid}."
                    )
                    raise TimeoutError(
                        f"Could not acquire lock for {self.lock_dir} (locked by PID {locker_pid})"
                    ) from e
                time.sleep(0.1)
            except Exception as e:
                if self.lock_file_handle:
                    self.lock_file_handle.close()
                log.error(f"Unexpected error acquiring lock {self.lock_dir}: {e}")
                raise

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
                # Cleanup lock directory
                self._force_cleanup()  # Use the robust cleanup
        elif self.lock_file_handle:  # Ensure handle is closed even if not locked
            self.lock_file_handle.close()
            self.lock_file_handle = None
            self._force_cleanup()  # Also attempt cleanup if handle existed

    def __enter__(self):
        self.acquire()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.release()


# --- Log File Handling ---
def read_log_file(
    log_file_path: Path, lock_timeout: Optional[float] = None
) -> List[Dict[str, Any]]:
    """Reads a JSON Lines log file safely."""
    entries = []
    if not log_file_path.is_file():
        log.debug(f"Log file does not exist: {log_file_path}")
        return entries
    lock = FileLock(str(log_file_path))
    try:
        with lock:  # Use context manager for acquire/release
            with open(log_file_path, "r", encoding="utf-8") as f:
                for i, line in enumerate(f):
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        entry = json.loads(line)
                        entries.append(entry)
                    except json.JSONDecodeError as e:
                        log.warning(
                            f"Invalid JSON on line {i + 1} in {log_file_path}: {e}"
                        )
                        log.warning(f"Problematic line: {line[:200]}...")
        log.debug(f"Successfully read {len(entries)} entries from {log_file_path}")
        return entries
    except (IOError, TimeoutError) as e:
        log.error(f"Error reading log file {log_file_path}: {e}")
        raise HistoryError(f"Could not read log file: {log_file_path}") from e
    except Exception as e:
        log.exception(f"Unexpected error reading log file {log_file_path}: {e}")
        raise HistoryError(f"Unexpected error reading log file: {log_file_path}") from e


def write_log_file(
    log_file_path: Path,
    entries: List[Dict[str, Any]],
    lock_timeout: Optional[float] = None,
):
    """Writes a list of entries to a JSON Lines log file atomically."""
    # Sort entries by index before writing to maintain order if modified
    # Use a stable sort if original order matters beyond index (though index should be sufficient)
    entries.sort(
        key=lambda x: (x.get("timestamp", 0), x.get("tool_call_index", float("inf")))
    )

    temp_path = log_file_path.with_suffix(
        log_file_path.suffix + ".tmp" + str(os.getpid())
    )
    lock = FileLock(str(log_file_path))
    try:
        with lock:  # Use context manager
            log_file_path.parent.mkdir(parents=True, exist_ok=True)
            with open(temp_path, "w", encoding="utf-8") as f:
                for entry in entries:
                    json.dump(entry, f, separators=(",", ":"))
                    f.write("\n")
            # Atomic rename/replace
            os.replace(temp_path, log_file_path)
            log.debug(
                f"Successfully wrote {len(entries)} entries to log file: {log_file_path}"
            )
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


def parse_timestamp(timestamp: Union[float, str]) -> float:
    """Parse various timestamp formats into a float epoch time."""
    if isinstance(timestamp, (int, float)):
        return float(timestamp)
    if isinstance(timestamp, str):
        tsre = re.compile(
            r"^(?P<yy>\d{4})[ -]?(?P<mm>\d{2})[ -]?(?P<dd>\d{2})[ T]?(?P<h>\d{2})[ :]?(?P<m>\d{2})[ :]?(?P<s>\d{2})\.?(?P<f>\d{1,9})?[+-]?((?P<tsh>\d{2})\:?(?P<tsm>\d{2}))?"
        )
        m = re.match(tsre, timestamp)
        if m is not None:
            tf = f".{m.group('f')}" if m.group("f") is not None else ".00"
            tz = f"+{m.group('tsh')}" if m.group("tsh") is not None else "+00"
            tz += f":{m.group('tsm')}" if m.group("tsm") is not None else ":00"
            tstd = f"{m.group('yy')}-{m.group('mm')}-{m.group('dd')}T{m.group('h')}:{m.group('m')}:{m.group('s')}{tf}{tz}"
            ts = datetime.strptime(tstd, "%Y-%m-%dT%H:%M:%S.%f%z")
            epoch_time = ts.timestamp()
            return epoch_time
        else:
            try:
                return float(timestamp)
            except ValueError:
                return 0.0
    # Handle the case when timestamp is other data type
    else:
        try:
            return float(timestamp)  # If time is epoch float string
        except:
            return 0.0


def format_timestamp_absolute(
    timestamp_val: Union[float, str],
    display_friendly: bool = False,
    tolerate_error: bool = False,
) -> str:
    """Format a timestamp as absolute time (e.g., '2025-03-31 15:49:39')."""
    try:
        epoch_time = parse_timestamp(timestamp_val)
        if epoch_time == 0.0 and not tolerate_error:
            return "unknown time"
        if display_friendly:
            return datetime.fromtimestamp(epoch_time, timezone.utc).strftime(
                "%Y-%m-%d %H:%M:%S"
            )
        else:
            return datetime.fromtimestamp(epoch_time, timezone.utc).strftime(
                "%Y-%m-%dT%H:%M:%SZ"
            )
    except (ValueError, TypeError, OSError) as e:
        log.debug(f"Error formatting absolute timestamp for '{timestamp_val}': {e}")
        if not tolerate_error:
            return "unknown time"
        return "1970-01-01 00:00:00" if display_friendly else "1970-01-01T00:00:00Z"


def format_timestamp_relative(timestamp_val: Union[float, str]) -> str:
    """Format a timestamp relative to now (e.g., '5m ago', 'yesterday')."""
    try:
        epoch_time = parse_timestamp(timestamp_val)
        if epoch_time == 0.0:
            return "unknown time"

        dt = datetime.fromtimestamp(epoch_time, timezone.utc).astimezone()
        now = datetime.now(timezone.utc).astimezone()
        diff = now - dt

        if diff.total_seconds() < 0:  # Handle future timestamps if they occur
            return dt.strftime("%Y-%m-%d %H:%M:%S")

        if diff.days == 0:
            if diff.seconds < 60:
                return "just now"
            if diff.seconds < 3600:
                return f"{diff.seconds // 60}m ago"
            return f"{diff.seconds // 3600}h ago"
        elif diff.days == 1:
            return "yesterday"
        elif diff.days < 7:
            return f"{diff.days}d ago"
        else:
            return dt.strftime("%Y-%m-%d")

    except (ValueError, TypeError, OSError) as e:
        log.debug(f"Error formatting relative timestamp for '{timestamp_val}': {e}")
        if isinstance(timestamp_val, str) and timestamp_val:
            return timestamp_val  # Return original string if parsing failed
        return "unknown time"


def parse_time_filter(time_str: str) -> Optional[int]:
    """Parse a time filter string like 30s, 5m, 1h, 3d1h into seconds."""
    pattern = r"(\d+)\s*([smhd])"  # Allow optional space
    matches = re.findall(pattern, time_str)
    if not matches:
        log.warning(f"Invalid time filter format: {time_str}")
        return None
    seconds = 0
    for value, unit in matches:
        try:
            val_int = int(value)
            if unit == "s":
                seconds += val_int
            elif unit == "m":
                seconds += val_int * 60
            elif unit == "h":
                seconds += val_int * 3600
            elif unit == "d":
                seconds += val_int * 86400
        except ValueError:
            log.warning(f"Invalid number '{value}' in time filter: {time_str}")
            return None
    return seconds


def generate_hex_timestamp() -> str:
    """Generate a timestamp as hexadecimal representation of the current Unix epoch time."""
    # Using UUID based on time ensures more uniqueness than just epoch hex
    # Use UUIDv1 (time-based) or combine time with random bytes
    # Let's use time + random for better distribution if needed, but epoch hex is simpler
    # return uuid.uuid1().hex # Requires node/randomness potentially
    epoch_time_ns = time.time_ns()  # Higher resolution
    return format(epoch_time_ns, "x")  # Hex of nanoseconds since epoch


def print_diff_with_color(diff_content: Optional[str]) -> None:
    """Print a diff with color highlighting."""
    if not diff_content:
        print(f"{COLOR_YELLOW}No diff content available.{COLOR_RESET}")
        return

    for line in diff_content.splitlines():
        if line.startswith("+") and not line.startswith("+++"):
            print(f"{COLOR_GREEN}{line}{COLOR_RESET}")
        elif line.startswith("-") and not line.startswith("---"):
            print(f"{COLOR_RED}{line}{COLOR_RESET}")
        elif line.startswith("@@"):
            print(f"{COLOR_CYAN}{line}{COLOR_RESET}")
        elif line.startswith(
            ("diff ", "--- ", "+++ ", "index ")
        ):  # Include index lines
            print(f"{COLOR_BLUE}{line}{COLOR_RESET}")
        else:
            print(line)
