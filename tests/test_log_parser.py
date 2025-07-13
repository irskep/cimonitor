"""Tests for the log parser functionality."""

from cimonitor.log_parser import LogParser


def test_filter_error_lines():
    """Test filtering error lines from step logs using real GitHub Actions structure."""
    # Based on real GitHub Actions log format
    step_log = """2025-07-13T04:07:49.4696757Z ##[group]Run echo "This step will fail intentionally to test CI log fetching"
2025-07-13T04:07:49.4697730Z echo "This step will fail intentionally to test CI log fetching"
2025-07-13T04:07:49.4698562Z echo "ERROR: Simulated failure for testing purposes"
2025-07-13T04:07:49.4699162Z exit 1
2025-07-13T04:07:49.4731808Z shell: /usr/bin/bash -e {0}
2025-07-13T04:07:49.4732326Z ##[endgroup]
2025-07-13T04:07:49.4804670Z This step will fail intentionally to test CI log fetching
2025-07-13T04:07:49.4806034Z ERROR: Simulated failure for testing purposes
2025-07-13T04:07:49.4818415Z ##[error]Process completed with exit code 1.
2025-07-13T04:07:49.4934884Z Post job cleanup."""

    error_lines = LogParser.filter_error_lines(step_log)

    # Should include group markers, error lines, and other important markers
    assert any("##[group]Run echo" in line for line in error_lines)
    assert any("ERROR: Simulated failure for testing purposes" in line for line in error_lines)
    assert any("##[error]Process completed with exit code 1." in line for line in error_lines)
    assert any("##[endgroup]" in line for line in error_lines)

    # Should not include regular command lines that don't have error keywords
    assert not any("shell: /usr/bin/bash" in line for line in error_lines)

    # Should include at least 4 lines (group start, error message, error marker, group end)
    assert len(error_lines) >= 4


def test_extract_step_logs():
    """Test extracting logs for specific failed steps using real GitHub Actions log structure."""
    # This is based on actual GitHub Actions log data
    full_logs = """2025-07-13T04:07:48.8923897Z ##[group]Run actions/checkout@v4
2025-07-13T04:07:48.8924737Z with:
2025-07-13T04:07:48.8925209Z   repository: irskep/github-ci-fetcher
2025-07-13T04:07:48.8925972Z   token: ***
2025-07-13T04:07:48.8931612Z ##[endgroup]
2025-07-13T04:07:49.0028957Z Syncing repository: irskep/github-ci-fetcher
2025-07-13T04:07:49.4450429Z ##[endgroup]
2025-07-13T04:07:49.4696757Z ##[group]Run echo "This step will fail intentionally to test CI log fetching"
2025-07-13T04:07:49.4697730Z echo "This step will fail intentionally to test CI log fetching"
2025-07-13T04:07:49.4698562Z echo "ERROR: Simulated failure for testing purposes"
2025-07-13T04:07:49.4699162Z exit 1
2025-07-13T04:07:49.4731808Z shell: /usr/bin/bash -e {0}
2025-07-13T04:07:49.4732326Z ##[endgroup]
2025-07-13T04:07:49.4804670Z This step will fail intentionally to test CI log fetching
2025-07-13T04:07:49.4806034Z ERROR: Simulated failure for testing purposes
2025-07-13T04:07:49.4818415Z ##[error]Process completed with exit code 1.
2025-07-13T04:07:49.4934884Z Post job cleanup."""

    failed_steps = [
        {
            "name": "Intentionally failing step",
            "number": 3,
            "started_at": "2025-07-13T04:07:49.4696757Z",
            "completed_at": "2025-07-13T04:07:49.4732326Z",
        }
    ]

    step_logs = LogParser.extract_step_logs(full_logs, failed_steps)

    assert "Intentionally failing step" in step_logs
    failing_log = step_logs["Intentionally failing step"]

    # Should include the step content and error context after endgroup
    assert (
        '##[group]Run echo "This step will fail intentionally to test CI log fetching"'
        in failing_log
    )
    assert "ERROR: Simulated failure for testing purposes" in failing_log
    assert "##[endgroup]" in failing_log
    assert "##[error]Process completed with exit code 1." in failing_log

    # Should not include content from other steps
    assert "Run actions/checkout@v4" not in failing_log


def test_extract_step_logs_with_partial_name_matching():
    """Test that step extraction works with partial name matching when exact names don't match."""
    # Real scenario where step name doesn't exactly match the ##[group]Run line
    full_logs = """2025-07-13T04:07:49.4696757Z ##[group]Run echo "This step will fail intentionally to test CI log fetching"
2025-07-13T04:07:49.4697730Z echo "This step will fail intentionally to test CI log fetching"
2025-07-13T04:07:49.4698562Z echo "ERROR: Simulated failure for testing purposes"
2025-07-13T04:07:49.4699162Z exit 1
2025-07-13T04:07:49.4732326Z ##[endgroup]
2025-07-13T04:07:49.4818415Z ##[error]Process completed with exit code 1."""

    # The actual step name as reported by GitHub API vs the command in ##[group]Run
    failed_steps = [
        {
            "name": "Intentionally failing step",  # This is how GitHub API reports it
            "number": 3,
            "started_at": "2025-07-13T04:07:49.4696757Z",
            "completed_at": "2025-07-13T04:07:49.4732326Z",
        }
    ]

    step_logs = LogParser.extract_step_logs(full_logs, failed_steps)

    # Should find the step using partial name matching ("intentionally" keyword)
    assert "Intentionally failing step" in step_logs
    failing_log = step_logs["Intentionally failing step"]
    assert "ERROR: Simulated failure for testing purposes" in failing_log
