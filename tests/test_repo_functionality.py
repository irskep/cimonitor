"""Tests for the new --repo functionality."""

from unittest.mock import Mock

import pytest

from cimonitor.cli import get_target_info, parse_pr_input, parse_repo_input


class TestRepoInputParsing:
    """Test repo input parsing functionality."""

    def test_parse_repo_input_valid(self):
        """Test parsing valid repo input."""
        owner, repo = parse_repo_input("owner/repo")
        assert owner == "owner"
        assert repo == "repo"

    def test_parse_repo_input_none(self):
        """Test parsing None repo input."""
        owner, repo = parse_repo_input(None)
        assert owner is None
        assert repo is None

    def test_parse_repo_input_empty(self):
        """Test parsing empty repo input."""
        owner, repo = parse_repo_input("")
        assert owner is None
        assert repo is None

    def test_parse_repo_input_no_slash(self):
        """Test parsing repo input without slash."""
        with pytest.raises(ValueError, match="Invalid repository format"):
            parse_repo_input("just-repo-name")

    def test_parse_repo_input_multiple_slashes(self):
        """Test parsing repo input with multiple slashes."""
        with pytest.raises(ValueError, match="Invalid repository format"):
            parse_repo_input("owner/repo/extra")

    def test_parse_repo_input_empty_parts(self):
        """Test parsing repo input with empty parts."""
        with pytest.raises(ValueError, match="Both owner and repository name must be non-empty"):
            parse_repo_input("/repo")

        with pytest.raises(ValueError, match="Both owner and repository name must be non-empty"):
            parse_repo_input("owner/")


class TestPRInputParsing:
    """Test PR input parsing functionality (ensuring it still works)."""

    def test_parse_pr_input_number(self):
        """Test parsing PR number."""
        owner, repo, pr_num = parse_pr_input("123")
        assert owner is None
        assert repo is None
        assert pr_num == 123

    def test_parse_pr_input_url(self):
        """Test parsing PR URL."""
        owner, repo, pr_num = parse_pr_input("https://github.com/owner/repo/pull/456")
        assert owner == "owner"
        assert repo == "repo"
        assert pr_num == 456

    def test_parse_pr_input_invalid(self):
        """Test parsing invalid PR input."""
        with pytest.raises(ValueError, match="Invalid PR input"):
            parse_pr_input("not-a-number-or-url")


class TestGetTargetInfoWithRepo:
    """Test get_target_info function with repo parameter."""

    def test_get_target_info_with_repo_and_pr(self):
        """Test get_target_info with --repo and --pr."""
        mock_fetcher = Mock()
        mock_fetcher.get_pr_head_sha.return_value = "abc123"

        owner, repo_name, commit_sha, target_description, pr_number = get_target_info(
            mock_fetcher, "test/repo", None, None, "1", False
        )

        assert owner == "test"
        assert repo_name == "repo"
        assert commit_sha == "abc123"
        assert target_description == "PR #1 in test/repo"
        assert pr_number == 1
        mock_fetcher.get_pr_head_sha.assert_called_once_with("test", "repo", 1)

    def test_get_target_info_with_repo_and_branch(self):
        """Test get_target_info with --repo and --branch."""
        mock_fetcher = Mock()
        mock_fetcher.get_branch_head_sha.return_value = "def456"

        owner, repo_name, commit_sha, target_description, pr_number = get_target_info(
            mock_fetcher, "test/repo", "main", None, None, False
        )

        assert owner == "test"
        assert repo_name == "repo"
        assert commit_sha == "def456"
        assert target_description == "branch main in test/repo"
        assert pr_number is None
        mock_fetcher.get_branch_head_sha.assert_called_once_with("test", "repo", "main")

    def test_get_target_info_repo_overrides_pr_url(self):
        """Test that --repo takes precedence over PR URL."""
        mock_fetcher = Mock()
        mock_fetcher.get_pr_head_sha.return_value = "abc123"

        owner, repo_name, commit_sha, target_description, pr_number = get_target_info(
            mock_fetcher,
            "override/repo",
            None,
            None,
            "https://github.com/original/repo/pull/1",
            False,
        )

        assert owner == "override"
        assert repo_name == "repo"
        assert commit_sha == "abc123"
        assert target_description == "PR #1 in override/repo"
        assert pr_number == 1
        # Should call with the override repo, not the original from URL
        mock_fetcher.get_pr_head_sha.assert_called_once_with("override", "repo", 1)

    def test_get_target_info_fallback_to_pr_url(self):
        """Test fallback to PR URL when --repo not provided."""
        mock_fetcher = Mock()
        mock_fetcher.get_pr_head_sha.return_value = "abc123"

        owner, repo_name, commit_sha, target_description, pr_number = get_target_info(
            mock_fetcher, None, None, None, "https://github.com/original/repo/pull/1", False
        )

        assert owner == "original"
        assert repo_name == "repo"
        assert commit_sha == "abc123"
        assert target_description == "PR #1 in original/repo"
        assert pr_number == 1
        mock_fetcher.get_pr_head_sha.assert_called_once_with("original", "repo", 1)

    def test_get_target_info_fallback_to_current_repo(self):
        """Test fallback to current repo when neither --repo nor PR URL provided."""
        mock_fetcher = Mock()
        mock_fetcher.get_repo_info.return_value = ("current", "repo")
        mock_fetcher.get_pr_head_sha.return_value = "abc123"

        owner, repo_name, commit_sha, target_description, pr_number = get_target_info(
            mock_fetcher, None, None, None, "1", False
        )

        assert owner == "current"
        assert repo_name == "repo"
        assert commit_sha == "abc123"
        assert target_description == "PR #1"
        assert pr_number == 1
        mock_fetcher.get_repo_info.assert_called_once()
        mock_fetcher.get_pr_head_sha.assert_called_once_with("current", "repo", 1)
