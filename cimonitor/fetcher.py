"""Core GitHub CI fetching functionality."""

import os
from typing import Any
from urllib.parse import urlparse

import requests
from git import Repo


class GitHubCIFetcher:
    def __init__(self, github_token: str | None = None):
        self.github_token = github_token or os.getenv("GITHUB_TOKEN")
        if not self.github_token:
            raise ValueError("GitHub token is required. Set GITHUB_TOKEN environment variable.")

        self.headers = {
            "Authorization": f"token {self.github_token}",
            "Accept": "application/vnd.github.v3+json",
        }

    def get_repo_info(self) -> tuple[str, str]:
        """Get owner and repo name from git remote origin URL."""
        try:
            repo = Repo(".")
            origin_url = repo.remotes.origin.url

            if origin_url.startswith("git@"):
                # Handle SSH format: git@github.com:owner/repo.git
                parts = origin_url.replace("git@github.com:", "").replace(".git", "").split("/")
            else:
                # Handle HTTPS format: https://github.com/owner/repo.git
                parsed_url = urlparse(origin_url)
                parts = parsed_url.path.strip("/").replace(".git", "").split("/")

            if len(parts) >= 2:
                return parts[0], parts[1]
            else:
                raise ValueError(f"Could not parse repository info from: {origin_url}")
        except Exception as e:
            raise ValueError(f"Failed to get repository info: {e}")

    def get_current_branch_and_commit(self) -> tuple[str, str]:
        """Get current branch name and latest commit SHA."""
        try:
            repo = Repo(".")

            if repo.head.is_detached:
                # If in detached HEAD state, use commit SHA
                commit_sha = repo.head.commit.hexsha
                branch_name = commit_sha[:8]  # Use short SHA as branch name
            else:
                branch_name = repo.active_branch.name
                commit_sha = repo.head.commit.hexsha

            return branch_name, commit_sha
        except Exception as e:
            raise ValueError(f"Failed to get git info: {e}")

    def get_workflow_runs(self, owner: str, repo: str, branch: str) -> list[dict[str, Any]]:
        """Get workflow runs for the current branch."""
        url = f"https://api.github.com/repos/{owner}/{repo}/actions/runs"
        params = {"branch": branch, "per_page": 10, "status": "completed"}

        try:
            response = requests.get(url, headers=self.headers, params=params)
            response.raise_for_status()
            return response.json().get("workflow_runs", [])
        except requests.RequestException as e:
            raise ValueError(f"Failed to fetch workflow runs: {e}")

    def get_job_logs(self, owner: str, repo: str, job_id: int) -> str:
        """Get logs for a specific job."""
        url = f"https://api.github.com/repos/{owner}/{repo}/actions/jobs/{job_id}/logs"

        try:
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            return response.text
        except requests.RequestException as e:
            return f"Failed to fetch logs for job {job_id}: {e}"

    def get_workflow_jobs(self, owner: str, repo: str, run_id: int) -> list[dict[str, Any]]:
        """Get jobs for a specific workflow run."""
        url = f"https://api.github.com/repos/{owner}/{repo}/actions/runs/{run_id}/jobs"

        try:
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            return response.json().get("jobs", [])
        except requests.RequestException as e:
            raise ValueError(f"Failed to fetch jobs for run {run_id}: {e}")

    def find_failed_jobs_in_latest_run(
        self, owner: str, repo: str, commit_sha: str
    ) -> list[dict[str, Any]]:
        """Find failed jobs in the latest workflow run for the given commit."""
        url = f"https://api.github.com/repos/{owner}/{repo}/commits/{commit_sha}/check-runs"

        try:
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            check_runs = response.json().get("check_runs", [])

            failed_jobs = []
            for check_run in check_runs:
                if check_run.get("conclusion") == "failure":
                    failed_jobs.append(check_run)

            return failed_jobs
        except requests.RequestException as e:
            raise ValueError(f"Failed to fetch check runs: {e}")

    def get_failed_steps(self, job: dict[str, Any]) -> list[dict[str, Any]]:
        """Extract failed steps from a job."""
        failed_steps = []
        steps = job.get("steps", [])

        for step in steps:
            if step.get("conclusion") == "failure":
                failed_steps.append(
                    {
                        "name": step.get("name", "Unknown Step"),
                        "number": step.get("number", 0),
                        "started_at": step.get("started_at"),
                        "completed_at": step.get("completed_at"),
                        "conclusion": step.get("conclusion"),
                    }
                )

        return failed_steps

    def get_job_by_id(self, owner: str, repo: str, job_id: int) -> dict[str, Any]:
        """Get a specific job by ID."""
        url = f"https://api.github.com/repos/{owner}/{repo}/actions/jobs/{job_id}"

        try:
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            raise ValueError(f"Failed to fetch job {job_id}: {e}")

    def get_all_jobs_for_commit(
        self, owner: str, repo: str, commit_sha: str
    ) -> list[dict[str, Any]]:
        """Get all jobs (failed and successful) for a specific commit."""
        # First get all workflow runs for this commit
        url = f"https://api.github.com/repos/{owner}/{repo}/actions/runs"
        params = {"head_sha": commit_sha, "per_page": 50}

        all_jobs = []

        try:
            response = requests.get(url, headers=self.headers, params=params)
            response.raise_for_status()
            workflow_runs = response.json().get("workflow_runs", [])

            # Get jobs for each workflow run
            for run in workflow_runs:
                run_id = run["id"]
                jobs = self.get_workflow_jobs(owner, repo, run_id)
                for job in jobs:
                    job["run_id"] = run_id  # Add run_id for reference
                all_jobs.extend(jobs)

            return all_jobs
        except requests.RequestException as e:
            raise ValueError(f"Failed to fetch jobs for commit {commit_sha}: {e}")

    def resolve_commit_sha(self, owner: str, repo: str, commit_ref: str) -> str:
        """Resolve a commit reference (SHA, branch, tag) to a full SHA."""
        # If it's already a full SHA (40 characters), return as-is
        if len(commit_ref) == 40 and all(c in "0123456789abcdef" for c in commit_ref.lower()):
            return commit_ref

        # Resolve via GitHub API
        url = f"https://api.github.com/repos/{owner}/{repo}/commits/{commit_ref}"

        try:
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            commit_data = response.json()
            return commit_data["sha"]
        except requests.RequestException as e:
            raise ValueError(f"Failed to resolve commit reference '{commit_ref}': {e}")

    def get_pr_head_sha(self, owner: str, repo: str, pr_number: int) -> str:
        """Get the head commit SHA for a pull request."""
        url = f"https://api.github.com/repos/{owner}/{repo}/pulls/{pr_number}"

        try:
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            pr_data = response.json()
            return pr_data["head"]["sha"]
        except requests.RequestException as e:
            raise ValueError(f"Failed to get PR {pr_number} head SHA: {e}")

    def get_branch_head_sha(self, owner: str, repo: str, branch_name: str) -> str:
        """Get the head commit SHA for a branch."""
        url = f"https://api.github.com/repos/{owner}/{repo}/branches/{branch_name}"

        try:
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            branch_data = response.json()
            return branch_data["commit"]["sha"]
        except requests.RequestException as e:
            raise ValueError(f"Failed to get branch '{branch_name}' head SHA: {e}")

    def get_workflow_runs_for_commit(
        self, owner: str, repo: str, commit_sha: str
    ) -> list[dict[str, Any]]:
        """Get workflow runs for a specific commit."""
        url = f"https://api.github.com/repos/{owner}/{repo}/actions/runs"
        params = {"head_sha": commit_sha, "per_page": 10}

        try:
            response = requests.get(url, headers=self.headers, params=params)
            response.raise_for_status()
            return response.json().get("workflow_runs", [])
        except requests.RequestException as e:
            raise ValueError(f"Failed to fetch workflow runs for commit {commit_sha}: {e}")

    def rerun_failed_jobs(self, owner: str, repo: str, run_id: int) -> bool:
        """Rerun failed jobs in a workflow run.

        Returns True if the rerun was successful, False otherwise.
        """
        url = f"https://api.github.com/repos/{owner}/{repo}/actions/runs/{run_id}/rerun-failed-jobs"

        try:
            response = requests.post(url, headers=self.headers)
            response.raise_for_status()
            return True
        except requests.RequestException as e:
            print(f"Failed to rerun failed jobs for run {run_id}: {e}")
            return False
