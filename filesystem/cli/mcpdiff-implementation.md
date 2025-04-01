# MCP Diff Tool Implementation Guide

This document explains the internal architecture and implementation details of the MCP Diff Tool. It's intended for developers who need to maintain or extend the tool.

## Codebase Structure

The tool consists of three main Python modules:

1. **mcpdiff.py** - Main executable with command handlers and CLI interface
2. **mcpdiff_history.py** - History management and file reconstruction logic
3. **mcpdiff_utils.py** - Utility functions for file operations, locking, etc.

## Key Components

### History Storage

Edit history is stored in the `.mcp/edit_history` directory with the following structure:

```
.mcp/edit_history/
  ├── logs/
  │   └── <conversation_id>.log    # JSON Lines format
  ├── diffs/
  │   └── <conversation_id>/
  │       └── <edit_id>.diff       # Git-style diffs
  └── checkpoints/
      └── <conversation_id>/
          └── <filename>_<edit_id>_<timestamp>.chkpt  # File snapshots
```

### Edit Entry Structure

Each edit operation is stored as a JSON object with fields such as:

- `edit_id`: Unique identifier for the edit
- `conversation_id`: ID of the conversation/session
- `timestamp`: When the edit occurred
- `operation`: Type of operation (create, edit, delete, move, etc.)
- `file_path`: Path to the file being modified
- `status`: Current status (pending, accepted, rejected)
- `diff_file`: Path to the diff file relative to diffs directory
- `hash_before`: Hash of the file before the edit
- `hash_after`: Hash of the file after the edit (for accepted edits)

### File Locking

The tool uses a robust file locking mechanism:

- Lock directories with PID files instead of simple lock files
- Stale lock detection and cleanup
- Configurable timeouts
- Process existence verification

### File Reconstruction

When accepting/rejecting edits, the file is reconstructed:

1. Find the latest checkpoint or starting point
2. Create a temporary working directory
3. Apply edits sequentially according to their status
4. Apply only 'accepted' edits when rejecting, or 'accepted' and 'pending' when accepting
5. Replace the workspace file with the reconstructed version

## Core Workflows

### Status Command Flow

1. Find workspace root directory
2. Read all log files into memory
3. Filter entries based on command-line criteria
4. Format and display matching entries

### Show Command Flow

1. Parse identifier (edit ID or conversation ID)
2. Find matching entry/entries in the history
3. For each entry:
   - Retrieve the diff file
   - Format and display the diff with color highlighting

### Accept/Reject Command Flow

1. Identify target edit(s) by ID or conversation
2. Group entries by file path for efficiency
3. For each file:
   - Verify no external modifications (interactive prompt if detected)
   - Create snapshot before modifications (for reject operations)
   - Update entry status in log file
   - Reconstruct file state based on accepted/pending entries
   - Restore from snapshot if reconstruction fails

### Review Command Flow

1. Filter for pending edits
2. Sort chronologically (oldest first)
3. For each edit:
   - Show edit details and diff
   - Prompt for action (accept/reject/skip/quit)
   - Process the chosen action using accept/reject logic

## Extension Points

When extending the tool, consider these key areas:

### Adding New Operations

1. Define the operation type in the log entry schema
2. Add specific handling in `apply_or_revert_edit()` function
3. Update the file reconstruction logic if needed

### Enhancing Diff Visualization

The diff visualization happens in the `print_diff_with_color()` function in `mcpdiff_utils.py`.

### Adding New Commands

1. Add a new subparser in `main()` function
2. Implement a handler function (e.g., `handle_new_command()`)
3. Register the handler with the subparser

## Security Considerations

The tool includes several security measures:

- Path safety verification to prevent edits outside the workspace
- Symlink resolution and validation
- File locking to prevent concurrent modifications
- Hash verification to detect external changes

## Performance Considerations

For large repositories with many edits:

- Consider using the `-n` limit option for status command
- Filter by conversation ID or file path to reduce processing time
- The tool reads all log files into memory - with very large history, this could cause memory pressure