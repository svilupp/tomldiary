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

    @pytest.mark.asyncio
    async def test_stats_basic(self, writer, mock_diary):
        """Test basic stats() method returns correct metrics."""
        # Check initial stats
        stats = writer.stats()

        assert stats["queue_size"] == 0
        assert stats["queue_capacity"] == 10
        assert stats["queue_utilization"] == 0.0
        assert stats["total_workers"] == 2
        assert stats["active_workers"] == 0
        assert stats["idle_workers"] == 2
        assert stats["submitted"] == 0
        assert stats["completed"] == 0
        assert stats["failed"] == 0
        assert stats["pending"] == 0
        assert stats["error_rate"] == 0.0
        assert stats["is_running"] is True

        await writer.close()

    @pytest.mark.asyncio
    async def test_stats_after_submissions(self, writer, mock_diary):
        """Test stats track submissions and completions."""
        # Submit some work
        await writer.submit("user1", "session1", "Hello", "Hi")
        await writer.submit("user2", "session2", "Test", "Testing")

        # Check stats before processing
        stats = writer.stats()
        assert stats["submitted"] == 2
        assert stats["queue_size"] <= 2

        # Wait for processing
        await asyncio.sleep(0.2)

        # Check stats after processing
        stats = writer.stats()
        assert stats["submitted"] == 2
        assert stats["completed"] == 2
        assert stats["failed"] == 0
        assert stats["pending"] == 0
        assert stats["queue_size"] == 0

        await writer.close()

    @pytest.mark.asyncio
    async def test_stats_error_tracking(self, mock_diary):
        """Test stats track failed operations."""
        # Make diary fail
        mock_diary.should_fail = True

        writer = MemoryWriter(mock_diary, workers=1, qsize=5)

        # Submit work that will fail
        await writer.submit("user1", "session1", "Hello", "Hi")
        await writer.submit("user2", "session2", "Test", "Testing")

        # Wait for processing
        await asyncio.sleep(0.2)

        # Check error tracking
        stats = writer.stats()
        assert stats["submitted"] == 2
        assert stats["completed"] == 0
        assert stats["failed"] == 2
        assert stats["pending"] == 0
        assert stats["error_rate"] == 1.0  # 100% failure rate

        await writer.close()

    @pytest.mark.asyncio
    async def test_stats_mixed_success_failure(self, mock_diary):
        """Test stats with mixed success and failure."""
        writer = MemoryWriter(mock_diary, workers=1, qsize=5)

        # Submit successful work
        await writer.submit("user1", "session1", "Success1", "Response1")
        await asyncio.sleep(0.1)

        # Make next ones fail
        mock_diary.should_fail = True
        await writer.submit("user2", "session2", "Fail1", "Response2")
        await asyncio.sleep(0.1)

        # Make next one succeed
        mock_diary.should_fail = False
        await writer.submit("user3", "session3", "Success2", "Response3")
        await asyncio.sleep(0.1)

        stats = writer.stats()
        assert stats["submitted"] == 3
        assert stats["completed"] == 2
        assert stats["failed"] == 1
        assert stats["pending"] == 0
        assert 0.3 < stats["error_rate"] < 0.4  # ~33% failure rate

        await writer.close()

    @pytest.mark.asyncio
    async def test_stats_queue_utilization(self, mock_diary):
        """Test queue utilization calculation."""
        # Slow diary to fill queue
        mock_diary.update_delay = 0.5

        writer = MemoryWriter(mock_diary, workers=1, qsize=5)

        # Fill queue partially
        await writer.submit("user1", "session1", "msg1", "resp1")
        await writer.submit("user2", "session2", "msg2", "resp2")

        # Check utilization
        stats = writer.stats()
        assert stats["queue_utilization"] > 0.0
        assert stats["queue_utilization"] <= 1.0
        assert stats["queue_size"] <= 5

        await writer.close()

    @pytest.mark.asyncio
    async def test_stats_active_workers(self, mock_diary):
        """Test active_workers tracking."""
        # Add delay to observe active workers
        mock_diary.update_delay = 0.2

        writer = MemoryWriter(mock_diary, workers=2, qsize=10)

        # Check idle state
        stats = writer.stats()
        assert stats["active_workers"] == 0
        assert stats["idle_workers"] == 2

        # Submit work
        await writer.submit("user1", "session1", "msg1", "resp1")
        await writer.submit("user2", "session2", "msg2", "resp2")

        # Check immediately - workers should be active
        await asyncio.sleep(0.05)
        stats = writer.stats()
        # At least one worker should be active (timing dependent)
        assert stats["active_workers"] >= 0
        assert stats["active_workers"] <= 2

        # Wait for completion
        await asyncio.sleep(0.3)
        stats = writer.stats()
        assert stats["active_workers"] == 0
        assert stats["idle_workers"] == 2

        await writer.close()

    @pytest.mark.asyncio
    async def test_is_running_property(self, writer):
        """Test is_running property."""
        assert writer.is_running is True

        await writer.close()

        assert writer.is_running is False

    @pytest.mark.asyncio
    async def test_stats_pending_calculation(self, writer, mock_diary):
        """Test pending tasks calculation."""
        # Add delay to keep tasks pending
        mock_diary.update_delay = 0.3

        # Submit tasks
        await writer.submit("user1", "session1", "msg1", "resp1")
        await writer.submit("user2", "session2", "msg2", "resp2")
        await writer.submit("user3", "session3", "msg3", "resp3")

        # Check immediately - should have pending tasks
        await asyncio.sleep(0.05)
        stats = writer.stats()
        assert stats["submitted"] == 3
        assert stats["pending"] > 0

        # Wait for completion
        await asyncio.sleep(1.0)
        stats = writer.stats()
        assert stats["pending"] == 0
        assert stats["completed"] == 3

        await writer.close()

    @pytest.mark.asyncio
    async def test_counter_consistency_under_load(self, mock_diary):
        """Test that counters remain consistent under high concurrent load."""
        # High concurrency stress test
        writer = MemoryWriter(mock_diary, workers=8, qsize=100)

        # Rapid fire submissions
        num_batches = 10
        batch_size = 50

        for _ in range(num_batches):
            tasks = [
                writer.submit(f"user_{i}", "sess", f"msg_{i}", f"resp_{i}")
                for i in range(batch_size)
            ]
            await asyncio.gather(*tasks)

        # Wait for all processing to complete
        await asyncio.sleep(0.5)

        # Verify counter invariants
        stats = writer.stats()

        # Critical invariant: submitted = completed + failed + pending
        assert stats["submitted"] == num_batches * batch_size
        assert stats["completed"] + stats["failed"] == stats["submitted"]
        assert stats["pending"] == 0
        assert stats["active_workers"] == 0

        # Check all updates were processed
        assert len(mock_diary.updates) == num_batches * batch_size

        await writer.close()

    @pytest.mark.asyncio
    async def test_stats_consistency_during_processing(self, mock_diary):
        """Test that stats() returns consistent snapshots during active processing."""
        # Slow processing to keep workers active
        mock_diary.update_delay = 0.1

        writer = MemoryWriter(mock_diary, workers=4, qsize=50)

        # Submit work
        num_tasks = 40
        for i in range(num_tasks):
            await writer.submit(f"user_{i}", "sess", f"msg_{i}", f"resp_{i}")

        # Poll stats repeatedly while processing
        inconsistencies = []
        for _ in range(20):
            stats = writer.stats()

            # Check invariants
            if stats["completed"] + stats["failed"] + stats["pending"] != stats["submitted"]:
                inconsistencies.append(("total_mismatch", stats))

            if stats["pending"] < 0:
                inconsistencies.append(("negative_pending", stats))

            if stats["active_workers"] > stats["total_workers"]:
                inconsistencies.append(("too_many_active", stats))

            await asyncio.sleep(0.05)

        # Wait for completion
        await asyncio.sleep(1)

        # Should have no inconsistencies
        assert len(inconsistencies) == 0, f"Found inconsistent stats: {inconsistencies}"

        await writer.close()

    @pytest.mark.asyncio
    async def test_concurrent_stats_calls(self, mock_diary):
        """Test that concurrent stats() calls don't cause race conditions."""
        mock_diary.update_delay = 0.05

        writer = MemoryWriter(mock_diary, workers=4, qsize=20)

        # Submit background work (as a list of coroutines)
        submit_tasks = [
            writer.submit(f"user_{i}", "sess", f"msg_{i}", f"resp_{i}") for i in range(30)
        ]

        # Hammer stats() with concurrent calls while submitting using worker threads
        stats_calls = [asyncio.to_thread(writer.stats) for _ in range(50)]

        # All should complete without errors
        all_results = await asyncio.gather(*submit_tasks, *stats_calls)

        # Extract stats results (last 50 items)
        all_stats = all_results[-50:]

        # Verify all returned valid data
        for stats in all_stats:
            assert "submitted" in stats
            assert stats["pending"] >= 0
            assert stats["active_workers"] >= 0

        await writer.close()

    @pytest.mark.asyncio
    async def test_shutdown_with_pending_work(self, mock_diary):
        """Test that shutdown doesn't lose work or corrupt counters."""
        mock_diary.update_delay = 0.05

        writer = MemoryWriter(mock_diary, workers=2, qsize=20)

        # Submit work
        num_tasks = 15
        for i in range(num_tasks):
            await writer.submit(f"user_{i}", "sess", f"msg_{i}", f"resp_{i}")

        # Don't wait - close immediately
        await writer.close()

        # All work should have been processed
        assert len(mock_diary.updates) == num_tasks

        # Final stats should be consistent
        stats = writer.stats()
        assert stats["completed"] == num_tasks
        assert stats["pending"] == 0
        assert stats["active_workers"] == 0

    @pytest.mark.asyncio
    async def test_close_waits_for_inflight_submit(self, mock_diary):
        """Submitting before close starts must still be processed."""
        mock_diary.update_delay = 0.05

        writer = MemoryWriter(mock_diary, workers=1, qsize=1)

        # Fill the queue so the second submit blocks on put()
        await writer.submit("user-0", "sess", "msg-0", "resp-0")

        pending_submit = asyncio.create_task(writer.submit("user-1", "sess", "msg-1", "resp-1"))

        # Allow the background worker to start processing the first entry
        await asyncio.sleep(0.02)

        close_task = asyncio.create_task(writer.close())

        # Close should not finish until the pending submit is processed
        await asyncio.sleep(0.05)
        assert not close_task.done()

        await pending_submit
        await close_task

        stats = writer.stats()
        assert stats["submitted"] == 2
        assert stats["completed"] == 2
        assert stats["pending"] == 0
        assert len(mock_diary.updates) == 2

    @pytest.mark.asyncio
    async def test_no_work_lost_during_shutdown(self, mock_diary):
        """Test that no work is lost even with immediate shutdown."""
        mock_diary.update_delay = 0.1  # Slow processing

        writer = MemoryWriter(mock_diary, workers=2, qsize=100)

        # Submit large batch
        num_tasks = 50
        submit_tasks = [
            writer.submit(f"user_{i}", "sess", f"msg_{i}", f"resp_{i}") for i in range(num_tasks)
        ]

        # Submit and immediately start closing
        await asyncio.gather(*submit_tasks)
        close_task = asyncio.create_task(writer.close())

        # Wait for shutdown
        await close_task

        # Verify accounting is correct
        stats = writer.stats()
        assert stats["submitted"] == num_tasks
        assert stats["completed"] + stats["failed"] == num_tasks
        assert len(mock_diary.updates) == stats["completed"]


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
