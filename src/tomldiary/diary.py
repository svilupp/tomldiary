import tomllib

import tomli_w
from pydantic_ai import format_as_xml

from .extractor_factory import build_extractor
from .models import _MODEL_VERSION, ConversationItem, MemoryDeps
from .utils import extract_categories_from_schema


class Diary:
    def __init__(
        self, backend, pref_table_cls, agent=None, max_prefs_per_category=100, max_conversations=100
    ):
        self.backend = backend
        self.pref_table_cls = pref_table_cls
        # Build agent once during initialization
        if agent:
            # Handle tuple case from tests (agent, allowed_cats)
            if isinstance(agent, tuple):
                self.agent = agent[0]
                self.allowed = agent[1]
            else:
                self.agent = agent
                self.allowed = extract_categories_from_schema(pref_table_cls)
        else:
            self.agent, self.allowed = build_extractor(pref_table_cls)
        self.max_prefs_per_category = max_prefs_per_category
        self.max_conversations = max_conversations
        self.schema_name = pref_table_cls.__name__

    # ------------ helpers ------------
    async def _load(self, user_id, kind):
        return await self.backend.load(user_id, kind) or ""

    async def _save(self, user_id, kind, content):
        return await self.backend.save(user_id, kind, content)

    async def _load_prefs(self, user_id):
        prefs_blob = await self._load(user_id, "preferences")
        if prefs_blob:
            prefs = tomllib.loads(prefs_blob)
        else:
            prefs = {
                "_meta": {"version": _MODEL_VERSION, "schema_name": self.schema_name},
                "preferences": {},
            }
        return prefs

    async def _load_convs(self, user_id):
        convs_blob = await self._load(user_id, "conversations")
        if convs_blob:
            convs = tomllib.loads(convs_blob)
        else:
            convs = {"_meta": {"version": _MODEL_VERSION, "schema_name": self.schema_name}}
        return convs

    async def _save_prefs(self, user_id, prefs):
        await self._save(user_id, "preferences", tomli_w.dumps(prefs))

    async def _save_convs(self, user_id, convs):
        await self._save(user_id, "conversations", tomli_w.dumps(convs))

    async def build_deps(self, user_id, session_id):
        prefs = await self._load_prefs(user_id)
        convs = await self._load_convs(user_id)

        # Create a MemoryDeps object with session_id and max_prefs_per_category
        deps = MemoryDeps(
            prefs, convs, self.allowed, self.schema_name, session_id, self.max_prefs_per_category
        )

        return deps

    async def ensure_session(self, user_id: str, session_id: str):
        """Create session if needed, return whether it's new"""
        convs = await self._load_convs(user_id)
        if session_id not in convs:
            # Check if we've hit the conversation limit
            # Count only actual conversation entries (not _meta)
            conv_entries = {k: v for k, v in convs.items() if k != "_meta"}
            if len(conv_entries) >= self.max_conversations:
                # Find the oldest conversation
                oldest_id = min(
                    conv_entries.keys(), key=lambda k: conv_entries[k].get("_created", "")
                )
                del convs[oldest_id]

            convs[session_id] = ConversationItem().model_dump(by_alias=True)
            await self._save_convs(user_id, convs)
            return True
        return False

    # ------------ preference management ------------
    async def _enforce_preference_limits(self, prefs):
        """Enforce max preferences per category by removing low-count items"""
        preferences = prefs.get("preferences", {})
        for category, items in preferences.items():
            if len(items) > self.max_prefs_per_category:
                # Sort by count and keep only the top N
                sorted_items = sorted(
                    items.items(), key=lambda x: x[1].get("_count", 0), reverse=True
                )
                preferences[category] = dict(sorted_items[: self.max_prefs_per_category])

    # ------------ main hook ------------
    async def update_memory(self, user_id, session_id, user_msg, assistant_msg):
        # Ensure session exists
        await self.ensure_session(user_id, session_id)

        deps = await self.build_deps(user_id, session_id)
        deps.convs[session_id]["_turns"] += 1

        # Get current preferences and summary for inclusion in the message
        current_preferences = deps.pretty_prefs()
        session_info = deps.convs[session_id]
        current_summary = session_info.get("summary", "")
        if not current_summary:
            current_summary = "No summary exists yet."

        # Structure all turn-specific data using format_as_xml
        # Create unsafe_inputs section
        unsafe_inputs = {"user_message": user_msg, "assistant_message": assistant_msg}

        # Create current_diary section
        current_diary = {
            "preferences": current_preferences,
            "conversation_summary": current_summary,
            "turns_count": str(session_info["_turns"]),
        }

        # Combine all data
        structured_input = (
            format_as_xml(unsafe_inputs, root_tag="unsafe_inputs")
            + "\n\n"
            + format_as_xml(current_diary, root_tag="current_diary")
        )

        # Use the stable agent
        await self.agent.run(
            structured_input,
            deps=deps,
        )

        # Enforce limits before saving
        await self._enforce_preference_limits(deps.prefs)

        # TOML already validated by output_validator
        # Backend handles path-level locking for concurrent access
        await self._save_prefs(user_id, deps.prefs)
        await self._save_convs(user_id, deps.convs)

    # ------------ quick introspection ------------
    async def preferences(self, user_id):  # raw TOML string
        return await self._load(user_id, "preferences")

    async def last_conversations(self, user_id, n=3):
        convs = await self._load_convs(user_id)
        # Filter out _meta
        conv_entries = {k: v for k, v in convs.items() if k != "_meta"}
        return dict(
            sorted(conv_entries.items(), key=lambda kv: kv[1]["_created"], reverse=True)[:n]
        )


# Backwards compatibility alias
TOMLDiary = Diary
