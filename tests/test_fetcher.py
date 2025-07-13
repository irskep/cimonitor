"""Tests for the GitHub CI fetcher functionality."""

from unittest.mock import patch

import pytest

from github_ci_fetcher.fetcher import GitHubCIFetcher


def test_github_ci_fetcher_init_with_token():
    """Test GitHubCIFetcher initialization with a token."""
    fetcher = GitHubCIFetcher("test_token")
    assert fetcher.github_token == "test_token"
    assert fetcher.headers["Authorization"] == "token test_token"


def test_github_ci_fetcher_init_without_token():
    """Test GitHubCIFetcher initialization without a token raises error."""
    with patch.dict("os.environ", {}, clear=True):
        with pytest.raises(ValueError, match="GitHub token is required"):
            GitHubCIFetcher()


@patch.dict("os.environ", {"GITHUB_TOKEN": "env_token"})
def test_github_ci_fetcher_init_from_env():
    """Test GitHubCIFetcher initialization from environment variable."""
    fetcher = GitHubCIFetcher()
    assert fetcher.github_token == "env_token"


def test_get_failed_steps():
    """Test extracting failed steps from job data."""
    fetcher = GitHubCIFetcher("test_token")

    job_data = {
        "steps": [
            {
                "name": "Passing Step",
                "number": 1,
                "conclusion": "success",
                "started_at": "2025-01-01T10:00:00Z",
                "completed_at": "2025-01-01T10:01:00Z",
            },
            {
                "name": "Failing Step",
                "number": 2,
                "conclusion": "failure",
                "started_at": "2025-01-01T10:01:00Z",
                "completed_at": "2025-01-01T10:02:00Z",
            },
        ]
    }

    failed_steps = fetcher.get_failed_steps(job_data)

    assert len(failed_steps) == 1
    assert failed_steps[0]["name"] == "Failing Step"
    assert failed_steps[0]["number"] == 2
    assert failed_steps[0]["conclusion"] == "failure"
