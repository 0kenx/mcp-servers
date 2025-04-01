#!/usr/bin/env python
# mcpdiff.py - Main executable

import sys
import argparse
import os
import shutil
import uuid
from pathlib import Path
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional

# Import from local utility and history modules
import mcpdiff_utils as utils
import mcpdiff_history as history
from mcpdiff_utils import (
    log, HistoryError, ExternalModificationError, TimeoutError, AmbiguousIDError,
    COLOR_RESET, COLOR_RED, COLOR_GREEN, COLOR_YELLOW, COLOR_CYAN, COLOR_BLUE,
    LOCK_TIMEOUT, HISTORY_DIR_NAME, CHECKPOINTS_DIR
)


# --- Command Handlers ---

def handle_status(args: argparse.Namespace, workspace_root: Path, history_root: Path, all_entries: List[Dict[str, Any]]) -> None:
    """Handle the status command."""
    log.debug("Processing status command")

    if not all_entries:
        print(f"{utils.COLOR_YELLOW}No edit history entries found.{utils.COLOR_RESET}")
        return

    # Apply filters - Use limit=0 to show all if limit not specified or <= 0
    display_limit = args.limit if args.limit > 0 else 0
    # Filter returns newest first if limited
    filtered_entries = history.filter_entries(
        all_entries,
        conv_id=args.conv,
        file_path=args.file,
        status=args.status,
        time_filter=args.time,
        op_type=args.op,
        limit=display_limit or None # Pass None if limit is 0 to get all (sorted newest first)
    )

    if not filtered_entries:
        print(f"{utils.COLOR_YELLOW}No entries match the specified filters.{utils.COLOR_RESET}")
        # Optionally print filter criteria here if useful
        return

    # Print header and entries
    history.print_entry_list_header()
    for entry in filtered_entries: # Already sorted newest first by filter_entries if limit used
        print(history.format_entry_summary(entry))

    # Print summary
    total_shown = len(filtered_entries)
    total_available = len(all_entries) # Or count after non-limit filters? Let's use total.
    print(f"\nShowing {total_shown} of {total_available} total entries.")
    if display_limit > 0 and total_shown == display_limit:
        print(f"(Limited to {display_limit}, use -n 0 to show all matching)")

    # Show filter info if any were applied
    filters_applied = args.conv or args.file or args.status or args.time or args.op
    if filters_applied:
        print(f"\n{utils.COLOR_CYAN}Applied filters:{utils.COLOR_RESET}")
        if args.conv: print(f"  Conversation ID: {args.conv}")
        if args.file: print(f"  File path: {args.file}")
        if args.status: print(f"  Status: {args.status}")
        if args.time: print(f"  Time filter: {args.time}")
        if args.op: print(f"  Operation type: {args.op}")


def handle_show(args: argparse.Namespace, workspace_root: Path, history_root: Path, all_entries: List[Dict[str, Any]]) -> None:
    """Handle the show command."""
    identifier = args.identifier
    log.debug(f"Processing show command for identifier: {identifier}")

    if not all_entries:
        print(f"{utils.COLOR_YELLOW}No edit history entries found.{utils.COLOR_RESET}")
        return

    # Try finding a single entry by edit ID prefix
    try:
        entry = history.find_entry_by_id(all_entries, identifier)
        if entry:
            print(f"\n{utils.COLOR_CYAN}Details for Edit: {entry.get('edit_id', 'N/A')}{utils.COLOR_RESET}")
            history.print_entry_list_header()
            print(history.format_entry_summary(entry))
            print("-" * 100)
            diff_content = history.get_diff_for_entry(entry, history_root)
            utils.print_diff_with_color(diff_content)
            return
        # If find_entry_by_id returned None (not found), proceed to check conversation ID
    except AmbiguousIDError as e:
        # Ambiguous ID error already printed message, just exit handler
        log.warning(f"Ambiguous ID provided: {e}")
        # Let it fall through to conversation search? Or exit? Let's exit.
        # print(f"{utils.COLOR_RED}Could not show details due to ambiguous ID.{utils.COLOR_RESET}")
        raise e # Re-raise for main handler to catch and report
    except KeyboardInterrupt:
         print("\nOperation cancelled during ambiguous ID selection.")
         return # Exit handler gracefully


    # If not found as a unique edit ID, try as a conversation ID prefix/suffix
    conv_entries = history.find_entries_by_conversation(all_entries, identifier)

    if not conv_entries:
        print(f"{utils.COLOR_RED}No edit or conversation found matching identifier: {identifier}{utils.COLOR_RESET}")
        return

    # Found conversation entries
    conv_id = conv_entries[0].get('conversation_id', identifier) # Use ID from first entry
    print(f"\n{utils.COLOR_CYAN}Showing {len(conv_entries)} edits for Conversation: {conv_id}{utils.COLOR_RESET}")

    for i, entry in enumerate(conv_entries): # Already sorted chronologically
        print("\n" + "=" * 80)
        print(f"{utils.COLOR_BLUE}Edit {i + 1}/{len(conv_entries)} - ID: {entry.get('edit_id', 'N/A')}{utils.COLOR_RESET}")
        history.print_entry_list_header()
        print(history.format_entry_summary(entry))
        print("-" * 100)
        diff_content = history.get_diff_for_entry(entry, history_root)
        utils.print_diff_with_color(diff_content)

    print("\n" + "=" * 80)


def _accept_or_reject_single(
    edit_id_prefix: str,
    action: str, # 'accept' or 'reject'
    workspace_root: Path,
    history_root: Path,
    all_entries: List[Dict[str, Any]],
    lock_timeout: Optional[float] = None
) -> Tuple[int, int]:
    """Helper to accept or reject a single edit."""
    successful = 0
    failed = 0
    try:
        entry = history.find_entry_by_id(all_entries, edit_id_prefix)
        if not entry:
            print(f"{utils.COLOR_RED}No entry found with ID prefix: {edit_id_prefix}{utils.COLOR_RESET}")
            return 0, 1 # 0 success, 1 failure

        edit_id = entry.get("edit_id", "N/A")
        current_status = entry.get("status", "unknown").lower()
        file_path_rel = entry.get("file_path")
        conv_id = entry.get("conversation_id", "unknown_conv")
        log_file_name = entry.get("log_file_source") # Get source log

        if not file_path_rel:
            print(f"{utils.COLOR_RED}Missing file path in entry {edit_id}. Cannot {action}.{utils.COLOR_RESET}")
            return 0, 1
        if not log_file_name:
             print(f"{utils.COLOR_RED}Missing log file source in entry {edit_id}. Cannot update status.{utils.COLOR_RESET}")
             return 0, 1

        file_path_abs = workspace_root / file_path_rel
        log_file_path = history_root / utils.LOGS_DIR / log_file_name


        # --- Pre-Action Checks ---
        if action == "accept":
            if current_status == "accepted":
                print(f"{utils.COLOR_YELLOW}Edit {edit_id} is already accepted.{utils.COLOR_RESET}")
                return 1, 0 # Already done, count as success
        elif action == "reject":
            if current_status == "rejected":
                print(f"{utils.COLOR_YELLOW}Edit {edit_id} is already rejected.{utils.COLOR_RESET}")
                return 1, 0 # Already done, count as success


        # --- Hash Verification (Check for external modifications) ---
        # Find the last *applied* edit before this one to get expected hash
        last_applied_edit = history.get_last_applied_edit_for_file(file_path_rel, all_entries)
        expected_hash = last_applied_edit.get("hash_after") if last_applied_edit else None

        if not history.verify_and_prompt_if_modified(file_path_abs, expected_hash, history_root, workspace_root):
             print(f"{utils.COLOR_YELLOW}Operation aborted by user due to external modifications.{utils.COLOR_RESET}")
             return 0, 1


        # --- Perform Action ---
        if action == "accept":
            # Ensure file state is correct by reconstructing (applying accepted & pending)
            print(f"Ensuring file state for {file_path_rel} before accepting {edit_id}...")
            recon_result = history.reconstruct_file_from_history(
                file_path_rel, all_entries, workspace_root, history_root, apply_only_accepted=False
            )
            if recon_result["error"]:
                print(f"{utils.COLOR_RED}Failed to reconstruct file state: {recon_result['error']}{utils.COLOR_RESET}")
                # Don't accept if reconstruction failed
                return 0, 1

            final_hash = recon_result["hash"]
            # Update the entry's hash_after field BEFORE updating status
            entry["hash_after"] = final_hash # Modify in-memory copy

            # Now update status in the log file
            if history.update_entry_status(entry, "accepted", history_root, lock_timeout=lock_timeout):
                print(f"{utils.COLOR_GREEN}Successfully accepted edit: {edit_id}{utils.COLOR_RESET}")
                successful += 1
            else:
                print(f"{utils.COLOR_RED}Failed to update status for accepted edit: {edit_id}{utils.COLOR_RESET}")
                # Should we revert the reconstruction? Risky. Log failure.
                failed += 1

        elif action == "reject":
            # 1. Take snapshot of current state *before* rejecting
            current_hash = utils.calculate_hash(str(file_path_abs)) if file_path_abs.exists() else None
            checkpoint_dir = history_root / CHECKPOINTS_DIR / conv_id
            checkpoint_dir.mkdir(parents=True, exist_ok=True)
            sanitized_path = file_path_rel.replace("/", "_").replace("\\", "_")
            # Use edit ID in checkpoint name for easier association
            chkpt_filename = f"{sanitized_path}_{edit_id}_{utils.generate_hex_timestamp()}.chkpt"
            checkpoint_path_abs = checkpoint_dir / chkpt_filename
            checkpoint_rel_path = history.get_relative_path(checkpoint_path_abs, history_root)

            snapshot_edit_id = "N/A" # Default if snapshot fails
            try:
                if file_path_abs.exists():
                    shutil.copy2(file_path_abs, checkpoint_path_abs)
                else:
                    checkpoint_path_abs.touch() # Create empty checkpoint if file missing

                # Log snapshot operation
                snapshot_edit_id = history.add_snapshot_log_entry(
                    file_path_rel, current_hash, checkpoint_rel_path, conv_id, log_file_name, history_root, lock_timeout
                )
                log.info(f"Created snapshot {checkpoint_rel_path} before rejecting {edit_id}")

            except Exception as snap_err:
                 print(f"{utils.COLOR_RED}Failed to create or log snapshot before rejecting: {snap_err}{utils.COLOR_RESET}")
                 # Proceed with rejection? Risky without snapshot. Let's abort.
                 return 0, 1


            # 2. Mark the edit as rejected *first*
            if not history.update_entry_status(entry, "rejected", history_root, lock_timeout=lock_timeout):
                print(f"{utils.COLOR_RED}Failed to mark edit {edit_id} as rejected. Aborting rejection process.{utils.COLOR_RESET}")
                # Consider deleting the snapshot? Maybe not, it records state *before* failure.
                return 0, 1
            print(f"{utils.COLOR_YELLOW}Marked edit {edit_id} as rejected.{utils.COLOR_RESET}")
            # Update all_entries list locally to reflect the change for reconstruction
            # This requires finding the entry in the main list and updating it.
            for idx, e in enumerate(all_entries):
                if e.get("edit_id") == edit_id:
                    all_entries[idx]["status"] = "rejected"
                    break


            # 3. Reconstruct file state, applying only 'accepted' edits
            print(f"Reconstructing file {file_path_rel} state (skipping rejected)...")
            recon_result = history.reconstruct_file_from_history(
                file_path_rel, all_entries, workspace_root, history_root, apply_only_accepted=True
            )

            # 4. Log the revert operation attempt
            revert_status = "done" if recon_result["error"] is None else "failed"
            final_hash = recon_result.get("hash")
            try:
                history.add_revert_log_entry(
                    edit_id, file_path_rel, current_hash, final_hash, revert_status,
                    conv_id, log_file_name, history_root, lock_timeout
                )
            except Exception as revert_log_err:
                 # Log failure but continue reporting main result
                 print(f"{utils.COLOR_RED}Failed to log revert operation: {revert_log_err}{utils.COLOR_RESET}")


            # 5. Handle reconstruction result
            if recon_result["error"]:
                print(f"{utils.COLOR_RED}Failed to reconstruct file after rejecting {edit_id}: {recon_result['error']}{utils.COLOR_RESET}")
                print(f"{utils.COLOR_YELLOW}Attempting to restore file from snapshot: {checkpoint_path_abs}{utils.COLOR_RESET}")
                try:
                    if checkpoint_path_abs.exists():
                        shutil.copy2(checkpoint_path_abs, file_path_abs) # Restore snapshot
                        print(f"{utils.COLOR_GREEN}Restored file from snapshot.{utils.COLOR_RESET}")
                    elif file_path_abs.exists():
                         # Snapshot doesn't exist, but file does? Maybe remove the file? Risky.
                         log.warning("Snapshot missing, cannot fully restore state before rejection.")
                    # Should we revert the status back to pending? Yes, failed rejection.
                    if history.update_entry_status(entry, current_status, history_root, lock_timeout=lock_timeout):
                         print(f"{utils.COLOR_YELLOW}Reset status of edit {edit_id} back to {current_status}.{utils.COLOR_RESET}")
                    else:
                         print(f"{utils.COLOR_RED}Failed to reset status for edit {edit_id} after failed rejection.{utils.COLOR_RESET}")
                    failed += 1

                except Exception as restore_err:
                     print(f"{utils.COLOR_RED}Failed to restore file from snapshot: {restore_err}{utils.COLOR_RESET}")
                     failed += 1
            else:
                print(f"{utils.COLOR_GREEN}Successfully rejected edit {edit_id} and reconstructed file.{utils.COLOR_RESET}")
                successful += 1

    except AmbiguousIDError as e:
        # Error message already printed by find_entry_by_id
        log.warning(f"Cannot {action} due to ambiguous ID: {e}")
        failed += 1
    except KeyboardInterrupt:
         print(f"\n{action.capitalize()} operation cancelled by user.")
         # Don't count as failure, just cancelled
    except Exception as e:
        log.exception(f"Unexpected error during {action} of single edit {edit_id_prefix}: {e}")
        print(f"{utils.COLOR_RED}An unexpected error occurred: {e}{utils.COLOR_RESET}")
        failed += 1

    return successful, failed


def _accept_or_reject_conversation(
    conv_id_prefix: str,
    action: str, # 'accept' or 'reject'
    workspace_root: Path,
    history_root: Path,
    all_entries: List[Dict[str, Any]],
    lock_timeout: Optional[float] = None
) -> Tuple[int, int]:
    """Helper to accept or reject all relevant edits for a conversation."""
    conv_entries = history.find_entries_by_conversation(all_entries, conv_id_prefix)
    if not conv_entries:
        print(f"{utils.COLOR_RED}No entries found for conversation matching ID: {conv_id_prefix}{utils.COLOR_RESET}")
        return 0, 0 # No entries, no failures

    conv_id = conv_entries[0].get("conversation_id", "unknown_conv")
    log.info(f"Processing {action} for conversation {conv_id} ({len(conv_entries)} entries total)")

    # Filter entries relevant for the action
    if action == "accept":
        relevant_entries = [e for e in conv_entries if e.get("status") == "pending"]
        if not relevant_entries:
             print(f"{utils.COLOR_YELLOW}No pending edits found to accept for conversation {conv_id}.{utils.COLOR_RESET}")
             return 0, 0
        print(f"Found {len(relevant_entries)} pending edits to accept.")
    elif action == "reject":
        relevant_entries = [e for e in conv_entries if e.get("status") in ["pending", "accepted"]]
        if not relevant_entries:
             print(f"{utils.COLOR_YELLOW}No pending or accepted edits found to reject for conversation {conv_id}.{utils.COLOR_RESET}")
             return 0, 0
        print(f"Found {len(relevant_entries)} pending/accepted edits to reject.")
    else:
        return 0, 0 # Should not happen

    # Group by file path for processing
    entries_by_file: Dict[str, List[Dict[str, Any]]] = {}
    for entry in relevant_entries:
        file_path = entry.get("file_path")
        if file_path:
            entries_by_file.setdefault(file_path, []).append(entry)

    total_successful = 0
    total_failed = 0

    # Process file by file
    for file_path_rel, file_edits in entries_by_file.items():
        print(f"\n--- Processing file: {file_path_rel} ({len(file_edits)} edits) ---")
        file_path_abs = workspace_root / file_path_rel
        log_file_name = file_edits[0].get("log_file_source") # Assume all edits for file in conv are in same log
        if not log_file_name:
            print(f"{utils.COLOR_RED}Cannot process file {file_path_rel}: missing log file source.{utils.COLOR_RESET}")
            total_failed += len(file_edits)
            continue

        # --- Hash Verification ---
        last_applied_edit = history.get_last_applied_edit_for_file(file_path_rel, all_entries)
        expected_hash = last_applied_edit.get("hash_after") if last_applied_edit else None
        if not history.verify_and_prompt_if_modified(file_path_abs, expected_hash, history_root, workspace_root):
             print(f"{utils.COLOR_YELLOW}Skipping file {file_path_rel} due to user cancellation.{utils.COLOR_RESET}")
             # How many failures? Count all relevant edits for this file as failed.
             total_failed += len(file_edits)
             continue

        # --- Perform Action for File ---
        file_success = 0
        file_failed = 0

        if action == "accept":
            # Reconstruct applies pending anyway
            print(f"Ensuring file state for {file_path_rel} before accepting...")
            recon_result = history.reconstruct_file_from_history(
                file_path_rel, all_entries, workspace_root, history_root, apply_only_accepted=False
            )
            if recon_result["error"]:
                print(f"{utils.COLOR_RED}Failed to reconstruct file state for {file_path_rel}: {recon_result['error']}{utils.COLOR_RESET}")
                file_failed += len(file_edits)
            else:
                final_hash = recon_result["hash"]
                # Update status for all relevant edits for this file
                for entry in file_edits:
                    entry["hash_after"] = final_hash # Update in-memory hash
                    if history.update_entry_status(entry, "accepted", history_root, lock_timeout=lock_timeout):
                        log.debug(f"Marked edit {entry.get('edit_id')} as accepted.")
                        file_success += 1
                    else:
                        log.error(f"Failed to mark edit {entry.get('edit_id')} as accepted.")
                        file_failed += 1
                if file_failed == 0:
                     print(f"{utils.COLOR_GREEN}Accepted {file_success} edits for {file_path_rel}.{utils.COLOR_RESET}")
                else:
                     print(f"{utils.COLOR_YELLOW}Accepted {file_success}, Failed {file_failed} status updates for {file_path_rel}.{utils.COLOR_RESET}")


        elif action == "reject":
            # 1. Snapshot
            current_hash = utils.calculate_hash(str(file_path_abs)) if file_path_abs.exists() else None
            checkpoint_dir = history_root / CHECKPOINTS_DIR / conv_id
            checkpoint_dir.mkdir(parents=True, exist_ok=True)
            sanitized_path = file_path_rel.replace("/", "_").replace("\\", "_")
            # Use conv ID and file name for checkpoint
            chkpt_filename = f"{sanitized_path}_{conv_id}_{utils.generate_hex_timestamp()}.chkpt"
            checkpoint_path_abs = checkpoint_dir / chkpt_filename
            checkpoint_rel_path = history.get_relative_path(checkpoint_path_abs, history_root)

            snapshot_failed = False
            snapshot_edit_id = "N/A"
            try:
                if file_path_abs.exists(): shutil.copy2(file_path_abs, checkpoint_path_abs)
                else: checkpoint_path_abs.touch()
                snapshot_edit_id = history.add_snapshot_log_entry(
                    file_path_rel, current_hash, checkpoint_rel_path, conv_id, log_file_name, history_root, lock_timeout
                )
            except Exception as snap_err:
                 print(f"{utils.COLOR_RED}Failed snapshot for {file_path_rel}: {snap_err}{utils.COLOR_RESET}")
                 snapshot_failed = True
                 file_failed += len(file_edits)


            if not snapshot_failed:
                # 2. Mark all as rejected
                reject_update_failed = False
                original_statuses = {} # Store original status in case we need to revert
                for entry in file_edits:
                    edit_id = entry.get("edit_id")
                    original_statuses[edit_id] = entry.get("status", "unknown")
                    if not history.update_entry_status(entry, "rejected", history_root, lock_timeout=lock_timeout):
                        log.error(f"Failed to mark edit {edit_id} as rejected.")
                        reject_update_failed = True
                    else:
                         # Update local all_entries list
                         for idx, e in enumerate(all_entries):
                            if e.get("edit_id") == edit_id:
                                all_entries[idx]["status"] = "rejected"
                                break


                if reject_update_failed:
                     print(f"{utils.COLOR_RED}Failed to mark one or more edits as rejected for {file_path_rel}. Aborting rejection for this file.{utils.COLOR_RESET}")
                     # TODO: Revert statuses? Complex. For now, just count as failure.
                     file_failed += len(file_edits) - file_success # Count successes so far
                else:
                    print(f"{utils.COLOR_YELLOW}Marked {len(file_edits)} edits for {file_path_rel} as rejected.{utils.COLOR_RESET}")

                    # 3. Reconstruct (applying only accepted)
                    print(f"Reconstructing file {file_path_rel} (skipping rejected)...")
                    recon_result = history.reconstruct_file_from_history(
                        file_path_rel, all_entries, workspace_root, history_root, apply_only_accepted=True
                    )

                    # 4. Log revert attempt (use last rejected edit ID for context?)
                    last_rejected_id = file_edits[-1].get("edit_id", "multi-reject")
                    revert_status = "done" if recon_result["error"] is None else "failed"
                    final_hash = recon_result.get("hash")
                    try:
                         history.add_revert_log_entry(
                              last_rejected_id, file_path_rel, current_hash, final_hash, revert_status,
                              conv_id, log_file_name, history_root, lock_timeout
                         )
                    except Exception as revert_log_err:
                          print(f"{utils.COLOR_RED}Failed to log revert op for {file_path_rel}: {revert_log_err}{utils.COLOR_RESET}")


                    # 5. Handle result
                    if recon_result["error"]:
                        print(f"{utils.COLOR_RED}Failed reconstruction for {file_path_rel}: {recon_result['error']}{utils.COLOR_RESET}")
                        print(f"{utils.COLOR_YELLOW}Attempting restore from snapshot: {checkpoint_path_abs}{utils.COLOR_RESET}")
                        try:
                             if checkpoint_path_abs.exists(): shutil.copy2(checkpoint_path_abs, file_path_abs)
                             # Revert statuses back
                             print(f"{utils.COLOR_YELLOW}Reverting statuses for {len(file_edits)} edits...{utils.COLOR_RESET}")
                             revert_status_ok = True
                             for entry in file_edits:
                                  eid = entry.get("edit_id")
                                  if not history.update_entry_status(entry, original_statuses.get(eid,"pending"), history_root, lock_timeout=lock_timeout):
                                       revert_status_ok = False
                             if not revert_status_ok: print(f"{utils.COLOR_RED}Failed to revert all statuses.{utils.COLOR_RESET}")

                        except Exception as restore_err:
                             print(f"{utils.COLOR_RED}Snapshot restore failed: {restore_err}{utils.COLOR_RESET}")
                        file_failed += len(file_edits)

                    else:
                         print(f"{utils.COLOR_GREEN}Successfully rejected edits and reconstructed {file_path_rel}.{utils.COLOR_RESET}")
                         file_success += len(file_edits)

        total_successful += file_success
        total_failed += file_failed
        # End loop for file_path_rel

    print("\n" + "-" * 30)
    print(f"Conversation {action} summary: {total_successful} successful actions, {total_failed} failed actions.")
    return total_successful, total_failed


def handle_accept(args: argparse.Namespace, workspace_root: Path, history_root: Path, all_entries: List[Dict[str, Any]]) -> None:
    """Handle the accept command."""
    log.debug("Processing accept command")
    lock_timeout = args.timeout # Pass timeout argument

    if not all_entries:
        print(f"{utils.COLOR_YELLOW}No edit history entries found.{utils.COLOR_RESET}")
        return

    if args.edit_id:
        _accept_or_reject_single(args.edit_id, "accept", workspace_root, history_root, all_entries, lock_timeout)
    elif args.conv:
        _accept_or_reject_conversation(args.conv, "accept", workspace_root, history_root, all_entries, lock_timeout)


def handle_reject(args: argparse.Namespace, workspace_root: Path, history_root: Path, all_entries: List[Dict[str, Any]]) -> None:
    """Handle the reject command."""
    log.debug("Processing reject command")
    lock_timeout = args.timeout # Pass timeout argument

    if not all_entries:
        print(f"{utils.COLOR_YELLOW}No edit history entries found.{utils.COLOR_RESET}")
        return

    if args.edit_id:
        _accept_or_reject_single(args.edit_id, "reject", workspace_root, history_root, all_entries, lock_timeout)
    elif args.conv:
        _accept_or_reject_conversation(args.conv, "reject", workspace_root, history_root, all_entries, lock_timeout)


def handle_review(args: argparse.Namespace, workspace_root: Path, history_root: Path, all_entries: List[Dict[str, Any]]) -> None:
    """Handle the review command."""
    log.debug("Processing review command")
    lock_timeout = args.timeout

    if not all_entries:
        print(f"{utils.COLOR_YELLOW}No edit history entries found.{utils.COLOR_RESET}")
        return

    # Filter for pending edits
    pending_entries = [e for e in all_entries if e.get("status") == "pending"]

    # Further filter by conversation if specified
    if args.conv:
        pending_entries = history.filter_entries(pending_entries, conv_id=args.conv, limit=None) # No limit for review

    if not pending_entries:
        print(f"{utils.COLOR_YELLOW}No pending edits found{f' for conversation {args.conv}' if args.conv else ''} to review.{utils.COLOR_RESET}")
        return

    print(f"Found {len(pending_entries)} pending edits to review. Edits are shown oldest first.")
    # Sort oldest first for review context
    pending_entries.sort(key=lambda e: (utils.parse_timestamp(e.get("timestamp", 0)), e.get("tool_call_index", float('inf'))))


    accepted_count = 0
    rejected_count = 0
    skipped_count = 0

    try:
        for i, entry in enumerate(pending_entries):
            edit_id = entry.get("edit_id", "N/A")
            conv_id = entry.get("conversation_id", "N/A")
            file_path_rel = entry.get("file_path", "N/A")

            print("\n" + "=" * 80)
            print(f"{utils.COLOR_CYAN}Reviewing Edit {i + 1}/{len(pending_entries)} - ID: {edit_id}{utils.COLOR_RESET}")
            print(f"Conversation: {conv_id}, File: {file_path_rel}")
            history.print_entry_list_header()
            print(history.format_entry_summary(entry))
            print("-" * 100)

            diff_content = history.get_diff_for_entry(entry, history_root)
            utils.print_diff_with_color(diff_content)

            while True:
                prompt = (f"\nAction? ({utils.COLOR_GREEN}[a]{utils.COLOR_RESET}ccept, "
                          f"{utils.COLOR_RED}[r]{utils.COLOR_RESET}eject, "
                          f"{utils.COLOR_BLUE}[s]{utils.COLOR_RESET}kip, "
                          f"{utils.COLOR_YELLOW}[q]{utils.COLOR_RESET}uit): ")
                choice = input(prompt).lower().strip()

                if choice in ["a", "accept"]:
                    print("Accepting...")
                    # Use the single accept function - it handles reconstruction & status update
                    # Pass the full all_entries list for context
                    a_ok, a_fail = _accept_or_reject_single(edit_id, "accept", workspace_root, history_root, all_entries, lock_timeout)
                    if a_ok > 0: accepted_count += 1
                    # Update all_entries list with accepted status for subsequent reviews in this session
                    for idx, e in enumerate(all_entries):
                        if e.get("edit_id") == edit_id:
                            all_entries[idx]["status"] = "accepted"
                            break
                    break # Next entry
                elif choice in ["r", "reject"]:
                    print("Rejecting...")
                    # Use the single reject function
                    r_ok, r_fail = _accept_or_reject_single(edit_id, "reject", workspace_root, history_root, all_entries, lock_timeout)
                    if r_ok > 0: rejected_count += 1
                    # Status already updated in all_entries by the helper on success
                    break # Next entry
                elif choice in ["s", "skip"]:
                    print(f"{utils.COLOR_YELLOW}Edit skipped.{utils.COLOR_RESET}")
                    skipped_count += 1
                    break # Next entry
                elif choice in ["q", "quit"]:
                    print(f"{utils.COLOR_YELLOW}Review session ended by user.{utils.COLOR_RESET}")
                    raise KeyboardInterrupt("Review quit by user") # Use exception to break outer loop
                else:
                    print(f"{utils.COLOR_RED}Invalid choice. Please try again.{utils.COLOR_RESET}")

    except KeyboardInterrupt:
         # Handled outside if needed, just means review stopped early
         pass
    finally:
        # Print summary of review session
        print("\n" + "=" * 80)
        print("Review Summary:")
        print(f"  {utils.COLOR_GREEN}Accepted: {accepted_count}{utils.COLOR_RESET}")
        print(f"  {utils.COLOR_RED}Rejected: {rejected_count}{utils.COLOR_RESET}")
        print(f"  {utils.COLOR_BLUE}Skipped:  {skipped_count}{utils.COLOR_RESET}")
        remaining = len(pending_entries) - (accepted_count + rejected_count + skipped_count)
        if remaining > 0:
             print(f"  {utils.COLOR_YELLOW}Remaining: {remaining}{utils.COLOR_RESET}")
        print("=" * 80)


def handle_cleanup(args: argparse.Namespace, workspace_root: Path, history_root: Path, all_entries: List[Dict[str, Any]]) -> None:
    """Handle the cleanup command."""
    log.info("Starting cleanup of stale locks...")
    count = history.cleanup_stale_locks(history_root)
    if count > 0:
        print(f"{utils.COLOR_GREEN}Cleaned up {count} stale lock(s).{utils.COLOR_RESET}")
    else:
        print("No stale locks found to clean up.")


# --- Main Execution ---

def main():
    parser = argparse.ArgumentParser(
        description="MCP Diff Tool: Review and manage LLM file edits.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  mcpdiff status                     # Show recent history status (newest first limited)
  mcpdiff st -n 0                    # Show all history status (newest first)
  mcpdiff status --conv 17... --file src/main.py --status pending
  mcpdiff show <edit_id_prefix>      # Show diff for a specific edit
  mcpdiff show <conv_id_prefix>      # Show all diffs for a conversation
  mcpdiff accept -e <edit_id_prefix> # Accept a specific edit (reconstructs file)
  mcpdiff accept -c <conv_id_prefix> # Accept all pending edits for a conversation
  mcpdiff reject -e <edit_id_prefix> # Reject an edit (snapshots, rejects, reconstructs)
  mcpdiff reject -c <conv_id_prefix> # Reject all pending/accepted edits for a conversation
  mcpdiff review                     # Interactively review pending edits (oldest first)
  mcpdiff review -c <conv_id>        # Review pending edits for a specific conversation
  mcpdiff cleanup                    # Clean up stale locks
""",
    )
    parser.add_argument(
        "-w", "--workspace",
        help="Path to the workspace root. Defaults to searching from CWD upwards.",
    )
    parser.add_argument(
        "--verbose", action="store_true", help="Enable debug logging."
    )
    parser.add_argument(
        "--timeout", type=float, default=LOCK_TIMEOUT, # Allow float timeouts
        help=f"Timeout in seconds for acquiring locks (default: {LOCK_TIMEOUT}).",
    )
    parser.add_argument(
        "--force-cleanup", action="store_true",
        help="Force cleanup of stale locks before running any command.",
    )

    subparsers = parser.add_subparsers(dest="command", required=True, help="Sub-command help")

    # --- Subparser Definitions ---
    # status
    parser_status = subparsers.add_parser("status", aliases=["st"], help="Show edit history status (newest first).")
    parser_status.add_argument("--conv", "-c", help="Filter by conversation ID prefix or suffix.")
    parser_status.add_argument("--file", "-f", help="Filter by file path substring.")
    parser_status.add_argument("--status", choices=["pending", "accepted", "rejected"], help="Filter by status.")
    parser_status.add_argument("-n", "--limit", type=int, default=50, help="Limit entries shown (0 for all matching, default: 50).")
    parser_status.add_argument("--time", help="Filter by time relative to now (e.g., '30s', '5m', '1h', '2d').")
    parser_status.add_argument("--op", help="Filter by operation type (e.g., edit, create, delete, move, replace).")
    parser_status.set_defaults(func=handle_status)

    # show
    parser_show = subparsers.add_parser("show", aliases=["sh", "s"], help="Show diff(s) for an edit or conversation ID.")
    parser_show.add_argument("identifier", help="The edit_id prefix or conversation_id prefix/suffix to show.")
    parser_show.set_defaults(func=handle_show)

    # accept
    parser_accept = subparsers.add_parser("accept", aliases=["a"], help="Accept edits (ensures file state reflects accepted/pending).")
    group_accept = parser_accept.add_mutually_exclusive_group(required=True)
    group_accept.add_argument("-e", "--edit-id", help="Specific edit_id prefix to accept.")
    group_accept.add_argument("-c", "--conv", help="Accept all pending edits for a conversation_id prefix/suffix.")
    parser_accept.set_defaults(func=handle_accept)

    # reject
    parser_reject = subparsers.add_parser("reject", aliases=["r"], help="Reject edits (snapshots current state, marks rejected, reconstructs file).")
    group_reject = parser_reject.add_mutually_exclusive_group(required=True)
    group_reject.add_argument("-e", "--edit-id", help="Specific edit_id prefix to reject.")
    group_reject.add_argument("-c", "--conv", help="Reject all pending/accepted edits for a conversation_id prefix/suffix.")
    parser_reject.set_defaults(func=handle_reject)

    # review
    parser_review = subparsers.add_parser("review", aliases=["v"], help="Interactively review pending edits (oldest first).")
    parser_review.add_argument("--conv", "-c", help="Review pending edits only for this conversation ID prefix/suffix.")
    parser_review.set_defaults(func=handle_review)

    # cleanup
    parser_cleanup = subparsers.add_parser("cleanup", aliases=["clean"], help="Clean up stale locks.")
    parser_cleanup.set_defaults(func=handle_cleanup)

    # help
    parser_help = subparsers.add_parser("help", aliases=["h"], help="Show help information.")
    # Set a dummy function that prints help
    parser_help.set_defaults(func=lambda args, *a, **k: parser.print_help())


    # --- Parse Args and Setup ---
    args = parser.parse_args()

    # Setup logging level
    if args.verbose:
        utils.log.setLevel(utils.logging.DEBUG)
        utils.logging.getLogger().setLevel(utils.logging.DEBUG) # Also set root logger level
        log.debug("Debug logging enabled.")
    else:
        utils.log.setLevel(utils.logging.INFO)
        utils.logging.getLogger().setLevel(utils.logging.WARNING) # Keep libraries quieter

    # Get lock timeout from args
    lock_timeout = args.timeout
    log.debug(f"Using lock timeout: {lock_timeout}s")


    # --- Find Workspace ---
    try:
        workspace_root = history.find_workspace_root(args.workspace)
        if not workspace_root:
            print(f"{utils.COLOR_RED}Error: Could not find workspace root (.mcp/{HISTORY_DIR_NAME}) from '{args.workspace or os.getcwd()}'.{utils.COLOR_RESET}", file=sys.stderr)
            sys.exit(1)

        # Security check deferred to history functions where paths are used

        history_root = workspace_root / ".mcp" / HISTORY_DIR_NAME
        log.debug(f"Using workspace root: {workspace_root}")
        log.debug(f"Using history root: {history_root}")

        # Force cleanup if requested or running cleanup command
        if args.force_cleanup or args.command == "cleanup":
            if args.command != "cleanup": # Only log if forced, not if it's the main command
                 log.debug("Performing pre-command cleanup of stale locks (--force-cleanup).")
            cleaned = history.cleanup_stale_locks(history_root)
            if cleaned > 0 and args.command != "cleanup":
                log.info(f"Cleaned up {cleaned} stale lock(s) before main operation.")
            if args.command == "cleanup":
                 # The handler will print the message, avoid double printing
                 pass


    except Exception as e:
        print(f"{utils.COLOR_RED}Error finding workspace: {e}{utils.COLOR_RESET}", file=sys.stderr)
        log.exception("Workspace finding error:")
        sys.exit(1)


    # --- Read All History Entries (Centralized) ---
    all_entries = []
    exit_code = 0
    try:
        # Read all entries once, pass to handlers. Pass lock_timeout here.
        # Skip reading if only doing cleanup or help.
        if args.command not in ["cleanup", "help"]:
             log.info("Reading edit history...")
             all_entries = history.find_all_entries(history_root, lock_timeout=lock_timeout)
             log.info(f"Found {len(all_entries)} total history entries.")

        # --- Execute Command ---
        # Pass workspace, history root, and the pre-read entries to the handler
        args.func(args, workspace_root, history_root, all_entries)

    except KeyboardInterrupt:
        print("\nOperation cancelled by user.", file=sys.stderr)
        exit_code = 130
    except (HistoryError, TimeoutError, AmbiguousIDError) as e:
        print(f"{utils.COLOR_RED}Error: {e}{utils.COLOR_RESET}", file=sys.stderr)
        exit_code = 1
    except Exception as e:
        print(f"{utils.COLOR_RED}An unexpected error occurred. Use --verbose for detailed logs.{utils.COLOR_RESET}", file=sys.stderr)
        print(f"{utils.COLOR_RED}Error details: {e}{utils.COLOR_RESET}", file=sys.stderr)
        log.exception("Unexpected error during command execution:")
        exit_code = 2

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
