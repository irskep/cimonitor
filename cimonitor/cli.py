"""Command-line interface for CI Monitor."""

import sys
import time
from datetime import datetime

import click

from .fetcher import GitHubCIFetcher
from .log_parser import LogParser


# Shared options for targeting commits/PRs/branches
def target_options(f):
    """Decorator to add common targeting options."""
    f = click.option("--branch", help="Specific branch to check (defaults to current branch)")(f)
    f = click.option("--commit", help="Specific commit SHA to check")(f)
    f = click.option("--pr", "--pull-request", type=int, help="Pull request number to check")(f)
    return f


def validate_target_options(branch, commit, pr):
    """Validate mutually exclusive target options."""
    target_options = [branch, commit, pr]
    specified_options = [opt for opt in target_options if opt is not None]
    if len(specified_options) > 1:
        click.echo("Error: Please specify only one of --branch, --commit, or --pr", err=True)
        sys.exit(1)


def get_target_info(fetcher, branch, commit, pr, verbose=False):
    """Get target commit SHA and description from options."""

    # Get repository info
    owner, repo_name = fetcher.get_repo_info()
    if verbose:
        click.echo(f"Repository: {owner}/{repo_name}")

    # Determine target commit SHA and description
    if pr:
        commit_sha = fetcher.get_pr_head_sha(owner, repo_name, pr)
        target_description = f"PR #{pr}"
        if verbose:
            click.echo(f"Pull Request: #{pr}")
            click.echo(f"Head commit: {commit_sha}")
    elif commit:
        commit_sha = fetcher.resolve_commit_sha(owner, repo_name, commit)
        target_description = f"commit {commit[:8] if len(commit) >= 8 else commit}"
        if verbose:
            click.echo(f"Commit: {commit}")
            click.echo(f"Resolved SHA: {commit_sha}")
    elif branch:
        commit_sha = fetcher.get_branch_head_sha(owner, repo_name, branch)
        target_description = f"branch {branch}"
        if verbose:
            click.echo(f"Branch: {branch}")
            click.echo(f"Head commit: {commit_sha}")
    else:
        # Default: use current branch and commit
        current_branch, commit_sha = fetcher.get_current_branch_and_commit()
        target_description = f"current branch ({current_branch})"
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
def status(branch, commit, pr, verbose):
    """Show CI status for the target commit/branch/PR."""
    try:
        # Validate options first, before any API calls
        validate_target_options(branch, commit, pr)

        fetcher = GitHubCIFetcher()
        owner, repo_name, commit_sha, target_description = get_target_info(
            fetcher, branch, commit, pr, verbose
        )

        # Find failed jobs for the target commit
        failed_check_runs = fetcher.find_failed_jobs_in_latest_run(owner, repo_name, commit_sha)

        if not failed_check_runs:
            click.echo(f"✅ No failing CI jobs found for {target_description}!")
            return

        click.echo(f"❌ Found {len(failed_check_runs)} failing CI job(s) for {target_description}:")
        click.echo()

        for i, check_run in enumerate(failed_check_runs, 1):
            name = check_run.get("name", "Unknown Job")
            conclusion = check_run.get("conclusion", "unknown")
            html_url = check_run.get("html_url", "")

            click.echo(f"{'=' * 60}")
            click.echo(f"FAILED JOB #{i}: {name}")
            click.echo(f"Status: {conclusion}")
            click.echo(f"URL: {html_url}")
            click.echo(f"{'=' * 60}")

            # Try to get workflow run info and step details
            if "actions/runs" in html_url:
                try:
                    # Extract run ID from URL
                    run_id = html_url.split("/runs/")[1].split("/")[0]
                    jobs = fetcher.get_workflow_jobs(owner, repo_name, int(run_id))

                    for job in jobs:
                        if job.get("conclusion") == "failure":
                            job_name = job.get("name", "Unknown")

                            # Show failed steps summary
                            failed_steps = fetcher.get_failed_steps(job)

                            if failed_steps:
                                click.echo(f"\\n📋 Failed Steps in {job_name}:")
                                for step in failed_steps:
                                    step_name = step["name"]
                                    step_num = step["number"]
                                    duration = "Unknown"

                                    if step["started_at"] and step["completed_at"]:
                                        start = datetime.fromisoformat(
                                            step["started_at"].replace("Z", "+00:00")
                                        )
                                        end = datetime.fromisoformat(
                                            step["completed_at"].replace("Z", "+00:00")
                                        )
                                        duration = f"{(end - start).total_seconds():.1f}s"

                                    click.echo(
                                        f"  ❌ Step {step_num}: {step_name} (took {duration})"
                                    )

                            click.echo()
                except Exception as e:
                    click.echo(f"Error processing job details: {e}")
            else:
                click.echo("Cannot retrieve detailed information for this check run type")

            click.echo()

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
def logs(branch, commit, pr, verbose, raw, job_id):
    """Show error logs for failed CI jobs."""
    try:
        # Validate options first, before any API calls
        validate_target_options(branch, commit, pr)

        fetcher = GitHubCIFetcher()
        owner, repo_name, commit_sha, target_description = get_target_info(
            fetcher, branch, commit, pr, verbose
        )

        # Handle specific job ID request
        if job_id:
            click.echo(f"📄 Raw logs for job ID {job_id}:")
            click.echo("=" * 80)
            job_info = fetcher.get_job_by_id(owner, repo_name, job_id)
            click.echo(f"Job: {job_info.get('name', 'Unknown')}")
            click.echo(f"Status: {job_info.get('conclusion', 'unknown')}")
            click.echo(f"URL: {job_info.get('html_url', '')}")
            click.echo("-" * 80)
            logs_content = fetcher.get_job_logs(owner, repo_name, job_id)
            click.echo(logs_content)
            return

        # Handle raw logs for all failed jobs
        if raw:
            all_jobs = fetcher.get_all_jobs_for_commit(owner, repo_name, commit_sha)
            failed_jobs = [job for job in all_jobs if job.get("conclusion") == "failure"]

            if not failed_jobs:
                click.echo("✅ No failing jobs found for this commit!")
                return

            click.echo(f"📄 Raw logs for {len(failed_jobs)} failed job(s):")
            click.echo()

            for i, job in enumerate(failed_jobs, 1):
                job_name = job.get("name", "Unknown")
                job_id = job.get("id")

                click.echo(f"{'=' * 80}")
                click.echo(f"RAW LOGS #{i}: {job_name} (ID: {job_id})")
                click.echo(f"{'=' * 80}")

                if job_id:
                    logs_content = fetcher.get_job_logs(owner, repo_name, job_id)
                    click.echo(logs_content)
                else:
                    click.echo("No job ID available")

                click.echo("\\n" + "=" * 80 + "\\n")
            return

        # Default: show filtered error logs
        failed_check_runs = fetcher.find_failed_jobs_in_latest_run(owner, repo_name, commit_sha)

        if not failed_check_runs:
            click.echo(f"✅ No failing CI jobs found for {target_description}!")
            return

        click.echo(
            f"📄 Error logs for {len(failed_check_runs)} failing job(s) in {target_description}:"
        )
        click.echo()

        for i, check_run in enumerate(failed_check_runs, 1):
            name = check_run.get("name", "Unknown Job")
            html_url = check_run.get("html_url", "")

            click.echo(f"{'=' * 60}")
            click.echo(f"LOGS #{i}: {name}")
            click.echo(f"{'=' * 60}")

            # Try to get workflow run info and step details
            if "actions/runs" in html_url:
                try:
                    # Extract run ID from URL
                    run_id = html_url.split("/runs/")[1].split("/")[0]
                    jobs = fetcher.get_workflow_jobs(owner, repo_name, int(run_id))

                    for job in jobs:
                        if job.get("conclusion") == "failure":
                            job_name = job.get("name", "Unknown")
                            job_id = job.get("id")

                            # Get failed steps
                            failed_steps = fetcher.get_failed_steps(job)

                            if job_id and failed_steps:
                                logs_content = fetcher.get_job_logs(owner, repo_name, job_id)

                                # Extract logs for just the failed steps
                                step_logs = LogParser.extract_step_logs(logs_content, failed_steps)

                                if step_logs:
                                    for step_name, step_log in step_logs.items():
                                        click.echo(f"\\n📄 Logs for Failed Step: {step_name}")
                                        click.echo("-" * 50)

                                        # Show only the step-specific logs
                                        if step_log.strip():
                                            # Filter for error-related content within the step
                                            shown_lines = LogParser.filter_error_lines(step_log)

                                            if shown_lines:
                                                for line in shown_lines:
                                                    if line.strip():
                                                        click.echo(line)
                                            else:
                                                # Fallback to last few lines of the step
                                                step_lines = step_log.split("\\n")
                                                for line in step_lines[-10:]:
                                                    if line.strip():
                                                        click.echo(line)
                                        else:
                                            click.echo("No logs found for this step")
                                else:
                                    click.echo(
                                        f"\\n📄 Could not extract step-specific logs for {job_name}"
                                    )
                                    click.echo("💡 This might be due to log format differences")
                            else:
                                click.echo("Could not retrieve job logs")

                            click.echo()

                except Exception as e:
                    click.echo(f"Error processing job details: {e}")
            else:
                click.echo("Cannot retrieve detailed information for this check run type")

            click.echo()

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
def watch(branch, commit, pr, verbose, until_complete, until_fail, retry):
    """Watch CI status with real-time updates."""
    try:
        # Validate options first, before any API calls
        validate_target_options(branch, commit, pr)

        # Validate watch options
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

        fetcher = GitHubCIFetcher()
        owner, repo_name, commit_sha, target_description = get_target_info(
            fetcher, branch, commit, pr, verbose
        )

        click.echo(f"🔄 Watching CI status for {target_description}...")
        click.echo(f"📋 Commit: {commit_sha}")
        if retry:
            click.echo(f"🔁 Will retry failed jobs up to {retry} time(s)")
        click.echo("Press Ctrl+C to stop watching\\n")

        poll_interval = 10  # seconds
        max_polls = 120  # 20 minutes total
        poll_count = 0
        retry_count = 0

        try:
            while poll_count < max_polls:
                workflow_runs = fetcher.get_workflow_runs_for_commit(owner, repo_name, commit_sha)

                if not workflow_runs:
                    click.echo("⏳ No workflow runs found yet...")
                else:
                    click.echo(f"📊 Found {len(workflow_runs)} workflow run(s):")

                    all_completed = True
                    any_failed = False
                    failed_runs = []

                    for run in workflow_runs:
                        name = run.get("name", "Unknown Workflow")
                        status = run.get("status", "unknown")
                        conclusion = run.get("conclusion")
                        created_at = run.get("created_at", "")
                        updated_at = run.get("updated_at", "")
                        run_id = run.get("id")

                        # Calculate duration
                        try:
                            start = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
                            if updated_at:
                                end = datetime.fromisoformat(updated_at.replace("Z", "+00:00"))
                            else:
                                end = datetime.now(start.tzinfo)
                            duration = end - start
                            duration_str = f"{int(duration.total_seconds())}s"
                        except Exception:
                            duration_str = "unknown"

                        # Status emoji and tracking
                        if status == "completed":
                            if conclusion == "success":
                                emoji = "✅"
                            elif conclusion == "failure":
                                emoji = "❌"
                                any_failed = True
                                failed_runs.append(run_id)
                            elif conclusion == "cancelled":
                                emoji = "🚫"
                                any_failed = True
                                failed_runs.append(run_id)
                            else:
                                emoji = "⚠️"
                                any_failed = True
                                failed_runs.append(run_id)
                        elif status == "in_progress":
                            emoji = "🔄"
                            all_completed = False
                        elif status == "queued":
                            emoji = "⏳"
                            all_completed = False
                        else:
                            emoji = "❓"
                            all_completed = False

                        click.echo(f"  {emoji} {name} ({status}) - {duration_str}")

                    # Check stopping conditions
                    if until_fail and any_failed:
                        click.echo("\\n💥 Stopping on first failure!")
                        sys.exit(1)

                    if all_completed:
                        if any_failed and retry and retry_count < retry:
                            retry_count += 1
                            click.echo(
                                f"\\n🔁 Retrying failed jobs (attempt {retry_count}/{retry})..."
                            )

                            # Retry failed runs
                            for run_id in failed_runs:
                                if fetcher.rerun_failed_jobs(owner, repo_name, run_id):
                                    click.echo(f"  ✅ Restarted failed jobs in run {run_id}")
                                else:
                                    click.echo(f"  ❌ Failed to restart jobs in run {run_id}")

                            # Reset polling for the retry
                            poll_count = 0
                            time.sleep(30)  # Wait a bit longer before starting to poll again
                            continue
                        elif any_failed:
                            if retry and retry_count >= retry:
                                click.echo(
                                    f"\\n💥 Max retries ({retry}) reached. Some workflows still failed!"
                                )
                            else:
                                click.echo("\\n💥 Some workflows failed!")
                            sys.exit(1)
                        else:
                            click.echo("\\n🎉 All workflows completed successfully!")
                            sys.exit(0)

                if poll_count < max_polls - 1:  # Don't sleep on last iteration
                    click.echo(
                        f"\\n⏰ Waiting {poll_interval}s... (poll {poll_count + 1}/{max_polls})"
                    )
                    time.sleep(poll_interval)

                poll_count += 1

            click.echo("\\n⏰ Polling timeout reached")
            sys.exit(1)

        except KeyboardInterrupt:
            click.echo("\\n👋 Watching stopped by user")
            sys.exit(0)

    except ValueError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)
    except Exception as e:
        click.echo(f"Unexpected error: {e}", err=True)
        sys.exit(1)


def main():
    """Entry point for the CLI."""
    cli()


if __name__ == "__main__":
    main()
