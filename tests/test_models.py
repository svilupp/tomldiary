"""Tests for tomldiary models."""

import tomllib
from typing import cast

import tomli_w

from tomldiary.models import (
    ConversationItem,
    ConversationsStore,
    MemoryDeps,
    MetaInfo,
    PreferenceItem,
    PreferencesStore,
)


class TestPreferenceItem:
    """Test PreferenceItem model."""

    def test_basic_creation(self):
        """Test basic preference item creation."""
        pref = PreferenceItem(text="loves pizza", contexts=["food", "italian"])

        assert pref.text == "loves pizza"
        assert pref.contexts == ["food", "italian"]
        assert pref.count == 1
        assert pref.created is not None
        assert pref.updated is not None
        assert pref.created_by == ""
        assert pref.updated_by == ""

    def test_toml_serialization(self):
        """Test TOML serialization with aliases."""
        pref = PreferenceItem(text="loves coffee", contexts=["drinks"])
        data = pref.model_dump(by_alias=True)

        # Check aliases are used
        assert "_count" in data
        assert "_created" in data
        assert "_updated" in data
        assert "_created_by" in data
        assert "_updated_by" in data
        assert "count" not in data

        # Test round-trip
        toml_str = tomli_w.dumps({"test": data})
        parsed = tomllib.loads(toml_str)
        assert parsed["test"]["_count"] == 1

    def test_field_aliases(self):
        """Test that field aliases work correctly."""
        pref = PreferenceItem(text="test")

        # Test by_alias=True
        data_with_alias = pref.model_dump(by_alias=True)
        assert "_count" in data_with_alias

        # Test by_alias=False
        data_without_alias = pref.model_dump(by_alias=False)
        assert "count" in data_without_alias


class TestConversationItem:
    """Test ConversationItem model."""

    def test_basic_creation(self):
        """Test basic conversation item creation."""
        conv = ConversationItem(summary="Test conversation", keywords=["test", "demo"])

        assert conv.summary == "Test conversation"
        assert conv.keywords == ["test", "demo"]
        assert conv.turns == 0
        assert conv.created is not None

    def test_toml_serialization(self):
        """Test TOML serialization."""
        conv = ConversationItem(summary="Chat about food", keywords=["food", "preferences"])
        data = conv.model_dump(by_alias=True)

        assert "_created" in data
        assert "_turns" in data
        assert data["summary"] == "Chat about food"
        assert data["keywords"] == ["food", "preferences"]


class TestMetaInfo:
    """Test MetaInfo model."""

    def test_creation(self):
        """Test MetaInfo creation."""
        meta = MetaInfo(schema_name="TestSchema")

        assert meta.version == "0.3"
        assert meta.schema_name == "TestSchema"

    def test_toml_serialization(self):
        """Test TOML serialization."""
        meta = MetaInfo(schema_name="MyPrefTable")
        data = meta.model_dump()

        assert data["version"] == "0.3"
        assert data["schema_name"] == "MyPrefTable"


class TestMemoryDeps:
    """Test MemoryDeps dataclass."""

    def test_creation(self):
        """Test MemoryDeps creation."""
        deps = MemoryDeps(
            prefs=cast(PreferencesStore, {"_meta": {}, "preferences": {}}),
            convs=cast(ConversationsStore, {"_meta": {}, "conversations": {"session1": {}}}),
            allowed_cats=["like", "dislike"],
            schema_name="TestSchema",
            session_id="session123",
            max_prefs_per_category=50,
        )

        assert deps.prefs["preferences"] == {}
        assert "session1" in deps.convs["conversations"]
        assert deps.allowed_cats == ["like", "dislike"]
        assert deps.schema_name == "TestSchema"
        assert deps.session_id == "session123"
        assert deps.max_prefs_per_category == 50

    def test_pretty_prefs_empty(self):
        """Test pretty_prefs with empty preferences."""
        deps = MemoryDeps(
            prefs=cast(PreferencesStore, {"_meta": {}, "preferences": {}}),
            convs=cast(ConversationsStore, {"_meta": {}, "conversations": {}}),
            allowed_cats=[],
            schema_name="Test",
            session_id="test123",
        )

        assert deps.pretty_prefs() == "(none)"

    def test_pretty_prefs_with_data(self):
        """Test pretty_prefs with actual data."""
        deps = MemoryDeps(
            prefs=cast(
                PreferencesStore,
                {
                    "_meta": {},
                    "preferences": {
                        "like": {
                            "pizza": {"text": "loves pizza", "_count": 2},
                            "coffee": {"text": "loves coffee", "_count": 1},
                        }
                    },
                },
            ),
            convs=cast(ConversationsStore, {"_meta": {}, "conversations": {}}),
            allowed_cats=["like"],
            schema_name="Test",
            session_id="test123",
        )

        pretty = deps.pretty_prefs()
        assert "like/pizza: loves pizza (2×)" in pretty
        assert "like/coffee: loves coffee (1×)" in pretty

    def test_pretty_session(self):
        """Test pretty_session formatting."""
        deps = MemoryDeps(
            prefs=cast(PreferencesStore, {"_meta": {}, "preferences": {}}),
            convs=cast(
                ConversationsStore,
                {
                    "_meta": {},
                    "conversations": {
                        "session1": {
                            "_created": "2024-01-01T00:00:00Z",
                            "_updated": "2024-01-01T00:01:00Z",
                            "_turns": 5,
                            "summary": "Chat about food preferences",
                            "keywords": ["food", "pizza", "coffee"],
                        }
                    },
                },
            ),
            allowed_cats=[],
            schema_name="Test",
            session_id="session1",
        )

        pretty = deps.pretty_session("session1")
        assert "Started: 2024-01-01T00:00:00Z" in pretty
        assert "Turns: 5" in pretty
        assert "Summary: Chat about food preferences" in pretty
        assert "Keywords: food, pizza, coffee" in pretty
