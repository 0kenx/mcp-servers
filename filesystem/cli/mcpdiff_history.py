# mcpdiff_history.py

import os
import subprocess
import shutil
import tempfile
import uuid
from pathlib import Path
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional, Tuple, Set, Union

# Import from utils module
import mcpdiff_utils as utils
from mcpdiff_utils import (
    log, HistoryError, ExternalModificationError, AmbiguousIDError,
    HISTORY_DIR_NAME, LOGS_DIR, DIFFS_DIR, CHECKPOINTS_DIR, LOCK_TIMEOUT,
    COLOR_RESET, COLOR_RED, COLOR_GREEN, COLOR_YELLOW, COLOR_BLUE, COLOR_CYAN
)

# --- Workspace Root Finding ---
def find_workspace_root(start_path: Optional[str] = None) -> Optional[Path]:
    """
    Find the workspace root (directory containing .mcp/edit_history) by walking up.
    """
    current = Path(start_path if start_path else os.getcwd()).resolve()
    log.debug(f"Starting workspace search from: {current}")
    while True:
        check_dir = current / ".mcp" / HISTORY_DIR_NAME
        if check_dir.is_dir():
            log.debug(f"Found workspace root marker at: {current}")
            return current
        if current.parent == current: # Stop at filesystem root
            log.debug("Reached filesystem root without finding workspace marker.")
            return None
        current = current.parent
    # This line is unreachable due to the root check
    # return None

def get_workspace_path(relative_path: str, workspace_root: Path) -> Path:
    """Convert a path relative to workspace root to an absolute path."""
    return (workspace_root / relative_path).resolve()

def get_relative_path(absolute_path: Path, workspace_root: Path) -> str:
    """Convert an absolute path to a path relative to workspace root."""
    try:
        # Ensure absolute_path is absolute and resolved
        abs_resolved = absolute_path.resolve()
        return str(abs_resolved.relative_to(workspace_root.resolve()))
    except ValueError:
        log.debug(f"Path {absolute_path} not relative to workspace {workspace_root}. Using absolute path string.")
        return str(absolute_path)
    except Exception as e:
         log.warning(f"Error getting relative path for {absolute_path} against {workspace_root}: {e}")
         return str(absolute_path) # Fallback

# --- History Entry Management ---

def find_all_entries(history_root: Path, lock_timeout: Optional[float] = None) -> List[Dict[str, Any]]:
    """Find all edit history entries from log files."""
    all_entries = []
    logs_dir = history_root / LOGS_DIR
    if not logs_dir.is_dir():
        return []

    log_files = list(logs_dir.glob("*.log"))
    log.debug(f"Found {len(log_files)} log files in {logs_dir}")

    # Consider parallelizing read if many log files and performance is critical
    for log_file in log_files:
        try:
            log.debug(f"Reading log file: {log_file}")
            # Pass the actual lock timeout value
            entries = utils.read_log_file(log_file, lock_timeout=lock_timeout)
            # Add log file source to each entry for later updates
            for entry in entries:
                entry['log_file_source'] = log_file.name
            all_entries.extend(entries)
            log.debug(f"Found {len(entries)} entries in {log_file}")
        except HistoryError as e:
             log.warning(f"Skipping log file {log_file} due to read error: {e}")
        except Exception as e:
            log.warning(f"Unexpected error reading log file {log_file}: {e}")

    # Sort entries chronologically (timestamp then index)
    try:
        all_entries.sort(key=lambda e: (utils.parse_timestamp(e.get("timestamp", 0)), e.get("tool_call_index", float('inf'))))
    except Exception as e:
        log.warning(f"Error sorting entries: {e}. Entries might be out of order.")

    log.debug(f"Total entries found and sorted: {len(all_entries)}")
    return all_entries


def filter_entries(
    entries: List[Dict[str, Any]],
    conv_id: Optional[str] = None,
    file_path: Optional[str] = None,
    status: Optional[str] = None,
    time_filter: Optional[str] = None,
    op_type: Optional[str] = None,
    limit: Optional[int] = 50, # Allow None for no limit internally
) -> List[Dict[str, Any]]:
    """Filter entries based on criteria."""
    filtered = entries # Start with all entries

    if conv_id:
        conv_id_lower = conv_id.lower()
        filtered = [e for e in filtered if (cid := e.get("conversation_id")) and (cid.lower().startswith(conv_id_lower) or cid.lower().endswith(conv_id_lower))]

    if file_path:
        # Normalize path separators for comparison
        norm_filter_path = file_path.replace("\\", "/")
        filtered = [e for e in filtered if (fp := e.get("file_path")) and norm_filter_path in fp.replace("\\", "/")]

    if status:
        status_lower = status.lower()
        filtered = [e for e in filtered if e.get("status", "").lower() == status_lower]

    if op_type:
        op_type_lower = op_type.lower()
        filtered = [e for e in filtered if e.get("operation", "").lower() == op_type_lower]

    if time_filter:
        seconds = utils.parse_time_filter(time_filter)
        if seconds is not None:
            cutoff_timestamp = time.time() - seconds
            filtered = [e for e in filtered if utils.parse_timestamp(e.get("timestamp", 0)) >= cutoff_timestamp]

    # Apply limit *after* all filtering, return latest first for display if limited
    # Note: find_all_entries sorts oldest first. For display, often newest is desired.
    # Let's reverse *after* filtering if a limit is applied.
    if limit is not None and limit > 0:
         # Return the *most recent* 'limit' entries that match
         return filtered[-limit:][::-1] # Get last 'limit', then reverse to show newest first
    elif limit == 0: # Allow showing all with limit=0
         return filtered[::-1] # Reverse all to show newest first
    else: # limit is None or negative (no limit requested internally)
         return filtered # Return as is (oldest first)


def find_entry_by_id(
    entries: List[Dict[str, Any]], id_prefix: str
) -> Optional[Dict[str, Any]]:
    """Find an entry by its ID prefix, handling ambiguity."""
    if not id_prefix: return None
    id_prefix_lower = id_prefix.lower()
    matching = [e for e in entries if (eid := e.get("edit_id")) and eid.lower().startswith(id_prefix_lower)]

    if not matching:
        return None

    if len(matching) == 1:
        return matching[0]

    # Check for exact match first if multiple prefix matches
    exact_match = [e for e in matching if e.get("edit_id", "").lower() == id_prefix_lower]
    if len(exact_match) == 1:
        return exact_match[0]

    # Ambiguity: Prompt user
    print(f"{utils.COLOR_RED}Ambiguous ID prefix '{id_prefix}' matches multiple entries:{utils.COLOR_RESET}")
    print_entry_list_header()
    for i, entry in enumerate(matching): # Show ambiguous matches newest first for relevance
        print(f"{utils.COLOR_CYAN}[{i + 1:2d}]{utils.COLOR_RESET} {format_entry_summary(entry)}")

    try:
        while True:
            choice = input(f"\n{utils.COLOR_YELLOW}Enter number to select (1-{len(matching)}) or 'q' to quit: {utils.COLOR_RESET}").strip().lower()
            if choice in ["q", "quit"]:
                raise KeyboardInterrupt("Operation cancelled by user during ambiguous selection")
            try:
                idx = int(choice) - 1
                if 0 <= idx < len(matching):
                    return matching[idx]
                else:
                    print(f"{utils.COLOR_RED}Invalid selection.{utils.COLOR_RESET}")
            except ValueError:
                print(f"{utils.COLOR_RED}Invalid input. Please enter a number or 'q'.{utils.COLOR_RESET}")
    except (EOFError, KeyboardInterrupt) as e:
         # Re-raise specific exception types expected by main handler
         if isinstance(e, KeyboardInterrupt): raise
         raise AmbiguousIDError(f"Could not resolve ambiguous ID '{id_prefix}'. Operation cancelled.") from e
    # Should not be reached
    return None


def find_entries_by_conversation(
    entries: List[Dict[str, Any]], conv_id_prefix: str
) -> List[Dict[str, Any]]:
    """Find all entries for a conversation by ID prefix or suffix, sorted chronologically."""
    if not conv_id_prefix: return []
    conv_id_lower = conv_id_prefix.lower()
    # Prioritize prefix match
    matching = [e for e in entries if (cid := e.get("conversation_id")) and cid.lower().startswith(conv_id_lower)]
    if not matching:
        # Fallback to suffix match
        matching = [e for e in entries if (cid := e.get("conversation_id")) and cid.lower().endswith(conv_id_lower)]

    # Already sorted chronologically by find_all_entries
    log.debug(f"Found {len(matching)} entries matching conv ID '{conv_id_prefix}'")
    return matching


def update_entry_status(
    entry_to_update: Dict[str, Any],
    new_status: str,
    history_root: Path,
    lock_timeout: Optional[float] = None,
) -> bool:
    """Update the status of a specific entry in its log file."""
    edit_id = entry_to_update.get("edit_id")
    log_file_name = entry_to_update.get("log_file_source") # Use the source log file name

    if not edit_id or not log_file_name:
        log.error(f"Cannot update entry: missing edit_id or log_file_source. Entry: {entry_to_update}")
        return False

    log_file_path = history_root / LOGS_DIR / log_file_name
    if not log_file_path.is_file():
        log.error(f"Log file '{log_file_path}' not found for updating entry '{edit_id}'.")
        return False

    try:
        # Read all entries from the specific log file
        # Pass the specific timeout value
        entries = utils.read_log_file(log_file_path, lock_timeout=lock_timeout)

        updated = False
        for i, entry in enumerate(entries):
            if entry.get("edit_id") == edit_id:
                if entry.get("status") == new_status:
                    log.debug(f"Entry {edit_id} already has status {new_status}. No update needed.")
                    return True # Considered success

                log.debug(f"Updating entry {edit_id} in {log_file_name}: status -> {new_status}")
                entries[i]["status"] = new_status
                # Use consistent ISO 8601 format with Z
                entries[i]["updated_at"] = datetime.now(timezone.utc).isoformat(timespec='milliseconds').replace('+00:00', 'Z')
                updated = True
                break # Assumes edit_id is unique within a log file

        if not updated:
            log.error(f"Entry {edit_id} not found in log file {log_file_path}. Cannot update status.")
            return False

        # Write back all entries to the same log file
        utils.write_log_file(log_file_path, entries, lock_timeout=lock_timeout)
        log.info(f"Successfully updated status of entry {edit_id} to {new_status} in {log_file_name}")
        return True

    except HistoryError as e:
         log.error(f"HistoryError updating status for {edit_id} in {log_file_path}: {e}")
         return False
    except Exception as e:
        log.exception(f"Unexpected error updating status for {edit_id} in {log_file_path}: {e}")
        return False


def get_diff_for_entry(entry: Dict[str, Any], history_root: Path) -> Optional[str]:
    """Get the diff content for an entry, trying multiple locations."""
    edit_id = entry.get("edit_id")
    conv_id = entry.get("conversation_id")
    diff_file_rel_path = entry.get("diff_file") # Relative path stored in log

    if not edit_id:
        log.debug(f"Cannot get diff, missing edit_id in entry: {entry}")
        return None

    # Handle operations without diffs explicitly
    operation = entry.get("operation", "").lower()
    if operation == "move":
        source = entry.get("source_path", "unknown_source")
        dest = entry.get("file_path", "unknown_dest")
        return f"OPERATION: MOVE\nSource: {source}\nDestination: {dest}"
    if operation in ["create", "delete", "snapshot", "revert"] and not diff_file_rel_path:
         # These might legitimately not have diffs sometimes (e.g., snapshot, revert, initial create)
         log.debug(f"Operation '{operation}' for {edit_id} may not have a diff file.")
         # Return specific info if possible
         if operation == "delete": return f"OPERATION: DELETE\nFile: {entry.get('file_path')}"
         if operation == "create": return f"OPERATION: CREATE\nFile: {entry.get('file_path')}"
         return f"OPERATION: {operation.upper()}\n(No diff file associated)"


    # Potential diff paths to check
    potential_paths: List[Path] = []

    # 1. Preferred: <history>/diffs/<conv_id>/<edit_id>.diff (Convention)
    if conv_id and edit_id:
        potential_paths.append(history_root / DIFFS_DIR / conv_id / f"{edit_id}.diff")

    # 2. From entry: <history>/diffs/<diff_file_rel_path> (As stored in log)
    #    The diff_file_rel_path might already include the conv_id directory part.
    if diff_file_rel_path:
        # Assume diff_file is relative to the DIFFS_DIR
        potential_paths.append(history_root / DIFFS_DIR / diff_file_rel_path)
        # Also consider if it's relative to history_root (less likely but possible)
        # potential_paths.append(history_root / diff_file_rel_path)

    # 3. Fallback Search: <history>/diffs/*/<edit_id>.diff (If conv_id was missing/wrong)
    #    This is less efficient but robust.
    if edit_id:
        search_pattern = f"{edit_id}.diff"
        diffs_base = history_root / DIFFS_DIR
        if diffs_base.is_dir():
             # Use rglob for recursive search
             potential_paths.extend(list(diffs_base.rglob(search_pattern)))


    # Try reading from potential paths
    checked_paths = set()
    for diff_path in potential_paths:
        abs_path = diff_path.resolve()
        if abs_path in checked_paths:
             continue # Don't check the same resolved path twice
        checked_paths.add(abs_path)

        if abs_path.is_file():
            log.debug(f"Found diff for {edit_id} at: {abs_path}")
            try:
                content = abs_path.read_text(encoding="utf-8")
                # Simple check for diff format (optional, but helpful)
                if "--- a/" in content or "+++ b/" in content or "@@ -" in content or content.startswith("OPERATION:"):
                     return content
                else:
                     log.warning(f"File {abs_path} exists but doesn't look like a diff. Content: {content[:100]}...")
                     # Continue searching for a better match if possible
            except Exception as e:
                log.error(f"Error reading diff file {abs_path}: {e}")
                # Continue searching

    log.warning(f"Could not find or read a valid diff file for entry {edit_id} after checking paths.")
    return None # Diff not found


def format_entry_summary(entry: Dict[str, Any]) -> str:
    """Format a single entry for display in summaries."""
    if not entry: return "[Invalid Entry Data]"

    edit_id_short = entry.get("edit_id", "no_id")[:8]
    conv_id_short = entry.get("conversation_id", "N/A")[:8]
    op = entry.get("operation", "UNK").lower()
    status = entry.get("status", "UNK").lower()
    file_path = entry.get("file_path", "N/A")
    timestamp_val = entry.get("timestamp", 0)

    time_str = utils.format_timestamp_absolute(timestamp_val, True)

    # Status Color
    status_color = utils.COLOR_YELLOW if status == "pending" else \
                   utils.COLOR_GREEN if status == "accepted" else \
                   utils.COLOR_RED if status == "rejected" else \
                   utils.COLOR_RESET # Default color

    # Operation Color & Detail
    op_color = utils.COLOR_BLUE # Default
    op_details = op
    if op == "edit": op_color = utils.COLOR_BLUE
    elif op == "create": op_color = utils.COLOR_GREEN
    elif op == "replace": op_color = utils.COLOR_YELLOW
    elif op == "delete": op_color = utils.COLOR_RED
    elif op in ["move", "rename"]:
        op_color = utils.COLOR_CYAN
        source = entry.get('source_path', '?')
        file_path = f"{source} -> {file_path}" # Combine paths for display

    op_colored = f"{op_color}{op:<9}{utils.COLOR_RESET}" # Pad to 9 chars
    status_colored = f"{status_color}{status:<8}{utils.COLOR_RESET}" # Pad to 8 chars

    # Ensure consistent spacing
    # Time: 19, Edit ID: 8, Conv ID: 8, Op: 9, Status: 8, File Path: Rest
    return f"{time_str:<19}  {edit_id_short:8}  {conv_id_short:8}  {op_colored}  {status_colored}  {file_path}"

def print_entry_list_header():
     """Prints the header row for lists of entries."""
     print(f"{utils.COLOR_CYAN}{'Time':<19}  {'Edit ID':8}  {'Conv ID':8}  {'Operation':<9}  {'Status':<8}  {'File Path'}{utils.COLOR_RESET}")
     print("-" * 100)


def apply_or_revert_edit(
    entry: Dict[str, Any],
    workspace_root: Path,
    history_root: Path,
    is_revert: bool = False,
) -> bool:
    """
    Apply or revert a single edit operation.
    Handles create, delete, move, edit, replace based on entry info.
    Uses diff file for edit/replace, checkpoint for delete revert.
    Returns True on success, False on failure.
    """
    edit_id = entry.get("edit_id", "unknown_id")
    operation = entry.get("operation", "unknown").lower()
    file_path_rel = entry.get("file_path")
    source_path_rel = entry.get("source_path") # For move/rename
    diff_file_rel = entry.get("diff_file")
    checkpoint_file_rel = entry.get("checkpoint_file")

    log.info(f"{'Reverting' if is_revert else 'Applying'} operation '{operation}' for edit {edit_id} on file '{file_path_rel}'")

    if not file_path_rel:
        log.error(f"Missing 'file_path' in entry {edit_id}. Cannot proceed.")
        return False
    target_path = workspace_root / file_path_rel

    # --- Security Check ---
    if not utils.verify_path_is_safe(target_path, workspace_root):
         log.error(f"Security: Target path '{target_path}' is outside or points outside workspace. Aborting.")
         return False
    if source_path_rel:
         source_path_abs = workspace_root / source_path_rel
         if not utils.verify_path_is_safe(source_path_abs, workspace_root):
              log.error(f"Security: Source path '{source_path_abs}' is outside or points outside workspace. Aborting.")
              return False


    # --- Get Absolute Paths for History Artifacts ---
    diff_path: Optional[Path] = None
    if diff_file_rel:
        # Assume diff_file path is relative to DIFFS_DIR
        # Allow for diff_file potentially having conv_id dir already
        potential_diff_path = history_root / DIFFS_DIR / diff_file_rel
        if potential_diff_path.is_file():
             diff_path = potential_diff_path
        else:
             # Fallback: Maybe it's just the filename under conv_id dir?
             conv_id = entry.get("conversation_id")
             if conv_id:
                  potential_diff_path_alt = history_root / DIFFS_DIR / conv_id / diff_file_rel
                  if potential_diff_path_alt.is_file():
                       diff_path = potential_diff_path_alt
        if not diff_path:
             log.warning(f"Diff file '{diff_file_rel}' specified in entry {edit_id} not found.")
             # Allow proceeding for ops that might not need it (revert create/delete)


    checkpoint_path: Optional[Path] = None
    if checkpoint_file_rel:
        # Checkpoints are relative to history_root
        potential_chkpt_path = history_root / checkpoint_file_rel
        if potential_chkpt_path.is_file():
             checkpoint_path = potential_chkpt_path
        else:
            log.warning(f"Checkpoint file '{checkpoint_file_rel}' specified in entry {edit_id} not found.")
            # Allow proceeding, but some reverts might fail


    # --- Handle Operations ---
    try:
        if operation == "create":
            if is_revert:
                # Revert create = delete file
                if target_path.exists():
                    log.debug(f"Reverting create: deleting {target_path}")
                    target_path.unlink()
                else:
                    log.debug(f"Reverting create: file {target_path} already deleted.")
                return True
            else:
                # Apply create = apply diff to empty file (or ensure file exists if no diff)
                # Ensure parent dir exists
                target_path.parent.mkdir(parents=True, exist_ok=True)
                if diff_path:
                     # Apply patch to create content
                     # We need an empty file to patch against
                     with open(target_path, 'w') as f: pass # Create empty file
                     cmd = ["git", "apply", "--verbose", "--unsafe-paths", str(diff_path)]
                     log.debug(f"Running apply for create: {' '.join(cmd)}")
                     result = subprocess.run(cmd, cwd=workspace_root, capture_output=True, text=True, check=False)
                     if result.returncode != 0:
                         log.error(f"Failed to apply diff for create {edit_id}: {result.stderr}\n{result.stdout}")
                         # Clean up potentially partially created file? Or leave it? Let's leave it.
                         return False
                     log.debug(f"Applied diff for create {edit_id} successfully.")
                     return True
                else:
                     # If no diff, just ensure the file exists (likely empty)
                     if not target_path.exists():
                         with open(target_path, 'w') as f: pass
                         log.debug(f"Applied create {edit_id}: created empty file {target_path}")
                     else:
                          log.debug(f"Applied create {edit_id}: file {target_path} already exists.")
                     return True


        elif operation == "delete":
            if is_revert:
                # Revert delete = restore from checkpoint
                if not checkpoint_path:
                    log.error(f"Cannot revert delete {edit_id}: checkpoint file not found or specified.")
                    return False
                log.debug(f"Reverting delete: restoring {target_path} from {checkpoint_path}")
                target_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(checkpoint_path, target_path) # Use copy2 to preserve metadata
                return True
            else:
                # Apply delete = delete file
                if target_path.exists():
                     log.debug(f"Applying delete: removing {target_path}")
                     target_path.unlink() # TODO: Handle directories? Assume files for now.
                else:
                     log.debug(f"Applying delete: file {target_path} already removed.")
                return True


        elif operation == "move":
            if not source_path_rel:
                log.error(f"Cannot process move {edit_id}: missing 'source_path'.")
                return False
            source_path = workspace_root / source_path_rel

            if is_revert:
                # Revert move = move target back to source
                log.debug(f"Reverting move: moving {target_path} back to {source_path}")
                if not target_path.exists():
                    log.error(f"Cannot revert move {edit_id}: destination {target_path} does not exist.")
                    return False
                source_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(target_path), str(source_path))
                return True
            else:
                # Apply move = move source to target
                log.debug(f"Applying move: moving {source_path} to {target_path}")
                if not source_path.exists():
                     # This might happen if applying edits out of order or after manual changes
                     log.warning(f"Cannot apply move {edit_id}: source {source_path} does not exist. Assuming it was already moved.")
                     # Check if target exists, if so, consider it successful.
                     return target_path.exists()
                target_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(source_path), str(target_path))
                return True


        elif operation in ["edit", "replace"]:
             # Both need a diff file to apply/revert meaningfully
             if not diff_path:
                 log.error(f"Cannot {'revert' if is_revert else 'apply'} {operation} {edit_id}: diff file not found.")
                 return False

             # Check if target file exists before applying/reverting patch
             # git apply might create the file if the diff adds it entirely,
             # but it's safer if the file exists for standard edits/replaces.
             # Exception: A 'replace' operation's diff might represent creating the file anew.
             # Let git apply handle file existence issues.
             # if not target_path.exists() and operation == "edit":
             #      log.error(f"Cannot {'revert' if is_revert else 'apply'} edit {edit_id}: target file {target_path} does not exist.")
             #      return False


             # Use git apply
             cmd = ["git", "apply", "--verbose", "--unsafe-paths"]
             if is_revert:
                 cmd.append("-R") # Apply reverse patch
             # Apply relative to workspace root
             cmd.extend(["--directory", str(workspace_root), str(diff_path)])

             log.debug(f"Running: {' '.join(cmd)}")
             # Run from workspace root context
             result = subprocess.run(cmd, cwd=workspace_root, capture_output=True, text=True, check=False)

             if result.returncode != 0:
                 # Attempt with --reject flag to see if it applies partially? No, keep it simple.
                 log.error(f"Failed to {'revert' if is_revert else 'apply'} {operation} {edit_id} using git apply.")
                 log.error(f"Command: {' '.join(cmd)}")
                 log.error(f"Stderr: {result.stderr}")
                 log.error(f"Stdout: {result.stdout}")
                 # Check common errors
                 if "does not exist in index" in result.stderr and not target_path.exists():
                      log.error(f"Hint: Target file {target_path.name} might be missing.")
                 elif "patch does not apply" in result.stderr:
                      log.error(f"Hint: File content may have changed since the diff was created.")
                 return False

             log.debug(f"Successfully {'reverted' if is_revert else 'applied'} {operation} {edit_id} using git apply.")
             return True

        else:
            log.error(f"Unsupported operation '{operation}' for edit {edit_id}. Cannot apply/revert.")
            return False

    except Exception as e:
        log.exception(f"Unexpected error during {'revert' if is_revert else 'apply'} of {edit_id}: {e}")
        return False


# --- File Reconstruction & Verification ---

def get_relevant_history_for_file(
    file_path_rel: str,
    all_entries: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """Extract and sort history entries relevant to a specific file path."""
    file_entries = [
        e for e in all_entries
        if e.get("file_path") == file_path_rel or e.get("source_path") == file_path_rel
    ]
    # Ensure sorting by timestamp then index (already done by find_all_entries, but re-sort for safety)
    file_entries.sort(key=lambda e: (utils.parse_timestamp(e.get("timestamp", 0)), e.get("tool_call_index", float('inf'))))
    return file_entries

def find_closest_checkpoint(
    target_entry_index: int,
    file_entries: List[Dict[str, Any]],
    history_root: Path
) -> Tuple[Optional[Path], int]:
    """
    Find the most recent valid checkpoint file at or before target_entry_index.
    Returns the checkpoint path and the index of the entry it corresponds to.
    """
    closest_chkpt_path: Optional[Path] = None
    closest_chkpt_entry_index: int = -1

    for i in range(target_entry_index, -1, -1):
        entry = file_entries[i]
        chkpt_rel = entry.get("checkpoint_file")
        # Checkpoints are relative to history_root
        if chkpt_rel:
             potential_path = (history_root / chkpt_rel).resolve()
             if potential_path.is_file():
                 log.debug(f"Found potential checkpoint {potential_path} at index {i} for entry {entry.get('edit_id')}")
                 closest_chkpt_path = potential_path
                 closest_chkpt_entry_index = i
                 break # Found the most recent one before or at the target index

    # Special case: If the very first entry is 'create', start from empty state.
    if closest_chkpt_entry_index == -1 and file_entries:
         first_op = file_entries[0].get("operation","").lower()
         # Check if *any* entry before target_entry_index implies existence
         file_existed_before_target = any(
              e.get("operation","").lower() != "create"
              for idx, e in enumerate(file_entries) if idx <= target_entry_index
         )
         # If the first *relevant* operation is create, start empty
         first_relevant_entry_index = -1
         for idx, e in enumerate(file_entries):
              if idx <= target_entry_index:
                  first_relevant_entry_index = idx
                  break
         if first_relevant_entry_index != -1 and file_entries[first_relevant_entry_index].get("operation","").lower() == "create":
              log.debug(f"No checkpoint found, starting reconstruction from initial 'create' operation at index {first_relevant_entry_index}.")
              closest_chkpt_entry_index = first_relevant_entry_index # Mark the create op index
              # closest_chkpt_path remains None, indicating start from empty


    if closest_chkpt_path:
         log.info(f"Using checkpoint '{closest_chkpt_path}' from entry {file_entries[closest_chkpt_entry_index].get('edit_id')} (index {closest_chkpt_entry_index}) for reconstruction.")
    elif closest_chkpt_entry_index != -1: # Started from create op
         log.info(f"Starting reconstruction from empty state based on 'create' operation at index {closest_chkpt_entry_index}.")
    else:
         log.warning(f"No checkpoint or initial 'create' operation found before or at index {target_entry_index} for file {file_entries[0].get('file_path', 'unknown') if file_entries else 'unknown'}. Reconstruction might be inaccurate.")


    return closest_chkpt_path, closest_chkpt_entry_index


def reconstruct_file_from_history(
    file_path_rel: str,
    all_entries: List[Dict[str, Any]],
    workspace_root: Path,
    history_root: Path,
    apply_only_accepted: bool = False, # If True, only apply 'accepted' edits, otherwise apply 'accepted' and 'pending'
) -> Dict[str, Any]:
    """
    Reconstructs the state of a file by finding the latest checkpoint
    and applying subsequent relevant edits ('accepted' and optionally 'pending').

    Returns: Dict containing {'hash': final_hash or None, 'error': error_message or None}
    """
    target_file_abs = workspace_root / file_path_rel
    log.info(f"Reconstructing file '{file_path_rel}' (apply_only_accepted={apply_only_accepted})")

    file_entries = get_relevant_history_for_file(file_path_rel, all_entries)

    if not file_entries:
        # If file exists but has no history, return its current hash.
        if target_file_abs.exists():
            current_hash = utils.calculate_hash(str(target_file_abs))
            log.info(f"No history found for existing file {file_path_rel}. Returning current hash: {current_hash}")
            return {"hash": current_hash, "error": None}
        else:
            log.info(f"No history found and file {file_path_rel} does not exist.")
            return {"hash": None, "error": None} # File doesn't exist and never did according to history

    # Find the latest entry index (which represents the desired state)
    latest_entry_index = len(file_entries) - 1

    # Find the most recent checkpoint at or before the latest entry
    checkpoint_path, start_entry_index = find_closest_checkpoint(latest_entry_index, file_entries, history_root)

    temp_dir = None
    try:
        # Create a temporary directory to work in isolation
        temp_dir = tempfile.mkdtemp(prefix="mcp_reconstruct_")
        temp_file_path = Path(temp_dir) / target_file_abs.name
        log.debug(f"Using temporary directory for reconstruction: {temp_dir}")

        # 1. Initialize temp file state from checkpoint or empty
        if checkpoint_path:
            log.debug(f"Initializing reconstruction from checkpoint: {checkpoint_path}")
            shutil.copy2(checkpoint_path, temp_file_path)
        elif start_entry_index != -1 and file_entries[start_entry_index].get("operation","").lower() == "create":
             log.debug(f"Initializing reconstruction with empty file (from create at index {start_entry_index})")
             temp_file_path.touch() # Create empty file
        else:
            # No checkpoint and not starting with 'create'. What state was it in?
            # This might happen if history is incomplete or the first recorded action wasn't create/checkpointed.
            # Best guess: if the actual file exists, start from that? Risky.
            # Safest: assume empty and log warning.
             log.warning(f"Cannot determine initial state for {file_path_rel}. Starting reconstruction from empty state.")
             temp_file_path.touch()


        # 2. Apply edits sequentially from start_entry_index + 1 up to latest_entry_index
        current_temp_file_path = temp_file_path # Track potential renames

        for i in range(start_entry_index + 1, latest_entry_index + 1):
            entry = file_entries[i]
            status = entry.get("status", "unknown").lower()
            operation = entry.get("operation", "unknown").lower()
            entry_id = entry.get('edit_id', 'unknown_id')

            # Determine if this edit should be applied
            should_apply = status == "accepted" or (status == "pending" and not apply_only_accepted)
            # Rejected edits are *never* applied during reconstruction
            if status == "rejected":
                 log.debug(f"Skipping rejected edit {entry_id} at index {i}")
                 continue

            if not should_apply:
                log.debug(f"Skipping edit {entry_id} (status: {status}, apply_only_accepted: {apply_only_accepted})")
                continue

            log.debug(f"Applying {status} edit {entry_id} (op: {operation}) at index {i}")

            # We need to apply relative to the temp dir containing the file
            temp_workspace_root = Path(temp_dir)

            # --- Create a dummy entry for apply_or_revert_edit ---
            # It needs paths relative to the *actual* workspace, but will operate
            # within the temp dir context provided via git apply --directory or shutil.
            # Construct a temporary entry dict for the apply function.
            # The function needs workspace_root for path resolution internal to it.
            # Crucially, git apply needs the diff path correctly.
            temp_entry_for_apply = entry.copy()

            # Get the correct diff path relative to the *real* history root
            diff_file_rel = entry.get("diff_file")
            actual_diff_path: Optional[Path] = None
            if diff_file_rel:
                 # Assume relative to DIFFS_DIR
                 p1 = history_root / DIFFS_DIR / diff_file_rel
                 p2 = None
                 conv_id = entry.get("conversation_id")
                 if conv_id:
                      p2 = history_root / DIFFS_DIR / conv_id / diff_file_rel

                 if p1.is_file(): actual_diff_path = p1
                 elif p2 and p2.is_file(): actual_diff_path = p2

            # --- Apply using a simplified logic within the temp context ---
            # We can't directly call apply_or_revert_edit as it modifies the actual workspace.
            # Re-implement the core apply logic here for the temp file.

            target_path_in_temp = current_temp_file_path # The file we are modifying

            try:
                if operation == "create":
                     # Should have been handled by initial state? If not, apply diff if exists.
                     if not target_path_in_temp.exists(): target_path_in_temp.touch()
                     if actual_diff_path:
                          cmd = ["git", "apply", "--verbose", "--unsafe-paths", str(actual_diff_path)]
                          # Apply relative to the temp dir
                          result = subprocess.run(cmd, cwd=temp_workspace_root, capture_output=True, text=True, check=False)
                          if result.returncode != 0: raise HistoryError(f"git apply failed for create {entry_id}: {result.stderr}")

                elif operation == "delete":
                     if target_path_in_temp.exists(): target_path_in_temp.unlink()

                elif operation == "move":
                    source_rel = entry.get("source_path")
                    dest_rel = entry.get("file_path")
                    if not source_rel or not dest_rel: raise HistoryError(f"Move op {entry_id} missing paths")
                    # The source *should* match the current temp file's expected relative path
                    # We just need to update where the next operation looks
                    new_temp_name = Path(dest_rel).name
                    new_temp_path = temp_workspace_root / new_temp_name
                    if target_path_in_temp.exists():
                         log.debug(f"Simulating move: renaming {target_path_in_temp} to {new_temp_path}")
                         target_path_in_temp.rename(new_temp_path)
                         current_temp_file_path = new_temp_path # Update tracked path
                    else:
                         log.warning(f"Skipping move {entry_id}: source {target_path_in_temp.name} doesn't exist in temp dir.")


                elif operation in ["edit", "replace"]:
                     if not actual_diff_path: raise HistoryError(f"{operation} op {entry_id} missing diff file")
                     if not target_path_in_temp.exists():
                          # If file doesn't exist, maybe the diff creates it (e.g., replace)
                          log.debug(f"Target {target_path_in_temp.name} doesn't exist in temp, git apply might create it.")
                          # Create empty file for git apply to patch against if needed?
                          # Let's assume git apply handles it.

                     cmd = ["git", "apply", "--verbose", "--unsafe-paths"]
                     # Apply relative to the temp dir
                     # We need to tell git apply the *target filename* within the temp dir
                     # Use --index and potentially --cached? No, simpler: apply directly
                     # We need cwd to be temp_dir, and diff path absolute
                     cmd.append(str(actual_diff_path))
                     log.debug(f"Running apply for {operation}: {' '.join(cmd)} in {temp_workspace_root}")
                     result = subprocess.run(cmd, cwd=temp_workspace_root, capture_output=True, text=True, check=False)
                     if result.returncode != 0:
                         # Check if target file exists now, maybe apply created it
                         if not target_path_in_temp.exists():
                              raise HistoryError(f"git apply failed for {operation} {entry_id} and target file doesn't exist: {result.stderr}")
                         else:
                              # File exists, maybe patch didn't apply cleanly?
                              raise HistoryError(f"git apply failed for {operation} {entry_id} (file exists): {result.stderr}")

            except Exception as apply_err:
                 log.error(f"Failed to apply {status} edit {entry_id} (op: {operation}) during reconstruction: {apply_err}")
                 # Stop reconstruction here? Or continue? Let's stop for safety.
                 return {"hash": None, "error": f"Failed applying edit {entry_id}: {apply_err}"}


        # 3. Final state is in current_temp_file_path
        final_hash = utils.calculate_hash(str(current_temp_file_path)) if current_temp_file_path.exists() else None

        # 4. Replace the actual file with the reconstructed one
        log.info(f"Reconstruction successful. Updating {target_file_abs}")
        target_file_abs.parent.mkdir(parents=True, exist_ok=True)
        if current_temp_file_path.exists():
             shutil.move(str(current_temp_file_path), target_file_abs)
        elif target_file_abs.exists():
             # If reconstruction resulted in a deleted file, delete the original
             log.info(f"Reconstruction resulted in deleted file. Removing {target_file_abs}")
             target_file_abs.unlink()
        else:
             # Reconstruction resulted in deleted file, and original doesn't exist. No action.
             log.info(f"Reconstruction resulted in deleted file, target {target_file_abs} already absent.")


        log.info(f"Reconstruction complete for {file_path_rel}. Final hash: {final_hash}")
        return {"hash": final_hash, "error": None}

    except Exception as e:
        log.exception(f"Error during reconstruction of {file_path_rel}: {e}")
        return {"hash": None, "error": str(e)}
    finally:
        # Clean up temporary directory
        if temp_dir and Path(temp_dir).exists():
            try:
                shutil.rmtree(temp_dir)
                log.debug(f"Cleaned up temporary directory: {temp_dir}")
            except Exception as cleanup_e:
                log.error(f"Failed to clean up temporary directory {temp_dir}: {cleanup_e}")


def verify_file_hash(file_path: Path, expected_hash: Optional[str]) -> bool:
    """Verify if the file's current hash matches the expected hash."""
    if not expected_hash:
        log.warning(f"Cannot verify hash for {file_path}: no expected hash provided.")
        # Decide on behavior: strict (fail) or lenient (pass)? Let's be lenient.
        return True
    if not file_path.exists():
        log.warning(f"Cannot verify hash for {file_path}: file does not exist.")
        # If expected hash exists, but file doesn't, it's a mismatch.
        return False # Expected content, but file is gone.

    current_hash = utils.calculate_hash(str(file_path))
    log.debug(f"Verifying hash for {file_path}: Current='{current_hash}', Expected='{expected_hash}'")
    return current_hash == expected_hash

def get_last_applied_edit_for_file(
    file_path_rel: str, all_entries: List[Dict[str, Any]]
) -> Optional[Dict[str, Any]]:
    """Get the last 'accepted' or 'pending' edit entry for a specific file path."""
    file_entries = get_relevant_history_for_file(file_path_rel, all_entries)
    # Iterate backwards to find the most recent accepted/pending
    for entry in reversed(file_entries):
        status = entry.get("status", "").lower()
        if status in ["accepted", "pending"]:
            return entry
    return None


def generate_diff_from_checkpoint(
    current_file_path: Path,
    checkpoint_file_path: Path,
    file_display_name: str # Relative path for display in diff header
) -> Optional[str]:
    """Generates a diff between a checkpoint and the current file."""
    if not current_file_path.is_file() or not checkpoint_file_path.is_file():
        log.error("Cannot generate diff: one or both files missing.")
        return None
    try:
        # Use git diff --no-index for comparing arbitrary files
        cmd = [
            "git", "diff", "--no-index", "--",
            str(checkpoint_file_path), str(current_file_path)
        ]
        # Rename paths in diff output for clarity
        # Git diff will use the full paths, need to adjust header lines
        log.debug(f"Generating diff: {' '.join(cmd)}")
        result = subprocess.run(cmd, capture_output=True, text=True, check=False) # Allow non-zero exit code for diffs

        if result.returncode > 1: # 0=no diff, 1=diff found, >1=error
             log.error(f"Error generating diff: {result.stderr}")
             return None

        diff_content = result.stdout
        # Replace the absolute paths in header with the display name
        # --- a/<abs_checkpoint_path>
        # +++ b/<abs_current_path>
        # becomes
        # --- a/relative/path/to/file
        # +++ b/relative/path/to/file
        lines = diff_content.splitlines()
        if len(lines) >= 2:
             # Be careful with paths containing spaces
             lines[0] = f"--- a/{file_display_name}"
             lines[1] = f"+++ b/{file_display_name}"
        return "\n".join(lines)

    except Exception as e:
        log.exception(f"Error generating diff between checkpoint and current file: {e}")
        return None


def verify_and_prompt_if_modified(
     file_path_abs: Path,
     expected_hash: Optional[str],
     history_root: Path,
     workspace_root: Path,
) -> bool:
    """
    Checks if a file matches expected hash. If not, shows diff vs last checkpoint
    and prompts user whether to proceed (overwriting changes).

    Returns True if verification passes OR user confirms overwrite.
    Returns False if verification fails AND user chooses not to proceed.
    """
    if verify_file_hash(file_path_abs, expected_hash):
        return True # Hash matches, proceed

    # Hash mismatch or file missing when expected
    log.warning(f"Hash mismatch detected for {file_path_abs}. Expected hash: {expected_hash}")

    # Find the *actual* last checkpoint file associated with the expected hash state
    # This requires searching through history entries.
    # For simplicity here, we assume the expected_hash corresponds to *some* state we
    # can find in checkpoints. A more robust solution would trace back the history.
    # Let's try finding *any* checkpoint with that hash.

    target_checkpoint: Optional[Path] = None
    if expected_hash:
        chkpt_dir = history_root / CHECKPOINTS_DIR
        if chkpt_dir.is_dir():
             for item in chkpt_dir.rglob('*.chkpt'): # Search recursively
                  if item.is_file():
                       try:
                           chkpt_hash = utils.calculate_hash(str(item))
                           if chkpt_hash == expected_hash:
                               target_checkpoint = item
                               log.debug(f"Found checkpoint {item} matching expected hash {expected_hash}")
                               break
                       except Exception as e:
                            log.warning(f"Could not hash checkpoint {item}: {e}")

    diff_content = None
    if target_checkpoint and file_path_abs.exists():
         file_rel_path = get_relative_path(file_path_abs, workspace_root)
         diff_content = generate_diff_from_checkpoint(file_path_abs, target_checkpoint, file_rel_path)
    elif not file_path_abs.exists() and expected_hash:
         diff_content = f"--- Expected File (hash: {expected_hash})\n+++ Current State\n- File content was expected but is missing."
    elif not target_checkpoint:
         diff_content = f"{utils.COLOR_YELLOW}Could not find checkpoint matching expected hash {expected_hash} to generate diff.{utils.COLOR_RESET}"


    print(f"\n{utils.COLOR_YELLOW}Warning: File has been modified unexpectedly:{utils.COLOR_RESET} {file_path_abs}")
    print(f"(Expected hash: {expected_hash}, Current hash: {utils.calculate_hash(str(file_path_abs)) if file_path_abs.exists() else 'File Missing'})")

    if diff_content:
        print(f"\n{utils.COLOR_CYAN}Difference between last known state and current state:{utils.COLOR_RESET}")
        utils.print_diff_with_color(diff_content)
    else:
        print(f"\n{utils.COLOR_YELLOW}Could not generate diff to show external changes.{utils.COLOR_RESET}")


    while True:
        try:
            choice = input(f"\n{utils.COLOR_YELLOW}Proceed and discard these external changes? (y/n): {utils.COLOR_RESET}").lower().strip()
            if choice in ["y", "yes"]:
                log.warning(f"User chose to proceed, overwriting external changes to {file_path_abs}")
                return True
            elif choice in ["n", "no"]:
                log.info(f"User chose not to proceed due to external changes to {file_path_abs}")
                return False
            print(f"{utils.COLOR_RED}Invalid choice. Please enter 'y' or 'n'.{utils.COLOR_RESET}")
        except (EOFError, KeyboardInterrupt):
             print("\nOperation cancelled by user.")
             return False


def cleanup_stale_locks(history_root: Path) -> int:
    """Clean up any stale lock directories under the history directory."""
    cleaned_count = 0
    if not history_root.is_dir():
        log.debug("History root does not exist, no locks to clean.")
        return 0

    # Use rglob to find all .lockdir directories recursively
    for lockdir in history_root.rglob("*.lockdir"):
        if lockdir.is_dir(): # Ensure it's actually a directory
            lock_instance = utils.FileLock(str(lockdir).replace(".lockdir", "")) # Recreate lock instance for path logic
            log.debug(f"Checking potential stale lock: {lockdir}")
            # Use the lock's internal checker and cleanup
            try:
                if lock_instance._check_stale_lock():
                    log.info(f"Cleaned up stale lock: {lockdir}")
                    cleaned_count += 1
            except Exception as e:
                 log.warning(f"Error checking/cleaning lock {lockdir}: {e}")

    return cleaned_count


def add_snapshot_log_entry(
    file_path_rel: str,
    current_hash: Optional[str],
    checkpoint_file_rel: str,
    conversation_id: str,
    related_log_file_name: str, # The log file to add this entry to
    history_root: Path,
    lock_timeout: Optional[float] = None
) -> str:
    """Creates and adds a snapshot log entry to the specified log file."""
    snapshot_edit_id = str(uuid.uuid4())
    snapshot_entry = {
        "edit_id": snapshot_edit_id,
        "conversation_id": conversation_id,
        "tool_call_index": -1, # Special index for system-generated entries
        "timestamp": datetime.now(timezone.utc).isoformat(timespec='milliseconds').replace('+00:00', 'Z'),
        "operation": "snapshot",
        "file_path": file_path_rel,
        "source_path": None,
        "tool_name": "mcpdiff",
        "status": "done", # Snapshots are always 'done'
        "diff_file": None,
        "checkpoint_file": checkpoint_file_rel,
        "hash_before": current_hash, # Hash before this snapshot action (which is the current state)
        "hash_after": current_hash,  # Hash after snapshot action (should be the same)
        "log_file_source": related_log_file_name # Store source log
    }

    log_file_path = history_root / LOGS_DIR / related_log_file_name
    try:
        entries = utils.read_log_file(log_file_path, lock_timeout=lock_timeout)
        entries.append(snapshot_entry)
        utils.write_log_file(log_file_path, entries, lock_timeout=lock_timeout)
        log.info(f"Added snapshot entry {snapshot_edit_id} for {file_path_rel} to {related_log_file_name}")
        return snapshot_edit_id
    except Exception as e:
        log.error(f"Failed to add snapshot entry to {log_file_path}: {e}")
        raise HistoryError(f"Could not log snapshot operation for {file_path_rel}") from e


def add_revert_log_entry(
    rejected_entry_id: str, # The ID of the edit being reverted/rejected
    file_path_rel: str,
    hash_before_revert: Optional[str],
    hash_after_revert: Optional[str],
    revert_status: str, # 'done' or 'failed'
    conversation_id: str,
    related_log_file_name: str,
    history_root: Path,
    lock_timeout: Optional[float] = None
) -> str:
    """Creates and adds a revert log entry."""
    revert_edit_id = str(uuid.uuid4()) # New ID for the revert action itself
    revert_entry = {
        "edit_id": revert_edit_id,
        "conversation_id": conversation_id,
        "tool_call_index": -2, # Special index for revert actions
        "timestamp": datetime.now(timezone.utc).isoformat(timespec='milliseconds').replace('+00:00', 'Z'),
        "operation": "revert",
        "file_path": file_path_rel,
        "source_path": None,
        "tool_name": "mcpdiff",
        "status": revert_status,
        "diff_file": None,
        "checkpoint_file": None,
        "hash_before": hash_before_revert,
        "hash_after": hash_after_revert,
        "rejected_edit_id": rejected_entry_id, # Link to the edit that was rejected
        "log_file_source": related_log_file_name
    }

    log_file_path = history_root / LOGS_DIR / related_log_file_name
    try:
        entries = utils.read_log_file(log_file_path, lock_timeout=lock_timeout)
        entries.append(revert_entry)
        utils.write_log_file(log_file_path, entries, lock_timeout=lock_timeout)
        log.info(f"Added revert entry {revert_edit_id} (for rejected {rejected_entry_id}) to {related_log_file_name}")
        return revert_edit_id
    except Exception as e:
        log.error(f"Failed to add revert entry to {log_file_path}: {e}")
        raise HistoryError(f"Could not log revert operation for {rejected_entry_id}") from e
