"""Business logic services for CI Monitor.

This module contains the core business logic separated from presentation concerns.
All functions use early-return patterns to avoid deep nesting.
"""

from datetime import datetime
from typing import Any
from urllib.parse import urlparse

from .constants import FALLBACK_LOG_LINES
from .fetcher import GitHubCIFetcher
from .log_parser import LogParser


class CIStatusResult:
    """Result object for CI status operations."""

    def __init__(self, failed_check_runs: list[dict[str, Any]], target_description: str):
        self.failed_check_runs = failed_check_runs
        self.target_description = target_description
        self.has_failures = len(failed_check_runs) > 0


class WorkflowStepInfo:
    """Information about a workflow step."""

    def __init__(self, name: str, number: int, duration: str = "Unknown"):
        self.name = name
        self.number = number
        self.duration = duration


class JobDetails:
    """Detailed information about a failed job."""

    def __init__(self, name: str, html_url: str, conclusion: str):
        self.name = name
        self.html_url = html_url
        self.conclusion = conclusion
        self.failed_steps: list[WorkflowStepInfo] = []
        self.step_logs: dict[str, str] = {}


def get_ci_status(
    fetcher: GitHubCIFetcher, owner: str, repo_name: str, commit_sha: str, target_description: str
) -> CIStatusResult:
    """Get CI status for a commit with detailed job information.

    Args:
        fetcher: GitHub CI fetcher instance
        owner: Repository owner
        repo_name: Repository name
        commit_sha: Target commit SHA
        target_description: Human-readable description of target

    Returns:
        CIStatusResult with failed jobs and details
    """
    failed_check_runs = fetcher.find_failed_jobs_in_latest_run(owner, repo_name, commit_sha)
    return CIStatusResult(failed_check_runs, target_description)


def get_job_details_for_status(
    fetcher: GitHubCIFetcher, owner: str, repo_name: str, check_run: dict[str, Any]
) -> JobDetails | None:
    """Get detailed information for a failed job for status display.

    Args:
        fetcher: GitHub CI fetcher instance
        owner: Repository owner
        repo_name: Repository name
        check_run: Check run data from GitHub API

    Returns:
        JobDetails object or None if details cannot be retrieved
    """
    name = check_run.get("name", "Unknown Job")
    conclusion = check_run.get("conclusion", "unknown")
    html_url = check_run.get("html_url", "")

    job_details = JobDetails(name, html_url, conclusion)

    # Early return if not a workflow run
    if "actions/runs" not in html_url:
        return job_details

    try:
        run_id = _extract_run_id_from_url(html_url)
        if not run_id:
            return job_details

        jobs = fetcher.get_workflow_jobs(owner, repo_name, run_id)
        _add_failed_steps_to_job_details(fetcher, jobs, job_details)

    except (ValueError, KeyError, TypeError):
        # Return basic job details if we can't parse the step information
        # This can happen with unexpected API response format or missing data
        pass
    except Exception:
        # Log unexpected errors but don't crash - return basic job details
        # TODO: Add proper logging here
        pass

    return job_details


def get_job_logs(
    fetcher: GitHubCIFetcher,
    owner: str,
    repo_name: str,
    commit_sha: str,
    target_description: str,
    job_id: int | None = None,
    raw: bool = False,
    show_groups: bool = True,
    step_filter: str | None = None,
    group_filter: str | None = None,
) -> dict[str, Any]:
    """Get logs for failed CI jobs.

    Args:
        fetcher: GitHub CI fetcher instance
        owner: Repository owner
        repo_name: Repository name
        commit_sha: Target commit SHA
        target_description: Human-readable description of target
        job_id: Specific job ID to get logs for (optional)
        raw: Whether to return raw logs
        show_groups: Whether to show only group summary
        step_filter: Filter pattern for steps
        group_filter: Filter pattern for groups

    Returns:
        Dictionary with log information and metadata
    """
    # Handle specific job ID request
    if job_id:
        return _get_specific_job_logs(
            fetcher, owner, repo_name, job_id, show_groups, step_filter, group_filter
        )

    # Handle raw logs request
    if raw:
        return _get_raw_logs_for_commit(fetcher, owner, repo_name, commit_sha)

    # Default: return filtered error logs with group analysis
    return _get_filtered_error_logs(
        fetcher,
        owner,
        repo_name,
        commit_sha,
        target_description,
        show_groups,
        step_filter,
        group_filter,
    )


def watch_ci_status(
    fetcher: GitHubCIFetcher,
    owner: str,
    repo_name: str,
    commit_sha: str,
    target_description: str,
    until_complete: bool = False,
    until_fail: bool = False,
    retry_count: int | None = None,
) -> dict[str, Any]:
    """Watch CI status for a single poll cycle.

    Args:
        fetcher: GitHub CI fetcher instance
        owner: Repository owner
        repo_name: Repository name
        commit_sha: Target commit SHA
        target_description: Human-readable description of target
        until_complete: Whether to wait until completion
        until_fail: Whether to stop on first failure
        retry_count: Number of retries remaining

    Returns:
        Dictionary with workflow status and recommended actions
    """
    workflow_runs = fetcher.get_workflow_runs_for_commit(owner, repo_name, commit_sha)

    if not workflow_runs:
        return {
            "status": "no_runs",
            "message": "No workflow runs found yet",
            "continue_watching": True,
        }

    status_summary = _analyze_workflow_runs(workflow_runs)

    # Check stopping conditions with early returns
    if until_fail and status_summary["any_failed"]:
        return {
            "status": "stop_on_failure",
            "workflows": status_summary["workflows"],
            "continue_watching": False,
        }

    if not status_summary["all_completed"]:
        return {
            "status": "in_progress",
            "workflows": status_summary["workflows"],
            "continue_watching": True,
        }

    # All completed - check if we need to retry
    if status_summary["any_failed"] and retry_count and retry_count > 0:
        return {
            "status": "retry_needed",
            "workflows": status_summary["workflows"],
            "failed_runs": status_summary["failed_runs"],
            "continue_watching": True,
        }

    if status_summary["any_failed"]:
        return {
            "status": "failed",
            "workflows": status_summary["workflows"],
            "continue_watching": False,
        }

    return {
        "status": "success",
        "workflows": status_summary["workflows"],
        "continue_watching": False,
    }


def retry_failed_workflows(
    fetcher: GitHubCIFetcher, owner: str, repo_name: str, failed_run_ids: list[int]
) -> dict[int, bool]:
    """Retry failed workflow runs.

    Args:
        fetcher: GitHub CI fetcher instance
        owner: Repository owner
        repo_name: Repository name
        failed_run_ids: List of run IDs to retry

    Returns:
        Dictionary mapping run_id to success status
    """
    results = {}
    for run_id in failed_run_ids:
        results[run_id] = fetcher.rerun_failed_jobs(owner, repo_name, run_id)
    return results


# Private helper functions


def _extract_run_id_from_url(html_url: str) -> int | None:
    """Extract run ID from GitHub Actions URL using proper URL parsing.

    Args:
        html_url: GitHub Actions URL like 'https://github.com/owner/repo/actions/runs/123456/jobs/789'

    Returns:
        The run ID (123456) or None if URL is invalid or doesn't contain a run ID
    """
    if not html_url or "actions/runs" not in html_url:
        return None

    try:
        parsed_url = urlparse(html_url)
        if not parsed_url.path:
            return None

        # Split path into components and find 'runs' segment
        path_parts = [part for part in parsed_url.path.split("/") if part]

        # Look for pattern: [..., 'actions', 'runs', '<run_id>', ...]
        for i, part in enumerate(path_parts):
            if (
                part == "runs"
                and i > 0
                and path_parts[i - 1] == "actions"
                and i + 1 < len(path_parts)
            ):
                run_id_str = path_parts[i + 1]
                if run_id_str.isdigit():
                    return int(run_id_str)
                break

        return None
    except (ValueError, AttributeError):
        return None


def _add_failed_steps_to_job_details(
    fetcher: GitHubCIFetcher, jobs: list[dict[str, Any]], job_details: JobDetails
) -> None:
    """Add failed step information to job details."""
    for job in jobs:
        if job.get("conclusion") != "failure":
            continue

        failed_steps = fetcher.get_failed_steps(job)
        if not failed_steps:
            continue

        for step in failed_steps:
            duration = _calculate_step_duration(step)
            step_info = WorkflowStepInfo(step["name"], step["number"], duration)
            job_details.failed_steps.append(step_info)


def _calculate_step_duration(step: dict[str, Any]) -> str:
    """Calculate duration for a workflow step."""
    if not step.get("started_at") or not step.get("completed_at"):
        return "Unknown"

    try:
        start = datetime.fromisoformat(step["started_at"].replace("Z", "+00:00"))
        end = datetime.fromisoformat(step["completed_at"].replace("Z", "+00:00"))
        return f"{(end - start).total_seconds():.1f}s"
    except (ValueError, TypeError):
        # Handle invalid timestamp format or missing data
        return "Unknown"
    except Exception:
        # Handle other unexpected errors in datetime calculation
        # TODO: Add proper logging here
        return "Unknown"


def _get_specific_job_logs(
    fetcher: GitHubCIFetcher,
    owner: str,
    repo_name: str,
    job_id: int,
    show_groups: bool = True,
    step_filter: str | None = None,
    group_filter: str | None = None,
) -> dict[str, Any]:
    """Get logs for a specific job ID."""
    job_info = fetcher.get_job_by_id(owner, repo_name, job_id)
    logs_content = fetcher.get_job_logs(owner, repo_name, job_id)

    # Add group analysis
    groups = LogParser.parse_log_groups(logs_content)

    # Apply filters
    filtered_groups = _apply_group_filters(groups, step_filter, group_filter)

    return {
        "type": "specific_job",
        "job_info": job_info,
        "logs": logs_content,
        "groups": filtered_groups,
        "show_groups": show_groups,
        "filters": {"step_filter": step_filter, "group_filter": group_filter},
    }


def _get_raw_logs_for_commit(
    fetcher: GitHubCIFetcher, owner: str, repo_name: str, commit_sha: str
) -> dict[str, Any]:
    """Get raw logs for all failed jobs in a commit."""
    all_jobs = fetcher.get_all_jobs_for_commit(owner, repo_name, commit_sha)
    failed_jobs = [job for job in all_jobs if job.get("conclusion") == "failure"]

    if not failed_jobs:
        return {"type": "raw_logs", "failed_jobs": [], "has_failures": False}

    # Fetch logs for each failed job
    job_logs = []
    for job in failed_jobs:
        job_id = job.get("id")
        if not job_id:
            continue

        logs_content = fetcher.get_job_logs(owner, repo_name, job_id)
        job_logs.append({"job": job, "logs": logs_content})

    return {"type": "raw_logs", "failed_jobs": job_logs, "has_failures": True}


def _apply_group_filters(
    groups: list[dict], step_filter: str | None, group_filter: str | None
) -> list[dict]:
    """Apply step and group filters to the list of groups."""
    filtered = groups

    if step_filter:
        filtered = [
            g for g in filtered if g["type"] == "step" and step_filter.lower() in g["name"].lower()
        ]

    if group_filter:
        filtered = [g for g in filtered if group_filter.lower() in g["name"].lower()]

    return filtered


def _remove_timestamps(logs: str) -> str:
    """Remove timestamp prefixes from log lines for cleaner output."""
    lines = logs.split("\n")
    cleaned_lines = []

    for line in lines:
        # Remove timestamp prefix (format: 2025-07-16T03:13:13.5152643Z)
        if line.startswith("20") and "T" in line and "Z" in line:
            # Find the first space after the timestamp and remove everything before it
            parts = line.split(" ", 1)
            if len(parts) > 1:
                cleaned_lines.append(parts[1])
            else:
                cleaned_lines.append(line)
        else:
            cleaned_lines.append(line)

    return "\n".join(cleaned_lines)


def _get_filtered_error_logs(
    fetcher: GitHubCIFetcher,
    owner: str,
    repo_name: str,
    commit_sha: str,
    target_description: str,
    show_groups: bool = True,
    step_filter: str | None = None,
    group_filter: str | None = None,
) -> dict[str, Any]:
    """Get filtered error logs for failed jobs."""
    failed_check_runs = fetcher.find_failed_jobs_in_latest_run(owner, repo_name, commit_sha)

    if not failed_check_runs:
        return {
            "type": "filtered_logs",
            "target_description": target_description,
            "failed_jobs": [],
            "has_failures": False,
            "groups": [],
            "show_groups": show_groups,
            "filters": {"step_filter": step_filter, "group_filter": group_filter},
        }

    job_logs = []
    all_groups = []
    seen_groups = set()  # Track unique groups by (name, type)

    for check_run in failed_check_runs:
        job_log_info = _process_check_run_for_logs(
            fetcher, owner, repo_name, check_run, show_groups, step_filter, group_filter
        )
        if job_log_info:
            job_logs.append(job_log_info)
            # Collect groups from each job, avoiding duplicates
            if "groups" in job_log_info:
                for group in job_log_info["groups"]:
                    group_key = (group["name"], group["type"])
                    if group_key not in seen_groups:
                        seen_groups.add(group_key)
                        all_groups.append(group)

    return {
        "type": "filtered_logs",
        "target_description": target_description,
        "failed_jobs": job_logs,
        "has_failures": True,
        "groups": all_groups,
        "show_groups": show_groups,
        "filters": {"step_filter": step_filter, "group_filter": group_filter},
    }


def _process_check_run_for_logs(
    fetcher: GitHubCIFetcher,
    owner: str,
    repo_name: str,
    check_run: dict[str, Any],
    show_groups: bool = True,
    step_filter: str | None = None,
    group_filter: str | None = None,
) -> dict[str, Any] | None:
    """Process a single check run to extract step logs."""
    name = check_run.get("name", "Unknown Job")
    html_url = check_run.get("html_url", "")

    # Early return if not a workflow run
    if "actions/runs" not in html_url:
        return {
            "name": name,
            "html_url": html_url,
            "step_logs": {},
            "error": "Cannot retrieve detailed information for this check run type",
        }

    try:
        run_id = _extract_run_id_from_url(html_url)
        if not run_id:
            return None

        jobs = fetcher.get_workflow_jobs(owner, repo_name, run_id)
        return _extract_step_logs_from_jobs(
            fetcher, owner, repo_name, jobs, name, show_groups, step_filter, group_filter
        )

    except (ValueError, KeyError, TypeError) as e:
        return {
            "name": name,
            "html_url": html_url,
            "step_logs": {},
            "error": f"Failed to parse job data: {e}",
        }
    except Exception as e:
        return {
            "name": name,
            "html_url": html_url,
            "step_logs": {},
            "error": f"Unexpected error processing job details: {type(e).__name__}: {e}",
        }


def _extract_step_logs_from_jobs(
    fetcher: GitHubCIFetcher,
    owner: str,
    repo_name: str,
    jobs: list[dict[str, Any]],
    job_name: str,
    show_groups: bool = True,
    step_filter: str | None = None,
    group_filter: str | None = None,
) -> dict[str, Any] | None:
    """Extract step logs from workflow jobs."""
    for job in jobs:
        if job.get("conclusion") != "failure":
            continue

        job_id = job.get("id")
        failed_steps = fetcher.get_failed_steps(job)

        if not job_id or not failed_steps:
            continue

        logs_content = fetcher.get_job_logs(owner, repo_name, job_id)
        all_steps = job.get("steps", [])

        # Add group analysis and step status
        groups = LogParser.parse_log_groups(logs_content)
        filtered_groups = _apply_group_filters(groups, step_filter, group_filter)
        step_status = LogParser.get_step_status_info(all_steps, failed_steps)

        step_logs = LogParser.extract_step_logs(logs_content, failed_steps, all_steps)

        if step_logs:
            # Filter each step's logs for errors and remove timestamps
            filtered_step_logs = {}
            for step_name, step_log in step_logs.items():
                if step_log.strip():
                    shown_lines = LogParser.filter_error_lines(step_log)
                    if shown_lines:
                        clean_log = "\n".join(shown_lines)
                        filtered_step_logs[step_name] = _remove_timestamps(clean_log)
                    else:
                        # Fallback to last few lines
                        step_lines = step_log.split("\n")
                        clean_log = "\n".join(
                            line for line in step_lines[-FALLBACK_LOG_LINES:] if line.strip()
                        )
                        filtered_step_logs[step_name] = _remove_timestamps(clean_log)

            return {
                "name": job_name,
                "job_name": job.get("name", "Unknown"),
                "step_logs": filtered_step_logs,
                "groups": filtered_groups,
                "step_status": step_status,
                "error": None,
            }
        else:
            # Fallback: show all logs when step parsing fails (remove timestamps)
            clean_logs = _remove_timestamps(logs_content)
            return {
                "name": job_name,
                "job_name": job.get("name", "Unknown"),
                "step_logs": {"Full Job Logs": clean_logs},
                "groups": filtered_groups,
                "step_status": step_status,
                "error": None,
            }

    return {"name": job_name, "step_logs": {}, "error": "Could not retrieve job logs"}


def _analyze_workflow_runs(workflow_runs: list[dict[str, Any]]) -> dict[str, Any]:
    """Analyze workflow runs and return status summary."""
    all_completed = True
    any_failed = False
    failed_runs = []
    workflows = []

    for run in workflow_runs:
        workflow_info = _process_single_workflow_run(run)
        workflows.append(workflow_info)

        if not workflow_info["completed"]:
            all_completed = False

        if workflow_info["failed"]:
            any_failed = True
            failed_runs.append(run.get("id"))

    return {
        "all_completed": all_completed,
        "any_failed": any_failed,
        "failed_runs": failed_runs,
        "workflows": workflows,
    }


def _process_single_workflow_run(run: dict[str, Any]) -> dict[str, Any]:
    """Process a single workflow run and return status info."""
    name = run.get("name", "Unknown Workflow")
    status = run.get("status", "unknown")
    conclusion = run.get("conclusion")

    # Calculate duration
    duration_str = _calculate_workflow_duration(run)

    # Determine status info
    if status == "completed":
        completed = True
        if conclusion == "success":
            emoji = "✅"
            failed = False
        else:
            emoji = "❌" if conclusion == "failure" else "🚫" if conclusion == "cancelled" else "⚠️"
            failed = True
    elif status == "in_progress":
        emoji = "🔄"
        completed = False
        failed = False
    elif status == "queued":
        emoji = "⏳"
        completed = False
        failed = False
    else:
        emoji = "❓"
        completed = False
        failed = False

    return {
        "name": name,
        "status": status,
        "conclusion": conclusion,
        "emoji": emoji,
        "duration": duration_str,
        "completed": completed,
        "failed": failed,
    }


def _calculate_workflow_duration(run: dict[str, Any]) -> str:
    """Calculate duration for a workflow run."""
    created_at = run.get("created_at", "")
    updated_at = run.get("updated_at", "")

    if not created_at:
        return "unknown"

    try:
        start = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
        if updated_at:
            end = datetime.fromisoformat(updated_at.replace("Z", "+00:00"))
        else:
            end = datetime.now(start.tzinfo)
        duration = end - start
        return f"{int(duration.total_seconds())}s"
    except (ValueError, TypeError):
        # Handle invalid timestamp format or missing timezone info
        return "unknown"
    except Exception:
        # Handle other unexpected errors in datetime calculation
        # TODO: Add proper logging here
        return "unknown"
