from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from pydantic import BaseModel, Field

_MODEL_VERSION = "0.3"


# ───────── metadata for TOML files ─────────
class MetaInfo(BaseModel):
    """Metadata header for TOML files"""

    version: str = _MODEL_VERSION
    schema_name: str = ""


# ───────── preference atom ─────────
class PreferenceItem(BaseModel):
    """
    text       : user-friendly description of the preference/facts learned
    contexts   : short phrases capturing the context in which the preference was mentioned
    count      : engine-managed hit counter (prefixed with _ in TOML)
    created    : ISO timestamp of first creation (engine-managed, prefixed with _ in TOML)
    updated    : ISO timestamp of last update (engine-managed, prefixed with _ in TOML)
    created_by : session_id that created this preference (engine-managed, prefixed with _ in TOML)
    updated_by : session_id that last updated this preference (engine-managed, prefixed with _ in TOML)
    """

    text: str
    contexts: list[str] = []
    count: int = Field(default=1, alias="_count")
    created: str = Field(default_factory=lambda: datetime.now(UTC).isoformat(), alias="_created")
    updated: str = Field(default_factory=lambda: datetime.now(UTC).isoformat(), alias="_updated")
    created_by: str = Field(default="", alias="_created_by")
    updated_by: str = Field(default="", alias="_updated_by")

    model_config = {"populate_by_name": True}


# ───────── conversation summary ─────
class ConversationItem(BaseModel):
    """
    created   : session start (prefixed with _ in TOML)
    updated   : last update timestamp (prefixed with _ in TOML)
    turns     : total user↔assistant pairs (prefixed with _ in TOML)
    summary   : rolling abstract/summary of the conversation so far
    keywords  : key nouns / verbs
    """

    created: str = Field(default_factory=lambda: datetime.now(UTC).isoformat(), alias="_created")
    updated: str = Field(default_factory=lambda: datetime.now(UTC).isoformat(), alias="_updated")
    turns: int = Field(default=0, alias="_turns")
    summary: str = ""
    keywords: list[str] = []

    model_config = {"populate_by_name": True}


# ───────── deps object passed into the extractor ─────────
@dataclass
class MemoryDeps:
    prefs: dict  # full preferences dict
    convs: dict  # full conversations dict
    allowed_cats: list[str]  # whitelist derived from table class
    schema_name: str  # name of the preference table class
    session_id: str  # current session_id for tracking created_by/updated_by
    max_prefs_per_category: int = 100  # maximum preferences per category

    # pretty-printers for the LLM
    def pretty_prefs(self) -> str:
        out = []
        for cat, items in self.prefs.get("preferences", {}).items():
            for pid, tbl in items.items():
                out.append(f"- {cat}/{pid}: {tbl['text']} ({tbl['_count']}×)")
        return "\n".join(out) or "(none)"

    def pretty_session(self, sid: str) -> str:
        c = self.convs["conversations"][sid]
        kws = ", ".join(c["keywords"])
        return (
            f"Started: {c['_created']}  •  Turns: {c['_turns']}\n"
            f"Summary: {c['summary']}\nKeywords: {kws}"
        )
