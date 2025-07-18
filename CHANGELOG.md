# Changelog

<!-- loosely based on https://keepachangelog.com/en/1.0.0/ -->

## Unreleased

### Added

## 0.1.7 - TBD

### Added

## 0.1.6 - 2025-07-18

### Added
- Merge conflict detection for pull requests

## 0.1.5 - 2025-07-17

### Added
- Initial 10-second wait in watch command before reporting "no workflow runs" to allow time for CI jobs to appear

## 0.1.4 - 2025-07-16

### Added
- Comprehensive log group parsing with nesting support and proper indentation
- Deterministic step-by-step status tracking using GitHub API data
- Filtering options: --step-filter, --group-filter, --show-groups (default: true)
- Concrete example for --group-filter usage in help text
- Timestamp removal for cleaner log output

### Fixed
- Duplicate group display when multiple jobs contain same groups
- Log parsing fallback to show full logs when step parsing fails

### Changed
- Enhanced log display with group summary and step status information
- Improved error log filtering and presentation

## 0.1.3 - 2025-07-16

### Added
- Improved release process documentation
- Fixed version management workflow

### Changed
- Corrected release workflow to maintain proper version sequencing

## 0.1.2 - 2025-07-16

### Added
- --repo argument for specifying repository
- Log parsing fallback improvements
- Better command-line documentation

### Changed
- Refactored codebase for improved maintainability

## 0.1.0 - 2025-07-13

Initial release
