# Changelog

<!-- loosely based on https://keepachangelog.com/en/1.0.0/ -->

## Unreleased

## 0.1.0 - 2025-01-13

### Added

- Initial release of CI Monitor
- GitHub CI workflow monitoring with real-time status updates
- Support for targeting commits, branches, and pull requests
- Step-level failure detection without downloading entire logs
- Smart log filtering showing only error-related content
- Real-time CI status polling with fail-fast options (`--poll`, `--poll-until-failure`)
- Raw log access for deep debugging (`--raw-logs`, `--job-id`)
- Cross-platform support (Ubuntu, macOS) with Python 3.10+
- Modern packaging with hatchling and UV dependency management
- Comprehensive CLI with mutual exclusivity validation
- PyPI publishing automation with trusted publishing
- Automated version bumping with git tagging