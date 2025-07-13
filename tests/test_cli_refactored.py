"""Tests for the refactored CLI presentation logic."""

from unittest.mock import Mock, patch

import pytest
from click.testing import CliRunner

from cimonitor.cli import cli
from cimonitor.services import CIStatusResult, JobDetails, WorkflowStepInfo


@pytest.fixture
def runner():
    """Create a Click test runner."""
    return CliRunner()


@pytest.fixture
def mock_fetcher():
    """Create a mock GitHubCIFetcher."""
    return Mock()


@patch("cimonitor.cli.GitHubCIFetcher")
@patch("cimonitor.cli.get_target_info")
@patch("cimonitor.cli.get_ci_status")
def test_status_command_no_failures(
    mock_get_ci_status, mock_get_target_info, mock_fetcher_class, runner
):
    """Test status command with no failures."""
    # Setup mocks
    mock_fetcher_class.return_value = Mock()
    mock_get_target_info.return_value = ("owner", "repo", "abc123", "test branch")
    mock_get_ci_status.return_value = CIStatusResult([], "test branch")

    result = runner.invoke(cli, ["status"])

    assert result.exit_code == 0
    assert "✅ No failing CI jobs found for test branch!" in result.output


@patch("cimonitor.cli.GitHubCIFetcher")
@patch("cimonitor.cli.get_target_info")
@patch("cimonitor.cli.get_ci_status")
@patch("cimonitor.cli.get_job_details_for_status")
def test_status_command_with_failures(
    mock_get_job_details, mock_get_ci_status, mock_get_target_info, mock_fetcher_class, runner
):
    """Test status command with failures."""
    # Setup mocks
    mock_fetcher = Mock()
    mock_fetcher_class.return_value = mock_fetcher
    mock_get_target_info.return_value = ("owner", "repo", "abc123", "test branch")

    failed_runs = [{"name": "Test Job", "conclusion": "failure", "html_url": "https://example.com"}]
    mock_get_ci_status.return_value = CIStatusResult(failed_runs, "test branch")

    job_details = JobDetails("Test Job", "https://example.com", "failure")
    job_details.failed_steps = [WorkflowStepInfo("Test Step", 1, "30.0s")]
    mock_get_job_details.return_value = job_details

    result = runner.invoke(cli, ["status"])

    assert result.exit_code == 0
    assert "❌ Found 1 failing CI job(s) for test branch:" in result.output
    assert "FAILED JOB #1: Test Job" in result.output
    assert "📋 Failed Steps in Test Job:" in result.output
    assert "❌ Step 1: Test Step (took 30.0s)" in result.output


@patch("cimonitor.cli.GitHubCIFetcher")
@patch("cimonitor.cli.get_target_info")
@patch("cimonitor.cli.get_job_logs")
def test_logs_command_no_failures(
    mock_get_job_logs, mock_get_target_info, mock_fetcher_class, runner
):
    """Test logs command with no failures."""
    # Setup mocks
    mock_fetcher_class.return_value = Mock()
    mock_get_target_info.return_value = ("owner", "repo", "abc123", "test branch")
    mock_get_job_logs.return_value = {
        "type": "filtered_logs",
        "target_description": "test branch",
        "failed_jobs": [],
        "has_failures": False,
    }

    result = runner.invoke(cli, ["logs"])

    assert result.exit_code == 0
    assert "✅ No failing CI jobs found for test branch!" in result.output


@patch("cimonitor.cli.GitHubCIFetcher")
@patch("cimonitor.cli.get_target_info")
@patch("cimonitor.cli.get_job_logs")
def test_logs_command_with_specific_job(
    mock_get_job_logs, mock_get_target_info, mock_fetcher_class, runner
):
    """Test logs command with specific job ID."""
    # Setup mocks
    mock_fetcher_class.return_value = Mock()
    mock_get_target_info.return_value = ("owner", "repo", "abc123", "test branch")
    mock_get_job_logs.return_value = {
        "type": "specific_job",
        "job_info": {
            "id": 123,
            "name": "Test Job",
            "conclusion": "failure",
            "html_url": "https://example.com",
        },
        "logs": "test log content",
    }

    result = runner.invoke(cli, ["logs", "--job-id", "123"])

    assert result.exit_code == 0
    assert "📄 Raw logs for job ID 123:" in result.output
    assert "Job: Test Job" in result.output
    assert "test log content" in result.output


@patch("cimonitor.cli.GitHubCIFetcher")
@patch("cimonitor.cli.get_target_info")
@patch("cimonitor.cli.get_job_logs")
def test_logs_command_raw(mock_get_job_logs, mock_get_target_info, mock_fetcher_class, runner):
    """Test logs command with raw flag."""
    # Setup mocks
    mock_fetcher_class.return_value = Mock()
    mock_get_target_info.return_value = ("owner", "repo", "abc123", "test branch")
    mock_get_job_logs.return_value = {
        "type": "raw_logs",
        "failed_jobs": [{"job": {"name": "Test Job", "id": 123}, "logs": "raw log content"}],
        "has_failures": True,
    }

    result = runner.invoke(cli, ["logs", "--raw"])

    assert result.exit_code == 0
    assert "📄 Raw logs for 1 failed job(s):" in result.output
    assert "RAW LOGS #1: Test Job (ID: 123)" in result.output
    assert "raw log content" in result.output


@patch("cimonitor.cli.GitHubCIFetcher")
@patch("cimonitor.cli.get_target_info")
@patch("cimonitor.cli.get_job_logs")
def test_logs_command_filtered(mock_get_job_logs, mock_get_target_info, mock_fetcher_class, runner):
    """Test logs command with filtered output."""
    # Setup mocks
    mock_fetcher_class.return_value = Mock()
    mock_get_target_info.return_value = ("owner", "repo", "abc123", "test branch")
    mock_get_job_logs.return_value = {
        "type": "filtered_logs",
        "target_description": "test branch",
        "failed_jobs": [
            {"name": "Test Job", "step_logs": {"Test Step": "error log content"}, "error": None}
        ],
        "has_failures": True,
    }

    result = runner.invoke(cli, ["logs"])

    assert result.exit_code == 0
    assert "📄 Error logs for 1 failing job(s) in test branch:" in result.output
    assert "LOGS #1: Test Job" in result.output
    assert "📄 Logs for Failed Step: Test Step" in result.output
    assert "error log content" in result.output


def test_validate_watch_options(runner):
    """Test watch option validation."""
    # Test conflicting options
    result = runner.invoke(cli, ["watch", "--until-complete", "--until-fail"])
    assert result.exit_code == 1
    assert "Cannot specify both --until-complete and --until-fail" in result.output

    # Test invalid retry count
    result = runner.invoke(cli, ["watch", "--retry", "0"])
    assert result.exit_code == 1
    assert "--retry must be a positive integer" in result.output

    # Test retry with other options
    result = runner.invoke(cli, ["watch", "--retry", "2", "--until-complete"])
    assert result.exit_code == 1
    assert "Cannot specify --retry with other watch options" in result.output


@patch("cimonitor.cli.GitHubCIFetcher")
@patch("cimonitor.cli.get_target_info")
@patch("cimonitor.cli.watch_ci_status")
@patch("cimonitor.cli.time.sleep")  # Mock sleep to speed up test
def test_watch_command_success(
    mock_sleep, mock_watch_ci_status, mock_get_target_info, mock_fetcher_class, runner
):
    """Test watch command with successful completion."""
    # Setup mocks
    mock_fetcher_class.return_value = Mock()
    mock_get_target_info.return_value = ("owner", "repo", "abc123", "test branch")
    mock_watch_ci_status.return_value = {
        "status": "success",
        "continue_watching": False,
        "workflows": [{"name": "Test", "emoji": "✅", "status": "completed", "duration": "300s"}],
    }

    result = runner.invoke(cli, ["watch"])

    assert result.exit_code == 0
    assert "🔄 Watching CI status for test branch..." in result.output
    assert "📊 Found 1 workflow run(s):" in result.output
    assert "🎉 All workflows completed successfully!" in result.output


@patch("cimonitor.cli.GitHubCIFetcher")
@patch("cimonitor.cli.get_target_info")
@patch("cimonitor.cli.watch_ci_status")
def test_watch_command_failure(
    mock_watch_ci_status, mock_get_target_info, mock_fetcher_class, runner
):
    """Test watch command with failure."""
    # Setup mocks
    mock_fetcher_class.return_value = Mock()
    mock_get_target_info.return_value = ("owner", "repo", "abc123", "test branch")
    mock_watch_ci_status.return_value = {
        "status": "failed",
        "continue_watching": False,
        "workflows": [{"name": "Test", "emoji": "❌", "status": "completed", "duration": "300s"}],
    }

    result = runner.invoke(cli, ["watch"])

    assert result.exit_code == 1
    assert "💥 Some workflows failed!" in result.output


def test_target_validation(runner):
    """Test target option validation."""
    result = runner.invoke(cli, ["status", "--branch", "main", "--commit", "abc123"])

    assert result.exit_code == 1
    assert "Please specify only one of --branch, --commit, or --pr" in result.output
