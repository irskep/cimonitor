"""Tests for the services module."""

from unittest.mock import Mock

import pytest

from cimonitor.services import (
    CIStatusResult,
    JobDetails,
    WorkflowStepInfo,
    get_ci_status,
    get_job_details_for_status,
    get_job_logs,
    retry_failed_workflows,
    watch_ci_status,
)


@pytest.fixture
def mock_fetcher():
    """Create a mock GitHubCIFetcher for testing."""
    return Mock()


def test_ci_status_result():
    """Test CIStatusResult class."""
    failed_runs = [{"name": "test", "conclusion": "failure"}]
    result = CIStatusResult(failed_runs, "test branch")

    assert result.failed_check_runs == failed_runs
    assert result.target_description == "test branch"
    assert result.has_failures is True

    # Test with no failures
    empty_result = CIStatusResult([], "test branch")
    assert empty_result.has_failures is False


def test_workflow_step_info():
    """Test WorkflowStepInfo class."""
    step = WorkflowStepInfo("Test Step", 1, "30.5s")

    assert step.name == "Test Step"
    assert step.number == 1
    assert step.duration == "30.5s"


def test_job_details():
    """Test JobDetails class."""
    job = JobDetails("Test Job", "https://example.com", "failure")

    assert job.name == "Test Job"
    assert job.html_url == "https://example.com"
    assert job.conclusion == "failure"
    assert job.failed_steps == []
    assert job.step_logs == {}


def test_get_ci_status(mock_fetcher):
    """Test get_ci_status function."""
    failed_runs = [{"name": "test", "conclusion": "failure"}]
    mock_fetcher.find_failed_jobs_in_latest_run.return_value = failed_runs

    result = get_ci_status(mock_fetcher, "owner", "repo", "abc123", "test branch")

    assert isinstance(result, CIStatusResult)
    assert result.failed_check_runs == failed_runs
    assert result.target_description == "test branch"
    assert result.has_failures is True

    mock_fetcher.find_failed_jobs_in_latest_run.assert_called_once_with("owner", "repo", "abc123")


def test_get_job_details_for_status_basic(mock_fetcher):
    """Test get_job_details_for_status with basic check run."""
    check_run = {
        "name": "Test Job",
        "conclusion": "failure",
        "html_url": "https://example.com/basic",
    }

    result = get_job_details_for_status(mock_fetcher, "owner", "repo", check_run)

    assert result.name == "Test Job"
    assert result.conclusion == "failure"
    assert result.html_url == "https://example.com/basic"
    assert result.failed_steps == []


def test_get_job_details_for_status_with_workflow(mock_fetcher):
    """Test get_job_details_for_status with workflow run."""
    check_run = {
        "name": "Test Job",
        "conclusion": "failure",
        "html_url": "https://github.com/owner/repo/actions/runs/123456",
    }

    mock_jobs = [
        {
            "conclusion": "failure",
            "name": "Job 1",
            "steps": [
                {
                    "name": "Step 1",
                    "number": 1,
                    "conclusion": "failure",
                    "started_at": "2025-01-01T10:00:00Z",
                    "completed_at": "2025-01-01T10:01:00Z",
                }
            ],
        }
    ]

    mock_fetcher.get_workflow_jobs.return_value = mock_jobs
    mock_fetcher.get_failed_steps.return_value = [
        {
            "name": "Step 1",
            "number": 1,
            "started_at": "2025-01-01T10:00:00Z",
            "completed_at": "2025-01-01T10:01:00Z",
        }
    ]

    result = get_job_details_for_status(mock_fetcher, "owner", "repo", check_run)

    assert result.name == "Test Job"
    assert len(result.failed_steps) == 1
    assert result.failed_steps[0].name == "Step 1"
    assert result.failed_steps[0].number == 1
    assert result.failed_steps[0].duration == "60.0s"


def test_get_job_logs_specific_job(mock_fetcher):
    """Test get_job_logs with specific job ID."""
    job_info = {"id": 123, "name": "Test Job", "conclusion": "failure"}
    logs = "test log content"

    mock_fetcher.get_job_by_id.return_value = job_info
    mock_fetcher.get_job_logs.return_value = logs

    result = get_job_logs(mock_fetcher, "owner", "repo", "abc123", "test", job_id=123)

    assert result["type"] == "specific_job"
    assert result["job_info"] == job_info
    assert result["logs"] == logs


def test_get_job_logs_raw(mock_fetcher):
    """Test get_job_logs with raw flag."""
    failed_jobs = [{"id": 123, "name": "Test Job", "conclusion": "failure"}]

    mock_fetcher.get_all_jobs_for_commit.return_value = failed_jobs
    mock_fetcher.get_job_logs.return_value = "test logs"

    result = get_job_logs(mock_fetcher, "owner", "repo", "abc123", "test", raw=True)

    assert result["type"] == "raw_logs"
    assert result["has_failures"] is True
    assert len(result["failed_jobs"]) == 1
    assert result["failed_jobs"][0]["job"] == failed_jobs[0]
    assert result["failed_jobs"][0]["logs"] == "test logs"


def test_get_job_logs_filtered(mock_fetcher):
    """Test get_job_logs with filtered output."""
    failed_runs = [
        {"name": "Test Job", "html_url": "https://github.com/owner/repo/actions/runs/123"}
    ]

    mock_fetcher.find_failed_jobs_in_latest_run.return_value = failed_runs
    mock_fetcher.get_workflow_jobs.return_value = []

    result = get_job_logs(mock_fetcher, "owner", "repo", "abc123", "test")

    assert result["type"] == "filtered_logs"
    assert result["target_description"] == "test"
    assert result["has_failures"] is True


def test_watch_ci_status_no_runs(mock_fetcher):
    """Test watch_ci_status with no workflow runs."""
    mock_fetcher.get_workflow_runs_for_commit.return_value = []

    result = watch_ci_status(mock_fetcher, "owner", "repo", "abc123", "test")

    assert result["status"] == "no_runs"
    assert result["continue_watching"] is True


def test_watch_ci_status_success(mock_fetcher):
    """Test watch_ci_status with successful workflows."""
    mock_runs = [
        {
            "name": "Test Workflow",
            "status": "completed",
            "conclusion": "success",
            "created_at": "2025-01-01T10:00:00Z",
            "updated_at": "2025-01-01T10:05:00Z",
            "id": 123,
        }
    ]

    mock_fetcher.get_workflow_runs_for_commit.return_value = mock_runs

    result = watch_ci_status(mock_fetcher, "owner", "repo", "abc123", "test")

    assert result["status"] == "success"
    assert result["continue_watching"] is False
    assert len(result["workflows"]) == 1
    assert result["workflows"][0]["name"] == "Test Workflow"
    assert result["workflows"][0]["emoji"] == "✅"


def test_watch_ci_status_failure(mock_fetcher):
    """Test watch_ci_status with failed workflows."""
    mock_runs = [
        {
            "name": "Test Workflow",
            "status": "completed",
            "conclusion": "failure",
            "created_at": "2025-01-01T10:00:00Z",
            "updated_at": "2025-01-01T10:05:00Z",
            "id": 123,
        }
    ]

    mock_fetcher.get_workflow_runs_for_commit.return_value = mock_runs

    result = watch_ci_status(mock_fetcher, "owner", "repo", "abc123", "test")

    assert result["status"] == "failed"
    assert result["continue_watching"] is False
    assert result["workflows"][0]["emoji"] == "❌"


def test_watch_ci_status_in_progress(mock_fetcher):
    """Test watch_ci_status with in-progress workflows."""
    mock_runs = [
        {
            "name": "Test Workflow",
            "status": "in_progress",
            "conclusion": None,
            "created_at": "2025-01-01T10:00:00Z",
            "updated_at": "2025-01-01T10:02:00Z",
            "id": 123,
        }
    ]

    mock_fetcher.get_workflow_runs_for_commit.return_value = mock_runs

    result = watch_ci_status(mock_fetcher, "owner", "repo", "abc123", "test")

    assert result["status"] == "in_progress"
    assert result["continue_watching"] is True
    assert result["workflows"][0]["emoji"] == "🔄"


def test_watch_ci_status_until_fail(mock_fetcher):
    """Test watch_ci_status with until_fail flag."""
    mock_runs = [
        {
            "name": "Test Workflow",
            "status": "completed",
            "conclusion": "failure",
            "created_at": "2025-01-01T10:00:00Z",
            "updated_at": "2025-01-01T10:05:00Z",
            "id": 123,
        }
    ]

    mock_fetcher.get_workflow_runs_for_commit.return_value = mock_runs

    result = watch_ci_status(mock_fetcher, "owner", "repo", "abc123", "test", until_fail=True)

    assert result["status"] == "stop_on_failure"
    assert result["continue_watching"] is False


def test_watch_ci_status_retry_needed(mock_fetcher):
    """Test watch_ci_status with retry needed."""
    mock_runs = [
        {
            "name": "Test Workflow",
            "status": "completed",
            "conclusion": "failure",
            "created_at": "2025-01-01T10:00:00Z",
            "updated_at": "2025-01-01T10:05:00Z",
            "id": 123,
        }
    ]

    mock_fetcher.get_workflow_runs_for_commit.return_value = mock_runs

    result = watch_ci_status(mock_fetcher, "owner", "repo", "abc123", "test", retry_count=1)

    assert result["status"] == "retry_needed"
    assert result["continue_watching"] is True
    assert 123 in result["failed_runs"]


def test_retry_failed_workflows(mock_fetcher):
    """Test retry_failed_workflows function."""
    mock_fetcher.rerun_failed_jobs.side_effect = [True, False]

    result = retry_failed_workflows(mock_fetcher, "owner", "repo", [123, 456])

    assert result[123] is True
    assert result[456] is False
    assert mock_fetcher.rerun_failed_jobs.call_count == 2


def test_workflow_duration_calculation():
    """Test workflow duration calculation edge cases."""
    from cimonitor.services import _calculate_workflow_duration

    # Test with missing created_at
    run = {"updated_at": "2025-01-01T10:05:00Z"}
    assert _calculate_workflow_duration(run) == "unknown"

    # Test with invalid datetime format
    run = {"created_at": "invalid", "updated_at": "2025-01-01T10:05:00Z"}
    assert _calculate_workflow_duration(run) == "unknown"

    # Test with valid datetimes
    run = {"created_at": "2025-01-01T10:00:00Z", "updated_at": "2025-01-01T10:05:00Z"}
    assert _calculate_workflow_duration(run) == "300s"


def test_step_duration_calculation():
    """Test step duration calculation edge cases."""
    from cimonitor.services import _calculate_step_duration

    # Test with missing timestamps
    step = {"started_at": None, "completed_at": "2025-01-01T10:01:00Z"}
    assert _calculate_step_duration(step) == "Unknown"

    # Test with invalid datetime format
    step = {"started_at": "invalid", "completed_at": "2025-01-01T10:01:00Z"}
    assert _calculate_step_duration(step) == "Unknown"

    # Test with valid timestamps
    step = {"started_at": "2025-01-01T10:00:00Z", "completed_at": "2025-01-01T10:01:00Z"}
    assert _calculate_step_duration(step) == "60.0s"


def test_extract_run_id_from_url():
    """Test run ID extraction from GitHub URLs."""
    from cimonitor.services import _extract_run_id_from_url

    # Test valid URL
    url = "https://github.com/owner/repo/actions/runs/123456/jobs/789"
    assert _extract_run_id_from_url(url) == 123456

    # Test invalid URL
    assert _extract_run_id_from_url("https://example.com") is None

    # Test malformed URL
    assert _extract_run_id_from_url("https://github.com/actions/runs/invalid") is None
