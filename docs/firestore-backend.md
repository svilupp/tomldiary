# Firestore Backend for TOMLDiary

This document provides detailed information about using the Firestore backend with TOMLDiary for cloud-based storage.

## Overview

The Firestore backend allows you to store TOMLDiary data in Google Cloud Firestore, enabling:
- Cloud-based storage for distributed applications
- Multi-region replication and high availability
- Automatic scaling and serverless operation
- Built-in security rules and authentication
- Real-time synchronization capabilities

### Interface Parity

FirestoreBackend implements the complete TOMLDiary backend interface:

✅ All 6 standard methods implemented
✅ Atomic operations (no locking needed)
✅ Idempotent operations
✅ Comprehensive error handling
✅ Production-ready logging

Unlike LocalBackend which uses path-level locking, FirestoreBackend relies on Firestore's native atomic operations for concurrent write safety. Both backends are fully interchangeable - you can use LocalBackend for development and FirestoreBackend for production with zero code changes.

For complete interface specifications, see [Backend Interface Documentation](backend-interface.md).

## Installation

Install TOMLDiary with Firestore support:

```bash
uv add 'tomldiary[firestore]'
# or
pip install 'tomldiary[firestore]'
```

This installs the required dependencies:
- `google-cloud-firestore` (>= 2.0.0)
- `loguru` (>= 0.7.0)

## Basic Usage

```python
from tomldiary import Diary
from tomldiary.backends import FirestoreBackend

# Initialize backend
backend = FirestoreBackend(
    project_id="my-gcp-project",
    base_path="app/memory"
)

# Create diary
diary = Diary(
    backend=backend,
    pref_table_cls=MyPreferenceSchema
)
```

## Configuration

### Required Parameters

- **`project_id`** (str): Your Google Cloud project ID

### Optional Parameters

- **`base_path`** (str, default: `"users"`): Base path for storing data in Firestore
  - **IMPORTANT**: Must have an **even number** of segments
  - Examples: `"app/memory"`, `"prod/users"`, `"v1/app/data/memory"`

- **`credentials_path`** (str, optional): Path to service account JSON file
  - If not provided, uses Application Default Credentials (ADC)
  - Cannot be used together with `credentials_dict`

- **`credentials_dict`** (dict, optional): Service account credentials as a dictionary
  - Alternative to `credentials_path` for passing credentials directly
  - Useful for cloud environments (Cloud Run, Cloud Functions) where reading from files is less secure
  - Cannot be used together with `credentials_path`

- **`database`** (str, default: `"(default)"`): Firestore database name

## Authentication Methods

### 1. Application Default Credentials (Recommended for GCP)

```python
backend = FirestoreBackend(
    project_id="my-project",
    base_path="app/memory"
)
```

This uses ADC, which automatically discovers credentials from:
- `GOOGLE_APPLICATION_CREDENTIALS` environment variable
- Cloud SDK: `gcloud auth application-default login`
- GCE/GKE/Cloud Run metadata server

### 2. Service Account JSON File

```python
backend = FirestoreBackend(
    project_id="my-project",
    base_path="app/memory",
    credentials_path="/path/to/service-account.json"
)
```

### 3. Service Account Dictionary (Recommended for Cloud Environments)

```python
import json
import os

# Load credentials from environment variable or secret manager
credentials_json = os.getenv("GCP_CREDENTIALS_JSON")
credentials = json.loads(credentials_json)

backend = FirestoreBackend(
    project_id="my-project",
    base_path="app/memory",
    credentials_dict=credentials
)
```

**Benefits:**
- More secure in serverless environments (Cloud Run, Cloud Functions, etc.)
- No file I/O required
- Works well with secret management systems
- Credentials can be injected at runtime

### 4. Environment Variables (for scripts/test_firestore.py)

```bash
export FIREBASE_ADMIN_CREDS='{"type":"service_account",...}'
export FIREBASE_ADMIN_PROJECT_ID="my-project"
export FIREBASE_WINDOW_SHOP_DB_NAME="my-database"
```

## Firestore Structure

TOMLDiary uses the following Firestore document structure:

```
{base_path}/                           # Collection/Document path
  {user_id}/                           # Collection (user ID)
    preferences.toml                   # Document
      - content: "...TOML string..."
      - updated_at: "2025-10-14T12:00:00Z"
      - version: "0.3"
    conversations.toml                 # Document
      - content: "...TOML string..."
      - updated_at: "2025-10-14T12:00:00Z"
      - version: "0.3"
```

### Example with `base_path="app/memory"`

```
app/                                   # Collection
  memory/                             # Document
    user-123/                         # Collection
      preferences.toml                # Document
      conversations.toml              # Document
    user-456/                         # Collection
      preferences.toml                # Document
      conversations.toml              # Document
```

## Base Path Requirements

Firestore requires paths to alternate between **collections** and **documents**:
- Collection / Document / Collection / Document / ...

This means the `base_path` must have an **even number** of segments:

### Valid Base Paths ✅

```python
# 2 segments
base_path="app/memory"
base_path="users/data"

# 4 segments
base_path="prod/app/v1/memory"
base_path="env/prod/service/users"
```

### Invalid Base Paths ❌

```python
# 1 segment (odd) - raises ValueError
base_path="users"

# 3 segments (odd) - raises ValueError
base_path="prod/app/memory"
```

## Backend Interface

The FirestoreBackend implements the standard TOMLDiary backend interface:

### Required Methods

```python
async def load(user_id: str, kind: str) -> str | None:
    """Load TOML content for a user and kind."""

async def save(user_id: str, kind: str, content: str) -> None:
    """Save TOML content for a user and kind."""
```

### Optional Utility Methods

```python
async def exists(user_id: str, kind: str) -> bool:
    """Check if document exists."""

async def list_users() -> list[str]:
    """List all user IDs."""

async def delete(user_id: str, kind: str) -> None:
    """Delete a document."""

async def delete_user(user_id: str) -> None:
    """Delete all data for a user."""
```

## Performance Characteristics

Based on testing with live Firestore:

| Operation | Typical Latency | Notes |
|-----------|----------------|-------|
| `save()` | 50-200ms | Depends on region/network |
| `load()` | 40-150ms | Faster for cached data |
| `exists()` | 40-120ms | Lightweight metadata check |
| `delete()` | 50-180ms | Similar to save |
| `list_users()` | 100-300ms | Lists collections |

**Optimization Tips:**
- Use batching for multiple operations
- Consider caching for frequently accessed data
- Use Firestore in the same region as your application
- Monitor with Firestore metrics in GCP Console

## Testing

### Unit Tests (Mock-based)

```bash
# Install with Firestore dependencies
uv add 'tomldiary[firestore]'

# Run all backend tests
pytest tests/test_backends.py

# Run only Firestore tests
pytest tests/test_backends.py::TestFirestoreBackend -v
```

If Firestore dependencies are not installed, tests are automatically skipped.

### Integration Tests (Live Firestore)

```bash
# Set up environment variables
export FIREBASE_ADMIN_CREDS='{"type":"service_account",...}'
export FIREBASE_ADMIN_PROJECT_ID="my-project"
export FIREBASE_WINDOW_SHOP_DB_NAME="my-database"

# Run integration tests
python scripts/test_firestore.py
```

This script:
- Tests all CRUD operations
- Creates a persistent test user for verification
- Measures latency statistics
- Cleans up temporary test data

## Security Considerations

1. **Authentication**: Always use service accounts with minimal required permissions
2. **Firestore Rules**: Configure security rules to restrict access
3. **Network**: Use VPC Service Controls for additional isolation
4. **Credentials**: Never commit service account JSON files to version control
5. **Encryption**: Firestore encrypts data at rest by default

### Example Firestore Rules

```javascript
rules_version = '2';
service cloud.firestore {
  match /databases/{database}/documents {
    // Replace with your base_path structure
    match /app/memory/{userId}/{document=**} {
      // Only allow authenticated users to access their own data
      allow read, write: if request.auth != null
                         && request.auth.uid == userId;
    }
  }
}
```

## Migration from LocalBackend

To migrate from LocalBackend to FirestoreBackend:

1. **Export existing data**:
```python
from pathlib import Path
from tomldiary.backends import LocalBackend

backend = LocalBackend(Path("./memories"))
# Read all user data using backend.load()
```

2. **Import to Firestore**:
```python
from tomldiary.backends import FirestoreBackend

new_backend = FirestoreBackend(
    project_id="my-project",
    base_path="app/memory"
)

# Write data using new_backend.save()
```

3. **Update application configuration**:
```python
# Old
backend = LocalBackend(Path("./memories"))

# New
backend = FirestoreBackend(
    project_id="my-project",
    base_path="app/memory"
)
```

## Troubleshooting

### Import Error: "google-cloud-firestore is required"

**Solution**: Install with `uv add 'tomldiary[firestore]'`

### ValueError: "Invalid base_path... EVEN number of path segments"

**Solution**: Ensure base_path has 2, 4, 6, etc. segments (not 1, 3, 5)

### Permission Denied / Authentication Error

**Solutions**:
- Check credentials file path
- Verify service account has Firestore permissions
- Try `gcloud auth application-default login`
- Check IAM roles include `Cloud Datastore User` or `Cloud Datastore Owner`

### Slow Performance

**Solutions**:
- Ensure Firestore database is in the same region as your app
- Check network latency
- Consider caching frequently accessed data
- Use Firestore composite indexes if using complex queries

### "Database not found"

**Solution**: Create Firestore database in GCP Console or specify correct database name

## Examples

See the following files for complete examples:

- **Basic usage**: `examples/firestore_example.py`
- **Integration tests**: `scripts/test_firestore.py`
- **Unit tests**: `tests/test_backends.py::TestFirestoreBackend`

## Support

For issues specific to:
- **TOMLDiary**: https://github.com/svilupp/tomldiary/issues
- **Firestore**: https://cloud.google.com/firestore/docs
- **Authentication**: https://cloud.google.com/docs/authentication
