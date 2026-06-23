from __future__ import annotations

import asyncio
import contextlib
import os
import threading
from collections.abc import Coroutine
from datetime import datetime
from typing import Any, TypeVar

from .diary import Diary
from .logging import get_logger

log = get_logger(__name__)

# Configuration defaults
QUEUE_MAXSIZE = 1000
WORKERS = max(8, (os.cpu_count() or 1) * 2)
SHUTDOWN_TIMEOUT = 30

T = TypeVar("T")


class _Shutdown:
    """Marker enqueued during shutdown to wake an idle worker blocked on q.get();
    it carries no work, so a worker acks it and exits.

    A typed singleton (rather than a bare ``object()``) so the queue's element
    union narrows cleanly: ``isinstance(item, _Shutdown)`` rules out the sentinel
    and leaves a precise ``_WorkItem`` tuple for the worker to unpack.
    """


_SHUTDOWN = _Shutdown()

# A queued unit of work, or the shutdown sentinel.
_WorkItem = tuple[str, str, str, str, datetime | None]

# Global task registry to prevent garbage collection
background_tasks: set[asyncio.Task[Any]] = set()


def fire_and_forget(coro: Coroutine[Any, Any, T], *, name: str | None = None) -> asyncio.Task[T]:
    """Create a background task with proper lifecycle management."""
    task = asyncio.create_task(coro, name=name)
    background_tasks.add(task)

    def _on_done(t: asyncio.Task[Any]) -> None:
        # Always drop the strong reference so the task can be collected.
        background_tasks.discard(t)
        # Cancelled tasks are expected (e.g. during shutdown); Task.exception()
        # would itself raise CancelledError, so guard for it first.
        if t.cancelled():
            return
        exc = t.exception()
        if exc is not None:
            log.exception("%s crashed", t.get_name(), exc_info=exc)

    task.add_done_callback(_on_done)
    return task


class MemoryWriter:
    """Queue-based memory writer with worker pool for concurrent processing."""

    def __init__(self, diary: Diary, *, workers: int = WORKERS, qsize: int = QUEUE_MAXSIZE) -> None:
        self.diary = diary
        # Queue item: (user_id, session_id, user_msg, assistant_msg, context_now)
        self.q: asyncio.Queue[_WorkItem | _Shutdown] = asyncio.Queue(maxsize=qsize)

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

    async def submit(
        self,
        user_id: str,
        session_id: str,
        user_msg: str,
        assistant_msg: str,
        *,
        context_now: datetime | None = None,
    ) -> None:
        """Submit a memory update request to the queue (may block on backpressure)."""
        with self._state_lock:
            if not self._accepting:
                raise RuntimeError("MemoryWriter is closed")

        # Queue operations are thread-safe, can be done outside lock. Count the
        # submission only once the item is actually enqueued: if put() is cancelled
        # while blocked on a full queue the item never enters the queue, so counting
        # it earlier would leave a phantom submission and break the
        # submitted == completed + failed + pending invariant permanently.
        await self.q.put((user_id, session_id, user_msg, assistant_msg, context_now))
        with self._state_lock:
            self._submitted_count += 1

    async def _worker(self, worker_id: int) -> None:
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
                    item = await asyncio.wait_for(self.q.get(), timeout=1.0)
                except TimeoutError:
                    continue

                if isinstance(item, _Shutdown):
                    # Shutdown wake-up: no work to do; ack and exit (sentinels are
                    # only ever enqueued during shutdown).
                    self.q.task_done()
                    break

                user_id, session_id, user_msg, assistant_msg, context_now = item

                # Increment active workers counter (thread-safe)
                with self._state_lock:
                    self._active_workers += 1

                try:
                    await self._process(
                        user_id, session_id, user_msg, assistant_msg, context_now=context_now
                    )

                    # Increment completed counter (thread-safe)
                    with self._state_lock:
                        self._completed_count += 1
                except asyncio.CancelledError:
                    # Cancellation (e.g. forced shutdown) is a BaseException and would
                    # otherwise skip the Exception handler, leaving the in-flight item
                    # unaccounted and pending stuck > 0. Treat the abandoned item as
                    # failed so submitted == completed + failed holds, then re-raise to
                    # honour the cancellation.
                    with self._state_lock:
                        self._failed_count += 1
                    raise
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

    async def _process(
        self,
        user_id: str,
        session_id: str,
        user_msg: str,
        assistant_msg: str,
        *,
        context_now: datetime | None = None,
    ) -> None:
        """Process a single memory update."""
        await self.diary.update_memory(
            user_id, session_id, user_msg, assistant_msg, context_now=context_now
        )

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

    async def close(self) -> None:
        """Gracefully shutdown the writer and all workers.

        Shutdown is bounded by SHUTDOWN_TIMEOUT: workers are given that long to
        drain the queue and finish in-flight work. If they do not finish in time
        (e.g. a slow or hung ``_process``), the remaining work is abandoned --
        the worker tasks are cancelled and any in-flight item is accounted as
        failed. The happy path, where the queue drains before the timeout,
        always lets workers finish naturally and is unaffected.
        """
        log.info("Shutting down MemoryWriter...")

        with self._state_lock:
            if not self._accepting and self._shutdown:
                # Already closed
                return
            self._accepting = False

        # Wait for queue to drain with timeout to prevent deadlock
        # (keep workers processing while accepting is disabled)
        timed_out = False
        try:
            await asyncio.wait_for(self.q.join(), timeout=SHUTDOWN_TIMEOUT)
            log.debug("Queue drained successfully")
        except TimeoutError:
            timed_out = True
            remaining = self.q.qsize()
            log.warning(
                f"Queue did not drain within {SHUTDOWN_TIMEOUT}s timeout, "
                f"{remaining} items remaining. Cancelling workers."
            )

        # Signal workers to stop after queue is drained (or after timeout)
        with self._state_lock:
            self._shutdown = True

        # Wake any idle workers blocked on q.get() so they observe the shutdown
        # flag now instead of waiting out the ~1s get() poll timeout. One sentinel
        # per worker; extras are harmless (a worker exits on the first it sees).
        for _ in self.workers:
            with contextlib.suppress(asyncio.QueueFull):
                self.q.put_nowait(_SHUTDOWN)

        if not timed_out:
            # Happy path: queue drained, so just let workers finish their current
            # loop iteration. They observe _shutdown + empty queue and exit cleanly.
            await self._stop_workers(grace=SHUTDOWN_TIMEOUT)
        else:
            # Drain did not finish in time: abandon remaining work and force the
            # bound by cancelling workers so close() cannot block on queued or hung
            # processing. Cancellation is requested with no grace period.
            await self._stop_workers(grace=0)

        log.info("MemoryWriter shutdown complete")

    async def _stop_workers(self, *, grace: float) -> None:
        """Join workers, cancelling them if they do not exit within ``grace`` seconds.

        ``cancel()`` alone is not always sufficient: a worker dequeuing from a
        non-empty queue can repeatedly resolve ``asyncio.wait_for(q.get())``
        synchronously, and ``wait_for`` may swallow a pending cancellation in that
        window. To guarantee a bound, we (re)issue cancellation and wait again, and
        ultimately abandon the tasks rather than block forever -- they remain
        tracked in ``background_tasks`` and are cancelled on interpreter shutdown.
        """
        # First, give workers a bounded chance to finish gracefully.
        if grace > 0:
            try:
                await asyncio.wait_for(
                    asyncio.gather(*self.workers, return_exceptions=True), timeout=grace
                )
                return
            except TimeoutError:
                log.warning("Workers did not exit within %ss, cancelling.", grace)

        # Force cancellation. The first cancel can be swallowed by a
        # wait_for(q.get()) that resolves synchronously; re-issue it on a short
        # poll so it is re-delivered once the worker is genuinely suspended, but
        # never block unboundedly.
        deadline = asyncio.get_event_loop().time() + 5.0
        while asyncio.get_event_loop().time() < deadline:
            for w in self.workers:
                if not w.done():
                    w.cancel()
            try:
                await asyncio.wait_for(
                    asyncio.gather(*self.workers, return_exceptions=True), timeout=0.05
                )
                return
            except TimeoutError:
                continue

        log.warning("Workers did not stop after cancellation; abandoning them.")


async def shutdown_all_background_tasks(timeout: int = SHUTDOWN_TIMEOUT) -> None:
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
