# GitHub CI Fetcher

A Python tool to fetch and display GitHub CI logs for failing builds. Quickly identify and debug CI failures without navigating through the GitHub web interface.

## Installation

```bash
pip install github-ci-fetcher
```

## Quick Start

1. Set your GitHub token as an environment variable:
   ```bash
   export GITHUB_TOKEN="your_github_token_here"
   ```

2. Navigate to a git repository and run:
   ```bash
   fetch-ci-logs
   ```

## Usage

### Basic Usage

```bash
# Check current branch's latest commit
fetch-ci-logs

# Show verbose output
fetch-ci-logs --verbose

# Show detailed error logs for failed steps
fetch-ci-logs --show-logs
```

### Target Specific Commits or Branches

```bash
# Check a specific commit
fetch-ci-logs --commit abc1234

# Check a specific branch
fetch-ci-logs --branch main

# Check a pull request
fetch-ci-logs --pr 123
```

### Advanced Options

```bash
# Show raw logs for debugging
fetch-ci-logs --raw-logs

# Show logs for a specific job ID
fetch-ci-logs --job-id 12345678
```

## Features

- **Step-level failure detection** - See which specific CI steps failed without downloading entire logs
- **Multiple target options** - Check commits, branches, or pull requests
- **Smart log filtering** - Shows only error-related content by default
- **Verbose mode** - Get detailed information about the repository and commit
- **Raw log access** - Full log output for debugging when needed

## Authentication

You need a GitHub personal access token with repository access. Create one at [GitHub Settings > Developer settings > Personal access tokens](https://github.com/settings/tokens).

Set it as an environment variable:
```bash
export GITHUB_TOKEN="your_token_here"
```

Or create a `.env` file in your project:
```
GITHUB_TOKEN=your_token_here
```

## Command Options

| Option | Description |
|--------|-------------|
| `--branch TEXT` | Check a specific branch (defaults to current branch) |
| `--commit TEXT` | Check a specific commit SHA |
| `--pr, --pull-request INTEGER` | Check a pull request number |
| `--verbose, -v` | Show verbose output |
| `--show-logs` | Show detailed error logs for failed steps only |
| `--raw-logs` | Show complete raw logs for all failed jobs |
| `--job-id INTEGER` | Show raw logs for specific job ID only |
| `--help` | Show help message |

**Note**: Target options (`--branch`, `--commit`, `--pr`) are mutually exclusive. If none specified, uses current branch and latest commit.

## Examples

```bash
# Basic check of current branch
fetch-ci-logs

# Check main branch with verbose output
fetch-ci-logs --branch main --verbose

# Check specific commit and show detailed logs
fetch-ci-logs --commit abc1234 --show-logs

# Check pull request #42
fetch-ci-logs --pr 42

# Debug a specific job
fetch-ci-logs --job-id 45867092486 --raw-logs
```

## Requirements

- Python 3.10+
- Git repository with GitHub remote
- GitHub personal access token
- Repository with GitHub Actions or other CI setup

## Development

This tool is built for developers who want to quickly identify CI failures without leaving their terminal or IDE. It's particularly useful when:

- Working with multiple branches or pull requests
- Debugging CI failures in team environments  
- Automating CI failure notifications
- Integrating CI status into development workflows

## License

MIT License - see [LICENSE](LICENSE) file for details.