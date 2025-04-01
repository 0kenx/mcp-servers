# MCP Diff Tool Quick Reference

## Basic Commands

| Command | Aliases | Description | Example |
| ------- | ------- | ----------- | ------- |
| `status` | `st` | Show edit history | `mcpdiff status` |
| `show` | `sh`, `s` | Show diff for edit/conversation | `mcpdiff show abc123` |
| `accept` | `a` | Accept edit(s) | `mcpdiff accept -e abc123` |
| `reject` | `r` | Reject edit(s) | `mcpdiff reject -e abc123` |
| `review` | `v` | Interactive review | `mcpdiff review` |
| `cleanup` | `clean` | Clean up stale locks | `mcpdiff cleanup` |
| `help` | `h` | Show help information | `mcpdiff help` |

## Common Options

| Option | Description | Example |
| ------ | ----------- | ------- |
| `-n, --limit N` | Limit entries shown (0 for all) | `mcpdiff status -n 0` |
| `-c, --conv ID` | Filter by conversation ID | `mcpdiff status -c abc123` |
| `-f, --file PATH` | Filter by file path | `mcpdiff status -f src/main.py` |
| `-e, --edit-id ID` | Specify edit ID | `mcpdiff accept -e abc123` |
| `--status TYPE` | Filter by status (pending/accepted/rejected) | `mcpdiff status --status pending` |
| `--time FILTER` | Filter by time (e.g., 30s, 5m, 1h, 2d) | `mcpdiff status --time 1h` |
| `--verbose` | Enable debug logging | `mcpdiff --verbose status` |

## Interactive Review Keys

During `mcpdiff review` sessions:

| Key | Action |
| --- | ------ |
| `a` | Accept current edit |
| `r` | Reject current edit |
| `s` | Skip to next edit |
| `q` | Quit review session |

## Common Workflows

### Review recent changes
```bash
mcpdiff status
mcpdiff show <edit_id>
```

### Accept all pending edits in a conversation
```bash
mcpdiff accept -c <conv_id>
```

### Interactively review pending edits
```bash
mcpdiff review
```

### Check if a file has pending edits
```bash
mcpdiff status -f path/to/file.py --status pending
```

### Fix stale locks after a crash
```bash
mcpdiff cleanup
```