from datetime import UTC, datetime, timedelta

import pytest

from tomldiary import compaction_tools
from tomldiary.compaction import CompactionConfig, CompactionDeps, CompactionStats


class DummyCtx:
    def __init__(self, deps):
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

    # Schedule trigger fires only once
    target_time = now + timedelta(seconds=5)
    cfg = CompactionConfig(enabled=True, schedule_at=target_time)
    assert not cfg.should_run(
        store="preferences",
        stats=stats,
        last_run=None,
        turns_since_compaction=None,
        now=now,
    )
    assert cfg.should_run(
        store="preferences",
        stats=stats,
        last_run=None,
        turns_since_compaction=None,
        now=target_time + timedelta(seconds=1),
    )
    assert not cfg.should_run(
        store="preferences",
        stats=stats,
        last_run=target_time + timedelta(seconds=1),
        turns_since_compaction=None,
        now=target_time + timedelta(seconds=2),
    )


@pytest.mark.asyncio
async def test_compaction_tool_mutations():
    deps = CompactionDeps(
        prefs={
            "preferences": {
                "likes": {
                    "pizza": {
                        "text": "likes pizza",
                        "contexts": ["food"],
                        "_count": 1,
                        "_updated": "2024-01-01T00:00:00Z",
                    }
                }
            }
        },
        convs={
            "conversations": {
                "chat-1": {
                    "summary": "long running discussion",
                    "keywords": ["pizza"],
                    "_updated": "2024-01-01T00:00:00Z",
                }
            }
        },
        include_preferences=True,
        include_conversations=True,
    )

    ctx = DummyCtx(deps)

    listing = await compaction_tools.list_preference_blocks(ctx)
    assert "likes/pizza" in listing

    await compaction_tools.rewrite_preference_block(
        ctx, "likes/pizza", text="still likes pizza", contexts=["food court"]
    )
    assert deps.prefs["preferences"]["likes"]["pizza"]["text"] == "still likes pizza"
    assert deps.prefs["preferences"]["likes"]["pizza"]["contexts"] == ["food court"]

    await compaction_tools.delete_preference_block(ctx, "likes/pizza")
    assert "pizza" not in deps.prefs.get("preferences", {}).get("likes", {})

    convo_listing = await compaction_tools.list_conversation_blocks(ctx)
    assert "chat-1" in convo_listing

    await compaction_tools.rewrite_conversation_block(
        ctx, "chat-1", summary="short summary", keywords=["concise"]
    )
    assert deps.convs["conversations"]["chat-1"]["summary"] == "short summary"
    assert deps.convs["conversations"]["chat-1"]["keywords"] == ["concise"]

    await compaction_tools.delete_conversation_block(ctx, "chat-1")
    assert "chat-1" not in deps.convs.get("conversations", {})
