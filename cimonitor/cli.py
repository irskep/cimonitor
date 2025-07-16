"""Command-line interface for CI Monitor."""

import re
import sys
import time

import click

from .constants import MAX_POLLS, POLL_INTERVAL_SECONDS, RETRY_SLEEP_SECONDS
from .fetcher import GitHubCIFetcher
from .services import (
    get_ci_status,
    get_job_details_for_status,
    get_job_logs,
    retry_failed_workflows,
    watch_ci_status,
)


def parse_pr_input(pr_input):
    """Parse PR input - can be either a number or a GitHub PR URL.

    Returns:
        tuple: (owner, repo, pr_number) if URL, or (None, None, pr_number) if just number
    """
    if not pr_input:
        return None, None, None

    # Try to parse as GitHub PR URL
    url_pattern = r"https://github\.com/([^/]+)/([^/]+)/pull/(\d+)"
    match = re.match(url_pattern, str(pr_input))

    if match:
        owner, repo, pr_number = match.groups()
        return owner, repo, int(pr_number)

    # Try to parse as just a number
    try:
        pr_number = int(pr_input)
        return None, None, pr_number
    except ValueError:
        raise ValueError(
            f"Invalid PR input: '{pr_input}'. Expected either a PR number (e.g., 123) or a GitHub PR URL (e.g., https://github.com/owner/repo/pull/123)"
        )


def parse_repo_input(repo_input):
    """Parse repository input in format 'owner/repo'.

    Returns:
        tuple: (owner, repo_name) or (None, None) if not provided
    """
    if not repo_input:
        return None, None

    if "/" not in repo_input:
        raise ValueError(
            f"Invalid repository format: '{repo_input}'. Expected format: 'owner/repo'"
        )

    parts = repo_input.split("/")
    if len(parts) != 2:
        raise ValueError(
            f"Invalid repository format: '{repo_input}'. Expected format: 'owner/repo'"
        )

    owner, repo_name = parts
    if not owner or not repo_name:
        raise ValueError(
            f"Invalid repository format: '{repo_input}'. Both owner and repository name must be non-empty"
        )

    return owner, repo_name


# Shared options for targeting commits/PRs/branches
def target_options(f):
    """Decorator to add common targeting options."""
    f = click.option(
        "--repo", help="Target repository in format 'owner/repo' (defaults to current repository)"
    )(f)
    f = click.option("--branch", help="Specific branch to check (defaults to current branch)")(f)
    f = click.option("--commit", help="Specific commit SHA to check")(f)
    f = click.option(
        "--pr", "--pull-request", help="Pull request number or GitHub PR URL to check"
    )(f)
    return f


def validate_target_options(branch, commit, pr):
    """Validate mutually exclusive target options."""
    target_options = [branch, commit, pr]
    specified_options = [opt for opt in target_options if opt is not None]
    if len(specified_options) > 1:
        click.echo("Error: Please specify only one of --branch, --commit, or --pr", err=True)
        sys.exit(1)


def get_target_info(fetcher, repo, branch, commit, pr, verbose=False):
    """Get target commit SHA and description from options."""

    # Parse inputs
    repo_owner, repo_name_from_arg = parse_repo_input(repo) if repo else (None, None)
    pr_owner, pr_repo, pr_number = parse_pr_input(pr) if pr else (None, None, None)

    # Determine repository - priority: --repo arg, PR URL, current repo
    if repo_owner and repo_name_from_arg:
        owner, repo_name = repo_owner, repo_name_from_arg
    elif pr_owner and pr_repo:
        owner, repo_name = pr_owner, pr_repo
    else:
        owner, repo_name = fetcher.get_repo_info()

    if verbose:
        click.echo(f"Repository: {owner}/{repo_name}")

    # Determine target commit SHA and description
    repo_suffix = f" in {owner}/{repo_name}" if repo_owner and repo_name_from_arg else ""

    if pr_number:
        commit_sha = fetcher.get_pr_head_sha(owner, repo_name, pr_number)
        if pr_owner and pr_repo:
            target_description = f"PR #{pr_number} in {owner}/{repo_name}"
        else:
            target_description = f"PR #{pr_number}{repo_suffix}"
        if verbose:
            click.echo(f"Pull Request: #{pr_number}")
            click.echo(f"Head commit: {commit_sha}")
    elif commit:
        commit_sha = fetcher.resolve_commit_sha(owner, repo_name, commit)
        target_description = f"commit {commit[:8] if len(commit) >= 8 else commit}{repo_suffix}"
        if verbose:
            click.echo(f"Commit: {commit}")
            click.echo(f"Resolved SHA: {commit_sha}")
    elif branch:
        commit_sha = fetcher.get_branch_head_sha(owner, repo_name, branch)
        target_description = f"branch {branch}{repo_suffix}"
        if verbose:
            click.echo(f"Branch: {branch}")
            click.echo(f"Head commit: {commit_sha}")
    else:
        # Default: use current branch and commit
        current_branch, commit_sha = fetcher.get_current_branch_and_commit()
        target_description = f"current branch ({current_branch}){repo_suffix}"
        if verbose:
            click.echo(f"Branch: {current_branch}")
            click.echo(f"Latest commit: {commit_sha}")

    return owner, repo_name, commit_sha, target_description


@click.group(invoke_without_command=True)
@click.version_option()
@click.pass_context
def cli(ctx):
    """CI Monitor - Monitor GitHub CI workflows, fetch logs, and track build status."""
    if ctx.invoked_subcommand is None:
        # Default to status command when no subcommand is provided
        ctx.invoke(status)


@cli.command()
@target_options
@click.option("--verbose", "-v", is_flag=True, help="Show verbose output")
def status(repo, branch, commit, pr, verbose):
    """Show CI status for the target commit/branch/PR."""
    try:
        validate_target_options(branch, commit, pr)
        fetcher = GitHubCIFetcher()
        owner, repo_name, commit_sha, target_description = get_target_info(
            fetcher, repo, branch, commit, pr, verbose
        )

        # Get CI status using business logic
        ci_status = get_ci_status(fetcher, owner, repo_name, commit_sha, target_description)

        # Early return for no failures
        if not ci_status.has_failures:
            click.echo(f"✅ No failing CI jobs found for {target_description}!")
            return

        # Display failed jobs
        _display_failed_jobs_status(fetcher, owner, repo_name, ci_status)

    except ValueError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)
    except Exception as e:
        click.echo(f"Unexpected error: {e}", err=True)
        sys.exit(1)


@cli.command()
@target_options
@click.option("--verbose", "-v", is_flag=True, help="Show verbose output")
@click.option("--raw", is_flag=True, help="Show complete raw logs (for debugging)")
@click.option("--job-id", type=int, help="Show logs for specific job ID only")
@click.option(
    "--show-groups/--no-show-groups", default=True, help="Show available log groups/steps summary"
)
@click.option("--step-filter", help="Filter to steps matching this pattern (e.g., 'test', 'build')")
@click.option(
    "--group-filter", help="Filter to groups matching this pattern (e.g., 'Run actions', 'mise')"
)
def logs(repo, branch, commit, pr, verbose, raw, job_id, show_groups, step_filter, group_filter):
    """Show error logs for failed CI jobs."""
    try:
        validate_target_options(branch, commit, pr)
        fetcher = GitHubCIFetcher()
        owner, repo_name, commit_sha, target_description = get_target_info(
            fetcher, repo, branch, commit, pr, verbose
        )

        # Get logs using business logic
        log_result = get_job_logs(
            fetcher,
            owner,
            repo_name,
            commit_sha,
            target_description,
            job_id,
            raw,
            show_groups,
            step_filter,
            group_filter,
        )

        # Display logs based on type
        _display_job_logs(log_result)

    except ValueError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)
    except Exception as e:
        click.echo(f"Unexpected error: {e}", err=True)
        sys.exit(1)


@cli.command()
@target_options
@click.option("--verbose", "-v", is_flag=True, help="Show verbose output")
@click.option("--until-complete", is_flag=True, help="Wait until all workflows complete")
@click.option("--until-fail", is_flag=True, help="Stop on first failure")
@click.option("--retry", type=int, metavar="COUNT", help="Auto-retry failed jobs up to COUNT times")
def watch(repo, branch, commit, pr, verbose, until_complete, until_fail, retry):
    """Watch CI status with real-time updates."""
    try:
        validate_target_options(branch, commit, pr)
        _validate_watch_options(until_complete, until_fail, retry)

        fetcher = GitHubCIFetcher()
        owner, repo_name, commit_sha, target_description = get_target_info(
            fetcher, repo, branch, commit, pr, verbose
        )

        _display_watch_header(target_description, commit_sha, retry)
        _run_watch_loop(
            fetcher,
            owner,
            repo_name,
            commit_sha,
            target_description,
            until_complete,
            until_fail,
            retry,
        )

    except ValueError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)
    except Exception as e:
        click.echo(f"Unexpected error: {e}", err=True)
        sys.exit(1)


def _validate_watch_options(until_complete, until_fail, retry):
    """Validate watch command options with early returns."""
    if until_complete and until_fail:
        click.echo("Error: Cannot specify both --until-complete and --until-fail", err=True)
        sys.exit(1)

    if retry is not None and retry < 1:
        click.echo("Error: --retry must be a positive integer", err=True)
        sys.exit(1)

    if retry and (until_complete or until_fail):
        click.echo(
            "Error: Cannot specify --retry with other watch options (retry includes polling)",
            err=True,
        )
        sys.exit(1)


def _display_watch_header(target_description, commit_sha, retry):
    """Display header information for watch command."""
    click.echo(f"🔄 Watching CI status for {target_description}...")
    click.echo(f"📋 Commit: {commit_sha}")
    if retry:
        click.echo(f"🔁 Will retry failed jobs up to {retry} time(s)")
    click.echo("Press Ctrl+C to stop watching\\n")


def _run_watch_loop(
    fetcher, owner, repo_name, commit_sha, target_description, until_complete, until_fail, retry
):
    """Run the main watch polling loop."""
    poll_interval = POLL_INTERVAL_SECONDS
    max_polls = MAX_POLLS
    poll_count = 0
    retry_count = 0

    try:
        while poll_count < max_polls:
            # Get status for this poll cycle
            watch_result = watch_ci_status(
                fetcher,
                owner,
                repo_name,
                commit_sha,
                target_description,
                until_complete,
                until_fail,
                retry_count if retry else None,
            )

            # Display current status
            _display_watch_status(watch_result)

            # Handle watch result with early returns
            if not watch_result["continue_watching"]:
                _handle_watch_completion(watch_result, retry, retry_count)
                return

            if watch_result["status"] == "retry_needed" and retry and retry_count < retry:
                retry_count += 1
                click.echo(f"\\n🔁 Retrying failed jobs (attempt {retry_count}/{retry})...")

                # Retry failed runs
                retry_results = retry_failed_workflows(
                    fetcher, owner, repo_name, watch_result["failed_runs"]
                )
                _display_retry_results(retry_results)

                # Reset polling for the retry
                poll_count = 0
                time.sleep(RETRY_SLEEP_SECONDS)  # Wait longer before starting to poll again
                continue

            # Continue polling
            if poll_count < max_polls - 1:  # Don't sleep on last iteration
                click.echo(f"\\n⏰ Waiting {poll_interval}s... (poll {poll_count + 1}/{max_polls})")
                time.sleep(poll_interval)

            poll_count += 1

        click.echo("\\n⏰ Polling timeout reached")
        sys.exit(1)

    except KeyboardInterrupt:
        click.echo("\\n👋 Watching stopped by user")
        sys.exit(0)


def _display_watch_status(watch_result):
    """Display status for current watch poll."""
    if watch_result["status"] == "no_runs":
        click.echo("⏳ No workflow runs found yet...")
        return

    workflows = watch_result.get("workflows", [])
    click.echo(f"📊 Found {len(workflows)} workflow run(s):")

    for workflow in workflows:
        click.echo(
            f"  {workflow['emoji']} {workflow['name']} ({workflow['status']}) - {workflow['duration']}"
        )


def _handle_watch_completion(watch_result, retry, retry_count):
    """Handle watch completion with appropriate exit codes."""
    status = watch_result["status"]

    if status == "stop_on_failure":
        click.echo("\\n💥 Stopping on first failure!")
        sys.exit(1)
    elif status == "failed":
        if retry and retry_count >= retry:
            click.echo(f"\\n💥 Max retries ({retry}) reached. Some workflows still failed!")
        else:
            click.echo("\\n💥 Some workflows failed!")
        sys.exit(1)
    elif status == "success":
        click.echo("\\n🎉 All workflows completed successfully!")
        sys.exit(0)


def _display_retry_results(retry_results):
    """Display results of retry attempts."""
    for run_id, success in retry_results.items():
        if success:
            click.echo(f"  ✅ Restarted failed jobs in run {run_id}")
        else:
            click.echo(f"  ❌ Failed to restart jobs in run {run_id}")


def _display_job_logs(log_result):
    """Display job logs based on result type."""
    log_type = log_result["type"]

    if log_type == "specific_job":
        _display_specific_job_logs(log_result)
    elif log_type == "raw_logs":
        _display_raw_logs(log_result)
    elif log_type == "filtered_logs":
        _display_filtered_logs(log_result)


def _display_specific_job_logs(log_result):
    """Display logs for a specific job ID."""
    job_info = log_result["job_info"]
    logs = log_result["logs"]

    click.echo(f"📄 Raw logs for job ID {job_info.get('id', 'Unknown')}:")
    click.echo("=" * 80)
    click.echo(f"Job: {job_info.get('name', 'Unknown')}")
    click.echo(f"Status: {job_info.get('conclusion', 'unknown')}")
    click.echo(f"URL: {job_info.get('html_url', '')}")
    click.echo("-" * 80)
    click.echo(logs)


def _display_raw_logs(log_result):
    """Display raw logs for all failed jobs."""
    failed_jobs = log_result["failed_jobs"]

    if not log_result["has_failures"]:
        click.echo("✅ No failing jobs found for this commit!")
        return

    click.echo(f"📄 Raw logs for {len(failed_jobs)} failed job(s):")
    click.echo()

    for i, job_log in enumerate(failed_jobs, 1):
        job = job_log["job"]
        logs = job_log["logs"]
        job_name = job.get("name", "Unknown")
        job_id = job.get("id")

        click.echo(f"{'=' * 80}")
        click.echo(f"RAW LOGS #{i}: {job_name} (ID: {job_id})")
        click.echo(f"{'=' * 80}")
        click.echo(logs)
        click.echo("\\n" + "=" * 80 + "\\n")


def _display_filtered_logs(log_result):
    """Display filtered error logs with group information."""
    target_description = log_result["target_description"]
    failed_jobs = log_result["failed_jobs"]
    show_groups = log_result.get("show_groups", True)
    groups = log_result.get("groups", [])
    filters = log_result.get("filters", {})

    if not log_result["has_failures"]:
        click.echo(f"✅ No failing CI jobs found for {target_description}!")
        return

    # Show group summary and step status at the top
    if show_groups and groups:
        click.echo(f"📋 Available log groups in {target_description}:")
        click.echo("=" * 60)

        # Show groups with nesting
        _display_groups_with_nesting(groups)

        # Show step status summary
        all_step_status = {}
        for job_log in failed_jobs:
            if "step_status" in job_log:
                all_step_status.update(job_log["step_status"])

        if all_step_status:
            _display_step_status_summary(all_step_status)

        # Show active filters
        if filters.get("step_filter") or filters.get("group_filter"):
            click.echo("🔍 Active Filters:")
            if filters.get("step_filter"):
                click.echo(f"  • Step filter: '{filters['step_filter']}'")
            if filters.get("group_filter"):
                click.echo(f"  • Group filter: '{filters['group_filter']}'")

        click.echo("=" * 60)
        click.echo("💡 Use --step-filter or --group-filter to focus on specific sections")
        click.echo('💡 Example: --group-filter="mise run test"')
        click.echo("💡 Use --show-groups=false to hide this summary")
        click.echo()

    click.echo(f"📄 Error logs for {len(failed_jobs)} failing job(s):")
    click.echo()

    for i, job_log in enumerate(failed_jobs, 1):
        click.echo(f"{'=' * 60}")
        click.echo(f"LOGS #{i}: {job_log['name']}")
        click.echo(f"{'=' * 60}")

        if job_log.get("error"):
            click.echo(job_log["error"])
        elif job_log["step_logs"]:
            for step_name, step_log in job_log["step_logs"].items():
                click.echo(f"\\n📄 Logs for Failed Step: {step_name}")
                click.echo("-" * 50)
                if step_log.strip():
                    click.echo(step_log)
                else:
                    click.echo("No logs found for this step")
        else:
            click.echo("Could not retrieve job logs")

        click.echo()


def _display_groups_with_nesting(groups):
    """Display groups with proper nesting indentation."""
    step_groups = [g for g in groups if g["type"] == "step"]
    setup_groups = [g for g in groups if g["type"] == "setup"]

    if setup_groups:
        click.echo("🔧 Setup/System Groups:")
        for group in setup_groups:
            indent = "  " + "  " * group.get("nesting_level", 0)
            click.echo(f"{indent}• {group['name']} (line {group['line_number']})")

    if step_groups:
        click.echo("🏃 Step Groups:")
        for group in step_groups:
            indent = "  " + "  " * group.get("nesting_level", 0)
            click.echo(f"{indent}• {group['name']} (line {group['line_number']})")


def _display_step_status_summary(step_status):
    """Display deterministic step status summary."""
    click.echo("📊 Step Status Summary:")

    success_steps = []
    failed_steps = []
    other_steps = []

    for step_name, status in step_status.items():
        if status["conclusion"] == "success":
            success_steps.append(step_name)
        elif status["conclusion"] == "failure":
            failed_steps.append(step_name)
        else:
            other_steps.append((step_name, status["conclusion"]))

    if success_steps:
        click.echo(f"  ✅ {len(success_steps)} successful steps")

    if failed_steps:
        click.echo(f"  ❌ {len(failed_steps)} failed steps:")
        for step in failed_steps:
            click.echo(f"    • {step}")

    if other_steps:
        for step_name, conclusion in other_steps:
            icon = "⏭️" if conclusion == "skipped" else "🚫" if conclusion == "cancelled" else "❓"
            click.echo(f"  {icon} {step_name} ({conclusion})")


def _display_failed_jobs_status(fetcher, owner, repo_name, ci_status):
    """Display failed jobs status with step details."""
    click.echo(
        f"❌ Found {len(ci_status.failed_check_runs)} failing CI job(s) for {ci_status.target_description}:"
    )
    click.echo()

    for i, check_run in enumerate(ci_status.failed_check_runs, 1):
        name = check_run.get("name", "Unknown Job")
        conclusion = check_run.get("conclusion", "unknown")
        html_url = check_run.get("html_url", "")

        click.echo(f"{'=' * 60}")
        click.echo(f"FAILED JOB #{i}: {name}")
        click.echo(f"Status: {conclusion}")
        click.echo(f"URL: {html_url}")
        click.echo(f"{'=' * 60}")

        # Get detailed job information
        job_details = get_job_details_for_status(fetcher, owner, repo_name, check_run)

        if not job_details:
            click.echo("Cannot retrieve detailed information for this check run type")
            click.echo()
            continue

        if job_details.failed_steps:
            click.echo(f"\\n📋 Failed Steps in {job_details.name}:")
            for step in job_details.failed_steps:
                click.echo(f"  ❌ Step {step.number}: {step.name} (took {step.duration})")
            click.echo()
        else:
            click.echo("Cannot retrieve detailed information for this check run type")
            click.echo()


def main():
    """Entry point for the CLI."""
    cli()


if __name__ == "__main__":
    main()
