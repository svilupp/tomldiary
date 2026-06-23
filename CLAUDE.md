# CLAUDE.md

`tomldiary` — a TOML-based memory system for AI agents. An LLM "extractor" agent
reads each conversation turn and curates durable user **preferences** + rolling
conversation **summaries**, stored as human-readable TOML behind a pluggable backend.

## Workflow — use the make commands

Run these (not raw `ruff`/`mypy`/`pytest`); they're **quiet on success** to save tokens.

- `make ci` — full gate (lint + format-check + typecheck + test); prints one `OK`/`FAIL` per leg. Run before declaring work done.
- `make lint` / `make typecheck` / `make format-check` — silent unless they fail (then full output).
- `make format` — autofix + reformat (mutates files; verbose).
- `make test` — pytest + coverage (verbose; use when you need the detail).

Commands mirror `.github/workflows/ci.yml`. Python via `uv run`; requires ≥3.11.

## Pattern index (file:line)

**Public API** — `src/tomldiary/__init__.py:29` (`__all__`); everything below is re-exported here.

**Core orchestration** — `src/tomldiary/diary.py`
- `Diary` `:31`, `__init__` `:32` (wires backend + pref-table class → extractor agent + optional compactor). `TOMLDiary` alias `:464`.
- `update_memory` `:329` — **the main hook**: ensure_session → build_deps → run extractor agent → enforce per-category limits → maybe compact → save.
- `build_deps` `:130`, `ensure_session` `:153` (evicts oldest at `max_conversations`), `_maybe_run_compactor` `:224`.
- Read accessors: `preferences` `:394`, `last_conversations` `:405`, `pretty_preferences` `:424`, `pretty_conversations` `:442`.

**Extractor agent factory** — `src/tomldiary/extractor_factory.py`
- `extractor_agent` `:72` — builds a `pydantic_ai.Agent`, `FallbackModel`-wrapped (model from `EXTRACTOR_MODEL` env, default `openai:gpt-5-mini`).
- Dynamic system prompt `:151` — timestamp computed **fresh per run** (do not bake a stale time into a long-lived factory; this is the current branch's fix). `_round_current_time` `:27` floors to 15 min to preserve prompt caching.
- TOML round-trip `@agent.output_validator` `:158` (rejects edits that don't serialize). `build_extractor` `:175` legacy alias.

**Agent tools** (LLM-callable; not unit-tested) — `src/tomldiary/tools.py`
- Writes: `upsert_preference` `:122` (create/update/boost; force-create with `id="new"`), `forget_preference` `:253`, `update_conversation_summary` `:276`.
- Reads: `list_categories` `:16`, `list_preferences` `:25`, `list_conversation_summary` `:70`.
- Dedup guard: `_find_similar_preferences` `:94` (`thefuzz.token_set_ratio`, threshold 70). Compaction tools: `src/tomldiary/compaction_tools.py`.

**Models / on-disk TOML shape** — `src/tomldiary/models.py`
- `_MODEL_VERSION = "0.3"` `:9` (bump → migration path in `diary._load_convs:81`).
- TypedDicts `PreferencesStore` `:48`, `ConversationsStore` `:55` (`_meta` + body). Pydantic `PreferenceItem` `:71`, `ConversationItem` `:94`. `MemoryDeps` `:113`.

**Backends** — `src/tomldiary/backends/`
- `BackendProtocol` (6 async methods) `base.py:39`; id safety `validate_identifier` `base.py:11`.
- `LocalBackend` `local.py:12` — atomic temp-write + rename `:52`, per-path `asyncio.Lock`. `FirestoreBackend` `firestore.py:53` (optional `[firestore]` extra; lazy import `backends/__init__.py:9`).

**Async write queue** — `src/tomldiary/writer.py`
- `MemoryWriter` `:46` (worker pool over a bounded queue): `submit` `:72`, `stats` `:167`, `close` `:229` (bounded by `SHUTDOWN_TIMEOUT`). `fire_and_forget` `:26`, `shutdown_all_background_tasks` `:317`.

**Compaction** — `src/tomldiary/compaction.py`
- `CompactionConfig` `:28` (+ `should_run` `:60`: char/segment/turn/daily-schedule triggers + cooldown; disabled by default). `CompactionDeps` block helpers `:130`. `compactor_agent` `:233`.

**Other** — Loaders (validate stored TOML → Pydantic) `loaders.py:18`/`:143`/`:221`/`:241`. Schema inspection `schema.py:18`. CLI `cli.py:16` (entry `cli:131`). Pretty-printers `pretty_print.py`. Logging `logging.py` (`get_logger`; env `TOMLDIARY_LOG_LEVEL`, `TOMLDIARY_LOG_FILE`). Prompts: `src/tomldiary/prompts/{extractor,compactor}_prompt.txt` (textprompts; required placeholders `{categories_doc}`, `{current_time}`).

## Conventions

- **Engine-managed fields** are `_`-prefixed in TOML (`_count`, `_created`, `_updated`, `_created_by`, `_updated_by`, `_turns`) and exposed as Pydantic aliases; the LLM only sets `text`/`contexts`/`summary`/`keywords`.
- **`context_now`** threads through `update_memory`/`build_deps`/tools to override "now" for testing/simulating past/future memories; falls back to `datetime.now(UTC)`. Keep it timezone-aware.
- Async throughout; backends do file I/O via `asyncio.to_thread`. Modules use `from __future__ import annotations`.
- ruff line-length 100; mypy is gradually-strict (per-module overrides in `pyproject.toml`). Some example/legacy files are excluded from ruff/mypy there.
