from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

from pydantic_ai import Agent, Tool
from textprompts import Prompt


@dataclass
class CompactionStats:
    """Snapshot of store statistics used to evaluate compaction triggers."""

    total_chars: int = 0
    largest_block: int = 0


@dataclass
class CompactionConfig:
    """Configuration controlling when automated compaction should run."""

    enabled: bool = False
    total_char_threshold: int | None = None
    segment_char_threshold: int | None = None
    user_turn_interval: int | None = None
    schedule_at: datetime | None = None
    cooldown_seconds: int = 0
    compact_preferences: bool = True
    compact_conversations: bool = True

    def __post_init__(self) -> None:
        if isinstance(self.schedule_at, str):
            self.schedule_at = datetime.fromisoformat(self.schedule_at)

    def should_run(
        self,
        *,
        store: str,
        stats: CompactionStats,
        last_run: datetime | None,
        turns_since_compaction: int | None,
        now: datetime,
    ) -> bool:
        """Return True if compaction should run for the provided store."""

        if not self.enabled:
            return False

        if store == "preferences" and not self.compact_preferences:
            return False
        if store == "conversations" and not self.compact_conversations:
            return False

        triggered = False

        if self.total_char_threshold is not None and stats.total_chars >= self.total_char_threshold:
            triggered = True

        if (
            self.segment_char_threshold is not None
            and stats.largest_block >= self.segment_char_threshold
        ):
            triggered = True

        if (
            store == "conversations"
            and self.user_turn_interval is not None
            and turns_since_compaction is not None
            and turns_since_compaction >= self.user_turn_interval
        ):
            triggered = True

        if (
            self.schedule_at is not None
            and now >= self.schedule_at
            and (last_run is None or last_run < self.schedule_at)
        ):
            triggered = True

        if not triggered:
            return False

        return not (
            last_run is not None
            and self.cooldown_seconds
            and now - last_run < timedelta(seconds=self.cooldown_seconds)
        )


@dataclass
class CompactionDeps:
    """Dependencies passed into the compaction agent."""

    prefs: dict
    convs: dict
    include_preferences: bool
    include_conversations: bool
    actor_label: str = "compactor"

    def preference_blocks(self) -> list[tuple[str, dict]]:
        if not self.include_preferences:
            return []
        blocks: list[tuple[str, dict]] = []
        for cat, items in self.prefs.get("preferences", {}).items():
            for pref_id, data in items.items():
                blocks.append((f"{cat}/{pref_id}", data))
        return blocks

    def conversation_blocks(self) -> list[tuple[str, dict]]:
        if not self.include_conversations:
            return []
        blocks: list[tuple[str, dict]] = []
        for session_id, data in self.convs.get("conversations", {}).items():
            blocks.append((session_id, data))
        return blocks

    # ───────── preference helpers ─────────
    def _split_pref_block(self, block_id: str) -> tuple[str, str]:
        try:
            category, pref_id = block_id.split("/", 1)
        except ValueError as exc:  # pragma: no cover - defensive guard
            raise ValueError("Preference block id must be in 'category/id' format") from exc
        return category, pref_id

    def get_preference_block(self, block_id: str) -> dict:
        if not self.include_preferences:
            raise ValueError("Preference compaction disabled for this run")
        category, pref_id = self._split_pref_block(block_id)
        return self.prefs.get("preferences", {}).get(category, {}).get(pref_id, {})

    def rewrite_preference_block(
        self,
        block_id: str,
        *,
        text: str,
        contexts: Iterable[str] | None = None,
    ) -> None:
        block = self.get_preference_block(block_id)
        if not block:
            raise KeyError(f"Preference block '{block_id}' not found")
        block["text"] = text
        if contexts is not None:
            block["contexts"] = list(contexts)
        block["_updated"] = datetime.now(UTC).isoformat()
        block["_updated_by"] = self.actor_label

    def delete_preference_block(self, block_id: str) -> None:
        if not self.include_preferences:
            raise ValueError("Preference compaction disabled for this run")
        category, pref_id = self._split_pref_block(block_id)
        prefs_root = self.prefs.get("preferences", {})
        cat_tbl = prefs_root.get(category, {})
        if pref_id in cat_tbl:
            del cat_tbl[pref_id]
            if not cat_tbl:
                prefs_root.pop(category, None)

    # ───────── conversation helpers ─────────
    def get_conversation_block(self, session_id: str) -> dict:
        if not self.include_conversations:
            raise ValueError("Conversation compaction disabled for this run")
        return self.convs.get("conversations", {}).get(session_id, {})

    def rewrite_conversation_block(
        self,
        session_id: str,
        *,
        summary: str,
        keywords: Iterable[str] | None = None,
    ) -> None:
        block = self.get_conversation_block(session_id)
        if not block:
            raise KeyError(f"Conversation block '{session_id}' not found")
        block["summary"] = summary
        if keywords is not None:
            block["keywords"] = list(keywords)
        block["_updated"] = datetime.now(UTC).isoformat()

    def delete_conversation_block(self, session_id: str) -> None:
        if not self.include_conversations:
            raise ValueError("Conversation compaction disabled for this run")
        convs_root = self.convs.get("conversations", {})
        if session_id in convs_root:
            del convs_root[session_id]


def compactor_agent(
    model_name: str | None = None,
    prompt_template: str | Path | Prompt | None = None,
) -> Agent[CompactionDeps]:
    """Build an agent responsible for compaction sweeps."""

    # Import here to avoid circular import at module level
    from . import compaction_tools

    if prompt_template is None:
        prompt_template = Path(__file__).parent / "prompts" / "compactor_prompt.txt"

    if isinstance(prompt_template, Prompt):
        prompt_obj = prompt_template
    else:
        prompt_obj = Prompt.from_path(Path(prompt_template), meta="allow")

    system_prompt = prompt_obj.prompt

    tools: list[Tool[CompactionDeps]] = [
        Tool(compaction_tools.list_preference_blocks, takes_ctx=True),
        Tool(compaction_tools.get_preference_block, takes_ctx=True),
        Tool(compaction_tools.rewrite_preference_block, takes_ctx=True),
        Tool(compaction_tools.delete_preference_block, takes_ctx=True),
        Tool(compaction_tools.list_conversation_blocks, takes_ctx=True),
        Tool(compaction_tools.get_conversation_block, takes_ctx=True),
        Tool(compaction_tools.rewrite_conversation_block, takes_ctx=True),
        Tool(compaction_tools.delete_conversation_block, takes_ctx=True),
    ]

    model_name = model_name or "openai:gpt-5-mini"

    return Agent(model_name, deps_type=CompactionDeps, tools=tools, system_prompt=system_prompt)
