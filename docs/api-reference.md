# API Reference

## Core Classes

### Diary

The main class for managing user memories.

```python
class Diary:
    def __init__(
        self,
        backend: Backend,
        pref_table_cls: Type[BaseModel],
        agent: Optional[Agent] = None,
        max_prefs_per_category: int = 100,
        max_conversations: int = 100
    )
```

#### Parameters

- `backend`: Storage backend instance (e.g., LocalBackend)
- `pref_table_cls`: Pydantic model defining preference categories
- `agent`: Optional custom extraction agent
- `max_prefs_per_category`: Maximum preferences per category (default: 100)
- `max_conversations`: Maximum conversation history (default: 100)

#### Methods

##### `async def preferences(user_id: str) -> str`
Returns user preferences as a TOML string.

##### `async def last_conversations(user_id: str, n: int = 3) -> Dict[str, ConversationItem]`
Returns the last N conversations for a user.

##### `async def ensure_session(user_id: str, session_id: str) -> bool`
Creates a new session if it doesn't exist. Returns True if created.

##### `async def update_memory(user_id: str, session_id: str, user_msg: str, assistant_msg: str)`
Processes and stores a conversation turn.

### MemoryWriter

Background queue system for non-blocking memory updates.

```python
class MemoryWriter:
    def __init__(
        self,
        diary: Diary,
        workers: int = 3,
        qsize: int = 100,
        retry_limit: int = 3,
        retry_delay: float = 1.0
    )
```

#### Parameters

- `diary`: Diary instance to write to
- `workers`: Number of background worker tasks
- `qsize`: Maximum queue size
- `retry_limit`: Maximum retries on failure
- `retry_delay`: Delay between retries in seconds

#### Methods

##### `async def submit(user_id: str, session_id: str, user_message: str, assistant_response: str)`
Queue a memory update for background processing.

##### `async def close()`
Gracefully shutdown the writer and wait for pending operations.

##### `def failed_count() -> int`
Returns the number of failed operations.

## Models

### PreferenceItem

A single user preference entry.

```python
class PreferenceItem(BaseModel):
    text: str
    contexts: List[str] = []
    count_: int = Field(1, alias="_count")
    created_: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat(), alias="_created")
    updated_: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat(), alias="_updated")
```

### ConversationItem

A conversation summary entry.

```python
class ConversationItem(BaseModel):
    created_: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat(), alias="_created")
    turns_: int = Field(0, alias="_turns")
    summary: str = ""
    keywords: List[str] = []
```

### MemoryDeps

Container for user memories passed to the extraction agent.

```python
class MemoryDeps(BaseModel):
    user_id: str
    session_id: str
    preferences: Union[BaseModel, Dict[str, Any]]
    conversations: Dict[str, ConversationItem]
    last_user_message: str = ""
    last_assistant_message: str = ""
```

## Backends

### LocalBackend

File system storage backend.

```python
class LocalBackend:
    def __init__(self, base_path: Path)
```

#### Methods

##### `async def load(user_id: str, kind: str) -> Optional[str]`
Load a TOML file for a user.

##### `async def save(user_id: str, kind: str, content: str)`
Save a TOML file for a user with atomic writes.

## Tools

The extraction agent has access to these tools:

### `read_preference(category: str) -> List[PreferenceItem]`
Read all preferences in a category.

### `upsert_preference(category: str, item_id: str, text: str, contexts: List[str])`
Create or update a preference.

### `forget_preference(category: str, item_id: str)`
Remove a preference.

### `summarize_conversation(summary: str, keywords: List[str])`
Update the current conversation summary.

## Utility Functions

### `shutdown_all_background_tasks(timeout: float = 10.0)`
Shutdown all background tasks gracefully.

### `build_extractor(pref_table_cls: Type[BaseModel]) -> Tuple[Agent, List[str]]`
Build the default extraction agent for a preference table.