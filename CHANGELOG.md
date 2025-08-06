# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.0.3] - 2025-08-06

### Changed
- **BREAKING**: Renamed `TOMLDiary` class to `Diary` (backwards compatibility maintained via alias)
- Updated data model version to v0.3 with automatic migration from v0.2
- Improved conversation storage structure with nested `conversations` section

### Added  
- Pretty printing utilities (`PreferencesPrinter`, `ConversationsPrinter`)
- Automatic data migration from v0.2 to v0.3 format
- Enhanced conversation model with `updated` timestamp field
- New pretty print functions for better data visualization

### Fixed
- Updated all examples and documentation to use new `Diary` class name
- Improved conversation data access patterns


## [0.0.1] - 2025-07-20

### Added
- Initial release of tomldiary