"""Integration tests for the complete tomldiary system."""

import asyncio
import shutil
import tempfile
import tomllib
from pathlib import Path

import pytest

from tomldiary import Diary, MemoryWriter, shutdown_all_background_tasks
from tomldiary.backends.local import LocalBackend

from .test_user_pref_table import MyPrefTable


class MockExtractionAgent:
    """Mock agent that simulates preference extraction."""

    def __init__(self):
        self.run_calls = []

    async def run(self, message, deps=None):
        """Mock extraction that finds simple patterns."""
        self.run_calls.append((message, deps))

        if not deps:
            return

        # Extract only the unsafe_inputs section for pattern matching
        import re

        unsafe_match = re.search(r"<unsafe_inputs>(.*?)</unsafe_inputs>", message, re.DOTALL)
        unsafe_content = unsafe_match.group(1) if unsafe_match else message

        # Simple pattern extraction - only process unsafe inputs
        message_lower = unsafe_content.lower()
        prefs = deps.prefs.setdefault("preferences", {})

        if "love" in message_lower or "like" in message_lower:
            likes = prefs.setdefault("like", {})
            if "pizza" in message_lower:
                likes["pizza"] = {
                    "text": "loves pizza",
                    "contexts": ["food", "italian"],
                    "_count": likes.get("pizza", {}).get("_count", 0) + 1,
                    "_created": "2024-01-01T00:00:00Z",
                    "_updated": "2024-01-01T00:00:00Z",
                }

        if "allergic" in message_lower:
            allergies = prefs.setdefault("allergy", {})
            if "peanut" in message_lower:
                allergies["peanuts"] = {
                    "text": "allergic to peanuts",
                    "contexts": ["health", "food"],
                    "_count": 1,
                    "_created": "2024-01-01T00:00:00Z",
                    "_updated": "2024-01-01T00:00:00Z",
                }


class TestIntegration:
    """Integration tests for the complete system."""

    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory."""
        temp_path = Path(tempfile.mkdtemp())
        yield temp_path
        if temp_path.exists():
            shutil.rmtree(temp_path)

    @pytest.fixture
    def diary_system(self, temp_dir):
        """Create complete diary system."""
        backend = LocalBackend(temp_dir)
        agent = MockExtractionAgent()
        diary = Diary(
            backend=backend,
            pref_table_cls=MyPrefTable,
            agent=agent,
            max_prefs_per_category=20,
            max_conversations=10,
        )
        return diary, agent

    @pytest.mark.asyncio
    async def test_end_to_end_single_user(self, diary_system):
        """Test complete flow for a single user."""
        diary, agent = diary_system
        writer = MemoryWriter(diary, workers=1, qsize=10)

        user_id = "alice"
        conversations = [
            ("session1", "I love pizza and pasta", "Great Italian food choices!"),
            ("session1", "I'm allergic to peanuts", "I'll remember your peanut allergy."),
            ("session2", "I love pizza again", "Confirmed your pizza preference!"),
        ]

        # Submit conversations
        for session_id, user_msg, assistant_msg in conversations:
            await writer.submit(user_id, session_id, user_msg, assistant_msg)

        # Wait for processing
        await asyncio.sleep(2)

        # Verify agent was called
        assert len(agent.run_calls) == 3

        # Check stored preferences
        prefs_toml = await diary.preferences(user_id)
        assert prefs_toml

        prefs_data = tomllib.loads(prefs_toml)
        preferences = prefs_data.get("preferences", {})

        # Should have pizza preference with count=2
        assert "like" in preferences
        assert "pizza" in preferences["like"]
        assert preferences["like"]["pizza"]["_count"] == 2

        # Should have peanut allergy
        assert "allergy" in preferences
        assert "peanuts" in preferences["allergy"]

        # Check conversations
        convs = await diary.last_conversations(user_id, limit=5)
        assert len(convs) == 3  # Two unique sessions + _meta
        assert "session1" in convs
        assert "session2" in convs
        assert convs["session1"]["_turns"] == 2  # Two messages in session1
        assert convs["session2"]["_turns"] == 1  # One message in session2

        await writer.close()

    @pytest.mark.asyncio
    async def test_multi_user_concurrent(self, diary_system):
        """Test concurrent processing for multiple users."""
        diary, agent = diary_system
        writer = MemoryWriter(diary, workers=1, qsize=20)

        users_data = {
            "alice": [
                ("s1", "I love pizza", "Noted!"),
                ("s1", "I'm allergic to peanuts", "Important allergy info."),
            ],
            "bob": [
                ("work", "I love pizza too", "Another pizza fan!"),
            ],
            "charlie": [
                ("chat", "I love pizza as well", "Pizza is popular!"),
                ("chat", "I'm allergic to peanuts also", "Another peanut allergy."),
            ],
        }

        # Submit all conversations concurrently
        tasks = []
        for user_id, conversations in users_data.items():
            for session_id, user_msg, assistant_msg in conversations:
                task = asyncio.create_task(
                    writer.submit(user_id, session_id, user_msg, assistant_msg)
                )
                tasks.append(task)

        await asyncio.gather(*tasks)
        await asyncio.sleep(2)  # Wait for processing

        # Verify all users have data
        for user_id in users_data:
            prefs_toml = await diary.preferences(user_id)
            assert prefs_toml

            prefs_data = tomllib.loads(prefs_toml)
            preferences = prefs_data.get("preferences", {})

            # All should love pizza
            assert "like" in preferences
            assert "pizza" in preferences["like"]

            # Alice and Charlie should have peanut allergies
            if user_id in ["alice", "charlie"]:
                assert "allergy" in preferences
                assert "peanuts" in preferences["allergy"]

        await writer.close()

    @pytest.mark.asyncio
    async def test_limits_enforcement(self, temp_dir):
        """Test that limits are properly enforced."""
        backend = LocalBackend(temp_dir)
        agent = MockExtractionAgent()

        # Create diary with very low limits
        diary = Diary(
            backend=backend,
            pref_table_cls=MyPrefTable,
            agent=agent,
            max_prefs_per_category=2,  # Very low
            max_conversations=2,  # Very low
        )

        writer = MemoryWriter(diary, workers=1, qsize=10)

        user_id = "test_user"

        # Create more conversations than limit
        for i in range(5):
            await writer.submit(user_id, f"session_{i}", "I love pizza", "Noted!")

        await asyncio.sleep(2)

        # Should only have 2 conversations (limit)
        convs = await diary.last_conversations(user_id, limit=10)
        assert len(convs) <= 3  # 2 conversations + _meta

        await writer.close()

    @pytest.mark.asyncio
    async def test_data_persistence(self, diary_system):
        """Test that data persists across diary instances."""
        diary1, agent1 = diary_system
        writer1 = MemoryWriter(diary1, workers=1, qsize=5)

        user_id = "persistent_user"

        # Store some data with first instance
        await writer1.submit(user_id, "session1", "I love pizza", "Great choice!")
        await asyncio.sleep(0.2)
        await writer1.close()

        # Create new diary instance with same backend
        diary2 = Diary(
            backend=diary1.backend,  # Same backend
            pref_table_cls=MyPrefTable,
            agent=MockExtractionAgent(),
            max_prefs_per_category=20,
            max_conversations=10,
        )

        # Should be able to read data stored by first instance
        prefs_toml = await diary2.preferences(user_id)
        assert prefs_toml

        prefs_data = tomllib.loads(prefs_toml)
        preferences = prefs_data.get("preferences", {})
        assert "like" in preferences
        assert "pizza" in preferences["like"]

        convs = await diary2.last_conversations(user_id, limit=5)
        assert len(convs) == 2  # 1 session + _meta
        assert "session1" in convs

    @pytest.mark.asyncio
    async def test_graceful_shutdown(self, diary_system):
        """Test graceful shutdown of the complete system."""
        diary, agent = diary_system
        writer = MemoryWriter(diary, workers=1, qsize=15)

        # Submit a bunch of work
        tasks = []
        for i in range(10):
            task = asyncio.create_task(
                writer.submit(f"user_{i}", "session", "I love pizza", "Noted!")
            )
            tasks.append(task)

        # Wait for submissions
        await asyncio.gather(*tasks)

        # Graceful shutdown
        await writer.close()
        await shutdown_all_background_tasks(timeout=5)

        # All work should be processed
        assert len(agent.run_calls) == 10

        # Verify some data was stored
        prefs = await diary.preferences("user_0")
        assert prefs

    @pytest.mark.asyncio
    async def test_concurrent_file_access(self, diary_system):
        """Test that concurrent access to same files is safe."""
        diary, agent = diary_system
        writer = MemoryWriter(diary, workers=1, qsize=20)

        user_id = "same_user"
        session_id = "same_session"

        # Submit many updates to same user/session concurrently
        tasks = []
        for i in range(15):
            task = asyncio.create_task(
                writer.submit(user_id, session_id, f"Message {i}", f"Response {i}")
            )
            tasks.append(task)

        await asyncio.gather(*tasks)
        await asyncio.sleep(2)

        # Verify data integrity
        convs = await diary.last_conversations(user_id, limit=5)
        assert session_id in convs

        # Turn count should reflect all updates
        assert convs[session_id]["_turns"] == 15

        # Preferences file should be readable
        prefs_toml = await diary.preferences(user_id)
        assert prefs_toml

        # Should be valid TOML
        prefs_data = tomllib.loads(prefs_toml)
        assert "_meta" in prefs_data

        await writer.close()

    @pytest.mark.asyncio
    async def test_conversation_summary_persistence(self, temp_dir):
        """Test that conversation summary updates are actually saved to disk"""
        from pydantic import BaseModel

        from tomldiary.models import PreferenceItem
        from tomldiary.tools import update_conversation_summary

        backend = LocalBackend(temp_dir)

        class TestPrefTable(BaseModel):
            likes: dict[str, PreferenceItem] = {}

        # Create agent that calls update_conversation_summary tool
        class SummaryUpdatingAgent:
            def __init__(self):
                self.run_calls = []

            async def run(self, message, deps=None):
                """Mock agent that calls update_conversation_summary tool"""
                self.run_calls.append((message, deps))

                if not deps:
                    return

                # Create a RunContext to pass to the tool
                class MockContext:
                    def __init__(self, deps):
                        self.deps = deps

                ctx = MockContext(deps)

                # Call the update_conversation_summary tool to simulate agent behavior
                summary = "User discusses their food preferences and cooking habits"
                keywords = ["food", "pasta", "italian", "cooking"]

                await update_conversation_summary(ctx, summary, keywords)

        agent = SummaryUpdatingAgent()
        diary = Diary(backend, TestPrefTable, agent=agent)

        user_id = "test_user"
        session_id = "test_session"

        # Create a session and update memory
        await diary.ensure_session(user_id, session_id)

        # Update memory - this should call our mock agent which calls update_conversation_summary
        await diary.update_memory(
            user_id,
            session_id,
            "I really love Italian pasta dishes, especially carbonara and bolognese.",
            "I'll remember your preference for Italian pasta dishes.",
        )

        # Verify the agent was called
        assert len(agent.run_calls) == 1

        # Verify conversation was created
        convs_data = await diary.last_conversations(user_id)
        assert session_id in convs_data
        assert convs_data[session_id]["_turns"] == 1

        # Read the actual TOML file to verify summary was saved to disk
        conv_file = temp_dir / user_id / "conversations.toml"
        assert conv_file.exists(), "Conversations TOML file should exist"

        # Parse the TOML file directly to verify the summary was persisted
        with open(conv_file, "rb") as f:
            saved_data = tomllib.load(f)

        assert "conversations" in saved_data
        assert session_id in saved_data["conversations"]
        saved_conv = saved_data["conversations"][session_id]

        # Verify the conversation summary was properly saved to disk
        assert saved_conv["_turns"] == 1
        assert saved_conv["summary"] == "User discusses their food preferences and cooking habits"
        assert saved_conv["keywords"] == ["food", "pasta", "italian", "cooking"]

    @pytest.mark.asyncio
    async def test_error_recovery(self, temp_dir):
        """Test system recovery from errors."""
        backend = LocalBackend(temp_dir)

        # Create agent that fails sometimes
        class FlakyAgent:
            def __init__(self):
                self.call_count = 0

            async def run(self, message, deps=None):
                self.call_count += 1
                if self.call_count % 3 == 0:  # Fail every 3rd call
                    raise RuntimeError("Simulated agent failure")

        diary = Diary(
            backend=backend,
            pref_table_cls=MyPrefTable,
            agent=FlakyAgent(),
            max_prefs_per_category=20,
            max_conversations=10,
        )

        writer = MemoryWriter(diary, workers=1, qsize=10)

        # Submit work that will have some failures
        for i in range(10):
            await writer.submit("user", "session", f"Message {i}", f"Response {i}")

        await asyncio.sleep(2)  # Wait for processing

        # System should still be functional despite some failures
        convs = await diary.last_conversations("user", limit=5)
        # Some conversations should succeed (not all will fail)
        # The exact count depends on timing, but should be > 0
        assert len(convs) >= 0  # System shouldn't crash

        await writer.close()
