-- lua/mcpdiff/init.lua
local uv = vim.loop -- Use libuv via vim.loop for process handling
local api = vim.api

local M = {}

-- Simple debug logging toggle
local is_debug = false
local function debug_print(...)
  if is_debug then print("MCPDiff Debug:", ...) end
end

-- Default configuration
local config = {
  mcpdiff_cmd = "mcpdiff", -- Assumes mcpdiff is in PATH
  float_border = "rounded",
  float_max_width = 0.8,
  float_max_height = 0.8,
}

-- Helper to get window dimensions for floating window
local function get_win_dims()
  local width = api.nvim_get_option("columns")
  local height = api.nvim_get_option("lines")
  local float_width = math.min(math.floor(width * config.float_max_width), 120) -- Max 120 cols
  local float_height = math.min(math.floor(height * config.float_max_height), 40) -- Max 40 rows
  local row = math.floor((height - float_height) / 2)
  local col = math.floor((width - float_width) / 2)
  return float_width, float_height, row, col
end

-- Add this helper function at the top with other local functions
local function convert_ansi_to_html(str)
  -- ANSI color code to highlight group mapping
  local ansi_to_hl = {
    -- Regular colors
    ['30'] = 'AnsiBlack',
    ['31'] = 'AnsiRed',
    ['32'] = 'AnsiGreen',
    ['33'] = 'AnsiYellow',
    ['34'] = 'AnsiBlue',
    ['35'] = 'AnsiMagenta',
    ['36'] = 'AnsiCyan',
    ['37'] = 'AnsiWhite',
    -- Bright colors
    ['90'] = 'AnsiBrightBlack',
    ['91'] = 'AnsiBrightRed',
    ['92'] = 'AnsiBrightGreen',
    ['93'] = 'AnsiBrightYellow',
    ['94'] = 'AnsiBrightBlue',
    ['95'] = 'AnsiBrightMagenta',
    ['96'] = 'AnsiBrightCyan',
    ['97'] = 'AnsiBrightWhite',
  }

  -- Define highlight groups if they don't exist
  for _, hl_group in pairs(ansi_to_hl) do
    if vim.fn.hlexists(hl_group) == 0 then
      local color = hl_group:gsub('Ansi', ''):gsub('Bright', '')
      local is_bright = hl_group:match('Bright') ~= nil
      vim.api.nvim_set_hl(0, hl_group, {
        fg = string.lower(color),
        bold = is_bright,
      })
    end
  end

  -- Convert ANSI escape sequences to Neovim syntax highlighting
  local result = str:gsub('\27%[([%d;]+)m(.-)\27%[0m', function(code, text)
    local hl_group = ansi_to_hl[code]
    if hl_group then
      return string.format('%%%s%%%s%%*', hl_group, text)
    end
    return text
  end)

  return result
end

-- Helper function to show output in a floating window
local function show_output_in_float(title, lines)
  local float_width, float_height, row, col = get_win_dims()

  -- Create terminal buffer
  local buf = api.nvim_create_buf(false, true)
  api.nvim_buf_set_option(buf, "bufhidden", "wipe")

  local win_opts = {
    relative = "editor",
    width = float_width,
    height = float_height,
    row = row,
    col = col,
    border = config.float_border,
    style = "minimal",
    title = title,
    title_pos = "center",
  }

  local win = api.nvim_open_win(buf, true, win_opts)

  -- Set window options
  if win and api.nvim_win_is_valid(win) then
    vim.wo[win].wrap = true
  end

  -- Write content to a temporary file
  local tmp_file = vim.fn.tempname()
  local tmp_handle = io.open(tmp_file, 'w')
  if tmp_handle then
    for _, line in ipairs(lines) do
      tmp_handle:write(line .. '\n')
    end
    tmp_handle:close()

    -- Use less to display the content with ANSI colors
    vim.fn.termopen(string.format('less -R %s', vim.fn.shellescape(tmp_file)), {
      on_exit = function()
        -- Clean up temp file
        vim.fn.delete(tmp_file)
      end
    })
  end

  -- Close float on 'q' or '<Esc>'
  api.nvim_buf_set_keymap(
    buf,
    "n",
    "q",
    "<Cmd>lua vim.api.nvim_win_close(" .. win .. ", true)<CR>",
    { noremap = true, silent = true }
  )
  api.nvim_buf_set_keymap(
    buf,
    "n",
    "<Esc>",
    "<Cmd>lua vim.api.nvim_win_close(" .. win .. ", true)<CR>",
    { noremap = true, silent = true }
  )
end

-- Helper function to run mcpdiff command
-- callback takes (exit_code, stdout_lines, stderr_lines)
local function run_mcpdiff(args, callback)
  local cmd_parts = { config.mcpdiff_cmd }
  vim.list_extend(cmd_parts, args)

  local stdout_lines = {}
  local stderr_lines = {}
  local exit_code = -1

  debug_print("Running: " .. table.concat(cmd_parts, " "))

  -- Create pipes before spawn
  local stdout_pipe = uv.new_pipe(false)
  local stderr_pipe = uv.new_pipe(false)

  if not stdout_pipe or not stderr_pipe then
    vim.schedule(function()
      callback(-1, {}, {"Failed to create stdio pipes"})
    end)
    return
  end

  local handle = uv.spawn(cmd_parts[1], {
    args = vim.list_slice(cmd_parts, 2),
    stdio = { nil, stdout_pipe, stderr_pipe }
  }, function(code, signal)
    exit_code = code
    -- Ensure pipes are closed before callback
    if stdout_pipe and not uv.is_closing(stdout_pipe) then
      uv.read_stop(stdout_pipe)
      uv.close(stdout_pipe)
    end
    if stderr_pipe and not uv.is_closing(stderr_pipe) then
      uv.read_stop(stderr_pipe)
      uv.close(stderr_pipe)
    end
    -- Close process handle and trigger callback
    if handle and not uv.is_closing(handle) then
      uv.close(handle, function()
        vim.schedule(function() 
          callback(exit_code, stdout_lines, stderr_lines) 
        end)
      end)
    else
      vim.schedule(function() 
        callback(exit_code, stdout_lines, stderr_lines) 
      end)
    end
  end)

  if not handle then
    -- Clean up pipes if spawn failed
    if stdout_pipe and not uv.is_closing(stdout_pipe) then uv.close(stdout_pipe) end
    if stderr_pipe and not uv.is_closing(stderr_pipe) then uv.close(stderr_pipe) end
    vim.schedule(function()
      callback(-1, {}, {"Failed to spawn mcpdiff process"})
    end)
    return
  end

  -- Read stdout
  uv.read_start(stdout_pipe, function(err, data)
    if err then
      table.insert(stderr_lines, "Error reading stdout: " .. vim.inspect(err))
      return
    end
    if data then
      vim.list_extend(stdout_lines, vim.split(data, "\n", { plain = true, trimempty = true }))
    end
  end)

  -- Read stderr
  uv.read_start(stderr_pipe, function(err, data)
    if err then
      table.insert(stderr_lines, "Error reading stderr: " .. vim.inspect(err))
      return
    end
    if data then
      vim.list_extend(stderr_lines, vim.split(data, "\n", { plain = true, trimempty = true }))
    end
  end)
end


--- Public Plugin Functions ---

-- Get mcpdiff status
function M.status(args_str)
  -- Filter out empty strings from the argument split
  local args = {}
  if args_str and args_str ~= "" then
    args = vim.split(args_str, "%s+", { trimempty = true })
  end
  
  run_mcpdiff(vim.list_extend({ "status" }, args), function(code, stdout_lines, stderr_lines)
    if code == 0 then
      if #stdout_lines > 0 then
        show_output_in_float("MCP Diff Status", stdout_lines)
      else
        vim.notify("mcpdiff status: No output", vim.log.levels.INFO)
      end
    else
      local msg = "mcpdiff status failed (code: " .. tostring(code) .. ")"
      if #stderr_lines > 0 then
          vim.notify(msg .. "\n" .. table.concat(stderr_lines, "\n"), vim.log.levels.ERROR)
      else
           vim.notify(msg, vim.log.levels.ERROR)
      end
    end
  end)
end

-- Show diff for an ID or conversation
function M.show(args_str)
    if not args_str or args_str == "" then
        vim.notify("McpdiffShow requires an edit ID or conversation ID prefix.", vim.log.levels.ERROR)
        return
    end
  -- Show expects a single identifier argument
  local args = { "show", args_str }
  run_mcpdiff(args, function(code, stdout_lines, stderr_lines)
    if code == 0 then
      if #stdout_lines > 0 then
          -- Note: ANSI colors from mcpdiff should render correctly in float if termguicolors is set
         show_output_in_float("MCP Diff Show: " .. args_str, stdout_lines)
      else
         vim.notify("mcpdiff show: No output", vim.log.levels.INFO)
      end
    else
      local msg = "mcpdiff show failed (code: " .. tostring(code) .. ")"
       if #stderr_lines > 0 then
           -- Show stderr in float as it might contain useful error details (like ambiguous ID)
           show_output_in_float("MCP Diff Show ERROR: " .. args_str, stderr_lines)
           vim.notify(msg, vim.log.levels.ERROR) -- Also notify
       else
           vim.notify(msg, vim.log.levels.ERROR)
       end
    end
  end)
end

-- Accept an edit or conversation
function M.accept(args_str)
  if not args_str or args_str == "" then
    vim.notify("McpdiffAccept requires arguments (e.g., '-e <id>' or '-c <id>')", vim.log.levels.ERROR)
    return
  end
  local args = vim.split(args_str or "", "%s+") -- Split user args
  run_mcpdiff(vim.list_extend({ "accept" }, args), function(code, stdout_lines, stderr_lines)
    local msg = "mcpdiff accept " .. args_str
    if code == 0 then
      vim.notify(msg .. " succeeded.\n" .. table.concat(stdout_lines, "\n"), vim.log.levels.INFO)
    else
        msg = msg .. " failed (code: " .. tostring(code) .. ")"
        if #stderr_lines > 0 then
           vim.notify(msg .. "\n" .. table.concat(stderr_lines, "\n"), vim.log.levels.ERROR)
       else
           vim.notify(msg, vim.log.levels.ERROR)
       end
    end
  end)
end

-- Reject an edit or conversation
function M.reject(args_str)
  if not args_str or args_str == "" then
    vim.notify("McpdiffReject requires arguments (e.g., '-e <id>' or '-c <id>')", vim.log.levels.ERROR)
    return
  end
  local args = vim.split(args_str or "", "%s+")
  run_mcpdiff(vim.list_extend({ "reject" }, args), function(code, stdout_lines, stderr_lines)
      local msg = "mcpdiff reject " .. args_str
      if code == 0 then
         vim.notify(msg .. " succeeded.\n" .. table.concat(stdout_lines, "\n"), vim.log.levels.INFO)
         vim.cmd("redraw!") -- Force redraw in case file content changed
      else
         msg = msg .. " failed (code: " .. tostring(code) .. ")"
         if #stderr_lines > 0 then
            vim.notify(msg .. "\n" .. table.concat(stderr_lines, "\n"), vim.log.levels.ERROR)
        else
            vim.notify(msg, vim.log.levels.ERROR)
        end
      end
  end)
end

-- Run interactive review in a terminal
function M.review(args_str)
    local args = vim.split(args_str or "", "%s+", { trimempty = true })
    local cmd_to_run = config.mcpdiff_cmd .. " review"
    if #args > 0 then
        local escaped_args = vim.tbl_map(vim.fn.shellescape, args)
        cmd_to_run = cmd_to_run .. " " .. table.concat(escaped_args, " ") -- Add args only if they exist
    end
    -- Use built-in terminal in a vertical split
    vim.cmd('vsplit | terminal ' .. cmd_to_run)
    -- Alternative using built-in terminal:
    -- vim.cmd('10split | terminal ' .. cmd_to_run)
    -- vim.cmd('wincmd k') -- Move focus back up
    print("Opened mcpdiff review in a terminal window.")
    -- NOTE: You might need the 'voldikss/vim-floaterm' plugin for the FloatermNew command.
    -- If you don't have it, replace the FloatermNew line with one of the :terminal alternatives.
end

-- Setup function for configuration
function M.setup(user_config)
  config = vim.tbl_deep_extend("force", config, user_config or {})
  is_debug = config.debug or false -- Allow enabling debug via setup
  -- Validate config if needed
end

return M
