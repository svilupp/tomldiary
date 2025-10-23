# Thread Safety and Code Quality Improvements - Implementation Plan

**Branch**: `claude/fix-thread-safety-workers-011CUPtcNDesCSM1QEoK2izG`

**Context**: With Python 3.14 introducing optional no-GIL mode, we need to ensure our concurrent code is architecturally sound and free of race conditions. This plan addresses thread-safety issues in MemoryWriter and related components.

---

## Issue Analysis & Prioritization

### ✅ CRITICAL (Must Fix) - Thread Safety Core Issues

#### 1. Race Conditions in Counter Operations
**Location**: `src/tomldiary/writer.py:51, 67, 70, 72, 75`

**Problem**:
- Operations like `self._active_workers += 1` and `self._submitted_count += 1` are NOT atomic
- In no-GIL Python 3.14, these are guaranteed race conditions
- Even in current Python, async operations can be interrupted at `await` points
- Multiple workers reading/writing simultaneously = lost updates

**Example Race**:
```python
# Both workers read _active_workers = 5
Worker A: reads 5, calculates 6, writes 6
Worker B: reads 5, calculates 6, writes 6  # Lost increment! Should be 7
```

**Impact**: HIGH - Observability metrics become unreliable, can show negative pending counts

**Fix**: Add `asyncio.Lock()` to protect all counter updates

---

#### 2. Inconsistent State in stats() Method
**Location**: `src/tomldiary/writer.py:105-126`

**Problem**:
- Reads multiple counters sequentially without synchronization
- Between reads, workers are updating counters
- Can return internally inconsistent snapshots

**Example**:
```python
submitted = self._submitted_count      # 100
# ... worker increments _completed_count ...
completed = self._completed_count      # 101 (impossible!)
pending = submitted - completed - failed  # NEGATIVE!
```

**Impact**: HIGH - Stats show impossible states, metrics unreliable

**Fix**: Use same lock to atomically read all counters

---

#### 3. _running Flag Visibility
**Location**: `src/tomldiary/writer.py:39, 49, 58, 141`

**Problem**:
- Boolean flag written from `close()`, read from `submit()` and workers
- No memory barrier or synchronization
- In no-GIL Python, visibility not guaranteed across threads

**Impact**: MEDIUM - Workers might not see shutdown signal, submit might accept work after close

**Fix**: Protect flag access with lock

---

### ✅ IMPORTANT (Should Fix) - Concurrency Correctness

#### 4. Graceful Shutdown Race Condition
**Location**: `src/tomldiary/writer.py:133-149`

**Problem**:
- Current pattern: `await self.q.join()` → `self._running = False` → `worker.cancel()`
- Workers check `while self._running` at line 58
- Worker could be between fetching item and incrementing counter when cancelled
- Could lose counter update in finally block

**Impact**: MEDIUM - Counters could be slightly off after shutdown

**Fix**: Better shutdown pattern:
1. Set `_running = False` first (stop accepting new work)
2. Wait for workers to finish naturally
3. Only cancel if timeout exceeded

---

#### 5. Queue Drain Deadlock Potential
**Location**: `src/tomldiary/writer.py:138`

**Problem**:
- `await self.q.join()` waits indefinitely for queue to empty
- If workers crash or exit early, `join()` hangs forever
- No timeout protection

**Impact**: MEDIUM - Application could hang on shutdown

**Fix**: Add timeout to join operation:
```python
try:
    await asyncio.wait_for(self.q.join(), timeout=30.0)
except asyncio.TimeoutError:
    logger.warning(f"Queue did not drain, {self.q.qsize()} items remaining")
```

---

#### 6. Initialization Check Race in submit()
**Location**: `src/tomldiary/writer.py:49-51`

**Problem**:
- Check-then-use pattern without synchronization
- Between checking `if not self._running` and raising exception, state could change
- Submit could increment counter after close started

**Impact**: LOW - Edge case, unlikely but theoretically possible

**Fix**: Check flag inside lock (same lock protecting counters)

---

### ✅ ENHANCEMENT (Nice to Have)

#### 7. Firestore Credentials as Dictionary
**Location**: `src/tomldiary/backends/firestore.py:78-122`

**Problem**:
- Currently only accepts `credentials_path` (file path)
- Teams using this in production might write credentials to `/tmp` (security risk)
- `/tmp` is often world-readable, files not always cleaned up
- Multiple instances could collide on same file path

**Security Risk**: Credentials on disk in predictable location

**Better Approach**: Allow passing credentials directly as dict:
```python
FirestoreBackend(
    project_id="my-project",
    credentials_dict={"type": "service_account", "project_id": "...", ...}
)
```

**Impact**: MEDIUM - Security improvement, better developer experience

---

### ❌ OUT OF SCOPE

#### 8. MemoryWriter Lifecycle in API/Lifespan
- User confirmed this is out of scope (API-specific, not in this repo)

#### 9. Debug Code (traceback.print_exc)
- Not found in current codebase
- Likely was in examples or already removed
- Not relevant to current changes

---

## Test Coverage Analysis

### Current Test Strengths
✅ Basic submission and processing (test_writer.py:111-122)
✅ Multiple concurrent submissions (test_writer.py:151-173)
✅ Error handling (test_writer.py:176-192)
✅ Graceful shutdown (test_writer.py:224-234)
✅ Stats tracking (test_writer.py:245-427)
✅ Active workers tracking (test_writer.py:364-393)

### Current Test Weaknesses
❌ No test for race conditions in counter updates
❌ No stress test with rapid concurrent updates
❌ No test verifying counter consistency invariants
❌ No test for concurrent stats() calls while workers running
❌ Backpressure test marked `@pytest.mark.xfail` (flaky)
❌ No test for shutdown race conditions

---

## Implementation Plan

### Phase 1: Thread-Safety Core (CRITICAL) 🔴

**Goal**: Make MemoryWriter thread-safe for Python 3.14 no-GIL mode

**Changes to `src/tomldiary/writer.py`**:

1. **Add lock in `__init__`** (line 33)
   ```python
   def __init__(self, diary, *, workers=WORKERS, qsize=QUEUE_MAXSIZE):
       self.diary = diary
       self.q = asyncio.Queue(maxsize=qsize)

       # Add synchronization lock for counters and state
       self._lock = asyncio.Lock()

       self.workers = [...]
       self._running = True

       # Observability metrics (protected by _lock)
       self._submitted_count = 0
       self._completed_count = 0
       self._failed_count = 0
       self._active_workers = 0
   ```

2. **Protect submit() method** (lines 47-52)
   ```python
   async def submit(self, user_id: str, session_id: str, user_msg: str, assistant_msg: str):
       """Submit a memory update request to the queue (may block on backpressure)."""
       async with self._lock:
           if not self._running:
               raise RuntimeError("MemoryWriter is closed")
           self._submitted_count += 1

       await self.q.put((user_id, session_id, user_msg, assistant_msg))
   ```

3. **Protect worker counter updates** (lines 67, 70, 72, 75)
   ```python
   async def _worker(self, worker_id: int):
       """Worker task that processes memory updates from the queue."""
       log.debug(f"Memory worker {worker_id} started")
       try:
           while True:
               # Check running flag inside lock
               async with self._lock:
                   if not self._running:
                       break

               try:
                   user_id, session_id, user_msg, assistant_msg = await asyncio.wait_for(
                       self.q.get(), timeout=1.0
                   )
               except TimeoutError:
                   continue

               async with self._lock:
                   self._active_workers += 1

               try:
                   await self._process(user_id, session_id, user_msg, assistant_msg)

                   async with self._lock:
                       self._completed_count += 1
               except Exception as e:
                   async with self._lock:
                       self._failed_count += 1
                   log.exception(f"Worker {worker_id} failed to process memory update: {e}")
               finally:
                   async with self._lock:
                       self._active_workers -= 1
                   self.q.task_done()
       except asyncio.CancelledError:
           log.debug(f"Memory worker {worker_id} cancelled")
       except Exception as e:
           log.exception(f"Memory worker {worker_id} crashed: {e}")
   ```

4. **Protect stats() method** (lines 86-126)
   ```python
   async def stats(self) -> dict[str, int | float | bool]:
       """
       Get current writer statistics for observability and monitoring.

       Returns a consistent snapshot of all metrics by reading them atomically.
       """
       async with self._lock:
           submitted = self._submitted_count
           completed = self._completed_count
           failed = self._failed_count
           active_workers = self._active_workers
           running = self._running

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
           "is_running": running,
       }
   ```

5. **Protect is_running property** (lines 128-131)
   ```python
   @property
   async def is_running(self) -> bool:
       """Check if writer is currently accepting tasks."""
       async with self._lock:
           return self._running
   ```

   Note: This makes the property async. Alternative: Keep it sync but document it's approximate.

**Performance Note**: Lock contention is minimal because:
- Lock is only held during integer operations (nanoseconds)
- Workers spend most time in `await self._process()` (milliseconds to seconds)
- Lock overhead is negligible compared to I/O operations

---

### Phase 2: Improve Test Coverage (CRITICAL) 🔴

**Goal**: Add tests that would catch the race conditions

**Changes to `tests/test_writer.py`**:

1. **Add test_counter_consistency_under_load**
   ```python
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
       stats = await writer.stats()

       # Critical invariant: submitted = completed + failed + pending
       assert stats["submitted"] == num_batches * batch_size
       assert stats["completed"] + stats["failed"] == stats["submitted"]
       assert stats["pending"] == 0
       assert stats["active_workers"] == 0

       # Check all updates were processed
       assert len(mock_diary.updates) == num_batches * batch_size

       await writer.close()
   ```

2. **Add test_stats_consistency_during_processing**
   ```python
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
           stats = await writer.stats()

           # Check invariants
           if stats["completed"] + stats["failed"] + stats["pending"] != stats["submitted"]:
               inconsistencies.append(stats)

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
   ```

3. **Add test_concurrent_stats_calls**
   ```python
   @pytest.mark.asyncio
   async def test_concurrent_stats_calls(self, mock_diary):
       """Test that concurrent stats() calls don't cause race conditions."""
       mock_diary.update_delay = 0.05

       writer = MemoryWriter(mock_diary, workers=4, qsize=20)

       # Submit background work
       submit_task = asyncio.create_task(
           asyncio.gather(*[
               writer.submit(f"user_{i}", "sess", f"msg_{i}", f"resp_{i}")
               for i in range(30)
           ])
       )

       # Hammer stats() with concurrent calls
       stats_tasks = [
           asyncio.create_task(writer.stats())
           for _ in range(50)
       ]

       # All should complete without errors
       all_stats = await asyncio.gather(*stats_tasks)
       await submit_task

       # Verify all returned valid data
       for stats in all_stats:
           assert "submitted" in stats
           assert stats["pending"] >= 0
           assert stats["active_workers"] >= 0

       await writer.close()
   ```

4. **Add test_shutdown_with_pending_work**
   ```python
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
       stats = await writer.stats()
       assert stats["completed"] == num_tasks
       assert stats["pending"] == 0
       assert stats["active_workers"] == 0
   ```

5. **Add test_no_work_lost_during_shutdown**
   ```python
   @pytest.mark.asyncio
   async def test_no_work_lost_during_shutdown(self, mock_diary):
       """Test that no work is lost even with immediate shutdown."""
       mock_diary.update_delay = 0.1  # Slow processing

       writer = MemoryWriter(mock_diary, workers=2, qsize=100)

       # Submit large batch
       num_tasks = 50
       submit_tasks = [
           writer.submit(f"user_{i}", "sess", f"msg_{i}", f"resp_{i}")
           for i in range(num_tasks)
       ]

       # Submit and immediately start closing
       await asyncio.gather(*submit_tasks)
       close_task = asyncio.create_task(writer.close())

       # Wait for shutdown
       await close_task

       # Verify accounting is correct
       stats = await writer.stats()
       assert stats["submitted"] == num_tasks
       assert stats["completed"] + stats["failed"] == num_tasks
       assert len(mock_diary.updates) == stats["completed"]
   ```

**Impact**: These tests will:
- Catch race conditions in counter updates
- Verify stats() returns consistent snapshots
- Ensure no work is lost during shutdown
- Provide confidence for Python 3.14 compatibility

---

### Phase 3: Improve Shutdown Logic (IMPORTANT) 🟡

**Goal**: Make shutdown more robust and prevent deadlocks

**Changes to `src/tomldiary/writer.py`**:

1. **Add timeout to queue drain** (line 138)
   ```python
   async def close(self):
       """Gracefully shutdown the writer and all workers."""
       log.info("Shutting down MemoryWriter...")

       # Signal workers to stop accepting new work
       async with self._lock:
           self._running = False

       # Wait for queue to drain with timeout
       try:
           await asyncio.wait_for(self.q.join(), timeout=30.0)
           log.debug("Queue drained successfully")
       except asyncio.TimeoutError:
           remaining = self.q.qsize()
           log.warning(
               f"Queue did not drain within timeout, {remaining} items remaining. "
               f"Proceeding with worker cancellation."
           )

       # Cancel all workers
       for worker in self.workers:
           worker.cancel()

       # Wait for workers to finish
       await asyncio.gather(*self.workers, return_exceptions=True)
       log.info("MemoryWriter shutdown complete")
   ```

2. **Improve worker loop** (line 58)
   - Already covered in Phase 1 (check _running inside lock)
   - Workers will naturally exit when `_running = False`
   - Cancellation is now only for cleanup, not primary shutdown mechanism

**Benefits**:
- No deadlock if workers crash
- More predictable shutdown behavior
- Workers exit naturally rather than being cancelled mid-operation

---

### Phase 4: Firestore Credentials Enhancement (ENHANCEMENT) 🟢

**Goal**: Allow passing credentials as dict for better security

**Changes to `src/tomldiary/backends/firestore.py`**:

1. **Update `__init__` signature** (line 78)
   ```python
   def __init__(
       self,
       project_id: str,
       base_path: str = "users",
       credentials_path: str | None = None,
       credentials_dict: dict | None = None,
       database: str = "(default)",
   ):
       """
       Initialize Firestore backend.

       Args:
           project_id: GCP project ID
           base_path: Base path for Firestore documents (e.g., "experiments/memory")
           credentials_path: Path to service account JSON file (optional)
           credentials_dict: Service account credentials as dict (optional)
           database: Firestore database name (default: "(default)")

       Raises:
           ValueError: If both credentials_path and credentials_dict are provided
           ValueError: If base_path has an odd number of segments
       """
       if credentials_path and credentials_dict:
           raise ValueError(
               "Cannot specify both credentials_path and credentials_dict. "
               "Please provide only one."
           )

       self.project_id = project_id
       self.database = database
       self.base_path = base_path.strip("/")

       # Validate base_path (existing code)
       path_segments = [s for s in self.base_path.split("/") if s]
       if len(path_segments) % 2 != 0:
           raise ValueError(...)

       # Initialize Firestore client
       if credentials_dict:
           # Use dict directly - no file I/O needed!
           from google.oauth2 import service_account

           credentials = service_account.Credentials.from_service_account_info(
               credentials_dict
           )
           self.db = firestore.Client(
               project=project_id, database=database, credentials=credentials
           )
           logger.info("FirestoreBackend initialized with credentials dict")

       elif credentials_path:
           # Use file path (existing code)
           from google.oauth2 import service_account

           credentials = service_account.Credentials.from_service_account_file(
               credentials_path
           )
           self.db = firestore.Client(
               project=project_id, database=database, credentials=credentials
           )
           logger.info(f"FirestoreBackend initialized with credentials file: {credentials_path}")

       else:
           # Use default credentials (works with emulator or ADC)
           self.db = firestore.Client(project=project_id, database=database)
           logger.info("FirestoreBackend initialized with default credentials (ADC)")

       logger.info(
           f"FirestoreBackend: project={project_id}, database={database}, "
           f"base_path={self.base_path} ({len(path_segments)} segments)"
       )
   ```

2. **Add test for credentials_dict**
   ```python
   # In tests/test_firestore.py or tests/backends/test_firestore.py

   @pytest.mark.asyncio
   async def test_init_with_credentials_dict():
       """Test FirestoreBackend initialization with credentials dict."""
       creds_dict = {
           "type": "service_account",
           "project_id": "test-project",
           "private_key_id": "key-id",
           "private_key": "-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----\n",
           "client_email": "test@test-project.iam.gserviceaccount.com",
           "client_id": "123456789",
           "auth_uri": "https://accounts.google.com/o/oauth2/auth",
           "token_uri": "https://oauth2.googleapis.com/token",
       }

       backend = FirestoreBackend(
           project_id="test-project",
           base_path="experiments/memory",
           credentials_dict=creds_dict,
       )

       assert backend.project_id == "test-project"
       assert backend.db is not None

   def test_init_with_both_credentials_fails():
       """Test that providing both credentials_path and credentials_dict fails."""
       with pytest.raises(ValueError, match="Cannot specify both"):
           FirestoreBackend(
               project_id="test-project",
               credentials_path="/path/to/creds.json",
               credentials_dict={"type": "service_account"},
           )
   ```

**Benefits**:
- No credentials written to disk
- Better security (no /tmp files)
- More flexible for cloud deployments (pass from env vars, secrets manager, etc.)
- Teams have full control over credential handling

---

## Testing Strategy

### Unit Tests
- [x] Existing: Basic operations, error handling, stats
- [ ] **NEW**: Race condition tests (Phase 2)
- [ ] **NEW**: Counter consistency tests (Phase 2)
- [ ] **NEW**: Concurrent stats() tests (Phase 2)
- [ ] **NEW**: Shutdown race tests (Phase 2)

### Integration Tests
- [x] Existing: Full system integration
- [ ] **NEW**: High-load stress tests
- [ ] **NEW**: Python 3.14 no-GIL compatibility tests (when available)

### Manual Testing
- Test on Python 3.14 preview builds with `--disable-gil` flag
- Load testing with production-like workloads
- Monitor metrics for consistency under load

---

## Rollout Plan

### Step 1: Core Thread Safety (Days 1-2)
1. Implement Phase 1 changes (add locks)
2. Implement Phase 2 changes (new tests)
3. Verify all tests pass
4. Code review

### Step 2: Shutdown Improvements (Day 3)
1. Implement Phase 3 changes (shutdown logic)
2. Verify graceful shutdown tests pass
3. Code review

### Step 3: Firestore Enhancement (Day 4)
1. Implement Phase 4 changes (credentials dict)
2. Add tests for new functionality
3. Update documentation
4. Code review

### Step 4: Documentation & Release (Day 5)
1. Update CHANGELOG.md
2. Update README.md with Python 3.14 compatibility note
3. Add migration guide if needed
4. Commit and push
5. Create PR

---

## Breaking Changes

### None Expected
- All changes are backward compatible
- Adding `async` to `is_running` property could be breaking, but we can keep it sync
- New `credentials_dict` parameter is optional

### Alternative: Keep is_running Synchronous
```python
@property
def is_running(self) -> bool:
    """
    Check if writer is currently accepting tasks.

    Note: This read is not synchronized, so the value may be stale.
    For a guaranteed consistent read, use stats()['is_running'].
    """
    return self._running
```

This avoids breaking change and is acceptable since:
- Reading a boolean is atomic on most platforms
- Worst case: slightly stale value
- Critical code paths should use stats() anyway

---

## Performance Considerations

### Lock Overhead
- **Concern**: Will locks slow down the system?
- **Answer**: No. Lock is held for ~10-100 nanoseconds (integer operations)
- **Context**: Workers spend milliseconds to seconds in I/O operations
- **Impact**: Lock overhead is <0.001% of total time

### Benchmark Results (Expected)
```
Without locks (current):  ~10,000 ops/sec
With locks (proposed):    ~9,990 ops/sec (0.1% slower)
```

The safety guarantee is worth the negligible performance cost.

---

## Success Criteria

### Phase 1 & 2 (Thread Safety)
✅ All existing tests pass
✅ New race condition tests pass
✅ Counter invariants hold under load
✅ stats() returns consistent snapshots
✅ No data races detected by thread sanitizers

### Phase 3 (Shutdown)
✅ Graceful shutdown completes within timeout
✅ No work lost during shutdown
✅ No deadlocks observed

### Phase 4 (Firestore)
✅ credentials_dict works correctly
✅ Backward compatible with credentials_path
✅ Documentation updated

---

## Open Questions

1. **Should `is_running` property be async?**
   - Option A: Make it async for consistency
   - Option B: Keep sync, document as approximate
   - **Recommendation**: Option B (avoid breaking change)

2. **Should we add metrics for lock contention?**
   - Could track lock wait times
   - Useful for performance monitoring
   - **Recommendation**: Not needed (lock contention will be minimal)

3. **Should we backport to older versions?**
   - These are correctness fixes
   - Should consider backporting to all maintained versions
   - **Recommendation**: Yes, especially for race condition fixes

---

## References

- [PEP 703: Making the Global Interpreter Lock Optional in CPython](https://peps.python.org/pep-0703/)
- [asyncio Synchronization Primitives](https://docs.python.org/3/library/asyncio-sync.html)
- [Python Memory Model](https://docs.python.org/3/c-api/memory.html)
- [Race Conditions in Async Code](https://superfastpython.com/asyncio-race-condition/)

---

## Timeline

| Phase | Duration | Deliverable |
|-------|----------|-------------|
| Phase 1 | 1-2 days | Thread-safe MemoryWriter |
| Phase 2 | 1-2 days | Comprehensive race condition tests |
| Phase 3 | 0.5-1 day | Robust shutdown logic |
| Phase 4 | 0.5-1 day | Firestore credentials dict |
| Total | 3-5 days | Production-ready, Python 3.14 compatible code |

---

**Next Steps**: Review this plan, get approval, and proceed with implementation.
