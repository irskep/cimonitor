"""Tests for improved error handling specificity."""

from unittest.mock import Mock, patch

from cimonitor.services import (
    _calculate_step_duration,
    _calculate_workflow_duration,
    _extract_run_id_from_url,
    _process_check_run_for_logs,
    get_job_details_for_status,
)


class TestErrorHandlingSpecificity:
    """Test that error handling is specific and provides useful feedback."""

    def test_calculate_step_duration_missing_timestamps(self):
        """Test step duration calculation with missing timestamp data."""
        # Test missing started_at
        step_missing_start = {"completed_at": "2025-01-01T10:01:00Z"}
        assert _calculate_step_duration(step_missing_start) == "Unknown"

        # Test missing completed_at
        step_missing_end = {"started_at": "2025-01-01T10:00:00Z"}
        assert _calculate_step_duration(step_missing_end) == "Unknown"

        # Test empty step data
        assert _calculate_step_duration({}) == "Unknown"

    def test_calculate_step_duration_invalid_timestamp_format(self):
        """Test step duration calculation with invalid timestamp formats."""
        # Test invalid timestamp format
        step_invalid = {"started_at": "not-a-timestamp", "completed_at": "2025-01-01T10:01:00Z"}
        assert _calculate_step_duration(step_invalid) == "Unknown"

        # Test None values
        step_none = {"started_at": None, "completed_at": "2025-01-01T10:01:00Z"}
        assert _calculate_step_duration(step_none) == "Unknown"

    def test_calculate_step_duration_valid_timestamps(self):
        """Test step duration calculation with valid timestamps."""
        step_valid = {"started_at": "2025-01-01T10:00:00Z", "completed_at": "2025-01-01T10:01:00Z"}
        result = _calculate_step_duration(step_valid)
        assert result == "60.0s"

    def test_calculate_workflow_duration_missing_created_at(self):
        """Test workflow duration calculation with missing created_at."""
        run_empty = {}
        assert _calculate_workflow_duration(run_empty) == "unknown"

        run_none = {"created_at": None}
        assert _calculate_workflow_duration(run_none) == "unknown"

        run_empty_string = {"created_at": ""}
        assert _calculate_workflow_duration(run_empty_string) == "unknown"

    def test_calculate_workflow_duration_invalid_format(self):
        """Test workflow duration calculation with invalid timestamp format."""
        run_invalid = {"created_at": "not-a-timestamp", "updated_at": "2025-01-01T10:05:00Z"}
        assert _calculate_workflow_duration(run_invalid) == "unknown"

    def test_calculate_workflow_duration_valid_timestamps(self):
        """Test workflow duration calculation with valid timestamps."""
        # Test with both created_at and updated_at
        run_complete = {"created_at": "2025-01-01T10:00:00Z", "updated_at": "2025-01-01T10:05:00Z"}
        result = _calculate_workflow_duration(run_complete)
        assert result == "300s"  # 5 minutes

        # Test with only created_at (should use current time)
        run_ongoing = {"created_at": "2025-01-01T10:00:00Z"}
        result = _calculate_workflow_duration(run_ongoing)
        # Should return some positive duration (can't predict exact value)
        assert result.endswith("s")
        assert result != "unknown"

    @patch("cimonitor.services.GitHubCIFetcher")
    def test_get_job_details_error_handling(self, mock_fetcher_class):
        """Test that get_job_details_for_status handles API errors gracefully."""
        mock_fetcher = Mock()
        mock_fetcher.get_workflow_jobs.side_effect = ValueError("Invalid API response")

        check_run = {
            "name": "Test Job",
            "conclusion": "failure",
            "html_url": "https://github.com/owner/repo/actions/runs/123456",
        }

        # Should not raise exception, should return basic job details
        result = get_job_details_for_status(mock_fetcher, "owner", "repo", check_run)

        assert result is not None
        assert result.name == "Test Job"
        assert result.conclusion == "failure"
        # Should have empty failed_steps since we couldn't get detailed info
        assert len(result.failed_steps) == 0

    def test_process_check_run_logs_error_handling(self):
        """Test that log processing handles errors gracefully."""
        mock_fetcher = Mock()
        mock_fetcher.get_workflow_jobs.side_effect = KeyError("Missing job data")

        check_run = {
            "name": "Test Job",
            "html_url": "https://github.com/owner/repo/actions/runs/123456",
        }

        result = _process_check_run_for_logs(
            mock_fetcher, "owner", "repo", check_run, True, None, None
        )

        assert result is not None
        assert result["name"] == "Test Job"
        assert "Failed to parse job data" in result["error"]
        assert result["step_logs"] == {}

    def test_process_check_run_logs_unexpected_error(self):
        """Test that unexpected errors are handled but logged."""
        mock_fetcher = Mock()
        # Simulate an unexpected error type
        mock_fetcher.get_workflow_jobs.side_effect = RuntimeError("Unexpected system error")

        check_run = {
            "name": "Test Job",
            "html_url": "https://github.com/owner/repo/actions/runs/123456",
        }

        result = _process_check_run_for_logs(
            mock_fetcher, "owner", "repo", check_run, True, None, None
        )

        assert result is not None
        assert result["name"] == "Test Job"
        assert "Unexpected error processing job details" in result["error"]
        assert "RuntimeError" in result["error"]
        assert result["step_logs"] == {}


class TestErrorHandlingRegression:
    """Test that the improved error handling doesn't break existing functionality."""

    def test_url_extraction_still_works(self):
        """Test that URL extraction continues to work after error handling improvements."""
        # Valid cases should still work
        valid_url = "https://github.com/owner/repo/actions/runs/123456"
        assert _extract_run_id_from_url(valid_url) == 123456

        # Invalid cases should return None gracefully
        assert _extract_run_id_from_url("") is None
        assert _extract_run_id_from_url(None) is None
        assert _extract_run_id_from_url("not-a-url") is None

    def test_duration_calculations_still_work(self):
        """Test that duration calculations work correctly for valid inputs."""
        # Valid step duration
        valid_step = {"started_at": "2025-01-01T10:00:00Z", "completed_at": "2025-01-01T10:00:30Z"}
        assert _calculate_step_duration(valid_step) == "30.0s"

        # Valid workflow duration
        valid_run = {"created_at": "2025-01-01T10:00:00Z", "updated_at": "2025-01-01T10:02:00Z"}
        assert _calculate_workflow_duration(valid_run) == "120s"
