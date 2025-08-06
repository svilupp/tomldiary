# TOMLDiary

**Memory, Simplified: TOML-Driven, Agent-Approved.**

TOMLDiary is a dead-simple, customizable memory system for agentic applications. It stores data in human-readable TOML files so your agents can keep a tidy diary of only the useful stuff.

## Key Benefits

- **Human-readable TOML storage** – easy to inspect, debug and manage.
- **Fully customizable** – define your own memory schema with simple Pydantic models.
- **Smart deduplication** – prevents duplicate preferences with FuzzyWuzzy similarity detection (70% threshold).
- **Enhanced limit enforcement** – visual indicators and pre-flight checking prevent failed operations.
- **Force creation mechanism** – bypass similarity detection when needed with `id="new"` parameter.
- **Minimal overhead** – lightweight design, backend agnostic and easy to integrate.
- **Atomic, safe writes** – ensures data integrity with proper file locking.

## Installation

Requires Python 3.11+

```bash
uv add tomldiary pydantic-ai
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

### Backend Options

The library supports different storage backends:

```python
# Local filesystem (default)
from tomldiary.backends import LocalBackend
backend = LocalBackend(Path("./memories"))

# S3 backend (implement S3Backend)
# backend = S3Backend(bucket="my-memories")

# Redis backend (implement RedisBackend)  
# backend = RedisBackend(host="localhost")
```

### Memory Writer Configuration

```python
# Configure the background writer
writer = MemoryWriter(
    diary=diary,
    workers=3,        # Number of background workers
    qsize=100,        # Queue size
    retry_limit=3,    # Max retries on failure
    retry_delay=1.0   # Delay between retries
)
```

## API Reference

### Diary

Main class for memory operations:

- `preferences(user_id)`: Get user preferences as TOML string
- `last_conversations(user_id, limit)`: Get last N conversation summaries
- `ensure_session(user_id, session_id)`: Create session if needed
- `update_memory(user_id, session_id, user_msg, assistant_msg)`: Process and store memory

### MemoryWriter

Background queue for non-blocking writes:

- `submit(user_id, session_id, user_message, assistant_response)`: Queue memory update
- `close()`: Graceful shutdown
- `failed_count()`: Number of failed operations

### Models

- `PreferenceItem`: Single preference with text, contexts, and metadata
- `ConversationItem`: Conversation with summary, keywords, and turn count
- `MemoryDeps`: Container for preferences and conversations

## Examples

See the `examples/` directory for:
- `simple_example.py`: Basic usage with educational agent (no LLM required)
- `example_cooking_show.py`: Advanced AI-powered cooking show with celebrity chef interviews
- `culinary_prefs.py`: Custom preference schema for culinary applications

**Note**: Examples use custom agents for educational purposes. The built-in extraction agent automatically uses the enhanced smart deduplication and limit enforcement tools described above.

## Development

```bash
# Install dev dependencies
uv sync --group dev

# Run tests
pytest

# Format code
ruff format .

# Lint code
ruff check .
```

## License

MIT License - see LICENSE file for details.