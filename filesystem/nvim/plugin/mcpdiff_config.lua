-- plugin/mcpdiff.lua

-- Load the main module (assuming it's in lua/mcpdiff/init.lua)
local mcpdiff = require("mcpdiff")

-- Optionally, call setup with user config if you have defaults elsewhere
-- mcpdiff.setup({})

-- Define user commands
vim.api.nvim_create_user_command(
  "McpdiffStatus",
  function(opts)
    mcpdiff.status(opts.fargs == nil and "" or table.concat(opts.fargs, " "))
  end,
  {
    nargs = "*", -- 0 or more arguments
    desc = "Show mcpdiff status (Args: filters like --conv, --file, --status)",
    -- Example completion (very basic):
    complete = function(arglead, cmdline, cursorpos)
        if string.find(cmdline, "--conv", 1, true) then return {} end
        if string.find(cmdline, "--file", 1, true) then return vim.fn.globpath('.', arglead .. '*', 0, 1) end -- File completion
        if string.find(cmdline, "--status", 1, true) then return {"pending", "accepted", "rejected"} end
        return {"--conv", "--file", "--status"}
    end
  }
)

vim.api.nvim_create_user_command(
  "McpdiffShow",
  function(opts)
    mcpdiff.show(opts.args)
  end,
  {
    nargs = 1, -- Requires exactly one argument (ID prefix)
    desc = "Show mcpdiff diff (Args: <edit_id | conv_id>)",
  }
)

vim.api.nvim_create_user_command(
  "McpdiffAccept",
  function(opts)
      mcpdiff.accept(opts.fargs == nil and "" or table.concat(opts.fargs, " "))
  end,
  {
    nargs = "+", -- Requires 1 or more arguments (e.g. -e ID or -c ID)
    desc = "Accept mcpdiff edits (Args: -e <edit_id> | -c <conv_id>)",
  }
)

vim.api.nvim_create_user_command(
  "McpdiffReject",
  function(opts)
      mcpdiff.reject(opts.fargs == nil and "" or table.concat(opts.fargs, " "))
  end,
  {
    nargs = "+", -- Requires 1 or more arguments (e.g. -e ID or -c ID)
    desc = "Reject mcpdiff edits and revert (Args: -e <edit_id> | -c <conv_id>)",
  }
)

vim.api.nvim_create_user_command(
  "McpdiffReview",
  function(opts)
      mcpdiff.review(opts.fargs == nil and "" or table.concat(opts.fargs, " "))
  end,
  {
    nargs = "*", -- 0 or more arguments (e.g. --conv ID)
    desc = "Interactively review pending mcpdiff edits (Args: filters like --conv)",
  }
)

print("MCPDiff plugin loaded.")
