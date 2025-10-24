import asyncio
import os
import threading

from .logging import get_logger

log = get_logger(__name__)

# Configuration defaults
QUEUE_MAXSIZE = 1000
WORKERS = max(8, (os.cpu_count() or 1) * 2)
SHUTDOWN_TIMEOUT = 30

# Global task registry to prevent garbage collection
background_tasks: set[asyncio.Task] = set()


def fire_and_forget(coro, *, name=None):
    """Create a background task with proper lifecycle management."""
    task = asyncio.create_task(coro, name=name)
    background_tasks.add(task)
    task.add_done_callback(background_tasks.discard)
    task.add_done_callback(
        lambda t: log.exception("%s crashed", t.get_name(), exc_info=t.exception())
        if t.exception()
        else None
    )
    return task


class MemoryWriter:
    """Queue-based memory writer with worker pool for concurrent processing."""

    def __init__(self, diary, *, workers=WORKERS, qsize=QUEUE_MAXSIZE):
        self.diary = diary
        self.q = asyncio.Queue(maxsize=qsize)

        # Synchronization lock for counters/state. Use threading.Lock so synchronous stats()
        # can take a consistent snapshot without awaiting.
        self._state_lock = threading.Lock()

        self.workers = [
            fire_and_forget(self._worker(i), name=f"memory-worker-{i}") for i in range(workers)
        ]
        self._accepting = True
        self._shutdown = False

        # Observability metrics (protect all updates with _state_lock)
        self._submitted_count = 0
        self._completed_count = 0
        self._failed_count = 0
        self._active_workers = 0

    async def submit(self, user_id: str, session_id: str, user_msg: str, assistant_msg: str):
        """Submit a memory update request to the queue (may block on backpressure)."""
        with self._state_lock:
            if not self._accepting:
                raise RuntimeError("MemoryWriter is closed")
            self._submitted_count += 1

        # Queue operations are thread-safe, can be done outside lock
        await self.q.put((user_id, session_id, user_msg, assistant_msg))

    async def _worker(self, worker_id: int):
        """Worker task that processes memory updates from the queue."""
        log.debug(f"Memory worker {worker_id} started")
        try:
            while True:
                with self._state_lock:
                    shutting_down = self._shutdown
                if shutting_down and self.q.empty():
                    break

                try:
                    # Wait for work with a timeout to allow graceful shutdown
                    user_id, session_id, user_msg, assistant_msg = await asyncio.wait_for(
                        self.q.get(), timeout=1.0
                    )
                except TimeoutError:
                    continue

                # Increment active workers counter (thread-safe)
                with self._state_lock:
                    self._active_workers += 1

                try:
                    await self._process(user_id, session_id, user_msg, assistant_msg)

                    # Increment completed counter (thread-safe)
                    with self._state_lock:
                        self._completed_count += 1
                except Exception as e:
                    # Increment failed counter (thread-safe)
                    with self._state_lock:
                        self._failed_count += 1
                    log.exception(f"Worker {worker_id} failed to process memory update: {e}")
                finally:
                    # Decrement active workers counter (thread-safe)
                    with self._state_lock:
                        self._active_workers -= 1
                    self.q.task_done()
        except asyncio.CancelledError:
            log.debug(f"Memory worker {worker_id} cancelled")
        except Exception as e:
            log.exception(f"Memory worker {worker_id} crashed: {e}")

    async def _process(self, user_id: str, session_id: str, user_msg: str, assistant_msg: str):
        """Process a single memory update."""
        await self.diary.update_memory(user_id, session_id, user_msg, assistant_msg)

    def stats(self) -> dict[str, int | float | bool]:
        """
        Get current writer statistics for observability and monitoring.

        Returns a consistent snapshot of all metrics by reading them atomically under lock.
        This prevents inconsistent states (e.g., completed > submitted) that could occur
        if counters are updated between reads.

        Returns:
            Dictionary containing:
            - queue_size: Current number of items in queue
            - queue_capacity: Maximum queue size
            - queue_utilization: Queue fullness (0.0 to 1.0)
            - total_workers: Number of worker tasks
            - active_workers: Workers currently processing tasks
            - idle_workers: Workers waiting for tasks
            - submitted: Total tasks submitted since start
            - completed: Total tasks completed successfully
            - failed: Total tasks that raised exceptions
            - pending: Current tasks in flight (submitted - completed - failed)
            - error_rate: Ratio of failed to submitted tasks
            - is_running: Whether writer is accepting new tasks
        """
        # Read all counters atomically to ensure consistent snapshot
        with self._state_lock:
            submitted = self._submitted_count
            completed = self._completed_count
            failed = self._failed_count
            active_workers = self._active_workers
            accepting = self._accepting

        # Queue operations are thread-safe, can read outside lock
        queue_size = self.q.qsize()
        queue_capacity = self.q.maxsize
        total_workers = len(self.workers)

        return {
            "queue_size": queue_size,
            "queue_capacity": queue_capacity,
            "queue_utilization": queue_size / queue_capacity if queue_capacity > 0 else 0.0,
            "total_workers": total_workers,
            "active_workers": active_workers,
            "idle_workers": total_workers - active_workers,
            "submitted": submitted,
            "completed": completed,
            "failed": failed,
            "pending": submitted - completed - failed,
            "error_rate": failed / max(submitted, 1),
            "is_running": accepting,
        }

    @property
    def is_running(self) -> bool:
        """
        Check if writer is currently accepting tasks.

        Note: This read is not synchronized, so the value may be slightly stale
        in high-concurrency scenarios. For a guaranteed consistent read, use
        stats()['is_running'] instead.
        """
        return self._accepting

    async def close(self):
        """Gracefully shutdown the writer and all workers."""
        log.info("Shutting down MemoryWriter...")

        with self._state_lock:
            if not self._accepting and self._shutdown:
                # Already closed
                return
            self._accepting = False

        # Wait for queue to drain with timeout to prevent deadlock
        # (keep workers processing while accepting is disabled)
        try:
            await asyncio.wait_for(self.q.join(), timeout=SHUTDOWN_TIMEOUT)
            log.debug("Queue drained successfully")
        except TimeoutError:
            remaining = self.q.qsize()
            log.warning(
                f"Queue did not drain within {SHUTDOWN_TIMEOUT}s timeout, "
                f"{remaining} items remaining. Proceeding with worker shutdown."
            )

        # Signal workers to stop after queue is drained (or after timeout)
        with self._state_lock:
            self._shutdown = True

        # Wait for workers to finish
        await asyncio.gather(*self.workers, return_exceptions=True)
        log.info("MemoryWriter shutdown complete")


async def shutdown_all_background_tasks(timeout=SHUTDOWN_TIMEOUT):
    """Shutdown all background tasks gracefully."""
    if not background_tasks:
        return

    log.info(f"Shutting down {len(background_tasks)} background tasks...")

    # Wait for tasks to complete naturally
    try:
        await asyncio.wait_for(
            asyncio.gather(*background_tasks, return_exceptions=True), timeout=timeout
        )
    except TimeoutError:
        log.warning(f"Background tasks didn't complete within {timeout}s, cancelling...")

        # Cancel remaining tasks
        for task in background_tasks:
            if not task.done():
                task.cancel()

        # Wait for cancellation to complete
        await asyncio.gather(*background_tasks, return_exceptions=True)

    log.info("All background tasks shut down")
