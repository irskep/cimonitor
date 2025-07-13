#!/usr/bin/env python3

import os
import sys
import requests
import click
from git import Repo
from typing import Optional, Dict, List, Any
import json
from urllib.parse import urlparse


class GitHubCIFetcher:
    def __init__(self, github_token: Optional[str] = None):
        self.github_token = github_token or os.getenv('GITHUB_TOKEN')
        if not self.github_token:
            raise ValueError("GitHub token is required. Set GITHUB_TOKEN environment variable.")
        
        self.headers = {
            'Authorization': f'token {self.github_token}',
            'Accept': 'application/vnd.github.v3+json'
        }
    
    def get_repo_info(self) -> tuple[str, str]:
        """Get owner and repo name from git remote origin URL."""
        try:
            repo = Repo('.')
            origin_url = repo.remotes.origin.url
            
            if origin_url.startswith('git@'):
                # Handle SSH format: git@github.com:owner/repo.git
                parts = origin_url.replace('git@github.com:', '').replace('.git', '').split('/')
            else:
                # Handle HTTPS format: https://github.com/owner/repo.git
                parsed_url = urlparse(origin_url)
                parts = parsed_url.path.strip('/').replace('.git', '').split('/')
            
            if len(parts) >= 2:
                return parts[0], parts[1]
            else:
                raise ValueError(f"Could not parse repository info from: {origin_url}")
        except Exception as e:
            raise ValueError(f"Failed to get repository info: {e}")
    
    def get_current_branch_and_commit(self) -> tuple[str, str]:
        """Get current branch name and latest commit SHA."""
        try:
            repo = Repo('.')
            
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
    
    def get_workflow_runs(self, owner: str, repo: str, branch: str) -> List[Dict[str, Any]]:
        """Get workflow runs for the current branch."""
        url = f"https://api.github.com/repos/{owner}/{repo}/actions/runs"
        params = {
            'branch': branch,
            'per_page': 10,
            'status': 'completed'
        }
        
        try:
            response = requests.get(url, headers=self.headers, params=params)
            response.raise_for_status()
            return response.json().get('workflow_runs', [])
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
    
    def get_workflow_jobs(self, owner: str, repo: str, run_id: int) -> List[Dict[str, Any]]:
        """Get jobs for a specific workflow run."""
        url = f"https://api.github.com/repos/{owner}/{repo}/actions/runs/{run_id}/jobs"
        
        try:
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            return response.json().get('jobs', [])
        except requests.RequestException as e:
            click.echo(f"Failed to fetch jobs for run {run_id}: {e}", err=True)
            return []
    
    def find_failed_jobs_in_latest_run(self, owner: str, repo: str, commit_sha: str) -> List[Dict[str, Any]]:
        """Find failed jobs in the latest workflow run for the given commit."""
        url = f"https://api.github.com/repos/{owner}/{repo}/commits/{commit_sha}/check-runs"
        
        try:
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            check_runs = response.json().get('check_runs', [])
            
            failed_jobs = []
            for check_run in check_runs:
                if check_run.get('conclusion') == 'failure':
                    failed_jobs.append(check_run)
            
            return failed_jobs
        except requests.RequestException as e:
            click.echo(f"Failed to fetch check runs: {e}", err=True)
            return []
    
    def get_failed_steps(self, job: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract failed steps from a job."""
        failed_steps = []
        steps = job.get('steps', [])
        
        for step in steps:
            if step.get('conclusion') == 'failure':
                failed_steps.append({
                    'name': step.get('name', 'Unknown Step'),
                    'number': step.get('number', 0),
                    'started_at': step.get('started_at'),
                    'completed_at': step.get('completed_at'),
                    'conclusion': step.get('conclusion')
                })
        
        return failed_steps
    
    def extract_step_logs(self, full_logs: str, failed_steps: List[Dict[str, Any]]) -> Dict[str, str]:
        """Extract log sections for specific failed steps using GitHub's step markers."""
        step_logs = {}
        log_lines = full_logs.split('\n')
        
        for step in failed_steps:
            step_name = step['name']
            step_lines = []
            
            # GitHub Actions uses ##[group]Run STEP_NAME and ##[endgroup] as boundaries
            # Look for the step by name in the ##[group]Run pattern
            capturing = False
            
            for i, line in enumerate(log_lines):
                # Start capturing when we find the step's group marker
                if f'##[group]Run {step_name}' in line:
                    capturing = True
                    step_lines.append(line)
                elif capturing:
                    step_lines.append(line)
                    
                    # Stop capturing when we hit the endgroup for this step
                    if '##[endgroup]' in line:
                        # Continue capturing a few more lines for errors that appear after endgroup
                        for j in range(i + 1, min(i + 10, len(log_lines))):
                            next_line = log_lines[j]
                            step_lines.append(next_line)
                            
                            # Stop if we hit another group or significant marker
                            if ('##[group]' in next_line or 
                                'Post job cleanup' in next_line):
                                break
                        break
            
            if step_lines:
                step_logs[step_name] = '\n'.join(step_lines)
            else:
                # Fallback: try partial name matching for steps with complex names
                for i, line in enumerate(log_lines):
                    # Look for key words from the step name in group markers
                    if ('##[group]Run' in line and 
                        any(word.lower() in line.lower() for word in step_name.split() if len(word) > 3)):
                        capturing = True
                        step_lines = [line]
                        
                        # Capture until endgroup
                        for j in range(i + 1, len(log_lines)):
                            next_line = log_lines[j]
                            step_lines.append(next_line)
                            
                            if '##[endgroup]' in next_line:
                                # Get a few more lines for error context
                                for k in range(j + 1, min(j + 10, len(log_lines))):
                                    error_line = log_lines[k]
                                    step_lines.append(error_line)
                                    if ('##[group]' in error_line or 
                                        'Post job cleanup' in error_line):
                                        break
                                break
                        
                        if step_lines:
                            step_logs[step_name] = '\n'.join(step_lines)
                        break
        
        return step_logs


@click.command()
@click.option('--branch', default=None, help='Specific branch to check (defaults to current branch)')
@click.option('--verbose', '-v', is_flag=True, help='Show verbose output')
@click.option('--show-logs', is_flag=True, help='Show detailed error logs (slower)')
def main(branch: Optional[str], verbose: bool, show_logs: bool):
    """Fetch GitHub CI logs for failing builds on the latest commit."""
    
    try:
        fetcher = GitHubCIFetcher()
        
        # Get repository info
        owner, repo_name = fetcher.get_repo_info()
        if verbose:
            click.echo(f"Repository: {owner}/{repo_name}")
        
        # Get current branch and commit
        current_branch, commit_sha = fetcher.get_current_branch_and_commit()
        target_branch = branch or current_branch
        
        if verbose:
            click.echo(f"Branch: {target_branch}")
            click.echo(f"Latest commit: {commit_sha}")
        
        # Find failed jobs for the latest commit
        failed_check_runs = fetcher.find_failed_jobs_in_latest_run(owner, repo_name, commit_sha)
        
        if not failed_check_runs:
            click.echo("✅ No failing CI jobs found for the latest commit!")
            return
        
        click.echo(f"❌ Found {len(failed_check_runs)} failing CI job(s):")
        click.echo()
        
        for i, check_run in enumerate(failed_check_runs, 1):
            name = check_run.get('name', 'Unknown Job')
            conclusion = check_run.get('conclusion', 'unknown')
            html_url = check_run.get('html_url', '')
            
            click.echo(f"{'='*60}")
            click.echo(f"FAILED JOB #{i}: {name}")
            click.echo(f"Status: {conclusion}")
            click.echo(f"URL: {html_url}")
            click.echo(f"{'='*60}")
            
            # Try to get workflow run info and step details
            if 'actions/runs' in html_url:
                try:
                    # Extract run ID from URL
                    run_id = html_url.split('/runs/')[1].split('/')[0]
                    jobs = fetcher.get_workflow_jobs(owner, repo_name, int(run_id))
                    
                    for job in jobs:
                        if job.get('conclusion') == 'failure':
                            job_name = job.get('name', 'Unknown')
                            job_id = job.get('id')
                            
                            # Show failed steps summary first
                            failed_steps = fetcher.get_failed_steps(job)
                            
                            if failed_steps:
                                click.echo(f"\n📋 Failed Steps in {job_name}:")
                                for step in failed_steps:
                                    step_name = step['name']
                                    step_num = step['number']
                                    duration = "Unknown"
                                    
                                    if step['started_at'] and step['completed_at']:
                                        from datetime import datetime
                                        start = datetime.fromisoformat(step['started_at'].replace('Z', '+00:00'))
                                        end = datetime.fromisoformat(step['completed_at'].replace('Z', '+00:00'))
                                        duration = f"{(end - start).total_seconds():.1f}s"
                                    
                                    click.echo(f"  ❌ Step {step_num}: {step_name} (took {duration})")
                                
                                click.echo()
                            
                            # Only show detailed logs if requested
                            if show_logs:
                                if job_id:
                                    logs = fetcher.get_job_logs(owner, repo_name, job_id)
                                    
                                    # Extract logs for just the failed steps
                                    step_logs = fetcher.extract_step_logs(logs, failed_steps)
                                    
                                    if step_logs:
                                        for step_name, step_log in step_logs.items():
                                            click.echo(f"\n📄 Logs for Failed Step: {step_name}")
                                            click.echo("-" * 50)
                                            
                                            # Show only the step-specific logs
                                            if step_log.strip():
                                                # Still filter for error-related content within the step
                                                step_lines = step_log.split('\n')
                                                shown_lines = []
                                                
                                                for line in step_lines:
                                                    # Show lines with error indicators or important info
                                                    if (any(keyword in line.lower() for keyword in 
                                                           ['error', 'failed', 'failure', '❌', '✗', 'exit code', '##[error]']) or
                                                        '##[group]' in line or '##[endgroup]' in line or
                                                        not line.startswith('2025-')):  # Include non-timestamp lines
                                                        shown_lines.append(line)
                                                
                                                if shown_lines:
                                                    for line in shown_lines:
                                                        if line.strip():
                                                            click.echo(line)
                                                else:
                                                    # Fallback to last few lines of the step
                                                    for line in step_lines[-10:]:
                                                        if line.strip():
                                                            click.echo(line)
                                            else:
                                                click.echo("No logs found for this step")
                                    else:
                                        click.echo(f"\n📄 Could not extract step-specific logs for {job_name}")
                                        click.echo("💡 This might be due to log format differences")
                                else:
                                    click.echo("Could not retrieve job logs")
                            else:
                                click.echo("💡 Use --show-logs to see detailed error logs for failed steps only")
                            
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


if __name__ == '__main__':
    main()