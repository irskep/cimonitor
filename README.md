# CI Monitor

CI Monitor is a command-line tool that lets AI agents and humans instantly access GitHub CI status, logs, and failure details without leaving the terminal.

**Eliminates Copy-Paste Development** - No more copying error messages from GitHub's web interface. Agents can directly access CI failures, logs, and status updates through a simple command-line interface.

**Universal Agent Compatibility** - Works with any AI coding assistant (Claude Code, Cursor, etc.) that can run terminal commands.

## Installation

```bash
pip install cimonitor
export GITHUB_TOKEN="your_github_token_here"
```

## Usage

```bash
# Check current branch
cimonitor

# Target specific commits/branches/PRs
cimonitor --commit abc1234 --show-logs
cimonitor --branch main --verbose  
cimonitor --pr 123

# Real-time monitoring
cimonitor --poll                    # Wait for completion
cimonitor --poll-until-failure     # Stop on first failure

# Debug specific jobs
cimonitor --job-id 12345678 --raw-logs
```

## What Agents Can Do

**Instant CI Diagnosis** - Check any commit, branch, or PR for failures and get structured output perfect for programmatic analysis.

**Real-Time Monitoring** - Use `--poll` to watch CI progress live, or `--poll-until-failure` for fail-fast workflows.

**Targeted Debugging** - Get step-level failure details and filtered error logs without downloading massive raw logs.

**Multi-Branch Operations** - Seamlessly check CI status across different branches, PRs, and commits in automated workflows.

## Key Features

- Step-level failure detection without downloading entire logs
- Smart log filtering showing only error-related content  
- Real-time CI status polling with fail-fast options
- Support for commits, branches, and pull requests
- Raw log access for deep debugging

## Requirements

- Python 3.10+, Git repository with GitHub remote, GitHub personal access token

## License

MIT License - see [LICENSE](LICENSE) file for details.