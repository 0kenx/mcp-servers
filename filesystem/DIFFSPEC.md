# **MCP Edit History & Diff Specification**

## 1. Overview

This document describes the design for enabling review and revert capabilities for file modifications performed by a Large Language Model (LLM) via an MCP filesystem server.

The core requirements are:

1.  **LLM Direct Edits:** The LLM should make file changes directly using provided MCP tools (`write_file`, `edit_file_diff`, `move_file`, `delete_file`).
2.  **Edit History:** A persistent history of all file modifications must be maintained.
3.  **Conversation Grouping:** Edits should be grouped by a `conversation_id` representing a single logical response or turn from the LLM.
4.  **Granular Review/Revert:** An external tool (`mcpdiff`) must allow users to review individual changes (as diffs) and accept/reject them.
5.  **Individual Revert:** Rejecting an edit should undo *only that specific change*, correctly handling potential line number shifts caused by preceding accepted/pending edits within the same conversation.
6.  **Conversation Revert/Accept:** The tool should allow accepting or rejecting *all* edits within a specific conversation.
7.  **No Git Dependency:** The solution should not rely on the Git version control system.
8.  **Robustness:** The system should handle file creation, deletion, moves, and replacements, and detect external modifications.

## 2. Architecture

The system employs a combination of server-side tracking within the MCP tools and a command-line interface (`mcpdiff`) for user interaction. It uses a dedicated hidden directory within each managed workspace to store history metadata, checkpoints, and diffs.

### 2.1. Core Components

*   **MCP Filesystem Server (`filesystem.py`):**
    *   Provides MCP tools for file operations (`read_*`, `write_file`, `edit_file_diff`, `move_file`, `delete_file`, etc.).
    *   Includes a decorator (`@track_edit_history`) applied to modifying tools.
    *   Manages access control via `allowed_directories`.
*   **Shared Utilities (`mcp_edit_utils.py`):**
    *   Contains helper functions for path validation (`validate_path`), history root management (`get_history_root`), locking (`acquire_lock`, `release_lock`), hashing (`calculate_hash`), diff generation (`generate_diff`), patch application (`apply_patch`), log file I/O (`read_log_file`, `write_log_file`), unique ID generation, and tool call indexing (`get_next_tool_call_index`).
*   **History Storage (`.mcp/edit_history/`):**
    *   Located within the root of each configured `allowed_directory`.
    *   Contains subdirectories: `logs/`, `diffs/`, `checkpoints/`.
*   **CLI Tool (`cli/mcpdiff.py`):**
    *   Provides user commands (`status`, `show`, `accept`, `reject`) to interact with the history storage.
    *   Implements the logic for re-applying changes when edits are rejected.

### 2.2. Data Flow & Tracking Process

1.  **Client Call:** An LLM client requests a modifying tool (e.g., `write_file`) via MCP.
    *   For the **first** tracked call in a conversation turn, `mcp_conversation_id` is omitted/null.
    *   For subsequent calls in the **same** turn, the client includes the `mcp_conversation_id` returned by the server from the first call.
2.  **Decorator Intercept (`track_edit_history`):**
    *   The decorator intercepts the call before the tool's core logic runs.
    *   It binds arguments and validates required parameters.
    *   **Conversation ID:** If `mcp_conversation_id` is missing, it generates a unique ID (e.g., `conv_{epoch_ms}_{rand_hex}`) and flags it as a new conversation. Otherwise, it uses the provided ID.
    *   **Tool Index:** It gets the next sequential `tool_call_index` for the current `conversation_id` using a shared, locked counter.
    *   **Path Validation:** It validates the target (and source for `move`) paths using `validate_path` against the server's `SERVER_ALLOWED_DIRECTORIES` list.
    *   **Locking:** Acquires exclusive file locks on the target file(s) and the conversation-specific log file using `filelock`.
3.  **State Capture (Before):**
    *   **Checkpoint:** If this is the first operation affecting this specific file path within this `conversation_id`, the decorator reads the current file content (under lock) and saves it as a checkpoint file (e.g., `.mcp/edit_history/checkpoints/{conv_id}/{sanitized_path}.chkpt`). Handles creation cases where no prior file exists.
    *   **Hashing:** Calculates the SHA256 hash (`hash_before`) of the file content *before* the operation.
    *   **Content Reading:** Reads the file content (`content_before`) into memory (for diff generation later).
4.  **Execute Tool Logic:** The decorator calls the original tool function (e.g., `write_file`, `edit_file_diff`) which performs the actual filesystem modification (write, delete, rename).
5.  **State Capture (After):**
    *   **Hashing:** Calculates the SHA256 hash (`hash_after`) of the file content *after* the operation (None for delete).
    *   **Content Reading:** Reads the file content (`content_after`) into memory (if applicable and needed for diff).
6.  **Diff Generation:**
    *   If the operation modified content (`create`, `replace`, `edit`), the decorator generates a unified diff between `content_before` and `content_after`.
    *   The diff is saved to a unique file (e.g., `.mcp/edit_history/diffs/{conv_id}/{edit_id}.diff`).
7.  **Logging:**
    *   A JSON log entry is created containing: `edit_id`, `conversation_id`, `tool_call_index`, `timestamp`, `operation` (create, replace, edit, delete, move), `file_path`, `source_path`, `tool_name`, `status` ("pending"), `diff_file` path, `checkpoint_file` path (if created), `hash_before`, `hash_after`.
    *   This entry is appended atomically (via temp file rename) to the conversation-specific log file (`.mcp/edit_history/logs/{conv_id}.log`) under lock.
8.  **Lock Release:** All acquired file locks are released in a `finally` block, and `.lock` files are removed.
9.  **Return Value Modification:** If a new `conversation_id` was generated, the decorator appends an informational message to the tool's original return string, instructing the client to use the new ID. Otherwise, it returns the tool's original result.

## 3. Storage Structure

Located within each workspace root configured as an `allowed_directory`.

```
<workspace_root>/
├── .mcp/                             # Hidden directory for MCP metadata
│   └── edit_history/                 # Root for this feature
│       ├── logs/                     # Conversation logs
│       │   ├── {conv_id_1}.log       # JSON Lines format, one entry per edit op
│       │   └── {conv_id_2}.log
│       ├── diffs/                    # Diffs for content changes
│       │   ├── {conv_id_1}/
│       │   │   ├── {edit_id_1}.diff  # Unified diff format
│       │   │   └── {edit_id_2}.diff
│       │   └── {conv_id_2}/
│       ├── checkpoints/              # Initial file states per conversation
│       │   ├── {conv_id_1}/
│       │   │   └── {sanitized_path_1}.chkpt # Raw file content
│       │   │   └── {sanitized_path_2}.chkpt
│       │   └── {conv_id_2}/
│       └── .lock                     # Optional global lock (currently unused)
└── actual_file.py
└── subdir/
    └── another_file.txt
```

*   **`{sanitized_path}`:** File path relative to workspace root, sanitized for safe filename use (e.g., `/` replaced by `_`, potentially hashed for length).

## 4. Log Entry Format (`logs/{conv_id}.log`)

JSON Lines format (one JSON object per line).

```json
{
  "edit_id": "uuid_string",             // Unique ID for this specific edit operation
  "conversation_id": "conv_string",     // ID grouping edits from one LLM turn
  "tool_call_index": 0,                 // Sequential order (0, 1, 2...) within the conversation
  "timestamp": "iso_timestamp_utc",     // Time of operation recording
  "operation": "create | replace | edit | delete | move", // Type of filesystem change
  "file_path": "/abs/path/to/target",   // Absolute, normalized path (destination for move)
  "source_path": "/abs/path/to/source", // Absolute, normalized path (only for "move") or null
  "tool_name": "write_file | edit_file_diff | delete_file | move_file", // MCP Tool used
  "status": "pending | accepted | rejected", // User review status (default: pending)
  "diff_file": "diffs/{conv_id}/{edit_id}.diff", // Relative path from history_root (or null)
  "checkpoint_file": "checkpoints/{conv_id}/{sanitized_path}.chkpt", // Relative path (or null)
  "hash_before": "sha256_string_or_null", // SHA256 hash before op (null if create)
  "hash_after": "sha256_string_or_null"   // SHA256 hash after op (null if delete)
}
```

## 5. CLI Tool (`mcpdiff`)

Provides the user interface for interacting with the history.

*   **`mcpdiff status [...]`**: Lists history entries, filterable by conversation, file, status. Shows `edit_id`, timestamp, status, operation, conversation, relative file path.
*   **`mcpdiff show <edit_id | conversation_id>`**: Displays the unified diff content associated with an `edit_id` or all edits in a `conversation_id`.
*   **`mcpdiff accept <edit_id | --conv conversation_id>`**:
    *   Changes the `status` field in the corresponding log entry/entries from "pending" to "accepted".
    *   Does **not** modify the actual file (file already reflects pending/accepted state).
    *   Requires log file lock for modification.
*   **`mcpdiff reject <edit_id | --conv conversation_id>`**:
    *   Changes the `status` field in the log entry/entries from "pending" (or "accepted") to "rejected".
    *   **Triggers the Re-apply Logic:** Calls `reapply_conversation_state` for each affected file within the specified conversation(s).
    *   Requires log file lock for modification.

## 6. Revert / Re-apply Logic (`reapply_conversation_state`)

This core logic, triggered by `mcpdiff reject`, reconstructs the correct state of a file after one or more edits within a conversation are rejected. It assumes **no manual edits** occurred between the initial LLM edits and the user running `mcpdiff accept/reject`.

1.  **Input:** `conversation_id`, `target_file_path`, `history_root`.
2.  **Load History:** Read all log entries for the `conversation_id`.
3.  **Filter Relevant:** Identify all edits affecting the `target_file_path`, tracing its history through potential `move` operations. Sort these relevant edits by `tool_call_index` ascending.
4.  **Find Checkpoint:** Locate the `checkpoint_file` path associated with the *first* relevant edit for the file's initial path in this conversation. Error if no checkpoint and first op wasn't `create`.
5.  **Acquire File Lock:** Lock the final `target_file_path`.
6.  **Restore Checkpoint:** Overwrite `target_file_path` with the content from the `checkpoint_file`. Handle `create` case (start empty). Determine initial `current_expected_hash`.
7.  **Iterate and Apply:** Loop through the sorted relevant edits:
    *   **Hash Check:** Calculate hash of the current file on disk. Compare it with `current_expected_hash` (the hash expected *before* this edit). If mismatch, raise `ExternalModificationError` and stop.
    *   **Check Status:** Read the edit's `status` from the log entry.
    *   **If `pending` or `accepted`:**
        *   Apply the operation (patch diff, delete file, rename file) to the actual file on disk.
        *   Update internal state trackers (`current_file_path` if moved, `file_exists_in_state`).
        *   Update `current_expected_hash` to the `hash_after` recorded in the log entry for this edit.
    *   **If `rejected`:**
        *   **Do not** apply the operation to the filesystem.
        *   Update internal state trackers (`current_file_path`, `file_exists_in_state`) *as if* the operation had occurred (to correctly track state for subsequent hash checks).
        *   Update `current_expected_hash` to the `hash_after` from the log entry (the hash the file *would* have had).
8.  **Final Verification:** After the loop, calculate the hash of the final file state. Compare with the final `current_expected_hash`. Log error on mismatch (indicates potential logic bug).
9.  **Release File Lock.**
10. **Return Success/Failure.**

## 7. Security and Robustness

*   **Path Validation:** `validate_path` is crucial. It resolves symlinks and ensures both the requested path and the final resolved path (and parent directories for creation) stay within strictly defined `allowed_directories`. It's called by the decorator *before* any file operation.
*   **Locking:** `filelock` is used to prevent race conditions during:
    *   Log file appends/modifications (`mcpdiff` vs server).
    *   File modifications during tool execution (server vs external process).
    *   File modifications during `mcpdiff reject` re-apply (mcpdiff vs server/external).
*   **Atomicity:** Log writes use `os.replace` for better atomicity against crashes.
*   **Checkpoints:** Provide a reliable starting point for re-applying state within a conversation.
*   **Hashing:** `hash_before` and `hash_after` are used by the re-apply logic to detect unexpected external file modifications between the time the history was recorded and when `mcpdiff reject` is run.
*   **Error Handling:** The decorator and core functions include `try...except` blocks to catch expected errors (validation, file not found, locks) and unexpected ones, returning informative messages or internal server errors. Lock release occurs in `finally` blocks.

## 8. Limitations and Future Considerations

*   **"No Manual Edits" Assumption:** The `reapply_conversation_state` logic fundamentally relies on the workspace files not being modified manually between the LLM's edits and the user's `mcpdiff` actions for that conversation. External modifications will be detected by the hash check, but require manual resolution.
*   **Performance:** Re-applying state for large files or long conversations might be slow. Log file modification for status updates involves rewriting, which can be slow for very large logs.
*   **Storage:** Checkpoints and diffs can consume significant space. A cleanup strategy (`mcpdiff cleanup`?) for old, fully resolved conversations might be needed.
*   **Concurrency:** Assumes a single server process interacting with a given workspace's history. Multiple concurrent server processes writing to the same history without higher-level coordination could potentially corrupt logs despite file locks.
*   **Complex Reverts:** Reverting `move` or `delete` operations, especially when subsequent edits target the moved/deleted path, is complex during the re-apply phase and needs careful testing.
*   **Patch Failures:** Although the re-apply strategy minimizes context issues *within* a conversation, the underlying `patch` command could theoretically still fail even without external edits (e.g., if a diff applies poorly). The system currently treats this as an internal error requiring investigation.

---

## 9. Edit Acceptance/Rejection Rules

The following rules govern the acceptance and rejection of edits:

1. **Status Management:**
   * Any pending edit can either be accepted or rejected
   * The status can be switched between accepted and rejected at any time

2. **Hash Verification:**
   * Before accepting or rejecting an edit, the system checks if the current file hash matches the hash recorded in the last edit of the file
   * If there's a hash mismatch, the user is shown a diff between the version of the last edit and the current version
   * The user can choose to abort the operation or continue, discarding all changes made after the last edit

3. **File State Reconstruction:**
   * The system reconstructs the current state of a file by starting from the nearest available snapshot
   * It applies all accepted and pending changes to this snapshot
   * For rejected edits, the system compensates for line number shifts but does not modify the diff files themselves

4. **Hash Recording:**
   * After processing an edit, the system calculates the final hash of the file
   * This hash is recorded with the operation in the log file

These rules ensure that file modifications are tracked accurately and that users can precisely control which changes are applied to their files, while maintaining consistent file state.

---
