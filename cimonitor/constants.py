"""Configuration constants for CI Monitor.

This module centralizes all magic numbers and configuration values
to improve maintainability and make the codebase more configurable.
"""

# Polling and timing constants
POLL_INTERVAL_SECONDS = 10
MAX_POLLS = 120  # 20 minutes total (120 * 10 seconds)
RETRY_SLEEP_SECONDS = 30

# Log parsing constants
POST_ENDGROUP_LINES = 10  # Lines to capture after ##[endgroup]
FALLBACK_LOG_LINES = 10  # Lines to show when step parsing fails
TIMESTAMP_TOLERANCE_SECONDS = 1.0  # Tolerance for timestamp matching

# GitHub API pagination
DEFAULT_PER_PAGE = 10
LARGE_PER_PAGE = 50

# Git/SHA constants
SHORT_SHA_LENGTH = 8
FULL_SHA_LENGTH = 40

# Log parsing thresholds
MIN_WORD_LENGTH_SEMANTIC = 2  # Minimum word length for semantic matching
MIN_WORD_LENGTH_PARTIAL = 3  # Minimum word length for partial matching

# Current year for timestamp filtering (should be made dynamic in future)
CURRENT_YEAR_PREFIX = "2025-"
