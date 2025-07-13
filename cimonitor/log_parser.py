"""Log parsing functionality for extracting step-specific logs."""

from typing import Any


class LogParser:
    @staticmethod
    def extract_step_logs(full_logs: str, failed_steps: list[dict[str, Any]]) -> dict[str, str]:
        """Extract log sections for specific failed steps using GitHub's step markers."""
        step_logs = {}
        log_lines = full_logs.split("\n")

        for step in failed_steps:
            step_name = step["name"]

            # Try exact name matching first
            step_content = LogParser._extract_step_by_exact_name(log_lines, step_name)
            if step_content:
                step_logs[step_name] = step_content
                continue

            # Fallback: try partial name matching
            step_content = LogParser._extract_step_by_partial_name(log_lines, step_name)
            if step_content:
                step_logs[step_name] = step_content

        return step_logs

    @staticmethod
    def _extract_step_by_exact_name(log_lines: list[str], step_name: str) -> str | None:
        """Extract step logs using exact name matching."""
        step_lines = []
        capturing = False

        for i, line in enumerate(log_lines):
            # Early return if we find the exact step
            if f"##[group]Run {step_name}" in line:
                capturing = True
                step_lines.append(line)
                continue

            if not capturing:
                continue

            step_lines.append(line)

            # Stop capturing when we hit the endgroup for this step
            if "##[endgroup]" in line:
                # Continue capturing a few more lines for errors that appear after endgroup
                LogParser._capture_post_endgroup_lines(log_lines, i, step_lines)
                break

        return "\n".join(step_lines) if step_lines else None

    @staticmethod
    def _extract_step_by_partial_name(log_lines: list[str], step_name: str) -> str | None:
        """Extract step logs using partial name matching as fallback."""
        keywords = [word for word in step_name.split() if len(word) > 3]
        if not keywords:
            return None

        for i, line in enumerate(log_lines):
            # Look for key words from the step name in group markers
            if "##[group]Run" not in line:
                continue

            if not any(word.lower() in line.lower() for word in keywords):
                continue

            step_lines = [line]

            # Capture until endgroup
            for j in range(i + 1, len(log_lines)):
                next_line = log_lines[j]
                step_lines.append(next_line)

                if "##[endgroup]" in next_line:
                    # Get a few more lines for error context
                    LogParser._capture_post_endgroup_lines(log_lines, j, step_lines)
                    break

            return "\n".join(step_lines) if step_lines else None

        return None

    @staticmethod
    def _capture_post_endgroup_lines(
        log_lines: list[str], endgroup_index: int, step_lines: list[str]
    ) -> None:
        """Capture additional lines after ##[endgroup] for error context."""
        for k in range(endgroup_index + 1, min(endgroup_index + 10, len(log_lines))):
            error_line = log_lines[k]
            step_lines.append(error_line)

            # Stop if we hit another group or significant marker
            if "##[group]" in error_line or "Post job cleanup" in error_line:
                break

    @staticmethod
    def filter_error_lines(step_log: str) -> list[str]:
        """Filter step logs to show only error-related content."""
        step_lines = step_log.split("\n")
        shown_lines = []

        error_keywords = ["error", "failed", "failure", "❌", "✗", "exit code", "##[error]"]

        for line in step_lines:
            # Early continue for empty lines
            if not line.strip():
                continue

            # Include lines with error keywords
            if any(keyword in line.lower() for keyword in error_keywords):
                shown_lines.append(line)
                continue

            # Include GitHub Actions markers
            if "##[group]" in line or "##[endgroup]" in line:
                shown_lines.append(line)
                continue

            # Include non-timestamp lines (command output, not just timestamps)
            if not line.startswith("2025-"):
                shown_lines.append(line)

        return shown_lines
