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
        max_conversations: int = 100,
        compaction_config: Optional[CompactionConfig] = None,
        compactor: Optional[Agent] = None,
    )
```

#### Parameters

- `backend`: Storage backend instance (e.g., LocalBackend)
- `pref_table_cls`: Pydantic model defining preference categories
- `agent`: Optional extraction agent or model name. If omitted, `extractor_agent()`
  is used with the model name from `EXTRACTOR_MODEL` (default `openai:gpt-5-mini`).
- `max_prefs_per_category`: Maximum preferences per category (default: 100)
- `max_conversations`: Maximum conversation history (default: 100)
- `compaction_config`: Optional `CompactionConfig` describing when automated
  clean-up sweeps should run.
- `compactor`: Custom compaction agent instance. When omitted and the config is
  enabled, `compactor_agent()` builds the default tool-enabled agent.

#### Methods

##### `async def preferences(user_id: str, skip_metadata: bool = False) -> str`
Returns user preferences as a TOML string. If `skip_metadata=True`, excludes the `_meta` section from the output.

##### `async def last_conversations(user_id: str, limit: int = 3, skip_metadata: bool = False) -> Dict[str, ConversationItem]`
Returns the last N conversations for a user. If `skip_metadata=True`, excludes the `_meta` section from the output.

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

##### `async def submit(user_id: str, session_id: str, user_msg: str, assistant_msg: str)`
Queue a memory update for background processing.

##### `async def close()`
Gracefully shutdown the writer and wait for pending operations.

##### `def failed_count() -> int`
Returns the number of failed operations.

### CompactionConfig

Controls automated compaction sweeps that prune or rewrite stored memories.

```python
class CompactionConfig:
    enabled: bool = False
    total_char_threshold: int | None = None
    segment_char_threshold: int | None = None
    user_turn_interval: int | None = None
    schedule_at: datetime | None = None
    cooldown_seconds: int = 0
    compact_preferences: bool = True
    compact_conversations: bool = True
```

When active, the diary records `_meta.compaction` stats for both stores, including
the last run timestamp, rolling character totals, and user-turn counters.

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

The extraction agent has access to these enhanced tools with smart deduplication and limit enforcement:

### `list_categories() -> str`
List all available preference categories with their exact names.

### `list_preferences(category: str | None = None) -> str`
List existing preferences with visual limit indicators (✅/⚠️/❌) and usage counts.
- Shows current category limits and space availability
- Displays preferences in format: `category/id: text (count×)`
- Essential for checking existing preferences before creating new ones

### `upsert_preference(category: str, id: str | None = None, text: str | None = None, contexts: List[str] | None = None, suppress_count_increment: bool = False) -> str`
**Enhanced preference management with smart deduplication:**

**CRITICAL WORKFLOW:**
1. **ALWAYS** call `list_preferences(category)` first to check existing preferences
2. **Boost existing**: `upsert_preference('likes', id='pref001')` - auto-increments count
3. **Update existing**: `upsert_preference('likes', id='pref001', text='new text')`
4. **Create new**: `upsert_preference('likes', text='new preference')`
5. **Force create**: `upsert_preference('likes', id='new', text='similar item')` - bypasses similarity detection

**Smart Features:**
- **Similarity Detection**: Uses FuzzyWuzzy (70% threshold) to prevent duplicates
- **Limit Enforcement**: Pre-flight checking prevents failed operations
- **Intelligent Errors**: Shows similar preferences with match percentages
- **Auto-increment**: Counts increment by default unless `suppress_count_increment=True`

### `forget_preference(category: str, id: str) -> str`
Remove a specific preference using exact category/id from `list_preferences()` output.

### `list_conversation_summary(session_id: str) -> str`
Get summary of a specific conversation session.

### `update_conversation_summary(summary: str, keywords: List[str] | None = None) -> str`
Update the summary and keywords for the current conversation session.

## Utility Functions

### `shutdown_all_background_tasks(timeout: float = 10.0)`
Shutdown all background tasks gracefully.

### `extractor_agent(pref_table_cls: Type[BaseModel], model: Model | KnownModelName | str | None = None, prompt_template: str | Path | Prompt | None = None, fallback_retries: int = 3, fallback_on: Callable[[Exception], bool] | Sequence[type[Exception]] | None = None) -> Agent`
Build the default extraction agent for a preference table. Uses `EXTRACTOR_MODEL`
or `openai:gpt-5-mini` when no model is provided. `build_extractor()` is a legacy alias.

### `extractor_prompt_check(prompt: str | Path | Prompt) -> None`
Validate a custom extractor prompt and warn about missing placeholders.
