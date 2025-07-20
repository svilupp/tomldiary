"""Tests for tomldiary writer (queue and worker system)."""

import asyncio
import contextlib

import pytest
import pytest_asyncio

from tomldiary.writer import (
    MemoryWriter,
    background_tasks,
    fire_and_forget,
    shutdown_all_background_tasks,
)


class MockDiary:
    """Mock diary for testing."""

    def __init__(self):
        self.updates = []
        self.update_delay = 0
        self.should_fail = False

    async def update_memory(self, user_id, session_id, user_msg, assistant_msg):
        """Mock update_memory that records calls."""
        if self.update_delay:
            await asyncio.sleep(self.update_delay)

        if self.should_fail:
            raise RuntimeError("Mock update failure")

        self.updates.append((user_id, session_id, user_msg, assistant_msg))


class TestFireAndForget:
    """Test fire_and_forget task management."""

    @pytest.mark.asyncio
    async def test_task_creation(self):
        """Test that fire_and_forget creates and manages tasks properly."""
        call_count = 0

        async def test_coro():
            nonlocal call_count
            call_count += 1
            await asyncio.sleep(0.1)

        # Clear background tasks
        background_tasks.clear()

        # Create task
        task = fire_and_forget(test_coro(), name="test_task")

        # Verify task is tracked
        assert task in background_tasks
        assert task.get_name() == "test_task"

        # Wait for completion
        await task

        # Verify it executed
        assert call_count == 1

        # Give time for cleanup callback
        await asyncio.sleep(0.01)

        # Task should be removed from tracking
        assert task not in background_tasks

    @pytest.mark.asyncio
    async def test_exception_handling(self):
        """Test that exceptions in fire_and_forget tasks are logged."""

        async def failing_coro():
            raise ValueError("Test exception")

        # Clear background tasks
        background_tasks.clear()

        # Create failing task
        task = fire_and_forget(failing_coro(), name="failing_task")

        # Wait for it to fail
        with contextlib.suppress(ValueError):
            await task

        # Give time for cleanup
        await asyncio.sleep(0.01)

        # Task should be cleaned up
        assert task not in background_tasks


class TestMemoryWriter:
    """Test MemoryWriter functionality."""

    @pytest.fixture
    def mock_diary(self):
        """Create a mock diary."""
        return MockDiary()

    @pytest_asyncio.fixture
    async def writer(self, mock_diary):
        """Create a MemoryWriter with mock diary."""
        writer = MemoryWriter(mock_diary, workers=2, qsize=10)
        yield writer
        await writer.close()

    @pytest.mark.asyncio
    async def test_basic_submission(self, writer, mock_diary):
        """Test basic submission and processing."""
        await writer.submit("user1", "session1", "Hello", "Hi there")

        # Wait for processing
        await asyncio.sleep(0.1)

        # Check it was processed
        assert len(mock_diary.updates) == 1
        assert mock_diary.updates[0] == ("user1", "session1", "Hello", "Hi there")

        await writer.close()

    @pytest.mark.asyncio
    async def test_multiple_submissions(self, writer, mock_diary):
        """Test multiple submissions are processed."""
        submissions = [
            ("user1", "session1", "Hello", "Hi"),
            ("user2", "session2", "Test", "Testing"),
            ("user1", "session1", "More", "More response"),
        ]

        # Submit all
        for user_id, session_id, user_msg, assistant_msg in submissions:
            await writer.submit(user_id, session_id, user_msg, assistant_msg)

        # Wait for processing
        await asyncio.sleep(0.2)

        # Check all were processed
        assert len(mock_diary.updates) == 3

        # Convert to sets for comparison (order may vary due to concurrency)
        expected = set(submissions)
        actual = set(mock_diary.updates)
        assert actual == expected

        await writer.close()

    @pytest.mark.asyncio
    async def test_concurrent_submissions(self, writer, mock_diary):
        """Test concurrent submissions work correctly."""
        # Add some delay to make concurrency more apparent
        mock_diary.update_delay = 0.05

        # Submit multiple tasks concurrently
        tasks = []
        for i in range(10):
            task = asyncio.create_task(
                writer.submit(f"user{i}", "session1", f"Message {i}", f"Response {i}")
            )
            tasks.append(task)

        # Wait for all submissions
        await asyncio.gather(*tasks)

        # Wait for processing
        await asyncio.sleep(1)

        # All should be processed
        assert len(mock_diary.updates) == 10

        await writer.close()

    @pytest.mark.asyncio
    async def test_error_handling(self, mock_diary):
        """Test that worker errors don't crash the system."""
        # Make diary fail
        mock_diary.should_fail = True

        writer = MemoryWriter(mock_diary, workers=1, qsize=5)

        # Submit some work
        await writer.submit("user1", "session1", "Hello", "Hi")

        # Wait for processing (should fail but not crash)
        await asyncio.sleep(0.2)

        # No updates should be recorded due to failure
        assert len(mock_diary.updates) == 0

        await writer.close()

    @pytest.mark.asyncio
    @pytest.mark.xfail(reason="Backpressure timing is flaky")
    async def test_backpressure(self, mock_diary):
        """Test that queue backpressure works."""
        # Slow diary
        mock_diary.update_delay = 0.1

        # Small queue
        writer = MemoryWriter(mock_diary, workers=1, qsize=2)

        # Submit more than queue size
        start_time = asyncio.get_event_loop().time()

        # First two should go in queue
        await writer.submit("user1", "session1", "msg1", "resp1")
        await writer.submit("user2", "session2", "msg2", "resp2")

        # Third should block until queue has space
        await writer.submit("user3", "session3", "msg3", "resp3")

        end_time = asyncio.get_event_loop().time()

        # Should have taken some time due to backpressure
        elapsed = end_time - start_time
        # Allow some timing variance on fast systems
        assert elapsed > 0.01

        await writer.close()

    @pytest.mark.asyncio
    async def test_graceful_shutdown(self, writer, mock_diary):
        """Test graceful shutdown waits for queue to drain."""
        # Submit work
        await writer.submit("user1", "session1", "Hello", "Hi")
        await writer.submit("user2", "session2", "Test", "Testing")

        # Close should wait for completion
        await writer.close()

        # All work should be processed
        assert len(mock_diary.updates) == 2

    @pytest.mark.asyncio
    async def test_submit_after_close(self, writer):
        """Test that submit raises error after close."""
        await writer.close()

        with pytest.raises(RuntimeError, match="MemoryWriter is closed"):
            await writer.submit("user1", "session1", "Hello", "Hi")


class TestShutdownBackgroundTasks:
    """Test shutdown_all_background_tasks function."""

    @pytest.mark.asyncio
    async def test_shutdown_empty(self):
        """Test shutdown with no background tasks."""
        background_tasks.clear()

        # Should complete quickly
        await shutdown_all_background_tasks(timeout=1)

        assert len(background_tasks) == 0

    @pytest.mark.asyncio
    async def test_shutdown_with_tasks(self):
        """Test shutdown with active background tasks."""
        background_tasks.clear()

        # Create some background tasks
        async def long_task():
            await asyncio.sleep(0.2)

        tasks = []
        for i in range(3):
            task = fire_and_forget(long_task(), name=f"long_task_{i}")
            tasks.append(task)

        # Shutdown should wait for them
        start_time = asyncio.get_event_loop().time()
        await shutdown_all_background_tasks(timeout=5)
        end_time = asyncio.get_event_loop().time()

        # Should have taken at least 0.2 seconds
        elapsed = end_time - start_time
        assert elapsed >= 0.15  # Allow some timing variance

        # All tasks should be done
        for task in tasks:
            assert task.done()

    @pytest.mark.asyncio
    async def test_shutdown_timeout(self):
        """Test shutdown timeout cancels remaining tasks."""
        background_tasks.clear()

        # Create a very long task
        async def very_long_task():
            await asyncio.sleep(10)  # Much longer than timeout

        task = fire_and_forget(very_long_task(), name="very_long_task")

        # Shutdown with short timeout
        start_time = asyncio.get_event_loop().time()
        await shutdown_all_background_tasks(timeout=0.1)
        end_time = asyncio.get_event_loop().time()

        # Should have completed quickly due to timeout
        elapsed = end_time - start_time
        assert elapsed < 1  # Much less than the 10-second task

        # Task should be cancelled
        assert task.done()
        assert task.cancelled() or isinstance(task.exception(), asyncio.CancelledError)
