# MCPDiff Neovim Integration

Integrates the [`mcpdiff`](#) command-line tool (for managing LLM file edit history stored in `.mcp/edit_history/`) into Neovim.

This plugin provides commands to view edit status, show diffs, accept/reject edits, and launch the interactive review process directly from Neovim.

## Features

*   View edit history status in a floating window (`:McpdiffStatus`).
*   Show diffs for specific edits or entire conversations in a floating window (`:McpdiffShow`).
*   Accept pending edits (`:McpdiffAccept`).
*   Reject pending or accepted edits, triggering the `mcpdiff` revert/re-apply logic (`:McpdiffReject`).
*   Launch the interactive `mcpdiff review` process in a terminal split (`:McpdiffReview`).
*   Asynchronous execution using `vim.loop` to avoid blocking Neovim.

## Requirements

*   **Neovim:** Version 0.8 or later recommended (uses `vim.loop`).
*   **`mcpdiff` CLI Tool:** The `mcpdiff` Python script must be executable and available in your system's `PATH`.

## Installation

This plugin is designed to be installed as a **local plugin** using [`lazy.nvim`](https://github.com/folke/lazy.nvim).

1.  **Place Plugin Code:**
    *   Clone or place the plugin code (containing the `lua/` and `plugin/` directories) into a dedicated location.
    *   **Option A (Direct Copy):** Copy the plugin directory (let's call it `mcpdiff`) into your Neovim config's local plugins directory, e.g.:
        ```
        ~/.config/nvim/lua/local_plugins/mcpdiff/
        ├── lua/
        │   └── mcpdiff/
        │       └── init.lua
        └── plugin/
            └── mcpdiff_config.lua
        ```
    *   **Option B (Symlink):** Keep the plugin code in its own Git repository and create a symlink from your Neovim config's local plugins directory to your repository:
        ```bash
        # Create the target directory if it doesn't exist
        mkdir -p ~/.config/nvim/lua/local_plugins/

        # Create the symlink (adjust paths as needed)
        ln -s /path/to/your/git/repo/mcpdiff ~/.config/nvim/lua/local_plugins/mcpdiff
        ```

2.  **Add Lazy Spec:**
    Create a file (e.g., `lua/plugins/mcpdiff.lua`) in your Neovim configuration with the following content:

    ```lua
    -- lua/plugins/mcpdiff.lua
    return {
      -- Unique key for lazy.nvim
      "local/mcpdiff",

      -- Path to the plugin directory *within your Neovim config structure*
      -- This MUST point to where the code lives or where the symlink is placed.
      dir = vim.fn.stdpath("config") .. "/lua/local_plugins/mcpdiff",

      -- Optional: Add dependencies if your plugin needs them
      -- dependencies = {},

      -- Optional: Configure the plugin (see Configuration section)
      opts = {
        -- mcpdiff_cmd = "/usr/local/bin/mcpdiff" -- Override if not in PATH
        -- debug = true
      },

      -- No need for explicit config function usually, lazy loads plugin dir
    }
    ```

3.  **Restart Neovim:** `lazy.nvim` will detect and load the plugin.

## Configuration

You can configure the plugin by passing options in the `opts` table of your `lazy.nvim` spec:

```lua
-- lua/plugins/mcpdiff.lua
return {
  "local/mcpdiff",
  dir = vim.fn.stdpath("config") .. "/lua/local_plugins/mcpdiff",
  opts = {
    -- Path to the mcpdiff executable (default: "mcpdiff")
    mcpdiff_cmd = "mcpdiff",

    -- Appearance for floating windows (status, show)
    float_border = "rounded", -- Or "single", "double", "shadow", etc.
    float_max_width = 0.8,    -- Max width relative to editor width (0.0 to 1.0)
    float_max_height = 0.8,   -- Max height relative to editor height (0.0 to 1.0)

    -- Enable debug prints for development (default: false)
    debug = false,
  },
}
```

The plugin will load these options via its `setup` function (which `lazy.nvim` calls implicitly if `opts` is provided).

## Usage

The plugin provides the following user commands:

*   `:McpdiffStatus [filters]`
    *   Shows the edit history status in a floating window.
    *   Optional `[filters]` are passed directly to the `mcpdiff status` command.
    *   *Examples:*
        *   `:McpdiffStatus`
        *   `:McpdiffStatus --status pending`
        *   `:McpdiffStatus --conv 17a...`
        *   `:McpdiffStatus --file src/main.py --limit 10`

*   `:McpdiffShow <id_prefix>`
    *   Shows the diff for a specific `edit_id` prefix or all diffs for a `conversation_id` prefix in a floating window. ANSI colors from `mcpdiff` should be rendered.
    *   *Examples:*
        *   `:McpdiffShow a50a...` (edit ID prefix)
        *   `:McpdiffShow 17a3...` (conversation ID prefix)

*   `:McpdiffAccept -e <edit_id_prefix>` / `:McpdiffAccept -c <conv_id_prefix>`
    *   Marks the specified edit(s) as 'accepted'.
    *   Requires either `-e` (edit ID prefix) or `-c` (conversation ID prefix).
    *   *Examples:*
        *   `:McpdiffAccept -e a50a...`
        *   `:McpdiffAccept -c 17a3...`

*   `:McpdiffReject -e <edit_id_prefix>` / `:McpdiffReject -c <conv_id_prefix>`
    *   Marks the specified edit(s) as 'rejected' and triggers the `mcpdiff` state re-application logic for the affected conversation(s).
    *   Requires either `-e` (edit ID prefix) or `-c` (conversation ID prefix).
    *   *Examples:*
        *   `:McpdiffReject -e a50a...`
        *   `:McpdiffReject -c 17a3...`

*   `:McpdiffReview [filters]`
    *   Opens the interactive `mcpdiff review` process in a new vertical terminal split.
    *   Optional `[filters]` (like `--conv <id_prefix>`) are passed to the command.
    *   *Examples:*
        *   `:McpdiffReview`
        *   `:McpdiffReview --conv 17a3...`

## Example Keybindings

You can map these commands to keys in your Neovim configuration:

```lua
-- Example using leader key
vim.keymap.set('n', '<leader>ms', '<Cmd>McpdiffStatus<CR>', { desc = "[M]CPDiff [S]tatus" })
vim.keymap.set('n', '<leader>mv', '<Cmd>McpdiffShow ', { desc = "[M]CPDiff Sho[v]w ID" }) -- Note space for entering ID
vim.keymap.set('n', '<leader>ma', '<Cmd>McpdiffAccept ', { desc = "[M]CPDiff [A]ccept" })
vim.keymap.set('n', '<leader>mr', '<Cmd>McpdiffReject ', { desc = "[M]CPDiff [R]eject" })
vim.keymap.set('n', '<leader>mi', '<Cmd>McpdiffReview<CR>', { desc = "[M]CPDiff Review [I]nteractive" })
```
*(Remember to add the arguments after commands like `Show`, `Accept`, `Reject` when using the keymap)*

## Troubleshooting

*   **Command not found:** Ensure the `mcpdiff` script is executable (`chmod +x /path/to/mcpdiff.py`) and its directory is included in your system's `PATH` environment variable, or configure the full path using the `mcpdiff_cmd` option in the plugin setup.
*   **Errors during `run_mcpdiff`:** Check Neovim's messages (`:messages`) or enable the `debug = true` option and check the output for more details about process spawning or pipe errors. Ensure `mcpdiff` runs correctly from your standard terminal first.
*   **Floating window issues:** Ensure your Neovim version is recent enough and that your terminal supports floating windows correctly.
*   **`:terminal` issues:** If the terminal split doesn't work as expected, consult `:help :terminal`.
```

