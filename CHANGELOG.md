# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.8.0] - 2025-10-30

### Changed
- Added comprehensive type hints to all public APIs and core modules
- Configured mypy for strict type checking

## [0.7.0] - 2025-10-26

### Added
- Added py.typed marker file for PEP 561 compliance, enabling type checking for downstream users

## [0.6.0] - 2025-10-23

### Changed
- Thread-safety improvements in `MemoryWriter` for Python 3.14 no-GIL compatibility: added `asyncio.Lock()` to protect counter operations, ensuring race-free statistics and consistent shutdown behavior
- Improved `MemoryWriter.close()` with protection to prevent deadlock if workers fail to drain queue
- FirestoreBackend now supports `credentials_dict` parameter for passing service account credentials as dict

## [0.5.0] - 2025-10-15

### Updated
- Backend Interface Standardization: LocalBackend now implements full 6-method interface (`exists`, `delete`, `delete_user`, `list_users`) matching FirestoreBackend for complete interchangeability
- Comprehensive backend interface documentation with implementation guidelines

## [0.4.0] - 2025-10-15

### Changed
- Fixed up `None` handling in FirestoreBackend tests
- Moved `loguru` to core dependencies and centralized logging configuration, optional ENVs for easier configuration `TOMLDIARY_LOG_LEVEL` and `TOMLDIARY_LOG_FILE`

## [0.3.0] - 2025-10-15

### Added
- Type schema utilities (`show_preferences_schema()`, `show_conversations_schema()`) for inspecting preference table structures in multiple formats (pretty/json/python) - useful for API design and documentation
- Safe data loading with `PreferenceLoader` and `ConversationLoader` using Pydantic TypeAdapter for runtime validation - see `examples/type_safety_demo.py`
- CLI interface for quick schema inspection: `tomldiary schema preferences <path:Class>` and `tomldiary schema conversations` commands with `--format` option (or `-f json` short option)

### Fixed
- FirestoreBackend now correctly handles empty string content (previously returned None for empty files)

## [0.2.0] - 2025-10-14

### Added
- Added `FirestoreBackend` to support Google Cloud Firestore for saving memories (see `examples/firestore_example.py` for usage or `scripts/firestore_test_connection.py` for testing your setup)
- Built-in observability for `MemoryWriter`: added `stats()` method and `is_running` property and metrics (queue depth, worker utilization, throughput, error rates)

## [0.1.0] - 2025-10-12

### Added
- Optional compaction ("summarization") agent and configuration (to compress the memory after X turns or if character limit is reached), see `examples/compaction_demo_quick.py`

### Updated
- Updated pydantic-ai dependency to 1.0 and textprompts dependency to 1.0
- Updated extractor prompt to version 3.0 with time context

### Added

## [0.0.5] - 2025-01-02

### Updated
- Time awareness for extractor agent: current time (rounded to nearest 15 minutes) is now provided to the agent via `{current_time}` placeholder
- Updated extractor prompt to version 3.0 with time context

## [0.0.4] - 2025-08-10

### Updated
- Renamed utility `build_extractor` to `extractor_agent`

### Added
- Added `fallback_on` and `fallback_retries` parameters to `extractor_agent` to support auto-retry on common errors
- Added `extractor_prompt_check` utility to validate custom extractor prompts (can be provided to `extractor_agent(..., prompt_template=...)` parameter)
- Default model loaded from `EXTRACTOR_MODEL` env when provided

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
