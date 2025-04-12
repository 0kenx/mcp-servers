import sys
import os
import subprocess
import json
import re
from typing import Optional, List, Dict, Any, Tuple

from mcp.server.fastmcp import FastMCP

MCP_INSTRUCTIONS = """
The GitHub Issue Vibe MCP Server helps you fix GitHub issues that are tagged with "vibe".

Key capabilities:
1. `vibe-fix-issue`: Pick and prepare a GitHub issue for fixing
   - Verifies git status is clean
   - Uses gh CLI to interact with GitHub repositories
   - Gets issues with "vibe" tag and "open" status without linked PRs or "blocked" tag
   - Can take a specific issue number or pick one based on priority
   - Creates a new branch from the source branch specified in the issue
   - Provides instructions from the issue for debugging

2. `vibe-commit-fix`: Finalize and submit your fix
   - Comments the changelog in the issue
   - Commits your changes and creates a pull request

Usage workflow:
1. Run `vibe-fix-issue` to pick an issue and set up your environment
2. Make the necessary code changes to fix the issue
3. Run `vibe-commit-fix` to submit your fix

Requirements:
- gh CLI must be installed and authenticated
- git must be installed
- You must have appropriate GitHub permissions for the repository
"""

# Create MCP server
mcp = FastMCP("github-vibe", instructions=MCP_INSTRUCTIONS)

# Environment variables
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
GIT_USER_NAME = os.environ.get("GIT_USER_NAME")
GIT_USER_EMAIL = os.environ.get("GIT_USER_EMAIL")
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")

# Working directory global variable
WORKING_DIRECTORY = None


def run_command(command: List[str], check: bool = True) -> Tuple[str, str, int]:
    """Run a shell command and return stdout, stderr, and return code."""
    try:
        result = subprocess.run(
            command, capture_output=True, text=True, check=check, cwd=WORKING_DIRECTORY
        )
        return result.stdout.strip(), result.stderr.strip(), result.returncode
    except subprocess.CalledProcessError as e:
        return (
            e.stdout.strip() if e.stdout else "",
            e.stderr.strip() if e.stderr else "",
            e.returncode,
        )


def check_git_status() -> Tuple[bool, str]:
    """Check if the git working directory is clean."""
    stdout, stderr, rc = run_command(["git", "status", "--porcelain"], check=False)

    if rc != 0:
        return False, f"Error checking git status: {stderr}"

    if stdout:
        return (
            False,
            "Git working directory is not clean. Please commit or stash your changes before continuing.",
        )

    return True, "Git working directory is clean."


def get_github_repo() -> Tuple[bool, str]:
    """Get the GitHub repository from the git remote."""
    stdout, stderr, rc = run_command(
        ["git", "remote", "get-url", "origin"], check=False
    )

    if rc != 0:
        return False, f"Error getting GitHub repository: {stderr}"

    # Try to extract the GitHub repository from the remote URL
    # Supports formats like:
    # - https://github.com/owner/repo.git
    # - git@github.com:owner/repo.git
    match = re.search(r"github\.com[:/]([^/]+/[^/]+?)(\.git)?$", stdout)
    if not match:
        return False, f"Could not extract GitHub repository from remote URL: {stdout}"

    repo = match.group(1)
    return True, repo


def get_vibe_issues(repo: str) -> Tuple[bool, List[Dict[Any, Any]], str]:
    """Get all open vibe issues without linked PRs or blocked tag."""
    # Use gh CLI to get issues with the 'vibe' label, open status, and no linked PR
    cmd = [
        "gh",
        "issue",
        "list",
        "--repo",
        repo,
        "--label",
        "vibe",
        "--state",
        "open",
        "--json",
        "number,title,labels,createdAt,body",
    ]

    stdout, stderr, rc = run_command(cmd, check=False)

    if rc != 0:
        return False, [], f"Error fetching GitHub issues: {stderr}"

    try:
        all_issues = json.loads(stdout)
        # Filter issues without the 'blocked' label and without linked PRs
        filtered_issues = []

        for issue in all_issues:
            label_names = [label["name"] for label in issue.get("labels", [])]
            if "blocked" not in label_names:
                # Check if issue has linked PRs
                pr_cmd = [
                    "gh",
                    "issue",
                    "view",
                    str(issue["number"]),
                    "--repo",
                    repo,
                    "--json",
                    "linkedPullRequests",
                ]
                pr_stdout, pr_stderr, pr_rc = run_command(pr_cmd, check=False)

                if pr_rc != 0:
                    return (
                        False,
                        [],
                        f"Error checking linked PRs for issue #{issue['number']}: {pr_stderr}",
                    )

                try:
                    pr_data = json.loads(pr_stdout)
                    linked_prs = pr_data.get("linkedPullRequests", [])
                    if not linked_prs:
                        filtered_issues.append(issue)
                except json.JSONDecodeError:
                    return (
                        False,
                        [],
                        f"Error parsing linked PR data for issue #{issue['number']}: {pr_stdout}",
                    )

        return True, filtered_issues, "Successfully fetched vibe issues."

    except json.JSONDecodeError:
        return False, [], f"Error parsing GitHub issues data: {stdout}"


def select_issue(
    issues: List[Dict[Any, Any]], issue_number: Optional[int] = None
) -> Tuple[bool, Dict[Any, Any], str]:
    """
    Select an issue to work on.

    If issue_number is provided, find that specific issue.
    Otherwise, select based on priority labels and age.
    """
    if not issues:
        return False, {}, "No eligible issues found."

    # If specific issue number provided, find it
    if issue_number:
        for issue in issues:
            if issue["number"] == issue_number:
                return True, issue, f"Selected issue #{issue_number}."
        return (
            False,
            {},
            f"Issue #{issue_number} not found or is not an eligible vibe issue.",
        )

    # Otherwise, select based on priority
    priority_order = ["Priority A", "Priority B", "Priority C", "Priority D"]

    # Group issues by priority
    priority_issues = {priority: [] for priority in priority_order}
    other_issues = []

    for issue in issues:
        label_names = [label["name"] for label in issue.get("labels", [])]

        # Check if issue has any priority label
        assigned_priority = False
        for priority in priority_order:
            if priority in label_names:
                priority_issues[priority].append(issue)
                assigned_priority = True
                break

        if not assigned_priority:
            other_issues.append(issue)

    # Select the oldest issue from the highest priority group
    for priority in priority_order:
        if priority_issues[priority]:
            # Sort by creation date (oldest first)
            sorted_issues = sorted(
                priority_issues[priority], key=lambda x: x["createdAt"]
            )

            # Check for linked issues (TODO: Implement this if needed)
            # For now, just pick the oldest
            selected_issue = sorted_issues[0]
            return (
                True,
                selected_issue,
                f"Selected issue #{selected_issue['number']} ({priority}).",
            )

    # If no priority issues found, pick the oldest non-priority issue
    if other_issues:
        sorted_issues = sorted(other_issues, key=lambda x: x["createdAt"])
        selected_issue = sorted_issues[0]
        return (
            True,
            selected_issue,
            f"Selected issue #{selected_issue['number']} (no priority label).",
        )

    return False, {}, "No eligible issues found after filtering."


def extract_source_branch(issue_body: str) -> Tuple[bool, str]:
    """Extract the source branch from the issue body."""
    # Try to find a line that specifies the source branch
    # Common patterns might be:
    # - "Source branch: main"
    # - "Branch: feature/xyz"
    # - "Starting branch: development"

    patterns = [
        r"(?i)source\s+branch:\s*(\S+)",
        r"(?i)starting\s+branch:\s*(\S+)",
        r"(?i)branch:\s*(\S+)",
    ]

    for pattern in patterns:
        match = re.search(pattern, issue_body)
        if match:
            return True, match.group(1)

    # Default to main if not specified
    return False, "main"


def create_branch(
    issue_number: int, issue_title: str, source_branch: str
) -> Tuple[bool, str]:
    """Create a new branch for the issue."""
    # Sanitize the issue title to create a valid branch name
    sanitized_title = re.sub(r"[^a-zA-Z0-9_-]", "-", issue_title.lower())
    sanitized_title = re.sub(
        r"-+", "-", sanitized_title
    )  # Replace multiple dashes with one
    branch_name = f"vibe/{issue_number}-{sanitized_title}"

    # First, fetch the latest changes
    fetch_stdout, fetch_stderr, fetch_rc = run_command(["git", "fetch"], check=False)
    if fetch_rc != 0:
        return False, f"Error fetching latest changes: {fetch_stderr}"

    # Check if the source branch exists
    check_stdout, check_stderr, check_rc = run_command(
        ["git", "rev-parse", "--verify", f"origin/{source_branch}"], check=False
    )
    if check_rc != 0:
        return False, f"Source branch '{source_branch}' does not exist: {check_stderr}"

    # Create a new branch from the source branch
    branch_stdout, branch_stderr, branch_rc = run_command(
        ["git", "checkout", "-b", branch_name, f"origin/{source_branch}"], check=False
    )

    if branch_rc != 0:
        return False, f"Error creating branch '{branch_name}': {branch_stderr}"

    return True, f"Created branch '{branch_name}' from '{source_branch}'."


def extract_debug_instructions(issue_body: str) -> str:
    """Extract debugging instructions from the issue body."""
    # This is a simplified implementation
    # In reality, you might want to look for specific sections or markdown formatting

    # Try to find a section about debugging or reproduction steps
    # For now, just extract text after certain keywords
    patterns = [
        r"(?i)## Steps to reproduce\s*([\s\S]*?)(?:\n##|\Z)",
        r"(?i)## Debug instructions\s*([\s\S]*?)(?:\n##|\Z)",
        r"(?i)## How to fix\s*([\s\S]*?)(?:\n##|\Z)",
        r"(?i)## Description\s*([\s\S]*?)(?:\n##|\Z)",  # Fallback to description
    ]

    for pattern in patterns:
        match = re.search(pattern, issue_body)
        if match and match.group(1).strip():
            return match.group(1).strip()

    # If no specific section found, return the whole body
    return issue_body


def validate_working_directory(directory: str) -> Tuple[bool, str]:
    """Validate working directory exists, is readable, and is a git repository."""
    if not directory:
        return False, "Working directory path is empty or not provided."

    if not os.path.isdir(directory):
        return False, f"'{directory}' is not a directory."

    if not os.access(directory, os.R_OK):
        return False, f"No read permission for '{directory}'."

    # Check if this is a git repository
    stdout, stderr, rc = run_command(
        ["git", "rev-parse", "--is-inside-work-tree"], check=False
    )
    if rc != 0:
        return False, f"'{directory}' is not a git repository or git is not installed."

    result = run_command(
        ["gh", "auth", "login", "--with-token", GITHUB_TOKEN], check=False
    )

    if result[2] != 0:
        return False, f"Error logging in to GitHub: {result[1]}"

    return True, f"Working directory '{directory}' is valid."


@mcp.tool()
async def vibe_fix_issue(
    working_directory: Optional[str] = None, issue_number: Optional[int] = None
) -> str:
    """
    Pick a GitHub issue tagged with 'vibe' and prepare it for fixing.

    This tool:
    1. Verifies git status (clean with no uncommitted/unstashed changes)
    2. Uses gh CLI to interact with GitHub
    3. Gets issues with "vibe" tag, "open" status, no linked PR, and no "blocked" tag
    4. Selects an appropriate issue based on priorities and linked issues
    5. Creates a new branch from the source branch specified in the issue
    6. Provides instructions from the issue for debugging

    Args:
        working_directory: The directory where git and gh commands will be executed.
                          Required on first call, can be omitted on subsequent calls.
        issue_number: Optional specific issue number to work on

    Returns:
        Instructions for fixing the selected issue
    """
    global WORKING_DIRECTORY

    # If working_directory is provided, validate and set global
    if working_directory is not None:
        valid, message = validate_working_directory(working_directory)
        if not valid:
            return f"Error: {message}"
        WORKING_DIRECTORY = os.path.abspath(working_directory)

    # Check if we have a working directory (either from parameter or previous call)
    if WORKING_DIRECTORY is None:
        return "Error: Working directory is not set. Please provide 'working_directory' parameter."

    # 1. Verify git status
    is_clean, git_status_msg = check_git_status()
    if not is_clean:
        return git_status_msg

    # 2. Get GitHub repository
    success, repo_result = get_github_repo()
    if not success:
        return repo_result

    repo = repo_result

    # 3. Get vibe issues
    success, issues, issues_msg = get_vibe_issues(repo)
    if not success:
        return issues_msg

    if not issues:
        return "No eligible vibe issues found."

    # 4. Select an issue
    success, selected_issue, selection_msg = select_issue(issues, issue_number)
    if not success:
        return selection_msg

    issue_number = selected_issue["number"]
    issue_title = selected_issue["title"]
    issue_body = selected_issue["body"]

    # 5. Extract source branch from issue
    success, source_branch = extract_source_branch(issue_body)
    if not success:
        source_branch_msg = f"Could not find source branch in issue, using '{source_branch}' as default."
    else:
        source_branch_msg = f"Source branch: {source_branch}"

    # 6. Create branch
    success, branch_msg = create_branch(issue_number, issue_title, source_branch)
    if not success:
        return branch_msg

    # 7. Extract debug instructions
    debug_instructions = extract_debug_instructions(issue_body)

    # Build response
    response = f"""# Issue #{issue_number}: {issue_title}

{source_branch_msg}
{branch_msg}

## Debug Instructions
{debug_instructions}

You are now ready to fix this issue. Make the necessary changes, and then run `vibe-commit-fix` to create a PR.
"""

    return response


@mcp.tool()
async def vibe_commit_fix(changelog: str) -> str:
    """
    Finalize and submit your fix for a vibe issue.

    This tool:
    1. Comments the provided changelog in the issue
    2. Commits your changes
    3. Creates a pull request

    Args:
        changelog: Description of the changes you made (will be used for commit message and PR)

    Returns:
        Result of the operation
    """
    # Check if global working directory is set
    if WORKING_DIRECTORY is None:
        return "Error: Working directory is not set. Run vibe-fix-issue first."

    # 1. Verify we're on a vibe branch
    branch_stdout, branch_stderr, branch_rc = run_command(
        ["git", "branch", "--show-current"], check=False
    )
    if branch_rc != 0:
        return f"Error getting current branch: {branch_stderr}"

    current_branch = branch_stdout.strip()
    if not current_branch.startswith("vibe/"):
        return "You are not on a vibe branch. Please run vibe-fix-issue first."

    # Extract issue number from branch name
    match = re.search(r"vibe/(\d+)", current_branch)
    if not match:
        return f"Could not extract issue number from branch name: {current_branch}"

    issue_number = match.group(1)

    # 2. Get GitHub repository
    success, repo_result = get_github_repo()
    if not success:
        return repo_result

    repo = repo_result

    # 3. Add a comment to the issue with the changelog
    comment_cmd = [
        "gh",
        "issue",
        "comment",
        issue_number,
        "--repo",
        repo,
        "--body",
        f"## Changelog\n{changelog}",
    ]
    comment_stdout, comment_stderr, comment_rc = run_command(comment_cmd, check=False)

    if comment_rc != 0:
        return f"Error adding comment to issue #{issue_number}: {comment_stderr}"

    # 4. Add all changes and commit
    # First, check if there are any changes
    status_stdout, status_stderr, status_rc = run_command(
        ["git", "status", "--porcelain"], check=False
    )
    if status_rc != 0:
        return f"Error checking git status: {status_stderr}"

    if not status_stdout:
        return "No changes to commit. Make some changes first."

    # Add all changes
    add_stdout, add_stderr, add_rc = run_command(["git", "add", "."], check=False)
    if add_rc != 0:
        return f"Error adding changes: {add_stderr}"

    # Commit changes
    commit_message = f"Fix #{issue_number}: {changelog}"
    commit_cmd = ["git", "commit", "-m", commit_message]
    commit_stdout, commit_stderr, commit_rc = run_command(commit_cmd, check=False)

    if commit_rc != 0:
        return f"Error committing changes: {commit_stderr}"

    # 5. Push and create PR
    # Push the branch
    push_cmd = ["git", "push", "--set-upstream", "origin", current_branch]
    push_stdout, push_stderr, push_rc = run_command(push_cmd, check=False)

    if push_rc != 0:
        return f"Error pushing changes: {push_stderr}"

    # Create PR
    pr_title = f"Fix #{issue_number}: {changelog.split('.')[0]}"  # Use first sentence as PR title
    pr_body = f"Fixes #{issue_number}\n\n## Changelog\n{changelog}"

    pr_cmd = [
        "gh",
        "pr",
        "create",
        "--title",
        pr_title,
        "--body",
        pr_body,
        "--repo",
        repo,
    ]

    pr_stdout, pr_stderr, pr_rc = run_command(pr_cmd, check=False)

    if pr_rc != 0:
        return f"Error creating PR: {pr_stderr}"

    # Extract PR URL from output
    pr_url = pr_stdout.strip()

    return f"""# Fix Submitted Successfully!

Changes have been committed and a pull request has been created.

- Issue: #{issue_number}
- Branch: {current_branch}
- Pull Request: {pr_url}

Thank you for fixing this issue!
"""


def main():
    print("GitHub Issue Vibe MCP Server running", file=sys.stderr)
    mcp.run()


if __name__ == "__main__":
    main()
