# pragma: no cover
from __future__ import annotations

from datetime import UTC, datetime

from pydantic_ai import RunContext
from thefuzz import fuzz

from .models import MemoryDeps

# These tools are helpers for the extraction agent and are not covered by tests.


# ───────── read-only tools ─────────
async def list_categories(ctx: RunContext[MemoryDeps]) -> str:  # pragma: no cover
    """List all available preference categories.

    Shows which categories you can use when creating or updating preferences.
    Always use one of these exact category names in upsert_preference().
    """
    return "\n".join(f"- **{c}**" for c in ctx.deps.allowed_cats)


async def list_preferences(
    ctx: RunContext[MemoryDeps], category: str | None = None
) -> str:  # pragma: no cover
    """List existing preferences, optionally filtered by category.

    Look for similar preferences that should be updated instead of creating new ones.

    Parameters:
    - category: Specific category to check (recommended) or None for all

    Returns format: "- category/id: text (count×)"
    Example: "- likes/pref001: black blazers (3×)"

    Use the exact 'id' (like 'pref001') when updating existing preferences.
    """
    if category and category not in ctx.deps.allowed_cats:
        return f"❌ Unknown category '{category}'."

    lines = []
    categories_shown = set()

    for cat, items in ctx.deps.prefs.get("preferences", {}).items():
        if category and cat != category:
            continue

        # Add limit status for this category
        if cat not in categories_shown:
            limit_status = _check_preference_limits(ctx, cat)
            lines.append(f"\n📊 {limit_status}")
            categories_shown.add(cat)

        for pid, tbl in items.items():
            lines.append(f"- {cat}/{pid}: {tbl['text']} ({tbl['_count']}×)")

    # If no specific category requested, show limit status for all categories
    if not category:
        missing_cats = set(ctx.deps.allowed_cats) - categories_shown
        for cat in missing_cats:
            limit_status = _check_preference_limits(ctx, cat)
            lines.append(f"\n📊 {limit_status}")
            lines.append(f"- {cat}: (no preferences yet)")

    return "\n".join(lines).strip() if lines else "(no preferences found)"


async def list_conversation_summary(
    ctx: RunContext[MemoryDeps], session_id: str
) -> str:  # pragma: no cover
    """Get summary of a specific conversation session."""
    try:
        return ctx.deps.pretty_session(session_id)
    except KeyError:
        return f"❌ No session with ID: '{session_id}'."


# ───────── helper functions ─────────
def _check_preference_limits(ctx: RunContext[MemoryDeps], category: str) -> str:  # pragma: no cover
    """Check current limit status for a category"""
    current_count = len(ctx.deps.prefs.get("preferences", {}).get(category, {}))
    max_count = ctx.deps.max_prefs_per_category

    if current_count >= max_count:
        return f"❌ Category '{category}' is at limit ({current_count}/{max_count}). Must update existing preference instead of creating new."
    elif current_count >= max_count * 0.8:  # 80% warning threshold
        return f"⚠️  Category '{category}' near limit ({current_count}/{max_count}). Consider updating existing preferences."
    else:
        return f"✅ Category '{category}' has space ({current_count}/{max_count})"


def _find_similar_preferences(
    ctx: RunContext[MemoryDeps], category: str, text: str, min_similarity: int = 70
) -> list[tuple[str, str, int]]:  # pragma: no cover
    """Find existing preferences with similar text, ranked by similarity score

    Returns list of tuples: (pref_id_with_category, actual_text, similarity_score)
    Sorted by similarity score (highest first)
    """
    cat_prefs = ctx.deps.prefs.get("preferences", {}).get(category, {})
    similar = []

    text_clean = text.strip()

    for pref_id, pref_data in cat_prefs.items():
        existing_text = pref_data.get("text", "").strip()

        # Use FuzzyWuzzy TokenSetRatio for robust phrase matching (better for partial overlaps)
        similarity_score = fuzz.token_set_ratio(text_clean, existing_text)

        if similarity_score >= min_similarity:
            similar.append((f"{category}/{pref_id}", existing_text, similarity_score))

    # Sort by similarity score (highest first)
    similar.sort(key=lambda x: x[2], reverse=True)
    return similar


# ───────── write tools ─────────
async def upsert_preference(
    ctx: RunContext[MemoryDeps],
    category: str,
    id: str | None = None,
    text: str | None = None,
    contexts: list[str] | None = None,
    suppress_count_increment: bool = False,
) -> str:  # pragma: no cover
    """Create new preference OR update existing one.

    CRITICAL WORKFLOW:
    1. To BOOST EXISTING: Just provide category and ID - count auto-increments!
    2. To UPDATE EXISTING: Provide category, ID, and new text
    3. To CREATE NEW: Provide category and text (id=None)
    4. To FORCE CREATE despite similarities: Use id="new"

    Parameters:
    - category: One of the allowed categories from list_categories()
    - id: Preference ID to update ('pref001'), None to create new, or "new" to force creation (special case)
    - text: New/updated preference text (required for new preferences, optional for updates)
    - contexts: Additional context examples (optional)
    - suppress_count_increment: Set True when doing multiple edits to avoid over-counting

    Examples (in priority order):
    1. Boost existing: upsert_preference('likes', id='pref001')  # Auto-increments count
    2. Update existing: upsert_preference('likes', id='pref001', text='refined black blazers') # text is updated
    3. Create new: upsert_preference('likes', text='burgundy scarves') # id is auto-generated
    4. Force create: upsert_preference('likes', id='new', text='similar item but different') # if there are similar preferences, this will create a new one anyway
    5. Multiple edits: upsert_preference('likes', id='pref001', text='...', suppress_count_increment=True) # suppressed count increment

    AVOID duplicates! Always check existing preferences first.
    """
    if category not in ctx.deps.allowed_cats:
        return f"❌ Category '{category}' is not allowed."

    # Handle boost existing (just category + id, no text needed)
    if id and id != "new" and not text:
        pref_root = ctx.deps.prefs.setdefault("preferences", {})
        cat_tbl = pref_root.setdefault(category, {})

        if id not in cat_tbl:
            return f"❌ Preference {category}/{id} not found. Use list_preferences('{category}') to see available IDs."

        # Just increment count
        if not suppress_count_increment:
            cat_tbl[id]["_count"] += 1
        cat_tbl[id]["_updated"] = datetime.now(UTC).isoformat()
        cat_tbl[id]["_updated_by"] = ctx.deps.session_id

        return f"✅ Boosted {category}/{id} (count: {cat_tbl[id]['_count']})."

    # Require text for new preferences or updates with text
    if not text:
        return "❌ 'text' parameter is required when creating new preferences or updating existing ones with new text."

    # Check for similar preferences when creating new (id is None or "new")
    if id is None or id == "new":
        # Check category limits first
        limit_status = _check_preference_limits(ctx, category)
        if limit_status.startswith("❌"):
            return limit_status

        # Check for similar existing preferences (unless forcing with id="new")
        if id != "new":
            similar_prefs = _find_similar_preferences(ctx, category, text)
            if similar_prefs:
                # Show top 5 with actual text and similarity scores
                similar_display = []
                for pref_id, actual_text, score in similar_prefs[:5]:
                    similar_display.append(f"{pref_id}: '{actual_text}' ({score}% match)")
                similar_list = "\n  • ".join(similar_display)

                return f"❌ Similar preferences found:\n  • {similar_list}\n\nTo update existing: upsert_preference('{category}', id='pref_id')\nTo force create anyway: upsert_preference('{category}', id='new', text='{text}')\nTo see all: list_preferences('{category}')"

        # Show warning if near limit
        if limit_status.startswith("⚠️"):
            # Still allow creation but warn
            pass

    pref_root = ctx.deps.prefs.setdefault("preferences", {})
    cat_tbl = pref_root.setdefault(category, {})

    # Generate ID for new preferences (id is None or "new")
    if id is None or id == "new":
        nums = [int(k[4:]) for k in cat_tbl if k.startswith("pref")]
        id = f"pref{max(nums, default=0) + 1:03d}"

    now = datetime.now(UTC).isoformat()
    session_id = ctx.deps.session_id
    if contexts is None:
        contexts = []

    # Check if this is a new preference or existing one
    is_new = id not in cat_tbl

    if is_new:
        # Creating new preference
        tbl = {
            "_created": now,
            "_updated": now,
            "_count": 1,
            "contexts": contexts,
            "_created_by": session_id,
            "_updated_by": session_id,
            "text": text,
        }
        cat_tbl[id] = tbl
        return f"✅ Created {category}/{id}: '{text}'."
    else:
        # Updating existing preference
        tbl = cat_tbl[id]
        tbl["_updated"] = now
        tbl["_updated_by"] = session_id
        tbl["text"] = text
        tbl["contexts"] = list(set(tbl["contexts"] + contexts))

        # Auto-increment count unless suppressed
        if not suppress_count_increment:
            tbl["_count"] += 1

        return f"✅ Updated {category}/{id}: '{text}' (count: {tbl['_count']})."


async def forget_preference(
    ctx: RunContext[MemoryDeps], category: str, id: str
) -> str:  # pragma: no cover
    """Remove a specific preference from memory.

    Parameters:
    - category: The preference category
    - id: Exact preference ID to remove (from list_preferences output)

    Use this to remove outdated or incorrect preferences.
    """
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
    """Update the summary and keywords for the current conversation session.

    Parameters:
    - summary: Concise summary of the conversation so far
    - keywords: List of important keywords/topics discussed (optional)

    Updates the rolling summary for the current conversation to help maintain context.
    """
    session_id = ctx.deps.session_id

    if session_id not in ctx.deps.convs.get("conversations", {}):
        return f"❌ Session '{session_id}' not found."

    # Update summary
    ctx.deps.convs["conversations"][session_id]["summary"] = summary

    # Update keywords if provided
    if keywords is not None:
        ctx.deps.convs["conversations"][session_id]["keywords"] = keywords

    return f"✅ Updated conversation summary for session '{session_id}'."
