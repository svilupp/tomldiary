# TOMLDiary

**Memory, Simplified: TOML-Driven, Agent-Approved.**

TOMLDiary is a dead-simple, customizable memory system for agentic applications. It stores data in human-readable TOML files so your agents can keep a tidy diary of only the useful stuff.

## Key Benefits

- **Human-readable TOML storage** – easy to inspect, debug and manage.
- **Fully customizable** – define your own memory schema with simple Pydantic models.
- **Smart deduplication** – prevents duplicate preferences with FuzzyWuzzy similarity detection (70% threshold).
- **Enhanced limit enforcement** – visual indicators and pre-flight checking prevent failed operations.
- **Force creation mechanism** – bypass similarity detection when needed with `id="new"` parameter.
- **Built-in observability** – comprehensive metrics for monitoring queue health, throughput, and error rates in production.
- **Minimal overhead** – lightweight design, backend agnostic and easy to integrate.
- **Atomic, safe writes** – ensures data integrity with proper file locking.

## Storage Backends

TOMLDiary supports multiple storage backends for different deployment scenarios:

- **LocalBackend** (included) – File-based storage with path-level locking. Perfect for development, local applications, and single-server deployments.
- **FirestoreBackend** (optional) – Google Cloud Firestore for cloud-based storage with multi-region replication, automatic scaling, and real-time sync. Requires `tomldiary[firestore]` installation.

See the [Backend Options](#backend-options) section below for configuration examples.

## Installation

Requires Python 3.11+

```bash
uv add tomldiary pydantic-ai
```

### Optional: Firestore Backend

To use the Firestore backend for cloud storage:

```bash
uv add 'tomldiary[firestore]'
# or with pip
pip install 'tomldiary[firestore]'
```

## Quick Start

```python
from pydantic import BaseModel
from typing import Dict
from tomldiary import Diary, PreferenceItem
from tomldiary.backends import LocalBackend

# Be as specific as possible in your preference schema, it passed to the system prompt of the agent extracting the data!
# This of the fields as the "slots" to organize facts into and tell the agent what to remember.
class MyPrefTable(BaseModel):
    """
    likes    : What the user enjoys
    dislikes : Things user avoids
    allergies: Substances causing reactions
    routines : User’s typical habits
    biography: User’s personal details
    """

    likes: Dict[str, PreferenceItem] = {}
    dislikes: Dict[str, PreferenceItem] = {}
    allergies: Dict[str, PreferenceItem] = {}
    routines: Dict[str, PreferenceItem] = {}
    biography: Dict[str, PreferenceItem] = {}


diary = Diary(
    backend=LocalBackend(path="./memories"),
    pref_table_cls=MyPrefTable,
    max_prefs_per_category=100,
    max_conversations=50,
)

await diary.ensure_session(user_id, session_id)
await diary.update_memory(
    user_id,
    session_id,
    user_msg="I'm allergic to walnuts.",
    assistant_msg="I'll remember you're allergic to walnuts.",
)
```

## TOML Memory Example

```toml
[_meta]
version = "0.3"
schema_name = "MyPrefTable"

[allergies.walnuts]
text = "allergic to walnuts"
contexts = ["diet", "health"]
_count = 1
_created = "2024-01-01T00:00:00Z"
_updated = "2024-01-01T00:00:00Z"
```

### Conversations File (`alice_conversations.toml`)
```toml
[_meta]
version = "0.3"
schema_name = "MyPrefTable"

[conversations.chat_123]
_created = "2024-01-01T00:00:00Z"
_turns = 5
summary = "Discussed food preferences and dietary restrictions"
keywords = ["food", "allergy", "italian"]
```

## Advanced Usage

### Custom Preference Categories

Create your own preference schema:

```python
class DetailedPrefTable(BaseModel):
    """
    dietary     : Food preferences and restrictions
    medical     : Health conditions and medications
    interests   : Hobbies and topics of interest
    goals       : Personal objectives and aspirations
    family      : Family members and relationships
    work        : Professional information
    """
    dietary: Dict[str, PreferenceItem] = {}
    medical: Dict[str, PreferenceItem] = {}
    interests: Dict[str, PreferenceItem] = {}
    goals: Dict[str, PreferenceItem] = {}
    family: Dict[str, PreferenceItem] = {}
    work: Dict[str, PreferenceItem] = {}
```

### Smart Preference Management

The system includes enhanced tools for intelligent preference management:

```python
# The extraction agent uses these enhanced tools automatically:
# - list_preferences(category) - shows limits with visual indicators (✅/⚠️/❌)  
# - upsert_preference() with smart workflows:
#   * Similarity detection prevents duplicates
#   * Auto-increment counts on updates  
#   * Force creation with id="new" when needed
#   * Intelligent error messages with match percentages

# Examples of enhanced error messages:
# "❌ Similar preferences found:
#   • likes/pref001: 'black blazers for work' (85% match)
#   • likes/pref003: 'dark blazers' (72% match)
# 
# To update existing: upsert_preference('likes', id='pref001')
# To force create anyway: upsert_preference('likes', id='new', text='black blazers')"
```

### Type Schema Utilities

TOMLDiary provides utilities to inspect and display type schemas for your preference tables, making it easy to design APIs, generate documentation, and ensure type safety.

```python
from tomldiary.schema import show_preferences_schema, show_conversations_schema

# Display schema in different formats
print(show_preferences_schema(MyPrefTable))  # Pretty tree format
print(show_preferences_schema(MyPrefTable, format="json"))  # JSON schema
print(show_preferences_schema(MyPrefTable, format="python"))  # Python types

# Show conversation schema
print(show_conversations_schema())  # Works without a class (standardized)
```

**CLI Access:**

```bash
# Inspect preference schema from command line
tomldiary schema preferences examples/culinary_prefs.py:CulinaryPrefTable

# Get JSON schema for API documentation
tomldiary schema preferences examples/culinary_prefs.py:CulinaryPrefTable -f json > schema.json

# View conversation schema
tomldiary schema conversations
```

**Use cases:**
- **API Design**: Generate JSON schemas for OpenAPI/Swagger documentation
- **Type Reference**: View Python type hints for your preference tables
- **Documentation**: Auto-generate schema documentation
- **Validation**: Understand the expected structure of your data

### Safe Data Loading

Load and validate TOML data with runtime type checking using Pydantic's TypeAdapter:

```python
from tomldiary.loaders import PreferenceLoader, load_preferences
from pydantic import ValidationError

# Load preferences with validation
loader = PreferenceLoader(MyPrefTable)

try:
    # Load from diary
    toml_data = await diary.preferences("user123")
    prefs = loader.load_from_toml_str(toml_data)

    # Now you have fully typed, validated data
    print(type(prefs))  # MyPrefTable
    print(type(prefs.likes))  # dict[str, PreferenceItem]

except ValidationError as e:
    print(f"Validation failed: {e}")

# Validate partial data (e.g., from API requests)
try:
    validated = loader.validate_partial("likes", incoming_api_data)
except ValidationError as e:
    return {"error": "Invalid preference data", "details": str(e)}
```

**Use cases:**
- **API Endpoints**: Validate incoming TOML payloads
- **Data Migration**: Ensure data integrity during migrations
- **Type Safety**: Runtime validation prevents type-related errors
- **Production Systems**: Catch schema mismatches early

### Backend Options

The library supports different storage backends:

#### Local Filesystem (Default)

```python
from pathlib import Path
from tomldiary.backends import LocalBackend

backend = LocalBackend(Path("./memories"))
```

#### Firestore (Cloud Storage)

Install first: `uv add 'tomldiary[firestore]'`

```python
from tomldiary.backends import FirestoreBackend

# Using default credentials (Application Default Credentials)
backend = FirestoreBackend(
    project_id="my-gcp-project",
    base_path="app/memory"  # Must have EVEN number of segments
)

# Or with explicit credentials
backend = FirestoreBackend(
    project_id="my-gcp-project",
    base_path="app/memory",
    credentials_path="/path/to/service-account.json",
    database="my-database"  # Optional, defaults to "(default)"
)
```

**Important**: The `base_path` must have an **even number** of segments due to Firestore's collection/document structure requirements. Examples:
- ✅ `"users/data"` (2 segments)
- ✅ `"app/memory"` (2 segments)
- ✅ `"prod/app/v1/memory"` (4 segments)
- ❌ `"users"` (1 segment - will raise ValueError)
- ❌ `"app/prod/memory"` (3 segments - will raise ValueError)

**Firestore Structure:**
```
{base_path}/
  {user_id}/
    preferences.toml    # Document with TOML content
    conversations.toml  # Document with TOML content
```

Test your setup with `uv run --extra firestore scripts/firestore_test_connection.py` or `uv run --extra firestore examples/firestore_example.py`.

#### Other Backends (Custom Implementation)

```python
# S3 backend (implement your own S3Backend)
# backend = S3Backend(bucket="my-memories")

# Redis backend (implement your own RedisBackend)
# backend = RedisBackend(host="localhost")
```

### Memory Writer Configuration

```python
# Configure the background writer
writer = MemoryWriter(
    diary=diary,
    workers=8,        # Number of background workers (default: 8 or 2×CPU)
    qsize=1000,       # Queue size (default: 1000)
)
```

### Observability and Monitoring

The `MemoryWriter` includes built-in observability for production deployments:

```python
# Get real-time statistics
stats = writer.stats()

# Returns comprehensive metrics:
{
    "queue_size": 5,              # Current items in queue
    "queue_capacity": 1000,       # Maximum queue size
    "queue_utilization": 0.005,   # Queue fullness (0.0 to 1.0)
    "total_workers": 8,           # Number of worker tasks
    "active_workers": 2,          # Workers currently processing
    "idle_workers": 6,            # Workers waiting for tasks
    "submitted": 1247,            # Total tasks submitted
    "completed": 1240,            # Total tasks completed
    "failed": 2,                  # Total tasks failed
    "pending": 5,                 # Tasks in flight
    "error_rate": 0.0016,         # Failure ratio
    "is_running": True            # Accepting new tasks
}

# Check if writer is running
if writer.is_running:
    await writer.submit(...)
```

#### Production Use Cases

**Health Check Endpoints:**
```python
@app.get("/health/memory")
async def memory_health():
    stats = writer.stats()
    status = "healthy" if stats["queue_utilization"] < 0.9 else "degraded"
    return {"status": status, "metrics": stats}
```

**Monitoring and Alerting:**
```python
# Alert on queue backpressure
stats = writer.stats()
if stats["queue_utilization"] > 0.8:
    alert("MemoryWriter queue depth high")

# Alert on error rate
if stats["error_rate"] > 0.1:
    alert(f"MemoryWriter error rate: {stats['error_rate']:.1%}")

# Alert on worker saturation
if stats["idle_workers"] == 0:
    alert("All MemoryWriter workers busy")
```

**Graceful Degradation:**
```python
# Reject requests if queue is near capacity
stats = writer.stats()
if stats["queue_utilization"] > 0.95:
    raise HTTPException(503, "Memory writer at capacity")
```

**Integration with Logfire:**
```python
import logfire

# Log periodic metrics
logfire.info("memory_writer_stats", **writer.stats())
```

## API Reference

### Diary

Main class for memory operations:

- `preferences(user_id)`: Get user preferences as TOML string
- `last_conversations(user_id, limit)`: Get last N conversation summaries
- `ensure_session(user_id, session_id)`: Create session if needed
- `update_memory(user_id, session_id, user_msg, assistant_msg)`: Process and store memory

#### Automated compaction sweeps

Use `CompactionConfig` to schedule background clean-up passes that trim redundant
preferences or stale conversation summaries. The configuration persists progress inside
`_meta.compaction` so counters survive restarts.

```python
from tomldiary.compaction import CompactionConfig

compaction = CompactionConfig(
    enabled=True,
    total_char_threshold=4000,      # trigger when serialized store exceeds N characters
    segment_char_threshold=600,     # or if any single block exceeds this size
    user_turn_interval=25,          # also run every 25 user turns
    cooldown_seconds=900,           # minimum gap between runs
    compact_preferences=True,       # target preference store
    compact_conversations=False,    # skip conversation summaries for this diary
)

diary = Diary(
    backend=backend,
    pref_table_cls=MyPrefTable,
    agent=extractor,
    compaction_config=compaction,
)
```

The compactor uses dedicated tools (`list_preference_blocks`, `rewrite_*`, `delete_*`) and
will loop through every block during a sweep. When disabled, the diary still records char
counts and turn statistics so triggers fire immediately once compaction is re-enabled.

### MemoryWriter

Background queue for non-blocking writes:

- `submit(user_id, session_id, user_message, assistant_response)`: Queue memory update
- `stats()`: Get comprehensive statistics for monitoring and observability
- `is_running`: Property to check if writer is accepting tasks
- `close()`: Graceful shutdown

### Models

- `PreferenceItem`: Single preference with text, contexts, and metadata
- `ConversationItem`: Conversation with summary, keywords, and turn count
- `MemoryDeps`: Container for preferences and conversations

## Examples

See the `examples/` directory for:
- `simple_example.py`: Basic usage with educational agent (no LLM required)
- `example_cooking_show.py`: Advanced AI-powered cooking show with celebrity chef interviews
- `dietary_preferences.py`: Restaurant booking agent with preference learning
- `culinary_prefs.py`: Custom preference schema for culinary applications
- `type_safety_demo.py`: **NEW v0.3** - Complete guide to schema inspection & safe data loading

**Note**: Examples use custom agents for educational purposes. The built-in extraction agent automatically uses the enhanced smart deduplication and limit enforcement tools described above.

## Development

```bash
# Install dev dependencies
uv sync --group dev

# Run tests
pytest

# Run tests with Firestore backend (optional)
uv add 'tomldiary[firestore]'
pytest  # Firestore tests will be included automatically

# Test Firestore backend with live credentials
# Set environment variables: FIREBASE_ADMIN_CREDS, FIREBASE_ADMIN_PROJECT_ID, FIREBASE_WINDOW_SHOP_DB_NAME
python scripts/test_firestore.py

# Format code
ruff format .

# Lint code
ruff check .
```

## License

MIT License - see LICENSE file for details.