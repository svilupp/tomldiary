from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, cast

from pydantic_ai import Agent, Tool
from textprompts import Prompt

from .models import (
    ConversationItemDict,
    ConversationsStore,
    PreferenceItemDict,
    PreferencesStore,
)


@dataclass
class CompactionStats:
    """Snapshot of store statistics used to evaluate compaction triggers."""

    total_chars: int = 0
    largest_block: int = 0


@dataclass
class CompactionConfig:
    """Configuration controlling when automated compaction should run."""

    enabled: bool = False
    #: Trigger when the serialized store exceeds N characters. None or 0/non-positive = disabled.
    total_char_threshold: int | None = None
    #: Trigger when any single block exceeds N characters. None or 0/non-positive = disabled.
    segment_char_threshold: int | None = None
    #: Trigger every N user turns (conversations only). None or 0/non-positive = disabled.
    user_turn_interval: int | None = None
    #: Recurring daily schedule: fires at most once per calendar day, on the first
    #: ``should_run`` whose ``now`` is at/after the scheduled time-of-day with no run yet
    #: today. The date component is ignored; only the time-of-day matters. Naive datetimes
    #: (or ISO strings without an offset) are coerced to UTC. None = disabled.
    schedule_at: datetime | None = None
    cooldown_seconds: int = 0
    compact_preferences: bool = True
    compact_conversations: bool = True

    def __post_init__(self) -> None:
        schedule_at = cast(object, self.schedule_at)
        if isinstance(schedule_at, str):
            self.schedule_at = datetime.fromisoformat(schedule_at)
        elif schedule_at is None:
            self.schedule_at = None
        else:
            self.schedule_at = cast(datetime, schedule_at)
        # Coerce naive datetimes to aware UTC so comparisons against an aware ``now`` work.
        if self.schedule_at is not None and self.schedule_at.tzinfo is None:
            self.schedule_at = self.schedule_at.replace(tzinfo=UTC)

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

        # A falsy/non-positive threshold means "disabled" (only None used to disable before).
        if self.total_char_threshold and stats.total_chars >= self.total_char_threshold:
            triggered = True

        if self.segment_char_threshold and stats.largest_block >= self.segment_char_threshold:
            triggered = True

        if (
            store == "conversations"
            and self.user_turn_interval
            and turns_since_compaction is not None
            and turns_since_compaction >= self.user_turn_interval
        ):
            triggered = True

        if self.schedule_at is not None and self._schedule_due(now=now, last_run=last_run):
            triggered = True

        if not triggered:
            return False

        return not (
            last_run is not None
            and self.cooldown_seconds
            and now - last_run < timedelta(seconds=self.cooldown_seconds)
        )

    def _schedule_due(self, *, now: datetime, last_run: datetime | None) -> bool:
        """Return True if the recurring daily schedule is due.

        Fires at most once per calendar day: when ``now`` is at/after the configured
        time-of-day and no run has happened yet today. All comparisons use the same UTC
        awareness as ``now`` (``schedule_at`` is coerced to aware UTC in ``__post_init__``).
        """

        assert self.schedule_at is not None  # gated by caller
        # Today's occurrence of the scheduled time-of-day, in ``now``'s timezone.
        today_target = now.replace(
            hour=self.schedule_at.hour,
            minute=self.schedule_at.minute,
            second=self.schedule_at.second,
            microsecond=self.schedule_at.microsecond,
        )
        if now < today_target:
            return False
        # Already ran at/after today's target → don't fire again today.
        return last_run is None or last_run < today_target


@dataclass
class CompactionDeps:
    """Dependencies passed into the compaction agent."""

    prefs: PreferencesStore
    convs: ConversationsStore
    include_preferences: bool
    include_conversations: bool
    actor_label: str = "compactor"

    def preference_blocks(self) -> list[tuple[str, PreferenceItemDict]]:
        if not self.include_preferences:
            return []
        blocks: list[tuple[str, PreferenceItemDict]] = []
        for cat, items in self.prefs.get("preferences", {}).items():
            for pref_id, data in items.items():
                blocks.append((f"{cat}/{pref_id}", data))
        return blocks

    def conversation_blocks(self) -> list[tuple[str, ConversationItemDict]]:
        if not self.include_conversations:
            return []
        conversations = self.convs.get("conversations")
        if not conversations:
            return []
        blocks: list[tuple[str, ConversationItemDict]] = []
        for session_id, data in conversations.items():
            blocks.append((session_id, data))
        return blocks

    # ───────── preference helpers ─────────
    def _split_pref_block(self, block_id: str) -> tuple[str, str]:
        try:
            category, pref_id = block_id.split("/", 1)
        except ValueError as exc:  # pragma: no cover - defensive guard
            raise ValueError("Preference block id must be in 'category/id' format") from exc
        return category, pref_id

    def get_preference_block(self, block_id: str) -> PreferenceItemDict | dict[str, Any]:
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
    def get_conversation_block(self, session_id: str) -> ConversationItemDict | dict[str, Any]:
        if not self.include_conversations:
            raise ValueError("Conversation compaction disabled for this run")
        conversations = self.convs.get("conversations", {})
        return conversations.get(session_id, {})

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
        conversations = self.convs.get("conversations")
        if not conversations:
            return
        if session_id in conversations:
            del conversations[session_id]


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
