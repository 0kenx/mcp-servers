# MCP Diff Tool Usage Guide

## Overview

The MCP Diff Tool (`mcpdiff`) is a command-line utility for reviewing and managing file edits in a workspace. It allows you to track, accept, reject, and review changes in a structured manner.

## Core Concepts

- **Edit History**: A log of all edit operations performed on files in the workspace
- **Conversation ID**: Groups related edits that occurred during a single conversation or session
- **Edit ID**: Unique identifier for a specific edit operation
- **Edit Status**: Can be `pending`, `accepted`, or `rejected`

## Commands

### Viewing Edit History

```bash
# Show recent edit history (newest first, limited to 50 entries by default)
mcpdiff status

# Show all history entries (no limit)
mcpdiff st -n 0

# Filter by conversation ID, file path, status, etc.
mcpdiff status --conv <conv_id> --file <file_path> --status pending
```

### Showing Diffs

```bash
# Show diff for a specific edit (using Edit ID prefix)
mcpdiff show <edit_id_prefix>

# Show all diffs for a conversation (using Conversation ID prefix/suffix)
mcpdiff show <conv_id_prefix>
```

### Accepting Edits

```bash
# Accept a specific edit 
mcpdiff accept -e <edit_id_prefix>

# Accept all pending edits for a conversation
mcpdiff accept -c <conv_id_prefix>
```

### Rejecting Edits

```bash
# Reject a specific edit
mcpdiff reject -e <edit_id_prefix>

# Reject all pending/accepted edits for a conversation
mcpdiff reject -c <conv_id_prefix>
```

### Interactive Review

```bash
# Interactively review all pending edits (oldest first)
mcpdiff review

# Review pending edits for a specific conversation
mcpdiff review -c <conv_id_prefix>
```

### Maintenance

```bash
# Clean up stale locks that might be present after crashes
mcpdiff cleanup
```

## Common Flags

- `-w, --workspace`: Specify the workspace root path (defaults to finding it from current directory)
- `--verbose`: Enable debug logging
- `--timeout`: Set timeout for acquiring locks (default: 10 seconds)
- `--force-cleanup`: Clean up stale locks before running a command

## Usage Examples

### Review and accept all edits from a conversation

```bash
# First, view edits from the conversation
mcpdiff status --conv abc123

# Review them interactively
mcpdiff review -c abc123

# Or accept all pending edits at once
mcpdiff accept -c abc123
```

### Check details of a specific edit

```bash
# Using the short edit ID prefix from status output
mcpdiff show 3f4a5b6c
```

### Reject a problematic edit

```bash
# Identify the edit ID first
mcpdiff status --file src/problem_file.py

# Then reject it
mcpdiff reject -e 3f4a5b6c
```

## File Structure

The tool manages edit history in the `.mcp/edit_history` directory within your workspace, containing:

- **logs/**: Edit operation logs in JSON Lines format
- **diffs/**: File difference records
- **checkpoints/**: File snapshots before modifications

## Notes

- When rejecting edits, a checkpoint of the current file state is created before modifications
- External file changes are detected and will prompt for confirmation to prevent data loss
- Ambiguous ID prefixes will prompt for selection among matching entries
- The interactive review mode provides a streamlined workflow for accepting/rejecting multiple edits