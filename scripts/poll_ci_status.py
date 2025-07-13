#!/usr/bin/env python3
"""Poll GitHub CI status for the current commit and report results."""

import os
import sys
import time
import subprocess
from datetime import datetime
from typing import Optional, Dict, Any

import requests

def get_repo_info() -> tuple[str, str]:
    """Get owner and repo name from git remote."""
    try:
        result = subprocess.run(
            ["git", "remote", "get-url", "origin"],
            capture_output=True,
            text=True,
            check=True
        )
        origin_url = result.stdout.strip()
        
        if origin_url.startswith("git@"):
            # SSH format: git@github.com:owner/repo.git
            parts = origin_url.replace("git@github.com:", "").replace(".git", "").split("/")
        else:
            # HTTPS format: https://github.com/owner/repo.git
            from urllib.parse import urlparse
            parsed = urlparse(origin_url)
            parts = parsed.path.strip("/").replace(".git", "").split("/")
        
        return parts[0], parts[1]
    except subprocess.CalledProcessError:
        print("❌ Error: Not in a git repository or no origin remote found")
        sys.exit(1)

def get_current_commit() -> str:
    """Get current commit SHA."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=True
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError:
        print("❌ Error: Could not get current commit")
        sys.exit(1)

def get_github_token() -> str:
    """Get GitHub token from environment."""
    token = os.getenv("GITHUB_TOKEN")
    if not token:
        print("❌ Error: GITHUB_TOKEN environment variable not set")
        sys.exit(1)
    return token

def get_workflow_runs(owner: str, repo: str, commit_sha: str, token: str) -> list[Dict[str, Any]]:
    """Get workflow runs for the specific commit."""
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json",
    }
    
    url = f"https://api.github.com/repos/{owner}/{repo}/actions/runs"
    params = {"head_sha": commit_sha, "per_page": 10}
    
    try:
        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()
        return response.json().get("workflow_runs", [])
    except requests.RequestException as e:
        print(f"❌ Error fetching workflow runs: {e}")
        return []

def format_duration(start_time: str, end_time: Optional[str] = None) -> str:
    """Format duration between start and end time."""
    try:
        start = datetime.fromisoformat(start_time.replace("Z", "+00:00"))
        if end_time:
            end = datetime.fromisoformat(end_time.replace("Z", "+00:00"))
        else:
            end = datetime.now(start.tzinfo)
        
        duration = end - start
        total_seconds = int(duration.total_seconds())
        minutes = total_seconds // 60
        seconds = total_seconds % 60
        
        if minutes > 0:
            return f"{minutes}m {seconds}s"
        else:
            return f"{seconds}s"
    except:
        return "unknown"

def print_status(runs: list[Dict[str, Any]], commit_sha: str):
    """Print current status of workflow runs."""
    print(f"\n🔍 CI Status for commit {commit_sha[:8]}")
    print("=" * 60)
    
    if not runs:
        print("⏳ No workflow runs found yet...")
        return
    
    for run in runs:
        name = run.get("name", "Unknown Workflow")
        status = run.get("status", "unknown")
        conclusion = run.get("conclusion")
        created_at = run.get("created_at", "")
        updated_at = run.get("updated_at", "")
        html_url = run.get("html_url", "")
        
        # Status emoji
        if status == "completed":
            if conclusion == "success":
                emoji = "✅"
            elif conclusion == "failure":
                emoji = "❌"
            elif conclusion == "cancelled":
                emoji = "🚫"
            else:
                emoji = "⚠️"
        elif status == "in_progress":
            emoji = "🔄"
        elif status == "queued":
            emoji = "⏳"
        else:
            emoji = "❓"
        
        duration = format_duration(created_at, updated_at)
        
        print(f"{emoji} {name}")
        print(f"   Status: {status}")
        if conclusion:
            print(f"   Result: {conclusion}")
        print(f"   Duration: {duration}")
        print(f"   URL: {html_url}")
        print()

def main():
    """Main polling loop."""
    print("🚀 GitHub CI Status Poller")
    print("Press Ctrl+C to stop polling")
    
    # Get repository info
    owner, repo = get_repo_info()
    commit_sha = get_current_commit()
    token = get_github_token()
    
    print(f"📦 Repository: {owner}/{repo}")
    print(f"📋 Commit: {commit_sha}")
    
    poll_interval = 10  # seconds
    max_polls = 120     # 20 minutes total
    poll_count = 0
    
    try:
        while poll_count < max_polls:
            runs = get_workflow_runs(owner, repo, commit_sha, token)
            print_status(runs, commit_sha)
            
            # Check if all runs are completed
            if runs:
                all_completed = all(run.get("status") == "completed" for run in runs)
                if all_completed:
                    success_count = sum(1 for run in runs if run.get("conclusion") == "success")
                    total_count = len(runs)
                    
                    if success_count == total_count:
                        print("🎉 All workflows completed successfully!")
                        sys.exit(0)
                    else:
                        print(f"💥 {total_count - success_count} workflow(s) failed!")
                        sys.exit(1)
            
            print(f"⏰ Waiting {poll_interval}s... (poll {poll_count + 1}/{max_polls})")
            time.sleep(poll_interval)
            poll_count += 1
        
        print("⏰ Polling timeout reached")
        sys.exit(1)
        
    except KeyboardInterrupt:
        print("\n👋 Polling stopped by user")
        sys.exit(0)

if __name__ == "__main__":
    main()