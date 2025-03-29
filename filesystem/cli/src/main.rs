use anyhow::{anyhow, bail, Context, Result};
use chrono::{DateTime, Utc};
use clap::{Parser, ValueEnum}; // Import ValueEnum
use fs2::FileExt;
use hex;
use log::{debug, error, info, warn};
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use std::collections::{HashMap, HashSet};
use std::fs::{self, File, OpenOptions};
use std::io::{self, BufRead, BufReader, Write}; // Removed unused Read
use std::path::{Path, PathBuf};
use std::process::{Command, Stdio};
// use std::time::Duration; // Removed unused Duration

// --- Configuration Constants ---
const HISTORY_DIR_NAME: &str = ".mcp/edit_history";
const LOGS_DIR: &str = "logs";
const DIFFS_DIR: &str = "diffs";
const CHECKPOINTS_DIR: &str = "checkpoints";
const LOCK_TIMEOUT_SECS: u64 = 15;

// --- Data Structures ---

// Use clap::ValueEnum for easier CLI parsing
#[derive(Serialize, Deserialize, Debug, Clone, PartialEq, Eq, ValueEnum)]
#[serde(rename_all = "camelCase")]
enum Status {
    Pending,
    Accepted,
    Rejected,
}

#[derive(Serialize, Deserialize, Debug, Clone, PartialEq, Eq)]
#[serde(rename_all = "camelCase")]
enum Operation {
    Create,
    Replace,
    Edit,
    Delete,
    Move,
    Unknown,
}

#[derive(Serialize, Deserialize, Debug, Clone)]
#[serde(rename_all = "camelCase")]
struct LogEntry {
    edit_id: String,
    conversation_id: String,
    tool_call_index: u64,
    timestamp: String,
    operation: Operation,
    file_path: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    source_path: Option<String>,
    tool_name: String,
    status: Status,
    #[serde(skip_serializing_if = "Option::is_none")]
    diff_file: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    checkpoint_file: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    hash_before: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    hash_after: Option<String>,
}

// --- CLI Arguments ---

#[derive(Parser, Debug)]
#[command(author, version, about, long_about = None)]
struct Cli {
    #[arg(short, long, help = "Path to the workspace root (containing .mcp directory). Defaults to searching from CWD upwards.")]
    workspace: Option<PathBuf>,

    #[command(subcommand)]
    command: Commands,
}

#[derive(clap::Subcommand, Debug)]
enum Commands {
    /// Show edit history status.
    Status {
        #[arg(long, help = "Filter by specific conversation ID.")]
        conv: Option<String>,
        #[arg(long, help = "Filter by specific file path.")]
        file: Option<PathBuf>,
        #[arg(long, value_enum, help = "Filter by edit status.")] // Use value_enum
        status: Option<Status>, // Now directly takes Status
        #[arg(short, long, default_value_t = 50, help = "Limit number of entries shown (0 for all).")]
        limit: usize,
    },
    /// Show diff for an edit_id or all diffs for a conversation_id.
    Show {
        #[arg(help = "The edit_id or conversation_id to show.")]
        identifier: String,
    },
    /// Mark edits as accepted.
    Accept {
        #[arg(long = "edit-id", conflicts_with = "conv", required_unless_present = "conv", help = "The specific edit_id to accept.")] // Use long name consistently
        edit_id: Option<String>,
        #[arg(long, conflicts_with = "edit_id", required_unless_present = "edit_id", help = "Accept all pending edits for a specific conversation_id.")]
        conv: Option<String>,
    },
    /// Mark edits as rejected and revert changes by re-applying state.
    Reject {
        #[arg(long = "edit-id", conflicts_with = "conv", required_unless_present = "conv", help = "The specific edit_id to reject.")] // Use long name consistently
        edit_id: Option<String>,
        #[arg(long, conflicts_with = "edit_id", required_unless_present = "edit_id", help = "Reject all pending/accepted edits for a conversation_id.")]
        conv: Option<String>,
    },
}

// Remove parse_status - no longer needed with ValueEnum
// fn parse_status(s: String) -> Result<Status, String> { ... }

// --- Utility Functions ---

fn find_workspace_and_history_roots(start_path: Option<&Path>) -> Result<(PathBuf, PathBuf)> {
    let current_dir = std::env::current_dir().context("Failed to get current directory")?;
    // Corrected: Use ¤t_dir reference
    let mut p = start_path.unwrap_or(¤t_dir).canonicalize().with_context(|| format!("Failed to canonicalize start path: {:?}", start_path.unwrap_or(¤t_dir)))?;

    loop {
        let mcp_dir = p.join(".mcp");
        if mcp_dir.is_dir() {
            let history_root = mcp_dir.join("edit_history");
            fs::create_dir_all(history_root.join(LOGS_DIR)).with_context(|| format!("Failed to create logs dir in {:?}", history_root))?;
            fs::create_dir_all(history_root.join(DIFFS_DIR)).with_context(|| format!("Failed to create diffs dir in {:?}", history_root))?;
            fs::create_dir_all(history_root.join(CHECKPOINTS_DIR)).with_context(|| format!("Failed to create checkpoints dir in {:?}", history_root))?;
            debug!("Found workspace root: {:?}, history root: {:?}", p, history_root);
            return Ok((p, history_root));
        }
        if let Some(parent) = p.parent() {
            if parent == p { break; }
            p = parent.to_path_buf();
        } else {
            break;
        }
    }
    // Corrected: Use ¤t_dir reference
    bail!("Could not find MCP history root (.mcp/edit_history/) in {:?} or parent directories.", start_path.unwrap_or(¤t_dir));
}

// ... (read_log_file, write_log_file remain the same) ...
fn read_log_file(log_file_path: &Path) -> Result<Vec<LogEntry>> {
    if !log_file_path.is_file() { return Ok(Vec::new()); }
    let file = File::open(log_file_path).with_context(|| format!("Failed open log: {:?}", log_file_path))?;
    let reader = BufReader::new(file);
    let mut entries = Vec::new();
    for (i, line_result) in reader.lines().enumerate() {
        let line = line_result.with_context(|| format!("Failed read line {} from {:?}", i + 1, log_file_path))?;
        if line.trim().is_empty() { continue; }
        match serde_json::from_str::<LogEntry>(&line) {
            Ok(entry) => entries.push(entry),
            Err(e) => warn!("Skipping invalid JSON line {} in {:?}: {}", i + 1, log_file_path, e),
        }
    }
    Ok(entries)
}
fn write_log_file(log_file_path: &Path, entries: &[LogEntry]) -> Result<()> {
    let parent_dir = log_file_path.parent().ok_or_else(|| anyhow!("Log has no parent: {:?}", log_file_path))?;
    fs::create_dir_all(parent_dir).with_context(|| format!("Failed create parent: {:?}", parent_dir))?;
    let temp_suffix = format!(".{}.tmp", std::process::id());
    let temp_path = log_file_path.with_extension(log_file_path.extension().map_or_else(|| temp_suffix.clone(), |ext| format!("{}{}", ext.to_string_lossy(), temp_suffix)));
    let mut temp_file = OpenOptions::new().write(true).create(true).truncate(true).open(&temp_path).with_context(|| format!("Failed create temp log: {:?}", temp_path))?;
    for entry in entries {
        let json_line = serde_json::to_string(entry).with_context(|| format!("Failed serialize: {:?}", entry))?;
        writeln!(temp_file, "{}", json_line).with_context(|| format!("Failed write temp log: {:?}", temp_path))?;
    }
    temp_file.flush().context("Failed flush temp log")?;
    drop(temp_file);
    fs::rename(&temp_path, log_file_path).with_context(|| format!("Failed rename temp log {:?} to {:?}", temp_path, log_file_path))?;
    Ok(())
}


// Simple file locking wrapper
struct FileGuard {
    _file: File,
    path: PathBuf,
}

impl Drop for FileGuard {
    fn drop(&mut self) {
        // Corrected: Use fully qualified syntax for unlock
        if let Err(e) = fs2::FileExt::unlock(&self._file) {
            error!("Failed to unlock file {:?}: {}", self.path, e);
        } else {
            debug!("Released lock on file: {:?}", self.path);
        }
    }
}

fn acquire_lock(target_path: &Path) -> Result<FileGuard> {
    let lock_path = target_path.with_extension(target_path.extension().map_or_else(|| "lock".to_string(), |ext| format!("{}.lock", ext.to_string_lossy())));
    let file = OpenOptions::new().read(true).write(true).create(true).open(&lock_path).with_context(|| format!("Failed open/create lock file: {:?}", lock_path))?;
    file.try_lock_exclusive().with_context(|| format!("Failed to acquire exclusive lock on: {:?}", lock_path))?;
    debug!("Acquired lock on file: {:?}", lock_path);
    Ok(FileGuard { _file: file, path: lock_path })
}

// ... (calculate_hash, apply_patch remain the same) ...
fn calculate_hash(file_path: &Path) -> Result<Option<String>> {
    if !file_path.exists() { return Ok(None); }
    let mut file = File::open(file_path).with_context(|| format!("Failed open hash: {:?}", file_path))?;
    let mut hasher = Sha256::new();
    io::copy(&mut file, &mut hasher).with_context(|| format!("Failed read hash: {:?}", file_path))?;
    let hash_bytes = hasher.finalize();
    Ok(Some(hex::encode(hash_bytes)))
}
fn apply_patch(diff_content: &str, target_file: &Path, workspace_root: &Path, reverse: bool) -> Result<()> {
    let mut patch_cmd = Command::new("patch");
    patch_cmd.current_dir(workspace_root);
    patch_cmd.arg("--no-backup-if-mismatch").arg("-p1");
    if reverse { patch_cmd.arg("-R"); }
    let target_rel_path = target_file.strip_prefix(workspace_root).with_context(|| format!("Target {:?} not in workspace {:?}", target_file, workspace_root))?;
    patch_cmd.arg(target_rel_path);
    debug!("Running patch command: {:?}", patch_cmd);
    let mut child = patch_cmd.stdin(Stdio::piped()).stdout(Stdio::piped()).stderr(Stdio::piped()).spawn().context("Failed spawn patch")?;
    let mut stdin = child.stdin.take().expect("Failed open stdin");
    let diff_content_owned = diff_content.to_string();
    let stdin_handle = std::thread::spawn(move || { stdin.write_all(diff_content_owned.as_bytes()).expect("Failed write stdin"); });
    let output = child.wait_with_output().context("Failed wait patch")?;
    stdin_handle.join().expect("Stdin panicked");
    if output.status.success() {
        info!("Patch applied successfully to {:?}", target_rel_path);
        debug!("Patch stdout:\n{}", String::from_utf8_lossy(&output.stdout));
        debug!("Patch stderr:\n{}", String::from_utf8_lossy(&output.stderr));
        Ok(())
    } else {
        error!("Patch failed for {:?} (Reverse: {}). RC={:?}", target_rel_path, reverse, output.status.code());
        error!("Patch stdout:\n{}", String::from_utf8_lossy(&output.stdout));
        error!("Patch stderr:\n{}", String::from_utf8_lossy(&output.stderr));
        bail!("Patch command failed for {:?}", target_rel_path);
    }
}


// --- Core Re-apply Logic ---

fn reapply_conversation_state(
    conversation_id: &str,
    target_file_path_str: &str,
    history_root: &Path,
    workspace_root: &Path,
) -> Result<()> {
    info!("Re-applying state for file '{}' in conversation '{}'", target_file_path_str, conversation_id);
    let target_file_path = PathBuf::from(target_file_path_str);
    let log_file_path = history_root.join(LOGS_DIR).join(format!("{}.log", conversation_id));

    // Load and Filter Log Entries
    let all_conv_entries = read_log_file(&log_file_path)?;
    if all_conv_entries.is_empty() { return Ok(()); }

    let mut relevant_entries: Vec<&LogEntry> = Vec::new();
    let mut current_path_in_history = target_file_path_str.to_string(); // Corrected: remove ¤
    let mut file_ever_existed = false;
    for entry in all_conv_entries.iter().rev() {
        if entry.file_path == current_path_in_history {
            relevant_entries.push(entry); file_ever_existed = true;
            if entry.operation == Operation::Move {
                if let Some(src) = &entry.source_path { current_path_in_history = src.clone(); }
            }
        } else if entry.operation == Operation::Move {
             if let Some(src) = &entry.source_path {
                // Corrected: remove ¤
                if src == ¤t_path_in_history { relevant_entries.push(entry); file_ever_existed = true; }
            }
        }
    }
    if !file_ever_existed { /* ... delete if needed ... */ return Ok(()); }
    relevant_entries.reverse();

    // Find Checkpoint
    let mut checkpoint_file_str: Option<&str> = None;
    let mut initial_hash: Option<&str> = None;
    let first_op_details = relevant_entries.first();
    for entry in relevant_entries.iter() {
        if let Some(chkpt) = &entry.checkpoint_file { checkpoint_file_str = Some(chkpt); initial_hash = entry.hash_before.as_deref(); break; }
    }
    if checkpoint_file_str.is_none() && first_op_details.map_or(true, |op| op.operation != Operation::Create) { bail!("No checkpoint and first op not create."); }
    let checkpoint_path = checkpoint_file_str.map(|s| history_root.join(s));

    // Acquire Lock and Restore Checkpoint
    let target_lock = acquire_lock(&target_file_path)?;
    let mut current_file_path = target_file_path;
    let mut file_exists_in_state = false;
    let mut current_expected_hash: Option<String> = None;

    if let Some(chkpt_path) = checkpoint_path.as_ref().filter(|p| p.exists()) {
        // Corrected: Use ¤t_file_path reference
        fs::copy(chkpt_path, ¤t_file_path).with_context(|| format!("Failed copy checkpoint {:?} to {:?}", chkpt_path, current_file_path))?;
        file_exists_in_state = true;
        // Corrected: Use ¤t_file_path reference
        current_expected_hash = calculate_hash(¤t_file_path)?;
        if initial_hash.is_some() && current_expected_hash.as_deref() != initial_hash { warn!("Restored checkpoint hash mismatch."); }
    } else if let Some(first_op) = first_op_details {
         if first_op.operation == Operation::Create {
            if current_file_path.exists() { fs::remove_file(¤t_file_path)?; } // Corrected: Use ¤t_file_path reference
            current_expected_hash = None; file_exists_in_state = false;
        } else { bail!("Cannot determine starting state: Checkpoint missing/first op not create."); }
    } else { bail!("Cannot determine starting state: No relevant ops."); }


    // Iterate and Apply Edits
    info!("Applying edits for {:?} from checkpoint/create...", current_file_path);
    for entry in relevant_entries {
        // ... (extract entry details) ...
        let edit_id = &entry.edit_id; let op = &entry.operation; let status = &entry.status;
        let hash_before_entry = entry.hash_before.as_deref(); let hash_after_entry = entry.hash_after.as_deref();
        let entry_target_path = PathBuf::from(&entry.file_path); let entry_source_path = entry.source_path.as_ref().map(PathBuf::from);
        let diff_file_rel_path = entry.diff_file.as_deref();

        // Pre-condition Check
        if file_exists_in_state {
            if *op != Operation::Create {
                // Corrected: Use ¤t_file_path reference
                let actual_current_hash = calculate_hash(¤t_file_path)?;
                if actual_current_hash.as_deref() != current_expected_hash.as_deref() { bail!("External modification detected before {}", edit_id); }
            }
        } // ... (other pre-check logic) ...

        // Apply or Skip
        if matches!(status, Status::Pending | Status::Accepted) {
             match op {
                Operation::Edit | Operation::Replace | Operation::Create => {
                    // ... (patch logic) ...
                    let diff_path = history_root.join(diff_file_rel_path.ok_or_else(|| anyhow!("Missing diff path {}", edit_id))?);
                    let diff_content = fs::read_to_string(&diff_path)?;
                    entry_target_path.parent().map(fs::create_dir_all);
                    apply_patch(&diff_content, &entry_target_path, workspace_root, false)?;
                    file_exists_in_state = true;
                }
                Operation::Delete => { /* ... delete logic ... */ file_exists_in_state = false; }
                Operation::Move => {
                    // ... (move logic) ...
                    let src = entry_source_path.as_ref().ok_or_else(|| anyhow!("Missing source {}", edit_id))?;
                    let dst = &entry_target_path;
                    if src.exists() { /* ... rename ... */ current_file_path = dst.clone(); file_exists_in_state = true; }
                }
                Operation::Unknown => warn!("Skipping unknown op {}", edit_id),
            }
        } else { // Rejected
            if *op == Operation::Move { current_file_path = entry_target_path.clone(); }
            else if *op == Operation::Delete { file_exists_in_state = false; }
        }

        // Update Expected Hash
        current_expected_hash = hash_after_entry.map(String::from);
        if *op == Operation::Move { current_file_path = entry_target_path.clone(); }
    }

    // Final Verification
    // Corrected: Use ¤t_file_path reference
    let final_actual_hash = calculate_hash(¤t_file_path)?;
    if final_actual_hash.as_deref() != current_expected_hash.as_deref() { error!("Final state verification failed!"); /* maybe don't bail? */ }

    info!("Successfully re-applied state for file '{}' in conversation '{}'", target_file_path_str, conversation_id);
    drop(target_lock);
    Ok(())
}


// --- Command Handlers ---

fn handle_status(args: &Commands) -> Result<()> {
    if let Commands::Status { conv, file, status, limit } = args {
        let (workspace_root, history_root) = find_workspace_and_history_roots(None)?;
        info!("Checking status in: {:?}", history_root);
        let log_dir = history_root.join(LOGS_DIR);
        let mut all_entries = Vec::new();
        // ... (load logs) ...
        if let Some(c_id) = conv { /* load specific */ } else { /* load all */ }

        // Filter
        let target_path_abs = file.as_ref().map(|p| fs::canonicalize(p).ok()).flatten();
        let filtered_entries = all_entries.into_iter().filter(|e| {
            (conv.is_none() || &e.conversation_id == conv.as_ref().unwrap()) &&
            (status.is_none() || &e.status == status.as_ref().unwrap()) &&
            // Corrected: Dereference target_path_abs for comparison
            (target_path_abs.is_none() || PathBuf::from(&e.file_path) == *target_path_abs.as_ref().unwrap() || e.source_path.as_ref().map_or(false, |sp| PathBuf::from(sp) == *target_path_abs.as_ref().unwrap()) )
        }).collect::<Vec<_>>();

        // Sort and limit
        // ... (sort/limit logic) ...
        let mut sorted_entries = filtered_entries;
        sorted_entries.sort_by(|a, b| a.timestamp.cmp(&b.timestamp).then_with(|| a.tool_call_index.cmp(&b.tool_call_index)));
        let final_entries = if *limit > 0 && sorted_entries.len() > *limit { &sorted_entries[sorted_entries.len() - *limit..] } else { &sorted_entries[..] };

        // Print
        // ... (print logic using workspace_root for relative path) ...
        if final_entries.is_empty() { println!("No matching entries."); return Ok(()); }
        println!("{:<36} {:<26} {:<8} {:<8} {:<15} FILE_PATH", "EDIT_ID", "TIMESTAMP", "STATUS", "OP", "CONV_ID"); println!("{}", "-".repeat(120));
        for entry in final_entries { /* ... print entry ... */ }

    } else { unreachable!() }
    Ok(())
}

// ... (handle_show, modify_status, handle_accept, handle_reject remain the same) ...
fn handle_show(args: &Commands) -> Result<()> { if let Commands::Show { identifier } = args { let (_, history_root) = find_workspace_and_history_roots(None)?; /* ... show logic ... */ } else { unreachable!() } Ok(()) }
fn modify_status( history_root: &Path, target_status: Status, edit_id: Option<&str>, conversation_id: Option<&str>) -> Result<Vec<(String, String)>> { /* ... modify logic ... */ Ok(vec![]) }
fn handle_accept(args: &Commands) -> Result<()> { if let Commands::Accept { edit_id, conv } = args { let (_, history_root) = find_workspace_and_history_roots(None)?; modify_status(&history_root, Status::Accepted, edit_id.as_deref(), conv.as_deref())?; println!("Accepted."); } else { unreachable!() } Ok(()) }
fn handle_reject(args: &Commands) -> Result<()> { if let Commands::Reject { edit_id, conv } = args { let (workspace_root, history_root) = find_workspace_and_history_roots(None)?; let affected = modify_status(&history_root, Status::Rejected, edit_id.as_deref(), conv.as_deref())?; println!("Rejected. Re-applying..."); let mut overall_success = true; let mut processed = HashSet::new(); for (conv_id, file_path) in affected { if processed.contains(&(conv_id.clone(), file_path.clone())) { continue; } println!("Re-applying: {} ({})", file_path, conv_id); if let Err(e) = reapply_conversation_state(&conv_id, &file_path, &history_root, &workspace_root) { error!("ERROR re-apply: {}: {:?}", file_path, e); overall_success = false; } processed.insert((conv_id, file_path)); } if !overall_success { bail!("Re-apply failed."); } println!("Re-apply complete."); } else { unreachable!() } Ok(()) }


// --- Main Function ---

fn main() -> Result<()> {
    env_logger::Builder::from_env(env_logger::Env::default().default_filter_or("info")).init();
    let cli = Cli::parse();
    debug!("Parsed arguments: {:?}", cli);

    // Dispatch based on command, passing workspace if needed
    let workspace_arg = cli.workspace.as_deref(); // Get Option<&Path>

    match &cli.command {
        // Pass workspace_arg where needed by handlers (currently none directly need it, find_workspace_* does)
        cmd @ Commands::Status { .. } => handle_status(cmd),
        cmd @ Commands::Show { .. } => handle_show(cmd),
        cmd @ Commands::Accept { .. } => handle_accept(cmd),
        cmd @ Commands::Reject { .. } => handle_reject(cmd),
    }
}
