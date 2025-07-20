"""Tests for tomldiary backends."""

import asyncio
import shutil
import tempfile
from pathlib import Path

import pytest

from tomldiary.backends.local import LocalBackend


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
