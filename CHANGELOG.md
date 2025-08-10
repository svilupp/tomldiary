# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.0.4] - 2025-08-10

### Updated
- Renamed utility `build_extractor` to `extractor_agent`

### Added
- Added `fallback_on` and `fallback_retries` parameters to `extractor_agent` to support auto-retry on common errors
- Added `extractor_prompt_check` utility to validate custom extractor prompts (can be provided to `extractor_agent(..., prompt_template=...)` parameter)

## [0.0.3] - 2025-08-06

### Changed
- **BREAKING**: Renamed `TOMLDiary` class to `Diary` (backwards compatibility maintained via alias)
- Updated data model version to v0.3 with automatic migration from v0.2
- Enhanced the generic prompt for `build_extractor()` and the tool descriptions
- Enhanced `upsert_preference()` workflow: removed boost parameter, auto-increment by default

### Added
- Pretty printing utilities (`PreferencesPrinter`, `ConversationsPrinter`) and diary methods `pretty_preferences()` and `pretty_conversations()` for convenience

### Fixed
- Fixed `update_conversation_summary` tool to correctly access nested conversation structure, ensuring conversation summaries are properly persisted to disk
- Updated cooking show example to use direct `diary.update_memory()` calls for reliable memory persistence


## [0.0.4] - 2025-08-06

### Added
- `extractor_agent` with configurable retries and env-driven default model (default `openai:gpt-5-mini`)
- `extractor_prompt_check` helper and example usage

### Changed
- Documentation and examples updated to reference `extractor_agent`



## [0.0.1] - 2025-07-20

### Added
- Initial release of tomldiary
