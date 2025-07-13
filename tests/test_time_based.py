"""Time-based tests for CI Monitor."""

from datetime import datetime
from zoneinfo import ZoneInfo

import pytest


def test_pacific_evening_gate():
    """Test that only passes after 11pm Pacific time.

    This test is designed to demonstrate the retry functionality.
    It will fail during the day and only pass after 11pm Pacific.
    """
    # Get current time in Pacific timezone
    pacific_tz = ZoneInfo("America/Los_Angeles")
    now_pacific = datetime.now(pacific_tz)

    # Check if it's after 11pm (23:00) Pacific time
    if now_pacific.hour >= 23:
        # It's after 11pm Pacific, test should pass
        assert True, f"✅ Test passes! Current Pacific time: {now_pacific.strftime('%H:%M:%S')}"
    else:
        # It's before 11pm Pacific, test should fail
        pytest.fail(
            f"❌ Test fails! Current Pacific time: {now_pacific.strftime('%H:%M:%S')} "
            f"(need to wait until 23:00 Pacific for this test to pass)"
        )
