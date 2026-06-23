from datetime import UTC, datetime, timedelta
from typing import cast

import pytest

from tomldiary import compaction_tools
from tomldiary.compaction import CompactionConfig, CompactionDeps, CompactionStats
from tomldiary.models import ConversationsStore, PreferencesStore


class DummyCtx:
    """Mock RunContext for testing compaction tools."""

    def __init__(self, deps: CompactionDeps) -> None:
        self.deps = deps


def test_compaction_config_trigger_conditions():
    now = datetime.now(UTC)
    cfg = CompactionConfig(enabled=True, total_char_threshold=5, segment_char_threshold=10)
    stats = CompactionStats(total_chars=7, largest_block=3)
    assert cfg.should_run(
        store="preferences",
        stats=stats,
        last_run=None,
        turns_since_compaction=None,
        now=now,
    )

    # Cooldown respected
    cfg.cooldown_seconds = 60
    assert not cfg.should_run(
        store="preferences",
        stats=stats,
        last_run=now,
        turns_since_compaction=None,
        now=now + timedelta(seconds=10),
    )

    # Segment threshold triggers
    stats = CompactionStats(total_chars=1, largest_block=12)
    assert cfg.should_run(
        store="preferences",
        stats=stats,
        last_run=None,
        turns_since_compaction=None,
        now=now,
    )

    # Conversation user turns trigger
    cfg = CompactionConfig(enabled=True, user_turn_interval=2, compact_preferences=False)
    stats = CompactionStats(total_chars=0, largest_block=0)
    assert not cfg.should_run(
        store="conversations",
        stats=stats,
        last_run=None,
        turns_since_compaction=1,
        now=now,
    )
    assert cfg.should_run(
        store="conversations",
        stats=stats,
        last_run=None,
        turns_since_compaction=2,
        now=now,
    )

    # Schedule trigger is recurring-daily: at most once per calendar day, after the
    # configured time-of-day, when no run has happened yet today.
    # (Previously this asserted strict one-shot behavior, which was the bug.)
    base = datetime(2026, 6, 23, 0, 0, 0, tzinfo=UTC)
    target_time = base + timedelta(hours=8)  # 08:00 UTC time-of-day
    cfg = CompactionConfig(enabled=True, schedule_at=target_time)
    # Before today's target time-of-day: does not fire.
    assert not cfg.should_run(
        store="preferences",
        stats=stats,
        last_run=None,
        turns_since_compaction=None,
        now=base + timedelta(hours=7),
    )
    # At/after today's target with no prior run: fires.
    assert cfg.should_run(
        store="preferences",
        stats=stats,
        last_run=None,
        turns_since_compaction=None,
        now=base + timedelta(hours=9),
    )
    # Already ran today after the target: does not fire again the same day.
    assert not cfg.should_run(
        store="preferences",
        stats=stats,
        last_run=base + timedelta(hours=9),
        turns_since_compaction=None,
        now=base + timedelta(hours=10),
    )


def test_naive_schedule_at_does_not_crash_should_run():
    """Bug A: a naive ISO ``schedule_at`` must not crash when compared to aware ``now``."""
    cfg = CompactionConfig(enabled=True, schedule_at="2026-06-23T08:00:00")
    # schedule_at is coerced to aware UTC, so comparison against an aware now is safe.
    assert cfg.schedule_at is not None
    assert cfg.schedule_at.tzinfo is not None
    now = datetime(2026, 6, 23, 9, 0, 0, tzinfo=UTC)
    # Must not raise TypeError("can't compare offset-naive and offset-aware datetimes").
    result = cfg.should_run(
        store="preferences",
        stats=CompactionStats(),
        last_run=None,
        turns_since_compaction=None,
        now=now,
    )
    assert result is True


def test_zero_char_threshold_does_not_trigger():
    """Bug B: a threshold of 0 means "disabled", not "always trigger"."""
    now = datetime.now(UTC)
    cfg = CompactionConfig(
        enabled=True,
        total_char_threshold=0,
        segment_char_threshold=0,
    )
    # Empty stats + zero thresholds: nothing should fire.
    assert not cfg.should_run(
        store="preferences",
        stats=CompactionStats(total_chars=0, largest_block=0),
        last_run=None,
        turns_since_compaction=None,
        now=now,
    )
    # Even with content present, a 0 threshold stays disabled.
    assert not cfg.should_run(
        store="preferences",
        stats=CompactionStats(total_chars=10_000, largest_block=10_000),
        last_run=None,
        turns_since_compaction=None,
        now=now,
    )
    # And a zero user_turn_interval is likewise disabled.
    cfg_turns = CompactionConfig(enabled=True, user_turn_interval=0, compact_preferences=False)
    assert not cfg_turns.should_run(
        store="conversations",
        stats=CompactionStats(),
        last_run=None,
        turns_since_compaction=1_000,
        now=now,
    )


def test_schedule_trigger_fires_on_two_different_days():
    """Bug C: the daily schedule recurs - it fires again on a later day."""
    base = datetime(2026, 6, 23, 0, 0, 0, tzinfo=UTC)
    cfg = CompactionConfig(enabled=True, schedule_at=base + timedelta(hours=8))  # 08:00 UTC
    stats = CompactionStats()

    # Day 1: fires after the scheduled time, no prior run.
    day1_fire = base + timedelta(hours=9)
    assert cfg.should_run(
        store="preferences",
        stats=stats,
        last_run=None,
        turns_since_compaction=None,
        now=day1_fire,
    )

    # Day 2: after the scheduled time-of-day again, last run was yesterday -> fires again.
    day2_now = base + timedelta(days=1, hours=9)
    assert cfg.should_run(
        store="preferences",
        stats=stats,
        last_run=day1_fire,
        turns_since_compaction=None,
        now=day2_now,
    )


@pytest.mark.asyncio
async def test_compaction_tool_mutations():
    deps = CompactionDeps(
        prefs=cast(
            PreferencesStore,
            {
                "_meta": {},
                "preferences": {
                    "likes": {
                        "pizza": {
                            "text": "likes pizza",
                            "contexts": ["food"],
                            "_count": 1,
                            "_created": "2024-01-01T00:00:00Z",
                            "_updated": "2024-01-01T00:00:00Z",
                            "_created_by": "test",
                            "_updated_by": "test",
                        }
                    }
                },
            },
        ),
        convs=cast(
            ConversationsStore,
            {
                "_meta": {},
                "conversations": {
                    "chat-1": {
                        "_created": "2024-01-01T00:00:00Z",
                        "_updated": "2024-01-01T00:00:00Z",
                        "_turns": 1,
                        "summary": "long running discussion",
                        "keywords": ["pizza"],
                    }
                },
            },
        ),
        include_preferences=True,
        include_conversations=True,
    )

    ctx = DummyCtx(deps)

    listing = await compaction_tools.list_preference_blocks(ctx)  # type: ignore[arg-type]
    assert "likes/pizza" in listing

    await compaction_tools.rewrite_preference_block(  # type: ignore[arg-type]
        ctx, "likes/pizza", text="still likes pizza", contexts=["food court"]
    )
    assert deps.prefs["preferences"]["likes"]["pizza"]["text"] == "still likes pizza"
    assert deps.prefs["preferences"]["likes"]["pizza"]["contexts"] == ["food court"]

    await compaction_tools.delete_preference_block(ctx, "likes/pizza")  # type: ignore[arg-type]
    assert "pizza" not in deps.prefs.get("preferences", {}).get("likes", {})

    convo_listing = await compaction_tools.list_conversation_blocks(ctx)  # type: ignore[arg-type]
    assert "chat-1" in convo_listing

    await compaction_tools.rewrite_conversation_block(  # type: ignore[arg-type]
        ctx, "chat-1", summary="short summary", keywords=["concise"]
    )
    assert deps.convs["conversations"]["chat-1"]["summary"] == "short summary"
    assert deps.convs["conversations"]["chat-1"]["keywords"] == ["concise"]

    await compaction_tools.delete_conversation_block(ctx, "chat-1")  # type: ignore[arg-type]
    assert "chat-1" not in deps.convs.get("conversations", {})
