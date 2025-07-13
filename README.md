# CI Monitor

CI Monitor is a command-line tool that lets AI agents and humans instantly access GitHub CI status, logs, and failure details without leaving the terminal.

**Eliminates Copy-Paste Development** - No more copying error messages from GitHub's web interface. Agents can directly access CI failures, logs, and status updates through a simple command-line interface.

**Universal Agent Compatibility** - Works with any AI coding assistant (Claude Code, Cursor, etc.) that can run terminal commands.

## Automated CI Debugging with Claude Code

```bash
# Single command to investigate and fix your PR's CI failures
cimonitor logs --pr 123 | claude \
  "Analyze these CI failures and fix the issues. Commit and push the fixes when done."

# Auto-retry flaky tests and get notified only for real failures
cimonitor watch --pr 123 --retry 3 | claude \
  "Monitor this output. If tests still fail after retries, analyze the logs and notify me with a summary of the real issues."
```

This powerful combination lets you:
- **Stay Focused**: No need to monitor job status and engage with an agent if you see a failure—let the agent do the waiting
- **Fix Real Issues**: Claude Code automatically parses CI logs, identifies root causes, implements fixes, and pushes solutions
- **Handle Flaky Tests**: Auto-retry failing jobs up to N times, only getting notified if failures persist

## Installation

```bash
pip install cimonitor
export GITHUB_TOKEN="your_github_token_here"
```

How to generate a token:
1. Visit [https://github.com/settings/tokens](https://github.com/settings/tokens),
2. "Generate new token" -> "Generate new token (classic)"
3. Check "repo" and "workflow"
4. Generate the token and export it as an environment variable as shown above

## Usage

```bash
# Check CI status
cimonitor status                    # Current branch
cimonitor status --pr 123          # Specific PR
cimonitor status --commit abc1234  # Specific commit

# Get error logs
cimonitor logs                      # Current branch (filtered logs)
cimonitor logs --pr 123            # PR logs
cimonitor logs --raw               # Raw unfiltered logs
cimonitor logs --job-id 12345678   # Specific job logs

# Watch CI progress
cimonitor watch                     # Watch current branch
cimonitor watch --until-complete   # Wait for completion
cimonitor watch --until-fail       # Stop on first failure
cimonitor watch --retry 3          # Auto-retry failed jobs up to 3 times
```

## Command Reference

### Main Command
```
Usage: cimonitor [OPTIONS] COMMAND [ARGS]...

  CI Monitor - Monitor GitHub CI workflows, fetch logs, and track build
  status.

Options:
  --version  Show the version and exit.
  --help     Show this message and exit.

Commands:
  logs    Show error logs for failed CI jobs.
  status  Show CI status for the target commit/branch/PR.
  watch   Watch CI status with real-time updates.
```

### cimonitor status
```
Usage: cimonitor status [OPTIONS]

  Show CI status for the target commit/branch/PR.

Options:
  --pr, --pull-request INTEGER  Pull request number to check
  --commit TEXT                 Specific commit SHA to check
  --branch TEXT                 Specific branch to check (defaults to current
                                branch)
  -v, --verbose                 Show verbose output
  --help                        Show this message and exit.
```

### cimonitor logs
```
Usage: cimonitor logs [OPTIONS]

  Show error logs for failed CI jobs.

Options:
  --pr, --pull-request INTEGER  Pull request number to check
  --commit TEXT                 Specific commit SHA to check
  --branch TEXT                 Specific branch to check (defaults to current
                                branch)
  -v, --verbose                 Show verbose output
  --raw                         Show complete raw logs (for debugging)
  --job-id INTEGER              Show logs for specific job ID only
  --help                        Show this message and exit.
```

### cimonitor watch
```
Usage: cimonitor watch [OPTIONS]

  Watch CI status with real-time updates.

Options:
  --pr, --pull-request INTEGER  Pull request number to check
  --commit TEXT                 Specific commit SHA to check
  --branch TEXT                 Specific branch to check (defaults to current
                                branch)
  -v, --verbose                 Show verbose output
  --until-complete              Wait until all workflows complete
  --until-fail                  Stop on first failure
  --retry COUNT                 Auto-retry failed jobs up to COUNT times
  --help                        Show this message and exit.
```

## What Agents Can Do

**Instant CI Diagnosis** - Check any commit, branch, or PR for failures and get structured output perfect for programmatic analysis.

**Real-Time Monitoring** - Use `watch --until-complete` to watch CI progress live, `watch --until-fail` for fail-fast workflows, or `watch --retry N` to automatically retry failed jobs and filter out flaky test failures.

**Targeted Debugging** - Get step-level failure details and filtered error logs without downloading massive raw logs.

**Multi-Branch Operations** - Seamlessly check CI status across different branches, PRs, and commits in automated workflows.

## License

MIT License - see [LICENSE](LICENSE) file for details.
