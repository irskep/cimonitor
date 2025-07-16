# Changelog

<!-- loosely based on https://keepachangelog.com/en/1.0.0/ -->

## Unreleased

### Added

## 0.1.5 - TBD

### Added

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

## 0.1.0 - 2025-01-13

Initial release
