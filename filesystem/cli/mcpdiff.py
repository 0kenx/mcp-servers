#!/usr/bin/env python
# mcpdiff.py

import argparse
import sys
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple

try:
    from mcp_edit_utils import (
        get_history_root,
        acquire_lock,
        release_lock,
        calculate_hash,
        read_log_file,
        write_log_file,
        apply_patch,
        HistoryError,
        ExternalModificationError,
        log,  # Use the logger from utils
        LOGS_DIR,
        DIFFS_DIR,
    )
except ImportError:
    print(
        "Error: Could not import mcp_shared_utils. Make sure it's accessible.",
        file=sys.stderr,
    )
    sys.exit(1)

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


def find_workspace_and_history(path: Optional[str]) -> Tuple[Path, Path]:
    """Finds the workspace and history root from CWD or specified path."""
    start_path = Path(path) if path else Path.cwd()
    history_root = get_history_root(str(start_path))
    if not history_root:
        print(
            f"Error: Could not find MCP history root (.mcp/edit_history/) in '{start_path}' or parent directories.",
            file=sys.stderr,
        )
        sys.exit(1)
    workspace_root = history_root.parent.parent  # Calculate here where needed
    return workspace_root, history_root


# --- handle_status ---
# Needs workspace_root for relative paths
def handle_status(args):
    workspace_root, history_root = find_workspace_and_history(
        args.workspace
    )  # Get workspace_root here
    log.info(f"Checking status in: {history_root}")
    log_dir = history_root / LOGS_DIR
    # ... (rest of status logic - unchanged, uses workspace_root correctly) ...
    all_entries = []
    if args.conv:  # Load specific conv log
        log_file = log_dir / f"{args.conv}.log"
        if log_file.exists():
            all_entries.extend(read_log_file(log_file))
        else:
            print(f"Log file not found: {args.conv}", file=sys.stderr)
    else:  # Load all logs
        for log_file in log_dir.glob("*.log"):
            all_entries.extend(read_log_file(log_file))
    # Filter
    filtered_entries = all_entries
    if args.file:
        target_path = str(Path(args.file).resolve())
        filtered_entries = [
            e
            for e in filtered_entries
            if e.get("file_path") == target_path or e.get("source_path") == target_path
        ]
    if args.status:
        filtered_entries = [
            e for e in filtered_entries if e.get("status") == args.status
        ]
    # Sort and limit
    filtered_entries.sort(
        key=lambda e: (e.get("timestamp", ""), e.get("tool_call_index", 0))
    )
    if args.limit > 0:
        filtered_entries = filtered_entries[-args.limit :]
    # Print
    if not filtered_entries:
        print("No matching history entries found.")
        return
    print(
        f"{'EDIT_ID':<36} {'TIMESTAMP':<26} {'STATUS':<8} {'OP':<8} {'CONV_ID':<15} FILE_PATH"
    )
    print("-" * 120)
    for entry in filtered_entries:
        ts = entry.get("timestamp", "")
        file_str = entry.get("file_path", "N/A")
        conv_id_short = entry.get("conversation_id", "N/A")[:15]
        try:
            ts_str = datetime.fromisoformat(ts.replace("Z", "+00:00")).strftime(
                "%Y-%m-%d %H:%M:%S"
            )
        except:
            ts_str = ts[:19]
        try:
            file_str = str(
                Path(file_str).relative_to(workspace_root)
            )  # Use workspace_root
        except ValueError:
            pass
        print(
            f"{entry.get('edit_id', 'N/A'):<36} {ts_str:<26} {entry.get('status', 'N/A'):<8} {entry.get('operation', 'N/A'):<8} {conv_id_short:<15} {file_str}"
        )


# --- handle_show ---
# Doesn't need workspace_root directly
def handle_show(args):
    # Corrected: workspace_root is not needed here, only history_root
    _, history_root = find_workspace_and_history(args.workspace)
    identifier = args.identifier
    # ... (rest of show logic - unchanged) ...
    found_diffs = False
    log_dir = history_root / LOGS_DIR
    potential_diff_path = None  # Try finding by edit_id first
    for conv_dir in (history_root / DIFFS_DIR).iterdir():
        if conv_dir.is_dir():
            diff_file = conv_dir / f"{identifier}.diff"
            if diff_file.exists():
                potential_diff_path = diff_file
                break
    if potential_diff_path:  # Found by edit_id
        try:
            with open(potential_diff_path, "r", encoding="utf-8") as f:
                print(f.read())
                found_diffs = True
        except IOError as e:
            print(f"Error reading diff {potential_diff_path}: {e}", file=sys.stderr)
    else:  # Try finding by conversation_id
        log_file = log_dir / f"{identifier}.log"
        if log_file.exists():
            entries = read_log_file(log_file)
            entries.sort(key=lambda e: e.get("tool_call_index", 0))
            for entry in entries:
                diff_path_str = entry.get("diff_file")
                print(
                    f"\n--- Edit: {entry['edit_id']} (Op: {entry['operation']}, File: {entry['file_path']}, Status: {entry['status']}) ---"
                )
                if diff_path_str:
                    diff_path = history_root / diff_path_str
                    if diff_path.exists():
                        try:
                            with open(diff_path, "r", encoding="utf-8") as f:
                                print(f.read())
                                found_diffs = True
                        except IOError as e:
                            print(
                                f"  Error reading diff file {diff_path}: {e}",
                                file=sys.stderr,
                            )
                    else:
                        print(f"  Diff file not found: {diff_path}")
                elif entry["operation"] not in ["delete", "move"]:
                    print("  (No diff file associated)")
    if not found_diffs:
        print(f"No diff found for identifier: {identifier}", file=sys.stderr)


# --- modify_status --- (unchanged)
def modify_status(
    history_root: Path,
    target_status: str,
    edit_id: Optional[str] = None,
    conversation_id: Optional[str] = None,
) -> List[Tuple[str, str]]:
    # ... (logic remains the same) ...
    if not edit_id and not conversation_id:
        raise ValueError("Need edit_id or conversation_id")
    log_dir = history_root / LOGS_DIR
    affected_files_map: Dict[Tuple[str, str], bool] = {}
    log_files_to_process: List[Path] = []
    if conversation_id:
        log_file = log_dir / f"{conversation_id}.log"
        if log_file.exists():
            log_files_to_process.append(log_file)
        else:
            raise FileNotFoundError(f"Log file not found: {conversation_id}")
    else:  # Find log containing edit_id
        found = False
        for log_file in log_dir.glob("*.log"):
            try:
                with open(log_file, "r") as f:
                    if edit_id in f.read():
                        log_files_to_process.append(log_file)
                        found = True
                        break
            except IOError:
                continue
        if not found:
            raise FileNotFoundError(f"Log not found for edit_id: {edit_id}")
    # Process logs
    for log_file in log_files_to_process:
        log_lock = None
        modified = False
        conv_id = log_file.stem
        try:
            log_lock = acquire_lock(str(log_file))
            entries = read_log_file(log_file)
            new_entries = []
            for entry in entries:
                current_edit_id = entry.get("edit_id")
                current_status = entry.get("status")
                target_this = False
                if edit_id and current_edit_id == edit_id:
                    target_this = True
                elif (
                    conversation_id
                    and entry.get("conversation_id") == conversation_id
                    and current_status == "pending"
                ):
                    target_this = True
                if target_this and current_status != target_status:
                    if (
                        current_status == "pending"
                    ):  # Only allow pending -> accepted/rejected
                        entry["status"] = target_status
                        modified = True
                        log.info(
                            f"Set status to '{target_status}' for {current_edit_id} in {conv_id}"
                        )
                        if entry.get("file_path"):
                            affected_files_map[(conv_id, entry["file_path"])] = True
                        if entry.get("source_path"):
                            affected_files_map[(conv_id, entry["source_path"])] = (
                                True  # Track source for moves
                            )
                    else:
                        log.warning(
                            f"Cannot change {current_edit_id} from '{current_status}' to '{target_status}'."
                        )
                new_entries.append(entry)
            if modified:
                write_log_file(log_file, new_entries)
        except (HistoryError, FileNotFoundError, TimeoutError) as e:
            log.error(f"Failed modify status in {log_file}: {e}")
        finally:
            release_lock(log_lock)
    return list(affected_files_map.keys())


# --- handle_accept --- (unchanged)
def handle_accept(args):
    _, history_root = find_workspace_and_history(args.workspace)
    try:
        modify_status(history_root, "accepted", args.edit_id, args.conv)
        print("Status updated to 'accepted'.")
    except (ValueError, FileNotFoundError) as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


# --- handle_reject --- (unchanged)
def handle_reject(args):
    _, history_root = find_workspace_and_history(args.workspace)
    try:
        affected_conv_files = modify_status(
            history_root, "rejected", args.edit_id, args.conv
        )
        print("Status updated to 'rejected'. Triggering re-apply...")
        overall_success = True
        processed_files = set()
        for conv_id, file_path in affected_conv_files:
            if (conv_id, file_path) in processed_files:
                continue
            print(
                f"Re-applying changes for file: {file_path} (conversation: {conv_id})"
            )
            success = reapply_conversation_state(conv_id, file_path, history_root)
            if not success:
                print(f"ERROR: Failed re-apply for: {file_path}", file=sys.stderr)
                overall_success = False
            processed_files.add((conv_id, file_path))
        if overall_success:
            print("Re-apply completed successfully.")
        else:
            print("Re-apply completed with errors.", file=sys.stderr)
            sys.exit(1)
    except (ValueError, FileNotFoundError, ExternalModificationError) as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        log.exception("Unexpected error during reject")
        print(f"Unexpected Error: {e}", file=sys.stderr)
        sys.exit(1)


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
        "--edit-id", help="The specific edit_id to accept."
    )  # Changed to --edit-id for clarity
    group_accept.add_argument(
        "--conv", help="Accept all pending edits for a conversation_id."
    )
    parser_accept.set_defaults(func=handle_accept)
    # reject
    parser_reject = subparsers.add_parser(
        "reject", help="Mark edits as rejected and revert changes."
    )
    group_reject = parser_reject.add_mutually_exclusive_group(required=True)
    group_reject.add_argument(
        "--edit-id", help="The specific edit_id to reject."
    )  # Changed to --edit-id
    group_reject.add_argument(
        "--conv", help="Reject all pending/accepted edits for a conversation_id."
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
