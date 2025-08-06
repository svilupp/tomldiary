"""Tests for tomldiary core diary functionality."""

import asyncio
import shutil
import tempfile
import tomllib
from pathlib import Path

import pytest

from tomldiary import Diary
from tomldiary.backends.local import LocalBackend
from tomldiary.models import MemoryDeps

from .test_user_pref_table import MyPrefTable


class MockAgent:
    """Mock pydantic-ai agent for testing."""

    def __init__(self):
        self.run_calls = []

    async def run(self, message, deps=None):
        """Mock run method."""
        self.run_calls.append((message, deps))

        # Simulate some preference extraction
        if deps and "love" in message.lower():
            deps.prefs.setdefault("preferences", {}).setdefault("like", {})["test"] = {
                "text": "test preference",
                "contexts": ["test"],
                "_count": 1,
                "_created": "2024-01-01T00:00:00Z",
                "_updated": "2024-01-01T00:00:00Z",
            }


class TestDiary:
    """Test Diary functionality."""

    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory for testing."""
        temp_path = Path(tempfile.mkdtemp())
        yield temp_path
        if temp_path.exists():
            shutil.rmtree(temp_path)

    @pytest.fixture
    def backend(self, temp_dir):
        """Create LocalBackend for testing."""
        return LocalBackend(temp_dir)

    @pytest.fixture
    def mock_agent(self):
        """Create mock agent."""
        return MockAgent()

    @pytest.fixture
    def diary(self, backend, mock_agent):
        """Create Diary with mock agent."""
        return Diary(
            backend=backend,
            pref_table_cls=MyPrefTable,
            agent=(mock_agent, ["like", "dislike", "allergy", "habit", "about"]),
            max_prefs_per_category=10,
            max_conversations=5,
        )

    @pytest.mark.asyncio
    async def test_ensure_session_new(self, diary):
        """Test ensure_session creates new session."""
        user_id = "test_user"
        session_id = "new_session"

        is_new = await diary.ensure_session(user_id, session_id)

        assert is_new is True

        # Check session exists
        convs = await diary.last_conversations(user_id, limit=10)
        assert session_id in convs
        assert convs[session_id]["_turns"] == 0

    @pytest.mark.asyncio
    async def test_ensure_session_existing(self, diary):
        """Test ensure_session with existing session."""
        user_id = "test_user"
        session_id = "existing_session"

        # Create session first time
        is_new1 = await diary.ensure_session(user_id, session_id)
        assert is_new1 is True

        # Try again
        is_new2 = await diary.ensure_session(user_id, session_id)
        assert is_new2 is False

    @pytest.mark.asyncio
    async def test_conversation_limit(self, diary):
        """Test that conversation limit is enforced."""
        user_id = "test_user"

        # Create more sessions than the limit (5)
        for i in range(7):
            await diary.ensure_session(user_id, f"session_{i}")

        # Should only have 5 sessions (oldest removed)
        convs = await diary.last_conversations(user_id, limit=10)
        assert len(convs) == 6  # 5 sessions + _meta

        # Filter out metadata for session count check
        session_ids = {k for k in convs if k != "_meta"}
        assert len(session_ids) == 5

        # Should have the most recent ones
        assert "session_6" in session_ids
        assert "session_5" in session_ids
        assert "session_0" not in session_ids  # Oldest should be removed

    @pytest.mark.asyncio
    async def test_build_deps(self, diary):
        """Test build_deps creates proper MemoryDeps."""
        user_id = "test_user"
        session_id = "test_session"

        await diary.ensure_session(user_id, session_id)
        deps = await diary.build_deps(user_id, session_id)

        assert isinstance(deps, MemoryDeps)
        assert deps.schema_name == "MyPrefTable"
        assert deps.max_prefs_per_category == 10
        assert len(deps.allowed_cats) > 0  # Should have preference categories

    @pytest.mark.asyncio
    async def test_update_memory(self, diary, mock_agent):
        """Test update_memory processes correctly."""
        user_id = "test_user"
        session_id = "test_session"
        user_msg = "I love pizza"
        assistant_msg = "Great choice!"

        await diary.update_memory(user_id, session_id, user_msg, assistant_msg)

        # Check agent was called
        assert len(mock_agent.run_calls) == 1
        message, deps = mock_agent.run_calls[0]
        assert "<unsafe_inputs>" in message
        assert f"<user_message>{user_msg}</user_message>" in message
        assert f"<assistant_message>{assistant_msg}</assistant_message>" in message
        assert "<current_diary>" in message
        assert isinstance(deps, MemoryDeps)

        # Check session was updated
        convs = await diary.last_conversations(user_id, limit=1)
        assert session_id in convs
        assert convs[session_id]["_turns"] == 1

    @pytest.mark.asyncio
    async def test_preference_limits(self, diary, backend):
        """Test preference limit enforcement."""
        # Create diary with very low preference limit
        diary_low_limit = Diary(
            backend=backend,
            pref_table_cls=MyPrefTable,
            agent=(MockAgent(), ["like", "dislike", "allergy", "habit", "about"]),
            max_prefs_per_category=2,  # Very low
            max_conversations=5,
        )

        # Manually create preferences exceeding limit
        prefs = {
            "_meta": {"version": "0.2", "schema_name": "MyPrefTable"},
            "preferences": {
                "like": {
                    "item1": {"text": "item 1", "_count": 1},
                    "item2": {"text": "item 2", "_count": 2},
                    "item3": {"text": "item 3", "_count": 3},
                    "item4": {"text": "item 4", "_count": 1},
                }
            },
        }

        # Apply limit enforcement
        await diary_low_limit._enforce_preference_limits(prefs)

        # Should keep only top 2 by count
        like_prefs = prefs["preferences"]["like"]
        assert len(like_prefs) == 2
        assert "item3" in like_prefs  # Highest count (3)
        assert "item2" in like_prefs  # Second highest (2)

    @pytest.mark.asyncio
    async def test_preferences_storage_retrieval(self, diary):
        """Test storing and retrieving preferences."""
        user_id = "test_user"

        # Store some test data
        test_prefs = {
            "_meta": {"version": "0.2", "schema_name": "MyPrefTable"},
            "preferences": {
                "like": {
                    "pizza": {
                        "text": "loves pizza",
                        "contexts": ["food"],
                        "_count": 1,
                        "_created": "2024-01-01T00:00:00Z",
                        "_updated": "2024-01-01T00:00:00Z",
                    }
                }
            },
        }

        import tomli_w

        await diary.backend.save(user_id, "preferences", tomli_w.dumps(test_prefs))

        # Retrieve preferences
        prefs_toml = await diary.preferences(user_id)
        assert prefs_toml is not None

        # Parse and verify
        prefs_data = tomllib.loads(prefs_toml)
        assert prefs_data["_meta"]["version"] == "0.2"
        assert prefs_data["preferences"]["like"]["pizza"]["text"] == "loves pizza"

    @pytest.mark.asyncio
    async def test_last_conversations(self, diary):
        """Test retrieving last conversations."""
        user_id = "test_user"

        # Create multiple sessions
        for i in range(5):
            await diary.ensure_session(user_id, f"session_{i}")

        # Get last 3
        recent = await diary.last_conversations(user_id, limit=3)
        assert len(recent) == 4  # 3 sessions + _meta

        # Should be most recent (sessions are sorted by creation time)
        session_ids = [k for k in recent if k != "_meta"]
        assert len(session_ids) == 3
        # Most recent should be session_4, session_3, session_2
        assert "session_4" in session_ids
        assert "session_3" in session_ids
        assert "session_2" in session_ids

    @pytest.mark.asyncio
    async def test_concurrent_memory_updates(self, diary, mock_agent):
        """Test concurrent memory updates to same user."""
        user_id = "test_user"
        session_id = "test_session"

        # Submit concurrent updates
        tasks = []
        for i in range(5):
            task = asyncio.create_task(
                diary.update_memory(user_id, session_id, f"Message {i}", f"Response {i}")
            )
            tasks.append(task)

        await asyncio.gather(*tasks)

        # Check all were processed
        assert len(mock_agent.run_calls) == 5

        # Check final turn count
        convs = await diary.last_conversations(user_id, limit=1)
        # Turn count should be at least 1 (race conditions may affect exact count)
        assert convs[session_id]["_turns"] >= 1
        assert convs[session_id]["_turns"] <= 5  # But not more than submitted

    @pytest.mark.asyncio
    async def test_empty_data_handling(self, diary):
        """Test handling of empty/missing data."""
        user_id = "nonexistent_user"

        # Should handle missing preferences gracefully
        prefs = await diary.preferences(user_id)
        assert prefs == ""

        # Should handle missing conversations gracefully
        convs = await diary.last_conversations(user_id, limit=5)
        assert len(convs) == 1  # Just _meta
        assert "_meta" in convs

        # build_deps should work with empty data
        deps = await diary.build_deps(user_id, "new_session")
        assert isinstance(deps, MemoryDeps)
        assert len(deps.prefs.get("preferences", {})) == 0

    @pytest.mark.asyncio
    async def test_migration_v02_to_v03(self, diary, backend):
        """Test automatic migration from v0.2 to v0.3 format."""
        user_id = "migration_test_user"

        # Manually create old v0.2 format conversation file
        old_format = {
            "_meta": {"version": "0.2", "schema_name": "MyPrefTable"},
            "session_1": {
                "_created": "2024-01-01T00:00:00Z",
                "_updated": "2024-01-01T00:00:00Z",
                "_turns": 3,
                "summary": "Test migration conversation",
                "keywords": ["test", "migration"],
            },
            "session_2": {
                "_created": "2024-01-02T00:00:00Z",
                "_updated": "2024-01-02T00:00:00Z",
                "_turns": 1,
                "summary": "Another test conversation",
                "keywords": ["another", "test"],
            },
        }

        import tomli_w

        await backend.save(user_id, "conversations", tomli_w.dumps(old_format))

        # Load conversations through diary (should trigger migration)
        convs = await diary._load_convs(user_id)

        # Verify migration happened
        assert convs["_meta"]["version"] == "0.3"
        assert "conversations" in convs
        assert "session_1" in convs["conversations"]
        assert "session_2" in convs["conversations"]

        # Verify data was preserved
        assert convs["conversations"]["session_1"]["_turns"] == 3
        assert convs["conversations"]["session_1"]["summary"] == "Test migration conversation"
        assert convs["conversations"]["session_2"]["_turns"] == 1

        # Verify migrated file was saved back
        raw_data = await backend.load(user_id, "conversations")
        migrated_data = tomllib.loads(raw_data)
        assert migrated_data["_meta"]["version"] == "0.3"
        assert "conversations" in migrated_data

        # Test that last_conversations works with migrated data
        recent = await diary.last_conversations(user_id, limit=5)
        assert "session_1" in recent
        assert "session_2" in recent
        assert len(recent) == 3  # 2 sessions + _meta
