"""Tests for target resolution functionality (commit, PR, branch)."""

from unittest.mock import patch

import pytest

from github_ci_fetcher.fetcher import GitHubCIFetcher


@pytest.fixture
def mock_fetcher():
    """Create a GitHubCIFetcher instance for testing."""
    return GitHubCIFetcher("test_token")


def test_resolve_commit_sha_full_sha(mock_fetcher):
    """Test that full SHA is returned as-is."""
    full_sha = "1234567890abcdef1234567890abcdef12345678"
    result = mock_fetcher.resolve_commit_sha("owner", "repo", full_sha)
    assert result == full_sha


@patch("requests.get")
def test_resolve_commit_sha_short_ref(mock_get, mock_fetcher):
    """Test resolving a short commit reference via API."""
    mock_response = mock_get.return_value
    mock_response.raise_for_status.return_value = None
    mock_response.json.return_value = {"sha": "1234567890abcdef1234567890abcdef12345678"}

    result = mock_fetcher.resolve_commit_sha("owner", "repo", "abc123")

    assert result == "1234567890abcdef1234567890abcdef12345678"
    mock_get.assert_called_once_with(
        "https://api.github.com/repos/owner/repo/commits/abc123", headers=mock_fetcher.headers
    )


@patch("requests.get")
def test_get_pr_head_sha(mock_get, mock_fetcher):
    """Test getting head SHA for a pull request."""
    mock_response = mock_get.return_value
    mock_response.raise_for_status.return_value = None
    mock_response.json.return_value = {"head": {"sha": "abcdef1234567890abcdef1234567890abcdef12"}}

    result = mock_fetcher.get_pr_head_sha("owner", "repo", 123)

    assert result == "abcdef1234567890abcdef1234567890abcdef12"
    mock_get.assert_called_once_with(
        "https://api.github.com/repos/owner/repo/pulls/123", headers=mock_fetcher.headers
    )


@patch("requests.get")
def test_get_branch_head_sha(mock_get, mock_fetcher):
    """Test getting head SHA for a branch."""
    mock_response = mock_get.return_value
    mock_response.raise_for_status.return_value = None
    mock_response.json.return_value = {
        "commit": {"sha": "fedcba0987654321fedcba0987654321fedcba09"}
    }

    result = mock_fetcher.get_branch_head_sha("owner", "repo", "main")

    assert result == "fedcba0987654321fedcba0987654321fedcba09"
    mock_get.assert_called_once_with(
        "https://api.github.com/repos/owner/repo/branches/main", headers=mock_fetcher.headers
    )


@patch("requests.get")
def test_resolve_commit_sha_api_error(mock_get, mock_fetcher):
    """Test error handling when commit resolution fails."""
    import requests

    mock_response = mock_get.return_value
    mock_response.raise_for_status.side_effect = requests.RequestException("Not Found")

    with pytest.raises(ValueError, match="Failed to resolve commit reference"):
        mock_fetcher.resolve_commit_sha("owner", "repo", "nonexistent")


@patch("requests.get")
def test_get_pr_head_sha_api_error(mock_get, mock_fetcher):
    """Test error handling when PR lookup fails."""
    import requests

    mock_response = mock_get.return_value
    mock_response.raise_for_status.side_effect = requests.RequestException("Not Found")

    with pytest.raises(ValueError, match="Failed to get PR 999 head SHA"):
        mock_fetcher.get_pr_head_sha("owner", "repo", 999)


@patch("requests.get")
def test_get_branch_head_sha_api_error(mock_get, mock_fetcher):
    """Test error handling when branch lookup fails."""
    import requests

    mock_response = mock_get.return_value
    mock_response.raise_for_status.side_effect = requests.RequestException("Not Found")

    with pytest.raises(ValueError, match="Failed to get branch 'nonexistent' head SHA"):
        mock_fetcher.get_branch_head_sha("owner", "repo", "nonexistent")
