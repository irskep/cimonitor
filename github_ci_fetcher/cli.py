"""Command-line interface for GitHub CI Fetcher."""

import sys
import time
from datetime import datetime

import click

from .fetcher import GitHubCIFetcher
from .log_parser import LogParser


@click.command()
@click.option(
    "--branch", default=None, help="Specific branch to check (defaults to current branch)"
)
@click.option("--commit", help="Specific commit SHA to check")
@click.option("--pr", "--pull-request", type=int, help="Pull request number to check")
@click.option("--verbose", "-v", is_flag=True, help="Show verbose output")
@click.option("--show-logs", is_flag=True, help="Show detailed error logs for failed steps only")
@click.option(
    "--raw-logs", is_flag=True, help="Show complete raw logs for all failed jobs (for debugging)"
)
@click.option("--job-id", type=int, help="Show raw logs for specific job ID only")
@click.option("--poll", is_flag=True, help="Poll CI status until all workflows complete")
@click.option("--poll-until-failure", is_flag=True, help="Poll CI status until first failure or all complete")
def main(
    branch: str | None,
    commit: str | None,
    pr: int | None,
    verbose: bool,
    show_logs: bool,
    raw_logs: bool,
    job_id: int | None,
    poll: bool,
    poll_until_failure: bool,
):
    """Fetch GitHub CI logs for failing builds.

    Target options (--branch, --commit, --pr) are mutually exclusive.
    If none specified, uses current branch and latest commit.
    """

    try:
        fetcher = GitHubCIFetcher()

        # Get repository info
        owner, repo_name = fetcher.get_repo_info()
        if verbose:
            click.echo(f"Repository: {owner}/{repo_name}")

        # Validate that only one target option is specified
        target_options = [branch, commit, pr]
        specified_options = [opt for opt in target_options if opt is not None]
        if len(specified_options) > 1:
            click.echo("Error: Please specify only one of --branch, --commit, or --pr", err=True)
            sys.exit(1)

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

        # Handle polling options
        if poll or poll_until_failure:
            if poll and poll_until_failure:
                click.echo("Error: Cannot specify both --poll and --poll-until-failure", err=True)
                sys.exit(1)
                
            click.echo(f"🔄 Polling CI status for {target_description}...")
            click.echo(f"📋 Commit: {commit_sha}")
            click.echo("Press Ctrl+C to stop polling\n")
            
            poll_interval = 10  # seconds
            max_polls = 120     # 20 minutes total
            poll_count = 0
            
            try:
                while poll_count < max_polls:
                    workflow_runs = fetcher.get_workflow_runs_for_commit(owner, repo_name, commit_sha)
                    
                    if not workflow_runs:
                        click.echo("⏳ No workflow runs found yet...")
                    else:
                        click.echo(f"📊 Found {len(workflow_runs)} workflow run(s):")
                        
                        all_completed = True
                        any_failed = False
                        
                        for run in workflow_runs:
                            name = run.get("name", "Unknown Workflow")
                            status = run.get("status", "unknown")
                            conclusion = run.get("conclusion")
                            created_at = run.get("created_at", "")
                            updated_at = run.get("updated_at", "")
                            
                            # Calculate duration
                            try:
                                start = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
                                if updated_at:
                                    end = datetime.fromisoformat(updated_at.replace("Z", "+00:00"))
                                else:
                                    end = datetime.now(start.tzinfo)
                                duration = end - start
                                duration_str = f"{int(duration.total_seconds())}s"
                            except:
                                duration_str = "unknown"
                            
                            # Status emoji and tracking
                            if status == "completed":
                                if conclusion == "success":
                                    emoji = "✅"
                                elif conclusion == "failure":
                                    emoji = "❌"
                                    any_failed = True
                                elif conclusion == "cancelled":
                                    emoji = "🚫"
                                    any_failed = True
                                else:
                                    emoji = "⚠️"
                                    any_failed = True
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
                        if poll_until_failure and any_failed:
                            click.echo("\n💥 Stopping on first failure!")
                            sys.exit(1)
                        
                        if all_completed:
                            if any_failed:
                                click.echo("\n💥 Some workflows failed!")
                                sys.exit(1)
                            else:
                                click.echo("\n🎉 All workflows completed successfully!")
                                sys.exit(0)
                    
                    if poll_count < max_polls - 1:  # Don't sleep on last iteration
                        click.echo(f"\n⏰ Waiting {poll_interval}s... (poll {poll_count + 1}/{max_polls})")
                        time.sleep(poll_interval)
                    
                    poll_count += 1
                
                click.echo("\n⏰ Polling timeout reached")
                sys.exit(1)
                
            except KeyboardInterrupt:
                click.echo("\n👋 Polling stopped by user")
                sys.exit(0)

        # Handle specific job ID request
        if job_id:
            click.echo(f"📄 Raw logs for job ID {job_id}:")
            click.echo("=" * 80)
            job_info = fetcher.get_job_by_id(owner, repo_name, job_id)
            click.echo(f"Job: {job_info.get('name', 'Unknown')}")
            click.echo(f"Status: {job_info.get('conclusion', 'unknown')}")
            click.echo(f"URL: {job_info.get('html_url', '')}")
            click.echo("-" * 80)
            logs = fetcher.get_job_logs(owner, repo_name, job_id)
            click.echo(logs)
            return

        # Handle raw logs for all failed jobs
        if raw_logs:
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
                    logs = fetcher.get_job_logs(owner, repo_name, job_id)
                    click.echo(logs)
                else:
                    click.echo("No job ID available")

                click.echo("\n" + "=" * 80 + "\n")
            return

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
                            job_id = job.get("id")

                            # Show failed steps summary first
                            failed_steps = fetcher.get_failed_steps(job)

                            if failed_steps:
                                click.echo(f"\n📋 Failed Steps in {job_name}:")
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

                            # Only show detailed logs if requested
                            if show_logs:
                                if job_id:
                                    logs = fetcher.get_job_logs(owner, repo_name, job_id)

                                    # Extract logs for just the failed steps
                                    step_logs = LogParser.extract_step_logs(logs, failed_steps)

                                    if step_logs:
                                        for step_name, step_log in step_logs.items():
                                            click.echo(f"\n📄 Logs for Failed Step: {step_name}")
                                            click.echo("-" * 50)

                                            # Show only the step-specific logs
                                            if step_log.strip():
                                                # Still filter for error-related content within the step
                                                shown_lines = LogParser.filter_error_lines(step_log)

                                                if shown_lines:
                                                    for line in shown_lines:
                                                        if line.strip():
                                                            click.echo(line)
                                                else:
                                                    # Fallback to last few lines of the step
                                                    step_lines = step_log.split("\n")
                                                    for line in step_lines[-10:]:
                                                        if line.strip():
                                                            click.echo(line)
                                            else:
                                                click.echo("No logs found for this step")
                                    else:
                                        click.echo(
                                            f"\n📄 Could not extract step-specific logs for {job_name}"
                                        )
                                        click.echo("💡 This might be due to log format differences")
                                else:
                                    click.echo("Could not retrieve job logs")
                            else:
                                click.echo(
                                    "💡 Use --show-logs to see detailed error logs for failed steps only"
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
