# Backend Interface Specification

## Overview

TOMLDiary defines a standard interface that all storage backends must implement. This ensures complete interchangeability between backends, allowing you to switch from LocalBackend (for development) to FirestoreBackend (for production) with zero code changes.

**Current Backends:**
- ✅ **LocalBackend** - File-based storage with atomic writes and path-level locking
- ✅ **FirestoreBackend** - Cloud storage with Firestore's native atomic operations

**Both backends implement the complete 6-method interface:**

| Method        | Purpose                          | Type             |
|---------------|----------------------------------|------------------|
| `load()`      | Load document content            | Core Operation   |
| `save()`      | Save/update document             | Core Operation   |
| `exists()`    | Check document existence         | Document Op      |
| `delete()`    | Delete specific document         | Document Op      |
| `delete_user()` | Delete all user data           | User Operation   |
| `list_users()` | List all user IDs               | User Operation   |

---

## Interface Methods

### Core Operations

#### `async def load(user_id: str, kind: str) -> str | None`

**Purpose:** Load a document's content for a user.

**Parameters:**
- `user_id` (str): User identifier
- `kind` (str): Document type - either `"preferences"` or `"conversations"`

**Returns:**
- `str`: TOML content if document exists
- `None`: If document doesn't exist

**Behavior:**
- Returns `None` for missing documents (does not raise exception)
- Raises exceptions only for I/O errors or permission issues

**Example:**
```python
content = await backend.load("alice", "preferences")
if content is not None:
    # Document exists, process TOML content
    prefs = toml.loads(content)
```

---

#### `async def save(user_id: str, kind: str, content: str) -> None`

**Purpose:** Save or update a document for a user.

**Parameters:**
- `user_id` (str): User identifier
- `kind` (str): Document type - either `"preferences"` or `"conversations"`
- `content` (str): TOML content to save

**Returns:** `None`

**Behavior:**
- Creates user directory/collection if it doesn't exist
- Overwrites existing document if present
- Should be atomic when possible
- Raises exceptions on I/O errors or permission issues

**Example:**
```python
toml_content = toml.dumps(data)
await backend.save("alice", "preferences", toml_content)
```

---

### Document Operations

#### `async def exists(user_id: str, kind: str) -> bool`

**Purpose:** Check if a document exists without loading its content.

**Parameters:**
- `user_id` (str): User identifier
- `kind` (str): Document type - either `"preferences"` or `"conversations"`

**Returns:**
- `True`: Document exists
- `False`: Document doesn't exist

**Use Cases:**
- Health checks (verify backend connectivity)
- Conditional operations (check before delete)
- User existence verification
- More efficient than `load()` when you only need to know if a document exists

**Example:**
```python
if await backend.exists("alice", "preferences"):
    # User has preferences, safe to load
    content = await backend.load("alice", "preferences")
```

---

#### `async def delete(user_id: str, kind: str) -> None`

**Purpose:** Delete a specific document for a user (surgical operation).

**Parameters:**
- `user_id` (str): User identifier
- `kind` (str): Document type - either `"preferences"` or `"conversations"`

**Returns:** `None`

**Behavior:**
- Deletes only the specified document
- Idempotent: succeeds silently if document doesn't exist
- Does NOT delete the entire user directory/collection
- Other documents for the same user remain untouched

**Use Cases:**
- Reset specific memory types (e.g., clear preferences but keep conversations)
- Partial memory resets
- Testing and cleanup

**Example:**
```python
# Reset only preferences, keep conversations
await backend.delete("alice", "preferences")

# User's conversations remain intact
convs = await backend.load("alice", "conversations")  # Still works
```

**Difference from `delete_user()`:**
- `delete()` removes ONE document (surgical)
- `delete_user()` removes ALL documents (complete wipe)

---

### User Operations

#### `async def delete_user(user_id: str) -> None`

**Purpose:** Delete ALL data for a user (complete user removal).

**Parameters:**
- `user_id` (str): User identifier

**Returns:** `None`

**Behavior:**
- Deletes all documents for the user:
  - `preferences.toml`
  - `conversations.toml`
  - Any other documents in the user's directory/collection
- **LocalBackend:** Removes entire user directory
- **FirestoreBackend:** Deletes all documents in user's collection
- Idempotent: succeeds silently if user doesn't exist

**Use Cases:**
- User account deletion / GDPR right to be forgotten
- Complete memory reset
- Testing cleanup

**Example:**
```python
# Remove all of alice's data
await backend.delete_user("alice")

# Verify deletion
assert await backend.exists("alice", "preferences") is False
assert await backend.exists("alice", "conversations") is False
```

**Important:** This is a complete wipe, unlike `delete()` which is surgical.

---

#### `async def list_users() -> list[str]`

**Purpose:** Get a list of all user IDs that have data stored.

**Parameters:** None

**Returns:**
- `list[str]`: List of user IDs
- Empty list `[]` if no users exist

**Use Cases:**
- Admin dashboards and monitoring
- Bulk operations (migrations, backups)
- Usage analytics
- Testing and debugging

**Example:**
```python
users = await backend.list_users()
print(f"Total users: {len(users)}")

# Bulk operation example
for user_id in users:
    prefs = await backend.load(user_id, "preferences")
    # Process each user's preferences
```

---

## Implementation Guidelines

### Async/Await Requirements

All methods MUST be `async` functions, even if the underlying implementation is synchronous:

```python
# LocalBackend uses asyncio.to_thread for sync I/O
async def load(self, user_id: str, kind: str) -> str | None:
    file_path = self.base_path / user_id / f"{kind}.toml"
    return await asyncio.to_thread(file_path.read_text)

# FirestoreBackend uses run_in_executor for sync Firestore calls
async def load(self, user_id: str, kind: str) -> str | None:
    doc_ref = self._get_document_ref(user_id, kind)
    loop = asyncio.get_event_loop()
    doc = await loop.run_in_executor(None, doc_ref.get)
    return doc.to_dict().get("content") if doc.exists else None
```

### Error Handling

**Core operations (`load`, `save`):**
- Return `None` for missing documents (don't raise)
- Raise exceptions for I/O errors, permission issues, network failures

**Document operations (`exists`, `delete`):**
- Return `False` for nonexistent documents (don't raise)
- Be idempotent (safe to call multiple times)

**User operations (`delete_user`, `list_users`):**
- Be idempotent (safe to call multiple times)
- Return empty list for `list_users()` if no users exist

### Logging Best Practices

Use `loguru` for consistent logging:

```python
from ..logging import get_logger

logger = get_logger(__name__)

async def delete(self, user_id: str, kind: str) -> None:
    if await asyncio.to_thread(file_path.exists):
        await asyncio.to_thread(file_path.unlink)
        logger.debug(f"Deleted {kind} for user {user_id}")
    else:
        logger.debug(f"Delete called but {kind} doesn't exist for user {user_id}")
```

**Log levels:**
- `DEBUG`: Individual file operations (created, deleted, loaded)
- `INFO`: User-level operations (user deleted, migration complete)
- `WARNING`: Recoverable issues (validation failures, retries)
- `ERROR`: Failures and exceptions

### Idempotency Requirements

These methods MUST be idempotent (safe to call multiple times):

- **`delete()`**: Deleting a nonexistent document succeeds silently
- **`delete_user()`**: Deleting a nonexistent user succeeds silently
- **`save()`**: Saving the same content multiple times results in same state

Example:
```python
# These should all succeed without error
await backend.delete("alice", "preferences")
await backend.delete("alice", "preferences")  # Succeeds again
await backend.delete("alice", "preferences")  # And again

await backend.delete_user("bob")
await backend.delete_user("bob")  # Succeeds even though bob is gone
```

### Thread Safety

**LocalBackend:**
- Uses path-level locking with `asyncio.Lock`
- Each file path gets its own lock
- Concurrent operations on different files proceed in parallel

**FirestoreBackend:**
- Relies on Firestore's native atomic operations
- No explicit locking needed
- Firestore handles concurrent writes automatically

---

## Backend Comparison

### LocalBackend

**Storage Structure:**
```
{base_path}/
  {user_id}/
    preferences.toml
    conversations.toml
```

**Characteristics:**
- ✅ Simple file-based storage
- ✅ Path-level locking for concurrent safety
- ✅ Atomic writes with temp files + rename
- ✅ Perfect for development and testing
- ✅ Works great for single-server deployments
- ⚠️ Not suitable for multi-server deployments

**Concurrency Model:**
- Path-level locking prevents concurrent writes to same file
- Different files can be written concurrently
- Uses `asyncio.to_thread()` to avoid blocking event loop

**Example:**
```python
from pathlib import Path
from tomldiary.backends import LocalBackend

backend = LocalBackend(Path("./memories"))
```

---

### FirestoreBackend

**Storage Structure:**
```
{base_path}/                           # e.g., "app/memory"
  {user_id}/                           # Collection
    preferences.toml                   # Document
    conversations.toml                 # Document
```

**Characteristics:**
- ✅ Cloud-based, multi-region storage
- ✅ Automatic scaling and replication
- ✅ Native atomic operations (no locking needed)
- ✅ Real-time sync capabilities
- ✅ Perfect for production multi-server deployments
- ⚠️ Requires GCP setup and credentials

**Path Requirements:**
- `base_path` must have EVEN number of segments (Firestore requirement)
- Examples: `"app/memory"` ✅, `"prod/app/v1/memory"` ✅, `"users"` ❌

**Concurrency Model:**
- No explicit locking
- Firestore provides atomic document operations
- Last-write-wins for concurrent updates

**Example:**
```python
from tomldiary.backends import FirestoreBackend

backend = FirestoreBackend(
    project_id="my-gcp-project",
    base_path="app/memory"  # Must have even segments!
)
```

---

## Implementing a New Backend

To create a new backend (e.g., RedisBackend, S3Backend, PostgreSQLBackend):

1. **Implement all 6 methods:**
   - `load()`, `save()` (core)
   - `exists()`, `delete()` (document ops)
   - `delete_user()`, `list_users()` (user ops)

2. **Follow async/await patterns:**
   ```python
   async def load(self, user_id: str, kind: str) -> str | None:
       # Your implementation here
       pass
   ```

3. **Handle errors appropriately:**
   - Return `None`/`False` for missing data
   - Raise exceptions for real errors

4. **Make operations idempotent:**
   - Safe to call delete operations multiple times

5. **Add logging:**
   - Use `loguru` logger
   - Log at appropriate levels

6. **Write comprehensive tests:**
   - Test all 6 methods
   - Test edge cases (concurrency, missing data, errors)
   - Use backend parity tests to ensure identical behavior

**Example skeleton:**
```python
import asyncio
from ..logging import get_logger

logger = get_logger(__name__)

class RedisBackend:
    """Redis backend for TOMLDiary."""

    def __init__(self, host: str = "localhost", port: int = 6379):
        self.redis = redis.Redis(host=host, port=port)

    async def load(self, user_id: str, kind: str) -> str | None:
        key = f"tomldiary:{user_id}:{kind}"
        value = await asyncio.to_thread(self.redis.get, key)
        return value.decode() if value else None

    async def save(self, user_id: str, kind: str, content: str) -> None:
        key = f"tomldiary:{user_id}:{kind}"
        await asyncio.to_thread(self.redis.set, key, content)
        logger.debug(f"Saved {kind} for user {user_id}")

    async def exists(self, user_id: str, kind: str) -> bool:
        key = f"tomldiary:{user_id}:{kind}"
        return await asyncio.to_thread(self.redis.exists, key) > 0

    async def delete(self, user_id: str, kind: str) -> None:
        key = f"tomldiary:{user_id}:{kind}"
        await asyncio.to_thread(self.redis.delete, key)
        logger.debug(f"Deleted {kind} for user {user_id}")

    async def delete_user(self, user_id: str) -> None:
        pattern = f"tomldiary:{user_id}:*"
        keys = await asyncio.to_thread(self.redis.keys, pattern)
        if keys:
            await asyncio.to_thread(self.redis.delete, *keys)
            logger.info(f"Deleted all data for user {user_id}")

    async def list_users(self) -> list[str]:
        pattern = "tomldiary:*"
        keys = await asyncio.to_thread(self.redis.keys, pattern)
        users = set()
        for key in keys:
            # Extract user_id from key format: tomldiary:{user_id}:{kind}
            parts = key.decode().split(":")
            if len(parts) >= 2:
                users.add(parts[1])
        return sorted(users)
```

---

## Testing Requirements

All backends MUST pass these tests:

### Core Operations
- ✅ `save()` then `load()` returns correct content
- ✅ `load()` nonexistent document returns `None`
- ✅ Multiple `save()` operations work (idempotent)

### Document Operations
- ✅ `exists()` returns `True` for existing documents
- ✅ `exists()` returns `False` for nonexistent documents
- ✅ `delete()` removes document
- ✅ `delete()` idempotent (can call multiple times)
- ✅ `delete()` only removes specified document, not others

### User Operations
- ✅ `delete_user()` removes all user documents
- ✅ `delete_user()` idempotent (can call multiple times)
- ✅ `list_users()` returns empty list when no users
- ✅ `list_users()` returns all user IDs
- ✅ `list_users()` only returns users (not files/artifacts)

### Edge Cases
- ✅ Unicode content handling
- ✅ Empty content handling
- ✅ Large content handling (>1MB)
- ✅ Concurrent operations on same document
- ✅ Concurrent operations on different documents

---

## Benefits of Standardization

1. **Interchangeability**
   - Switch backends with zero code changes
   - Use LocalBackend for tests, FirestoreBackend for production

2. **Testing**
   - Test your app with LocalBackend (fast, no setup)
   - Deploy with FirestoreBackend (scalable, distributed)

3. **Feature Completeness**
   - All backends support same operations
   - No feature gaps between backends
   - No `hasattr()` checks or workarounds needed

4. **Future-Proof**
   - New backends automatically compatible
   - Interface designed for extension

---

## Version History

- **v0.5.0** (Current): Complete interface parity achieved
  - LocalBackend now implements all 6 methods
  - Both backends fully interchangeable
  - No compatibility checks needed

- **v0.3.0**: FirestoreBackend added with complete interface
- **v0.1.0**: LocalBackend with `load()` and `save()` only
