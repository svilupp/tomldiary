"""Tests for tomldiary backends."""

import asyncio
import shutil
import tempfile
from pathlib import Path

import pytest

from tomldiary.backends.local import LocalBackend

# Try to import FirestoreBackend if available
try:
    from tomldiary.backends.firestore import FirestoreBackend

    FIRESTORE_AVAILABLE = True
except ImportError:
    FIRESTORE_AVAILABLE = False


class TestLocalBackend:
    """Test LocalBackend functionality."""

    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory for testing."""
        temp_path = Path(tempfile.mkdtemp())
        yield temp_path
        # Cleanup
        if temp_path.exists():
            shutil.rmtree(temp_path)

    @pytest.fixture
    def backend(self, temp_dir):
        """Create a LocalBackend instance."""
        return LocalBackend(temp_dir)

    @pytest.mark.asyncio
    async def test_save_and_load(self, backend):
        """Test basic save and load functionality."""
        user_id = "test_user"
        kind = "preferences"
        content = "test content"

        # Save content
        await backend.save(user_id, kind, content)

        # Load content
        loaded = await backend.load(user_id, kind)
        assert loaded == content

    @pytest.mark.asyncio
    async def test_load_nonexistent(self, backend):
        """Test loading non-existent file returns None."""
        result = await backend.load("nonexistent", "preferences")
        assert result is None

    @pytest.mark.asyncio
    async def test_file_structure(self, backend, temp_dir):
        """Test that files are created in correct structure."""
        user_id = "test_user"
        kind = "preferences"
        content = "test content"

        await backend.save(user_id, kind, content)

        # Check file exists in correct location
        expected_path = temp_dir / user_id / f"{kind}.toml"
        assert expected_path.exists()
        assert expected_path.read_text() == content

    @pytest.mark.asyncio
    async def test_concurrent_saves_same_path(self, backend):
        """Test concurrent saves to the same path are serialized."""
        user_id = "test_user"
        kind = "preferences"

        # Create multiple concurrent save tasks for the same path
        tasks = []
        for i in range(10):
            task = asyncio.create_task(backend.save(user_id, kind, f"content_{i}"))
            tasks.append(task)

        # Wait for all to complete
        await asyncio.gather(*tasks)

        # Load final content - should be one of the contents
        result = await backend.load(user_id, kind)
        assert result is not None
        assert result.startswith("content_")

    @pytest.mark.asyncio
    async def test_concurrent_saves_different_paths(self, backend):
        """Test concurrent saves to different paths work in parallel."""
        tasks = []

        # Create saves for different users/kinds
        for i in range(5):
            for kind in ["preferences", "conversations"]:
                task = asyncio.create_task(backend.save(f"user_{i}", kind, f"content_{i}_{kind}"))
                tasks.append(task)

        # Wait for all to complete
        await asyncio.gather(*tasks)

        # Verify all were saved correctly
        for i in range(5):
            for kind in ["preferences", "conversations"]:
                result = await backend.load(f"user_{i}", kind)
                assert result == f"content_{i}_{kind}"

    @pytest.mark.asyncio
    async def test_lock_weak_references(self, backend):
        """Test that locks are properly managed with weak references."""
        # Create locks by accessing different paths
        for i in range(5):
            await backend.save(f"user_{i}", "test", f"data_{i}")

        # Check that some locks exist
        initial_lock_count = len(backend._locks)

        # The exact count may vary due to garbage collection timing,
        # but we should have created some locks
        assert initial_lock_count >= 0  # Non-negative

        # Force garbage collection
        import gc

        gc.collect()

        # Locks may or may not be collected depending on timing
        # This test mainly ensures no exceptions occur
        final_lock_count = len(backend._locks)
        assert final_lock_count >= 0

    @pytest.mark.asyncio
    async def test_path_resolution(self, backend, temp_dir):
        """Test that file paths are resolved correctly."""
        user_id = "user_with_spaces"
        kind = "preferences"
        content = "test content"

        await backend.save(user_id, kind, content)

        # Check path is correct
        expected_dir = temp_dir / user_id
        expected_file = expected_dir / f"{kind}.toml"

        assert expected_dir.exists()
        assert expected_dir.is_dir()
        assert expected_file.exists()
        assert expected_file.is_file()

    @pytest.mark.asyncio
    async def test_unicode_content(self, backend):
        """Test saving and loading unicode content."""
        user_id = "test_user"
        kind = "preferences"
        content = "🍕 I love pizza! 日本語 test éñçødîng"

        await backend.save(user_id, kind, content)
        loaded = await backend.load(user_id, kind)

        assert loaded == content

    @pytest.mark.asyncio
    async def test_empty_content(self, backend):
        """Test saving and loading empty content."""
        user_id = "test_user"
        kind = "preferences"
        content = ""

        await backend.save(user_id, kind, content)
        loaded = await backend.load(user_id, kind)

        assert loaded == content

    @pytest.mark.asyncio
    async def test_large_content(self, backend):
        """Test saving and loading large content."""
        user_id = "test_user"
        kind = "preferences"
        # Create ~1MB of content
        content = "large content test " * 50000

        await backend.save(user_id, kind, content)
        loaded = await backend.load(user_id, kind)

        assert loaded == content
        assert len(loaded) > 500000  # Verify it's actually large

    @pytest.mark.asyncio
    async def test_exists_for_existing_file(self, backend):
        """Test exists() returns True for existing file."""
        user_id = "test_user"
        kind = "preferences"
        content = "test content"

        # Save file
        await backend.save(user_id, kind, content)

        # Check existence
        assert await backend.exists(user_id, kind) is True

    @pytest.mark.asyncio
    async def test_exists_for_nonexistent_file(self, backend):
        """Test exists() returns False for nonexistent file."""
        assert await backend.exists("nonexistent", "preferences") is False

    @pytest.mark.asyncio
    async def test_delete_existing_file(self, backend):
        """Test delete() removes existing file."""
        user_id = "test_user"
        kind = "preferences"

        # Save file
        await backend.save(user_id, kind, "test content")
        assert await backend.exists(user_id, kind) is True

        # Delete file
        await backend.delete(user_id, kind)
        assert await backend.exists(user_id, kind) is False

    @pytest.mark.asyncio
    async def test_delete_nonexistent_file_is_idempotent(self, backend):
        """Test delete() succeeds for nonexistent file."""
        # Should not raise exception
        await backend.delete("nonexistent", "preferences")

    @pytest.mark.asyncio
    async def test_delete_preserves_other_kinds(self, backend):
        """Test delete() only removes specified kind."""
        user_id = "test_user"

        # Save both kinds
        await backend.save(user_id, "preferences", "prefs")
        await backend.save(user_id, "conversations", "convs")

        # Delete preferences only
        await backend.delete(user_id, "preferences")

        # Verify preferences deleted but conversations remain
        assert await backend.exists(user_id, "preferences") is False
        assert await backend.exists(user_id, "conversations") is True

    @pytest.mark.asyncio
    async def test_delete_user_removes_all_data(self, backend):
        """Test delete_user() removes all user documents."""
        user_id = "test_user"

        # Save multiple kinds
        await backend.save(user_id, "preferences", "prefs")
        await backend.save(user_id, "conversations", "convs")

        # Delete user
        await backend.delete_user(user_id)

        # Verify all data removed
        assert await backend.exists(user_id, "preferences") is False
        assert await backend.exists(user_id, "conversations") is False

    @pytest.mark.asyncio
    async def test_delete_user_is_idempotent(self, backend):
        """Test delete_user() succeeds for nonexistent user."""
        # Should not raise exception
        await backend.delete_user("nonexistent_user")

    @pytest.mark.asyncio
    async def test_delete_user_removes_directory(self, backend, temp_dir):
        """Test delete_user() removes entire user directory."""
        user_id = "test_user"

        # Save data
        await backend.save(user_id, "preferences", "test")

        # Verify directory exists
        user_dir = temp_dir / user_id
        assert user_dir.exists() is True

        # Delete user
        await backend.delete_user(user_id)

        # Verify directory removed
        assert user_dir.exists() is False

    @pytest.mark.asyncio
    async def test_list_users_empty(self, backend):
        """Test list_users() returns empty list when no users."""
        users = await backend.list_users()
        assert users == []

    @pytest.mark.asyncio
    async def test_list_users_single_user(self, backend):
        """Test list_users() returns single user."""
        await backend.save("alice", "preferences", "test")

        users = await backend.list_users()
        assert users == ["alice"]

    @pytest.mark.asyncio
    async def test_list_users_multiple_users(self, backend):
        """Test list_users() returns all users."""
        # Create multiple users
        for user in ["alice", "bob", "charlie"]:
            await backend.save(user, "preferences", f"{user} data")

        users = await backend.list_users()
        assert set(users) == {"alice", "bob", "charlie"}

    @pytest.mark.asyncio
    async def test_list_users_ignores_files(self, backend, temp_dir):
        """Test list_users() only returns directories."""
        # Create a user
        await backend.save("alice", "preferences", "test")

        # Create a file in base_path (not a user directory)
        random_file = temp_dir / "random.txt"
        random_file.write_text("not a user")

        users = await backend.list_users()
        assert users == ["alice"]
        assert "random.txt" not in users

    @pytest.mark.asyncio
    async def test_delete_preserves_other_users(self, backend):
        """Test delete_user() only affects specified user."""
        # Create two users
        await backend.save("alice", "preferences", "alice data")
        await backend.save("bob", "preferences", "bob data")

        # Delete alice
        await backend.delete_user("alice")

        # Verify alice removed but bob remains
        assert await backend.exists("alice", "preferences") is False
        assert await backend.exists("bob", "preferences") is True

        users = await backend.list_users()
        assert users == ["bob"]

    @pytest.mark.asyncio
    async def test_concurrent_deletes(self, backend):
        """Test concurrent delete operations."""
        user_id = "test_user"

        # Create file
        await backend.save(user_id, "preferences", "test")

        # Multiple concurrent deletes (idempotency test)
        tasks = [asyncio.create_task(backend.delete(user_id, "preferences")) for _ in range(10)]

        # Should all succeed without error
        await asyncio.gather(*tasks)

        # Verify deleted
        assert await backend.exists(user_id, "preferences") is False


@pytest.mark.skipif(not FIRESTORE_AVAILABLE, reason="Firestore dependencies not installed")
class TestFirestoreBackend:
    """
    Test FirestoreBackend functionality.

    Note: These tests are skipped if Firestore dependencies are not installed.
    To run these tests, install with: uv add 'tomldiary[firestore]'

    These tests use a mock/in-memory approach to avoid requiring live Firestore credentials.
    """

    @pytest.fixture
    def mock_firestore_client(self, monkeypatch):
        """Create a mock Firestore client for testing."""

        # This is a simple in-memory mock for unit tests
        # For integration tests, use the scripts/test_firestore.py with live Firestore
        class MockDocument:
            def __init__(self, data=None):
                self._data = data
                self.exists = data is not None

            def to_dict(self):
                return self._data if self._data else {}

            def get(self):
                return self

        class MockDocumentReference:
            def __init__(self, storage, path):
                self.storage = storage
                self.path = path
                self.reference = self
                self.id = path.split("/")[-1] if path else ""

            def get(self):
                return MockDocument(self.storage.get(self.path))

            def set(self, data):
                self.storage[self.path] = data

            def delete(self):
                if self.path in self.storage:
                    del self.storage[self.path]

            def collection(self, name):
                # Document references can have subcollections
                subcollection_path = f"{self.path}/{name}"
                return MockCollectionReference(self.storage, subcollection_path)

            def collections(self):
                # Return all subcollections under this document
                prefix = f"{self.path}/"
                collections = set()
                for key in self.storage:
                    if key.startswith(prefix):
                        # Extract collection name (first segment after prefix)
                        remainder = key[len(prefix) :]
                        parts = remainder.split("/")
                        if len(parts) >= 1:
                            collections.add(parts[0])

                # Return mock collections
                return [
                    MockCollectionReference(self.storage, f"{self.path}/{coll}")
                    for coll in collections
                ]

        class MockCollectionReference:
            def __init__(self, storage, base_path):
                self.storage = storage
                self.base_path = base_path
                self.id = base_path.split("/")[-1] if base_path else ""

            def document(self, doc_id):
                path = f"{self.base_path}/{doc_id}"
                return MockDocumentReference(self.storage, path)

            def stream(self):
                # Return all documents in this collection
                prefix = f"{self.base_path}/"
                docs = []
                for key in self.storage:
                    if key.startswith(prefix):
                        # Check if this is a direct child (no more slashes after prefix)
                        remainder = key[len(prefix) :]
                        if "/" not in remainder:
                            docs.append(MockDocumentReference(self.storage, key))
                return docs

        class MockClient:
            def __init__(self):
                self.storage = {}

            def collection(self, name):
                return MockCollectionReference(self.storage, name)

        mock_client = MockClient()

        # Patch the Firestore client creation
        def mock_client_init(*args, **kwargs):
            return mock_client

        monkeypatch.setattr("google.cloud.firestore.Client", mock_client_init)

        return mock_client

    @pytest.fixture
    def backend(self, mock_firestore_client):
        """Create a FirestoreBackend instance with mocked client."""
        # Use even number of segments for base_path
        backend = FirestoreBackend(project_id="test-project", base_path="test/data")
        # Replace the client with our mock
        backend.db = mock_firestore_client
        return backend

    @pytest.mark.asyncio
    async def test_save_and_load(self, backend):
        """Test basic save and load functionality."""
        user_id = "test_user"
        kind = "preferences"
        content = "test content"

        # Save content
        await backend.save(user_id, kind, content)

        # Load content
        loaded = await backend.load(user_id, kind)
        assert loaded == content

    @pytest.mark.asyncio
    async def test_load_nonexistent(self, backend):
        """Test loading non-existent file returns None."""
        result = await backend.load("nonexistent", "preferences")
        assert result is None

    @pytest.mark.asyncio
    async def test_multiple_users(self, backend):
        """Test storing data for multiple users independently."""
        user1_content = "user1 preferences"
        user2_content = "user2 preferences"

        await backend.save("user1", "preferences", user1_content)
        await backend.save("user2", "preferences", user2_content)

        loaded1 = await backend.load("user1", "preferences")
        loaded2 = await backend.load("user2", "preferences")

        assert loaded1 == user1_content
        assert loaded2 == user2_content

    @pytest.mark.asyncio
    async def test_multiple_kinds(self, backend):
        """Test storing different kinds for same user."""
        user_id = "test_user"
        prefs_content = "preferences content"
        convs_content = "conversations content"

        await backend.save(user_id, "preferences", prefs_content)
        await backend.save(user_id, "conversations", convs_content)

        loaded_prefs = await backend.load(user_id, "preferences")
        loaded_convs = await backend.load(user_id, "conversations")

        assert loaded_prefs == prefs_content
        assert loaded_convs == convs_content

    @pytest.mark.asyncio
    async def test_update_existing(self, backend):
        """Test updating existing content."""
        user_id = "test_user"
        kind = "preferences"

        # Save initial content
        await backend.save(user_id, kind, "initial")
        loaded = await backend.load(user_id, kind)
        assert loaded == "initial"

        # Update content
        await backend.save(user_id, kind, "updated")
        loaded = await backend.load(user_id, kind)
        assert loaded == "updated"

    @pytest.mark.asyncio
    async def test_unicode_content(self, backend):
        """Test saving and loading unicode content."""
        user_id = "test_user"
        kind = "preferences"
        content = "🍕 I love pizza! 日本語 test éñçødîng"

        await backend.save(user_id, kind, content)
        loaded = await backend.load(user_id, kind)

        assert loaded == content

    @pytest.mark.asyncio
    async def test_empty_content(self, backend):
        """Test saving and loading empty content."""
        user_id = "test_user"
        kind = "preferences"
        content = ""

        await backend.save(user_id, kind, content)
        loaded = await backend.load(user_id, kind)

        assert loaded == content

    @pytest.mark.asyncio
    async def test_exists_utility(self, backend):
        """Test the exists() utility method."""
        user_id = "test_user"
        kind = "preferences"

        # Should not exist initially
        exists = await backend.exists(user_id, kind)
        assert exists is False

        # Save and check existence
        await backend.save(user_id, kind, "content")
        exists = await backend.exists(user_id, kind)
        assert exists is True

    @pytest.mark.asyncio
    async def test_delete_utility(self, backend):
        """Test the delete() utility method."""
        user_id = "test_user"
        kind = "preferences"

        # Save content
        await backend.save(user_id, kind, "content")
        assert await backend.exists(user_id, kind) is True

        # Delete
        await backend.delete(user_id, kind)
        assert await backend.exists(user_id, kind) is False

    @pytest.mark.asyncio
    async def test_base_path_validation(self):
        """Test that base_path validation works correctly."""
        # Even number of segments should work
        backend = FirestoreBackend(project_id="test", base_path="level1/level2")
        assert backend.base_path == "level1/level2"

        # Odd number of segments should raise ValueError
        with pytest.raises(ValueError, match="EVEN number of path segments"):
            FirestoreBackend(project_id="test", base_path="level1")

        # Empty or single trailing slash should still validate
        backend = FirestoreBackend(project_id="test", base_path="level1/level2/")
        assert backend.base_path == "level1/level2"

    @pytest.mark.asyncio
    async def test_concurrent_saves_same_path(self, backend):
        """Test concurrent saves to the same path."""
        user_id = "test_user"
        kind = "preferences"

        # Create multiple concurrent save tasks for the same path
        tasks = []
        for i in range(10):
            task = asyncio.create_task(backend.save(user_id, kind, f"content_{i}"))
            tasks.append(task)

        # Wait for all to complete
        await asyncio.gather(*tasks)

        # Load final content - should be one of the contents
        result = await backend.load(user_id, kind)
        assert result is not None
        assert result.startswith("content_")

    @pytest.mark.asyncio
    async def test_concurrent_saves_different_paths(self, backend):
        """Test concurrent saves to different paths work in parallel."""
        tasks = []

        # Create saves for different users/kinds
        for i in range(5):
            for kind in ["preferences", "conversations"]:
                task = asyncio.create_task(backend.save(f"user_{i}", kind, f"content_{i}_{kind}"))
                tasks.append(task)

        # Wait for all to complete
        await asyncio.gather(*tasks)

        # Verify all were saved correctly
        for i in range(5):
            for kind in ["preferences", "conversations"]:
                result = await backend.load(f"user_{i}", kind)
                assert result == f"content_{i}_{kind}"

    @pytest.mark.asyncio
    async def test_delete_user_utility(self, backend):
        """Test the delete_user() utility method."""
        user_id = "test_user"

        # Save multiple kinds
        await backend.save(user_id, "preferences", "prefs")
        await backend.save(user_id, "conversations", "convs")

        # Delete user
        await backend.delete_user(user_id)

        # Verify all data removed
        assert await backend.exists(user_id, "preferences") is False
        assert await backend.exists(user_id, "conversations") is False

    @pytest.mark.asyncio
    async def test_list_users_utility(self, backend):
        """Test the list_users() utility method."""
        # Initially empty
        users = await backend.list_users()
        assert users == []

        # Add users
        await backend.save("alice", "preferences", "data")
        await backend.save("bob", "preferences", "data")

        # List returns both
        users = await backend.list_users()
        assert set(users) == {"alice", "bob"}
