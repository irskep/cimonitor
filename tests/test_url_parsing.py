"""Tests for URL parsing robustness improvements."""

from cimonitor.services import _extract_run_id_from_url


class TestExtractRunIdFromUrl:
    """Test the improved URL parsing for GitHub Actions URLs."""

    def test_valid_standard_url(self):
        """Test parsing of standard GitHub Actions URL."""
        url = "https://github.com/owner/repo/actions/runs/123456/jobs/789"
        assert _extract_run_id_from_url(url) == 123456

    def test_valid_url_without_job_id(self):
        """Test parsing URL that ends with run ID."""
        url = "https://github.com/owner/repo/actions/runs/987654"
        assert _extract_run_id_from_url(url) == 987654

    def test_valid_url_with_query_params(self):
        """Test parsing URL with query parameters."""
        url = "https://github.com/owner/repo/actions/runs/555555?check_suite_focus=true"
        assert _extract_run_id_from_url(url) == 555555

    def test_valid_url_with_fragment(self):
        """Test parsing URL with fragment."""
        url = "https://github.com/owner/repo/actions/runs/111111#step:1:1"
        assert _extract_run_id_from_url(url) == 111111

    def test_edge_case_empty_string(self):
        """Test parsing empty string."""
        assert _extract_run_id_from_url("") is None

    def test_edge_case_none_input(self):
        """Test parsing None input."""
        assert _extract_run_id_from_url(None) is None

    def test_edge_case_no_actions_runs(self):
        """Test URL that doesn't contain 'actions/runs'."""
        url = "https://github.com/owner/repo/issues/123"
        assert _extract_run_id_from_url(url) is None

    def test_edge_case_malformed_url(self):
        """Test malformed URL that would break split() method."""
        url = "https://github.com/owner/repo/actions/runs/"
        assert _extract_run_id_from_url(url) is None

    def test_edge_case_non_numeric_run_id(self):
        """Test URL with non-numeric run ID."""
        url = "https://github.com/owner/repo/actions/runs/not-a-number"
        assert _extract_run_id_from_url(url) is None

    def test_edge_case_multiple_runs_segments(self):
        """Test URL with multiple 'runs' segments (edge case)."""
        # This is a contrived case but tests robustness
        url = "https://github.com/runs/repo/actions/runs/123456"
        assert _extract_run_id_from_url(url) == 123456

    def test_edge_case_runs_at_end(self):
        """Test URL ending with 'runs' but no ID."""
        url = "https://github.com/owner/repo/actions/runs"
        assert _extract_run_id_from_url(url) is None

    def test_edge_case_invalid_url_format(self):
        """Test completely invalid URL format."""
        url = "not-a-url-at-all"
        assert _extract_run_id_from_url(url) is None

    def test_edge_case_actions_runs_in_domain(self):
        """Test URL with 'actions/runs' in domain name (shouldn't match)."""
        url = "https://actions-runs.example.com/some/path"
        assert _extract_run_id_from_url(url) is None

    def test_robustness_very_long_run_id(self):
        """Test with very long run ID (should still work)."""
        url = "https://github.com/owner/repo/actions/runs/999999999999999999"
        assert _extract_run_id_from_url(url) == 999999999999999999

    def test_robustness_leading_trailing_slashes(self):
        """Test that malformed URLs with multiple slashes return None."""
        url = "https://github.com///owner//repo//actions//runs//123456///"
        # This malformed URL should return None since it's not a valid GitHub Actions URL
        assert _extract_run_id_from_url(url) is None


# Regression tests for the old split() method issues
class TestRegressionFromSplitMethod:
    """Test cases that would have failed with the old split() approach."""

    def test_old_method_would_fail_empty_split(self):
        """Test case where split() would create empty strings."""
        # Old method: url.split("/runs/")[1].split("/")[0]
        # This would fail on URLs ending with /runs/
        url = "https://github.com/owner/repo/actions/runs/"
        # Old method would do: "".split("/")[0] -> ""
        # Then int("") would raise ValueError
        assert _extract_run_id_from_url(url) is None

    def test_old_method_would_fail_no_runs_segment(self):
        """Test case where split() would raise IndexError."""
        url = "https://github.com/owner/repo/actions/workflows/123"
        # Old method would try: ["https://github.com/owner/repo/actions/workflows/123"][1]
        # This would raise IndexError because split("/runs/") returns only 1 element
        assert _extract_run_id_from_url(url) is None

    def test_old_method_would_fail_multiple_runs(self):
        """Test case where split() behavior is unpredictable."""
        url = "https://github.com/runs/repo/actions/runs/123456"
        # Old method: split("/runs/") -> ["https://github.com", "/repo/actions", "/123456"]
        # Then [1].split("/")[0] -> "" (empty string from "/repo/actions")
        # Our new method correctly finds the actual run ID by looking for "actions/runs" pattern
        assert _extract_run_id_from_url(url) == 123456
