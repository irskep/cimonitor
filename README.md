# CI Monitor

CI Monitor is a command-line tool that lets AI agents and humans instantly access GitHub CI status, logs, and failure details without leaving the terminal.

**Eliminates Copy-Paste Development** - No more copying error messages from GitHub's web interface. Agents can directly access CI failures, logs, and status updates through a simple command-line interface.

**Universal Agent Compatibility** - Works with any AI coding assistant (Claude Code, Cursor, etc.) that can run terminal commands.

## Automated CI Debugging with Claude Code

```bash
# Single command to investigate and fix your PR's CI failures
cimonitor --pr 123 --logs | claude "Analyze these CI failures and fix the issues. Commit and push the fixes when done."

# Auto-retry flaky tests and get notified only for real failures
cimonitor --pr 123 --watch-and-retry 3 | claude "Monitor this output. If tests still fail after retries, analyze the logs and notify me with a summary of the real issues."
```

This powerful combination lets you:
- **Fix Real Issues**: Claude Code automatically parses CI logs, identifies root causes, implements fixes, and pushes solutions
- **Handle Flaky Tests**: Auto-retry failing jobs up to N times, only getting notified if failures persist
- **Smart Notifications**: Get intelligent summaries of actual problems, not transient flakes
- **Zero Manual Work**: No copying error messages or switching between terminal and browser

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
cimonitor --commit abc1234 --logs
cimonitor --branch main --verbose
cimonitor --pr 123

# Real-time monitoring
cimonitor --watch-until-completion  # Wait for completion
cimonitor --watch-until-fail        # Stop on first failure
cimonitor --watch-and-retry 3       # Watch and auto-retry failed jobs up to 3 times

# Debug specific jobs
cimonitor --job-id 12345678 --raw-logs
```

## What Agents Can Do

**Instant CI Diagnosis** - Check any commit, branch, or PR for failures and get structured output perfect for programmatic analysis.

**Real-Time Monitoring** - Use `--watch-until-completion` to watch CI progress live, `--watch-until-fail` for fail-fast workflows, or `--watch-and-retry N` to automatically retry failed jobs and filter out flaky test failures.

**Targeted Debugging** - Get step-level failure details and filtered error logs without downloading massive raw logs.

**Multi-Branch Operations** - Seamlessly check CI status across different branches, PRs, and commits in automated workflows.

## Key Features

- Step-level failure detection without downloading entire logs
- Smart log filtering showing only error-related content
- Real-time CI status monitoring with fail-fast options
- Automatic retry of failed jobs with configurable retry limits (perfect for filtering out flaky tests)
- Support for commits, branches, and pull requests
- Raw log access for deep debugging

## Requirements

- Python 3.10+, Git repository with GitHub remote, GitHub personal access token

## License

MIT License - see [LICENSE](LICENSE) file for details.
