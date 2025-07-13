"""Test file with an intentionally failing test."""


def test_intentional_failure():
    """This test is designed to fail for demonstration purposes."""
    assert False, "you found the failure, now delete this test"  # noqa: B011
