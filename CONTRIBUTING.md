# Contributing to MCP Servers

Thank you for your interest in contributing to the MCP Servers project! This document provides guidelines and instructions for contributing.

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [Development Workflow](#development-workflow)
- [Submitting Changes](#submitting-changes)
- [Documentation](#documentation)
- [Testing](#testing)
- [Coding Standards](#coding-standards)

## Code of Conduct

This project is governed by our [Code of Conduct](CODE_OF_CONDUCT.md). By participating, you are expected to uphold this code.

## Getting Started

### Prerequisites

- Python 3.12 or newer
- Docker (for containerized development)
- Git

### Setting Up Your Development Environment

1. Fork the repository on GitHub
2. Clone your fork locally:
   ```bash
   git clone https://github.com/your-username/mcp-servers.git
   cd mcp-servers
   ```
3. Set up the upstream remote:
   ```bash
   git remote add upstream https://github.com/0kenx/mcp-servers.git
   ```
4. Create a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows, use: venv\Scripts\activate
   ```
5. Install development dependencies:
   ```bash
   pip install -e ".[dev]"
   ```

## Development Workflow

1. Create a new branch for your feature or bugfix:
   ```bash
   git checkout -b feature/your-feature-name
   ```
   or
   ```bash
   git checkout -b fix/issue-number
   ```

2. Make your changes, following the coding standards below

3. Add comprehensive tests for your changes

4. Update documentation as needed

5. Add your changes to the Changelog under the "Unreleased" section

6. Commit your changes with clear, descriptive commit messages:
   ```bash
   git commit -m "Add feature: your feature description"
   ```

7. Keep your branch updated with the upstream:
   ```bash
   git fetch upstream
   git rebase upstream/main
   ```

## Submitting Changes

1. Push your changes to your fork:
   ```bash
   git push origin feature/your-feature-name
   ```

2. Create a Pull Request through the GitHub website

3. Ensure your PR description clearly describes the problem and solution
   - Include the relevant issue number if applicable
   - Fill out the PR template completely

4. Wait for review and address any feedback

## Documentation

- All new features should include appropriate documentation
- Update existing documentation when changing functionality
- Follow the existing documentation style
- Use clear, concise language and provide examples where appropriate

## Testing

- All new code should have corresponding tests
- Run existing tests to ensure your changes don't break existing functionality:
  ```bash
  pytest
  ```
- Aim for high test coverage for your new code

## Coding Standards

### Python

- Follow PEP 8 style guidelines
- Use type hints for function arguments and return values
- Write docstrings for all functions, classes, and modules
- Format your code using Black:
  ```bash
  black .
  ```
- Check your code with flake8:
  ```bash
  flake8 .
  ```
- Use isort to sort imports:
  ```bash
  isort .
  ```

### JavaScript/TypeScript

- Follow the ESLint configuration for the project
- Use ES6+ features where appropriate
- Format your code using Prettier:
  ```bash
  prettier --write .
  ```

## Server-Specific Guidelines

### Filesystem MCP Server

- Ensure all file operations validate paths against allowed directories
- Write comprehensive tests for new file operations
- Update the grammar parsers when adding support for new languages
- Maintain backward compatibility with existing MCP tools

### Exec MCP Server

- Always consider security implications when adding execution features
- Test thoroughly in isolated Docker environments
- Document resource usage for intensive operations
- Ensure command execution includes proper timeout handling

### Web Processing MCP Server

- Follow web scraping best practices and respect robots.txt
- Include error handling for network issues and malformed responses
- Document API usage examples for Claude integration
- Consider rate limiting and bandwidth usage

## Release Process

1. Update the version number in relevant files
2. Ensure the CHANGELOG.md is up to date
3. Tag the release with Git:
   ```bash
   git tag -a v1.0.0 -m "Version 1.0.0"
   git push origin v1.0.0
   ```
4. Build and publish new Docker images

## Questions?

If you have any questions about contributing, please open an issue or reach out to the maintainers.

Thank you for contributing to the MCP Servers project!
