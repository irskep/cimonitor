# CI Monitor

A Python tool to monitor GitHub CI workflows, fetch logs, and track build status. Quickly identify and debug CI failures without navigating through the GitHub web interface.

## Installation

```bash
pip install cimonitor
```

## Quick Start

1. Set your GitHub token as an environment variable:
   ```bash
   export GITHUB_TOKEN="your_github_token_here"
   ```

2. Navigate to a git repository and run:
   ```bash
   cimonitor
   ```

## Usage

### Basic Usage

```bash
# Check current branch's latest commit
cimonitor

# Show verbose output
cimonitor --verbose

# Show detailed error logs for failed steps
cimonitor --show-logs
```

### Target Specific Commits or Branches

```bash
# Check a specific commit
cimonitor --commit abc1234

# Check a specific branch
cimonitor --branch main

# Check a pull request
cimonitor --pr 123
```

### Advanced Options

```bash
# Show raw logs for debugging
cimonitor --raw-logs

# Show logs for a specific job ID
cimonitor --job-id 12345678

# Poll CI status until all workflows complete
cimonitor --poll

# Poll CI status and stop on first failure
cimonitor --poll-until-failure
```

## Features

- **Step-level failure detection** - See which specific CI steps failed without downloading entire logs
- **Multiple target options** - Check commits, branches, or pull requests
- **Smart log filtering** - Shows only error-related content by default
- **Verbose mode** - Get detailed information about the repository and commit
- **Raw log access** - Full log output for debugging when needed
- **CI status polling** - Monitor workflow progress in real-time with `--poll` options

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
| `--poll` | Poll CI status until all workflows complete |
| `--poll-until-failure` | Poll CI status until first failure or all complete |
| `--help` | Show help message |

**Note**: Target options (`--branch`, `--commit`, `--pr`) are mutually exclusive. If none specified, uses current branch and latest commit.

## Examples

```bash
# Basic check of current branch
cimonitor

# Check main branch with verbose output
cimonitor --branch main --verbose

# Check specific commit and show detailed logs
cimonitor --commit abc1234 --show-logs

# Check pull request #42
cimonitor --pr 42

# Debug a specific job
cimonitor --job-id 45867092486 --raw-logs

# Monitor CI progress in real-time
cimonitor --poll --verbose

# Stop monitoring on first failure
cimonitor --poll-until-failure
```

## Requirements

- Python 3.10+
- Git repository with GitHub remote
- GitHub personal access token
- Repository with GitHub Actions or other CI setup

## Use Cases

**For Developers:**
- Quickly identify CI failures without leaving the terminal
- Debug specific failing steps with targeted log filtering
- Monitor CI progress for multiple branches or pull requests

**For AI Agents:**
- Automated CI failure detection and reporting
- Real-time monitoring with `--poll` for autonomous workflows
- Fail-fast behavior with `--poll-until-failure` for efficient resource usage
- Structured output for parsing and decision-making

## License

MIT License - see [LICENSE](LICENSE) file for details.