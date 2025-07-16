"""Log parsing functionality for extracting step-specific logs."""

from typing import Any

from .constants import (
    CURRENT_YEAR_PREFIX,
    MIN_WORD_LENGTH_PARTIAL,
    MIN_WORD_LENGTH_SEMANTIC,
    POST_ENDGROUP_LINES,
    TIMESTAMP_TOLERANCE_SECONDS,
)


class LogParser:
    @staticmethod
    def extract_step_logs(
        full_logs: str, failed_steps: list[dict[str, Any]], all_steps: list[dict[str, Any]] = None
    ) -> dict[str, str]:
        """Extract log sections for specific failed steps using exact name matching only."""
        step_logs = {}
        log_lines = full_logs.split("\n")

        for step in failed_steps:
            step_name = step["name"]

            # Try exact name matching only - no heuristics
            step_content = LogParser._extract_step_by_exact_name(log_lines, step_name)
            if step_content:
                step_logs[step_name] = step_content

        return step_logs

    @staticmethod
    def parse_log_groups(full_logs: str) -> list[dict[str, str]]:
        """Parse all ##[group] sections in the logs and return metadata with nesting."""
        log_lines = full_logs.split("\n")
        groups = []
        group_stack = []

        for i, line in enumerate(log_lines):
            if "##[group]" in line:
                # Extract the group name
                if "##[group]Run " in line:
                    # For Run commands, extract the command
                    group_name = (
                        line.split("##[group]Run ", 1)[1] if "##[group]Run " in line else line
                    )
                    group_type = "step"
                else:
                    # For other groups, extract the group name
                    group_name = line.split("##[group]", 1)[1] if "##[group]" in line else line
                    group_type = "setup"

                # Extract timestamp if present
                timestamp = ""
                if line.startswith("20") and "T" in line and "Z" in line:
                    timestamp = line.split("Z")[0] + "Z"

                # Track nesting level
                nesting_level = len(group_stack)
                group_info = {
                    "name": group_name.strip(),
                    "type": group_type,
                    "timestamp": timestamp,
                    "line_number": i + 1,
                    "nesting_level": nesting_level,
                    "parent": group_stack[-1]["name"] if group_stack else None,
                }

                groups.append(group_info)
                group_stack.append(group_info)

            elif "##[endgroup]" in line and group_stack:
                group_stack.pop()

        return groups

    @staticmethod
    def get_step_status_info(all_steps: list[dict], failed_steps: list[dict]) -> dict[str, dict]:
        """Get deterministic status information for all steps."""
        step_status = {}

        for step in all_steps:
            step_name = step.get("name", "Unknown")
            step_status[step_name] = {
                "status": step.get("status", "unknown"),
                "conclusion": step.get("conclusion", "unknown"),
                "number": step.get("number"),
                "started_at": step.get("started_at"),
                "completed_at": step.get("completed_at"),
                "is_failed": step in failed_steps,
            }

        return step_status

    @staticmethod
    def _extract_step_by_timestamp(
        log_lines: list[str], step_name: str, started_at: str
    ) -> str | None:
        """Extract step logs using exact timestamp matching with GitHub API step start time."""
        from datetime import datetime

        try:
            # Parse the step start time from GitHub API
            step_start = datetime.fromisoformat(started_at.replace("Z", "+00:00"))

            # Look for exact timestamp match in logs
            for i, line in enumerate(log_lines):
                # Look for ##[group]Run markers
                if "##[group]Run " not in line:
                    continue

                # Extract timestamp from log line
                if line.startswith("20") and "T" in line and "Z" in line:
                    try:
                        # Extract timestamp (format: 2025-07-16T03:13:13.5152643Z)
                        log_timestamp_str = line.split("Z")[0] + "Z"
                        log_timestamp = datetime.fromisoformat(
                            log_timestamp_str.replace("Z", "+00:00")
                        )

                        # Only accept exact matches within 1 second (to account for subsecond precision)
                        time_diff = abs((log_timestamp - step_start).total_seconds())

                        if time_diff <= TIMESTAMP_TOLERANCE_SECONDS:
                            # Extract this section
                            step_lines = [line]

                            # Capture until endgroup
                            for j in range(i + 1, len(log_lines)):
                                next_line = log_lines[j]
                                step_lines.append(next_line)

                                if "##[endgroup]" in next_line:
                                    # Continue capturing a few more lines for errors that appear after endgroup
                                    LogParser._capture_post_endgroup_lines(log_lines, j, step_lines)
                                    break

                            return "\n".join(step_lines) if step_lines else None

                    except (ValueError, TypeError):
                        # Skip lines with invalid timestamp format
                        continue

        except (ValueError, TypeError):
            # If timestamp parsing fails, fall back to other methods
            pass

        return None

    @staticmethod
    def _extract_step_by_number_with_context(
        log_lines: list[str], step_number: int, step_name: str, all_steps: list[dict[str, Any]]
    ) -> str | None:
        """Extract step logs using semantic matching between API step name and log markers."""
        # For "Run tests", look for test-related log markers
        if "test" in step_name.lower():
            # Find Run markers that contain test-related keywords (be specific to avoid false matches)
            test_keywords = ["test", "pytest", "jest", "spec"]

            for i, line in enumerate(log_lines):
                if "##[group]Run " in line:
                    line_lower = line.lower()
                    if any(keyword in line_lower for keyword in test_keywords):
                        # Extract this section
                        step_lines = [line]

                        # Capture until endgroup
                        for j in range(i + 1, len(log_lines)):
                            next_line = log_lines[j]
                            step_lines.append(next_line)

                            if "##[endgroup]" in next_line:
                                # Continue capturing a few more lines for errors that appear after endgroup
                                LogParser._capture_post_endgroup_lines(log_lines, j, step_lines)
                                break

                        return "\n".join(step_lines) if step_lines else None

        # For other step types, try to match by semantic similarity
        # Extract key words from step name (excluding "Run")
        step_words = [
            word.lower()
            for word in step_name.replace("Run ", "").split()
            if len(word) > MIN_WORD_LENGTH_SEMANTIC
        ]

        if step_words:
            for i, line in enumerate(log_lines):
                if "##[group]Run " in line:
                    line_lower = line.lower()
                    # Check if any key words from step name appear in the log marker
                    if any(word in line_lower for word in step_words):
                        # Extract this section
                        step_lines = [line]

                        # Capture until endgroup
                        for j in range(i + 1, len(log_lines)):
                            next_line = log_lines[j]
                            step_lines.append(next_line)

                            if "##[endgroup]" in next_line:
                                # Continue capturing a few more lines for errors that appear after endgroup
                                LogParser._capture_post_endgroup_lines(log_lines, j, step_lines)
                                break

                        return "\n".join(step_lines) if step_lines else None

        return None

    @staticmethod
    def _extract_step_by_number(
        log_lines: list[str], step_number: int, step_name: str
    ) -> str | None:
        """Extract step logs using step number to find the correct ##[group]Run section.

        Note: This requires access to the full job steps to determine which Run marker
        corresponds to the failed step. For now, this is a placeholder that should be
        enhanced to use the job context.
        """
        # This is a simplified approach - we would need the full job steps context
        # to properly map API step numbers to log Run markers

        # For the common case where step_name starts with "Run", we can try to find
        # the corresponding log marker by counting Run steps
        if not step_name.startswith("Run"):
            return None

        # Find all ##[group]Run markers
        run_markers = []
        for i, line in enumerate(log_lines):
            if "##[group]Run " in line:
                run_markers.append(i)

        # This is a heuristic - would be better to use proper job context
        # For now, assume the step_number corresponds roughly to run marker position
        # This works for many cases but isn't perfect

        # Try different mapping strategies
        possible_indices = [
            step_number - 1,  # Direct mapping (step 5 -> run 5)
            len([i for i in range(1, step_number) if i <= len(run_markers)])
            - 1,  # Count preceding runs
        ]

        for run_index in possible_indices:
            if 0 <= run_index < len(run_markers):
                step_start_index = run_markers[run_index]

                # Extract the section from this marker
                step_lines = [log_lines[step_start_index]]

                # Capture until endgroup
                for j in range(step_start_index + 1, len(log_lines)):
                    next_line = log_lines[j]
                    step_lines.append(next_line)

                    if "##[endgroup]" in next_line:
                        # Continue capturing a few more lines for errors that appear after endgroup
                        LogParser._capture_post_endgroup_lines(log_lines, j, step_lines)
                        break

                content = "\n".join(step_lines)
                # Basic validation - check if this looks like the right step
                if step_name.lower().replace(" ", "") in content.lower().replace(" ", ""):
                    return content

        return None

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
        keywords = [word for word in step_name.split() if len(word) > MIN_WORD_LENGTH_PARTIAL]
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
        for k in range(
            endgroup_index + 1, min(endgroup_index + POST_ENDGROUP_LINES, len(log_lines))
        ):
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
            if not line.startswith(CURRENT_YEAR_PREFIX):
                shown_lines.append(line)

        return shown_lines
