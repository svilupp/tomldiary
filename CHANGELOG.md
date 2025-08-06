# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.0.3] - 2025-08-06

### Changed
- **BREAKING**: Renamed `TOMLDiary` class to `Diary` (backwards compatibility maintained via alias)
- Updated data model version to v0.3 with automatic migration from v0.2
- Enhanced the generic prompt for `build_extractor()` and the tool descriptions
- Enhanced `upsert_preference()` workflow: removed boost parameter, auto-increment by default

### Added
- Pretty printing utilities (`PreferencesPrinter`, `ConversationsPrinter`) and diary methods `pretty_preferences()` and `pretty_conversations()` for convenience



## [0.0.1] - 2025-07-20

### Added
- Initial release of tomldiary