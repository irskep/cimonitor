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
            step_lines = []

            # GitHub Actions uses ##[group]Run STEP_NAME and ##[endgroup] as boundaries
            # Look for the step by name in the ##[group]Run pattern
            capturing = False

            for i, line in enumerate(log_lines):
                # Start capturing when we find the step's group marker
                if f"##[group]Run {step_name}" in line:
                    capturing = True
                    step_lines.append(line)
                elif capturing:
                    step_lines.append(line)

                    # Stop capturing when we hit the endgroup for this step
                    if "##[endgroup]" in line:
                        # Continue capturing a few more lines for errors that appear after endgroup
                        for j in range(i + 1, min(i + 10, len(log_lines))):
                            next_line = log_lines[j]
                            step_lines.append(next_line)

                            # Stop if we hit another group or significant marker
                            if "##[group]" in next_line or "Post job cleanup" in next_line:
                                break
                        break

            if step_lines:
                step_logs[step_name] = "\n".join(step_lines)
            else:
                # Fallback: try partial name matching for steps with complex names
                for i, line in enumerate(log_lines):
                    # Look for key words from the step name in group markers
                    if "##[group]Run" in line and any(
                        word.lower() in line.lower() for word in step_name.split() if len(word) > 3
                    ):
                        capturing = True
                        step_lines = [line]

                        # Capture until endgroup
                        for j in range(i + 1, len(log_lines)):
                            next_line = log_lines[j]
                            step_lines.append(next_line)

                            if "##[endgroup]" in next_line:
                                # Get a few more lines for error context
                                for k in range(j + 1, min(j + 10, len(log_lines))):
                                    error_line = log_lines[k]
                                    step_lines.append(error_line)
                                    if (
                                        "##[group]" in error_line
                                        or "Post job cleanup" in error_line
                                    ):
                                        break
                                break

                        if step_lines:
                            step_logs[step_name] = "\n".join(step_lines)
                        break

        return step_logs

    @staticmethod
    def filter_error_lines(step_log: str) -> list[str]:
        """Filter step logs to show only error-related content."""
        step_lines = step_log.split("\n")
        shown_lines = []

        for line in step_lines:
            # Show lines with error indicators or important info
            if (
                any(
                    keyword in line.lower()
                    for keyword in [
                        "error",
                        "failed",
                        "failure",
                        "❌",
                        "✗",
                        "exit code",
                        "##[error]",
                    ]
                )
                or "##[group]" in line
                or "##[endgroup]" in line
                or not line.startswith("2025-")
            ):  # Include non-timestamp lines
                shown_lines.append(line)

        return shown_lines
