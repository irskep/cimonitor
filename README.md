# GitHub CI Fetcher

A Python tool to fetch and display GitHub CI logs for failing builds on the latest commit of the current branch.

## Setup

1. Install dependencies:
   ```bash
   mise run install
   ```

2. Set your GitHub token:
   ```bash
   export GITHUB_TOKEN=your_github_token_here
   ```

## Usage

Fetch CI logs for failing builds:
```bash
mise run ci-logs
```

Or run directly:
```bash
uv run ci_logs.py
```

### Options

- `--verbose, -v`: Show verbose output
- `--branch BRANCH`: Check a specific branch (defaults to current branch)

### Examples

```bash
# Basic usage
mise run ci-logs

# Verbose output
mise run ci-logs -- --verbose

# Check specific branch
mise run ci-logs -- --branch main

# Show help
uv run ci_logs.py --help
```

## Requirements

- Python 3.12+
- GitHub repository with CI/CD setup
- GitHub personal access token with repo access
- mise and uv installed