# GitHub Issue Vibe MCP Server

This MCP server helps you fix GitHub issues that are tagged with "vibe". It provides tools to pick an issue, create a branch, and submit a fix.

## Tools

### vibe-fix-issue

Picks and prepares a GitHub issue for fixing:
- Verifies git status is clean
- Uses gh CLI to interact with GitHub repositories
- Gets issues with "vibe" tag and "open" status without linked PRs or "blocked" tag
- Can take a specific issue number or pick one based on priority
- Creates a new branch from the source branch specified in the issue
- Provides instructions from the issue for debugging

### vibe-commit-fix

Finalizes and submits your fix:
- Comments the changelog in the issue
- Commits your changes and creates a pull request

## Requirements

- gh CLI must be installed and authenticated
- git must be installed
- You must have appropriate GitHub permissions for the repository

## Usage

1. Run `vibe-fix-issue` to pick an issue and set up your environment
2. Make the necessary code changes to fix the issue
3. Run `vibe-commit-fix` to submit your fix
