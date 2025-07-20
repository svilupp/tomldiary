# pragma: no cover
from __future__ import annotations

from datetime import UTC, datetime

from pydantic_ai import RunContext

from .models import MemoryDeps

# These tools are helpers for the extraction agent and are not covered by tests.


# ───────── read-only tools ─────────
async def list_categories(ctx: RunContext[MemoryDeps]) -> str:  # pragma: no cover
    """List all available preference categories."""
    return "\n".join(f"- **{c}**" for c in ctx.deps.allowed_cats)


async def list_preferences(
    ctx: RunContext[MemoryDeps], category: str | None = None
) -> str:  # pragma: no cover
    """List preferences, optionally filtered by category."""
    if category and category not in ctx.deps.allowed_cats:
        return f"❌ Unknown category '{category}'."
    lines = []
    for cat, items in ctx.deps.prefs.get("preferences", {}).items():
        if category and cat != category:
            continue
        for pid, tbl in items.items():
            lines.append(f"- {cat}/{pid}: {tbl['text']} ({tbl['_count']}×)")
    return "\n".join(lines) or "(none)"


async def list_conversation_summary(
    ctx: RunContext[MemoryDeps], session_id: str
) -> str:  # pragma: no cover
    """Get summary of a specific conversation session."""
    try:
        return ctx.deps.pretty_session(session_id)
    except KeyError:
        return f"❌ No session with ID: '{session_id}'."


# ───────── write tools ─────────
async def upsert_preference(
    ctx: RunContext[MemoryDeps],
    category: str,
    text: str,
    id: str | None = None,
    contexts: list[str] | None = None,
    boost: bool = False,
) -> str:  # pragma: no cover
    """Add or update a preference in the specified category."""
    if category not in ctx.deps.allowed_cats:
        return f"❌ Category '{category}' is not allowed."

    pref_root = ctx.deps.prefs.setdefault("preferences", {})
    cat_tbl = pref_root.setdefault(category, {})

    if id is None:
        nums = [int(k[4:]) for k in cat_tbl if k.startswith("pref")]
        id = f"pref{max(nums, default=0) + 1:03d}"

    now = datetime.now(UTC).isoformat()
    session_id = ctx.deps.session_id
    if contexts is None:
        contexts = []

    # Check if this is a new preference or existing one
    is_new = id not in cat_tbl
    tbl = cat_tbl.get(id, {"_created": now, "_count": 0, "contexts": [], "_created_by": session_id})

    tbl["_updated"] = now
    tbl["_updated_by"] = session_id
    tbl["text"] = text
    tbl["contexts"] = list(set(tbl["contexts"] + contexts))
    tbl["_count"] += 1 if boost else max(1, tbl["_count"])

    # Set created_by only for new preferences
    if is_new:
        tbl["_created_by"] = session_id

    cat_tbl[id] = tbl
    return f"✅ Saved {category}/{id}."


async def forget_preference(
    ctx: RunContext[MemoryDeps], category: str, id: str
) -> str:  # pragma: no cover
    """Remove a specific preference from memory."""
    try:
        del ctx.deps.prefs["preferences"][category][id]
        return f"🗑️ Deleted {category}/{id}."
    except KeyError:
        return f"❌ {category}/{id} not found."


async def update_conversation_summary(
    ctx: RunContext[MemoryDeps],
    summary: str,
    keywords: list[str] | None = None,
) -> str:  # pragma: no cover
    """Update the summary and keywords for the current conversation session."""
    session_id = ctx.deps.session_id

    if session_id not in ctx.deps.convs:
        return f"❌ Session '{session_id}' not found."

    # Update summary
    ctx.deps.convs[session_id]["summary"] = summary

    # Update keywords if provided
    if keywords is not None:
        ctx.deps.convs[session_id]["keywords"] = keywords

    return f"✅ Updated conversation summary for session '{session_id}'."
