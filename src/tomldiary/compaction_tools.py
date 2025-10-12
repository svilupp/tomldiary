from __future__ import annotations

from pydantic_ai import RunContext

# Import at runtime to make type available for pydantic-ai introspection
# This is safe as long as compaction.py doesn't import compaction_tools at module level
from .compaction import CompactionDeps


async def list_preference_blocks(ctx: RunContext[CompactionDeps]) -> str:
    """List the preference blocks available for compaction."""

    blocks = ctx.deps.preference_blocks()
    if not blocks:
        return "No preference blocks scheduled for compaction."

    lines = []
    for block_id, data in blocks:
        text = data.get("text", "")
        lines.append(f"- {block_id} ({len(text)} chars)")
    return "\n".join(lines)


async def get_preference_block(ctx: RunContext[CompactionDeps], block_id: str) -> str:
    """Return the raw text + context for a specific preference block."""

    try:
        block = ctx.deps.get_preference_block(block_id)
    except ValueError as exc:  # pragma: no cover - passthrough message
        return str(exc)

    if not block:
        return f"Preference block '{block_id}' not found."

    contexts = ", ".join(block.get("contexts", [])) or "(no contexts)"
    return f"Text: {block.get('text', '')}\nContexts: {contexts}\nCount: {block.get('_count', 0)}"


async def rewrite_preference_block(
    ctx: RunContext[CompactionDeps],
    block_id: str,
    *,
    text: str,
    contexts: list[str] | None = None,
) -> str:
    """Rewrite a specific preference block."""

    try:
        ctx.deps.rewrite_preference_block(block_id, text=text, contexts=contexts)
    except (KeyError, ValueError) as exc:
        return str(exc)
    return f"Rewrote preference block '{block_id}'."


async def delete_preference_block(ctx: RunContext[CompactionDeps], block_id: str) -> str:
    """Remove a preference block."""

    try:
        ctx.deps.delete_preference_block(block_id)
    except ValueError as exc:
        return str(exc)
    return f"Deleted preference block '{block_id}'."


async def list_conversation_blocks(ctx: RunContext[CompactionDeps]) -> str:
    """List the conversation blocks available for compaction."""

    blocks = ctx.deps.conversation_blocks()
    if not blocks:
        return "No conversation blocks scheduled for compaction."

    lines = []
    for session_id, data in blocks:
        summary = data.get("summary", "")
        lines.append(f"- {session_id} ({len(summary)} chars)")
    return "\n".join(lines)


async def get_conversation_block(ctx: RunContext[CompactionDeps], session_id: str) -> str:
    """Return the summary and keywords for a conversation block."""

    try:
        block = ctx.deps.get_conversation_block(session_id)
    except ValueError as exc:  # pragma: no cover - passthrough message
        return str(exc)

    if not block:
        return f"Conversation block '{session_id}' not found."

    keywords = ", ".join(block.get("keywords", [])) or "(no keywords)"
    return f"Summary: {block.get('summary', '')}\nKeywords: {keywords}"


async def rewrite_conversation_block(
    ctx: RunContext[CompactionDeps],
    session_id: str,
    *,
    summary: str,
    keywords: list[str] | None = None,
) -> str:
    """Rewrite a conversation summary block."""

    try:
        ctx.deps.rewrite_conversation_block(session_id, summary=summary, keywords=keywords)
    except (KeyError, ValueError) as exc:
        return str(exc)
    return f"Rewrote conversation block '{session_id}'."


async def delete_conversation_block(ctx: RunContext[CompactionDeps], session_id: str) -> str:
    """Delete a conversation block entirely."""

    try:
        ctx.deps.delete_conversation_block(session_id)
    except ValueError as exc:
        return str(exc)
    return f"Deleted conversation block '{session_id}'."
