# Advanced Usage

## Custom Preference Categories

You can define complex preference schemas to match your application's needs:

```python
from pydantic import BaseModel
from typing import Dict
from tomldiary import PreferenceItem

class DetailedPrefTable(BaseModel):
    """
    dietary     : Food preferences, restrictions, and allergies
    medical     : Health conditions, medications, and medical history
    interests   : Hobbies, topics of interest, and entertainment preferences
    goals       : Personal and professional objectives
    family      : Family members, relationships, and important dates
    work        : Job information, skills, and professional preferences
    lifestyle   : Daily routines, habits, and living preferences
    communication : Preferred communication styles and channels
    """
    dietary: Dict[str, PreferenceItem] = {}
    medical: Dict[str, PreferenceItem] = {}
    interests: Dict[str, PreferenceItem] = {}
    goals: Dict[str, PreferenceItem] = {}
    family: Dict[str, PreferenceItem] = {}
    work: Dict[str, PreferenceItem] = {}
    lifestyle: Dict[str, PreferenceItem] = {}
    communication: Dict[str, PreferenceItem] = {}
```

The docstring is important - it's injected into the LLM prompt to guide preference extraction.

## Custom Backends

### Implementing a Custom Backend

Create a backend by implementing the backend protocol:

```python
from typing import Optional
import aioboto3

class S3Backend:
    def __init__(self, bucket: str, prefix: str = "memories"):
        self.bucket = bucket
        self.prefix = prefix
        self.session = aioboto3.Session()

    async def load(self, user_id: str, kind: str) -> Optional[str]:
        async with self.session.client('s3') as s3:
            key = f"{self.prefix}/{user_id}_{kind}.toml"
            try:
                response = await s3.get_object(Bucket=self.bucket, Key=key)
                content = await response['Body'].read()
                return content.decode('utf-8')
            except s3.exceptions.NoSuchKey:
                return None

    async def save(self, user_id: str, kind: str, content: str):
        async with self.session.client('s3') as s3:
            key = f"{self.prefix}/{user_id}_{kind}.toml"
            await s3.put_object(
                Bucket=self.bucket,
                Key=key,
                Body=content.encode('utf-8'),
                ContentType='application/toml'
            )
```

### Redis Backend Example

```python
import aioredis
from typing import Optional

class RedisBackend:
    def __init__(self, redis_url: str = "redis://localhost"):
        self.redis_url = redis_url
        self.redis = None

    async def _get_redis(self):
        if not self.redis:
            self.redis = await aioredis.from_url(self.redis_url)
        return self.redis

    async def load(self, user_id: str, kind: str) -> Optional[str]:
        redis = await self._get_redis()
        key = f"memory:{user_id}:{kind}"
        value = await redis.get(key)
        return value.decode('utf-8') if value else None

    async def save(self, user_id: str, kind: str, content: str):
        redis = await self._get_redis()
        key = f"memory:{user_id}:{kind}"
        await redis.set(key, content)
```

## Custom Extraction Agent

You can provide your own extraction agent:

```python
from pydantic_ai import RunContext
from tomldiary import extractor_agent
from tomldiary.models import MemoryDeps

# Start with the default agent
agent = extractor_agent(MyPrefTable)


@agent.system_prompt
def custom_system_prompt(ctx: RunContext[MemoryDeps]) -> str:
    return """
    You are a specialized memory extraction agent.
    Focus on extracting only the most important information.
    Be conservative about what you store.
    """.strip()


# Use your custom agent
diary = Diary(
    backend=backend,
    pref_table_cls=MyPrefTable,
    agent=agent
)
```

## Performance Tuning

### Memory Writer Configuration

For high-throughput applications:

```python
writer = MemoryWriter(
    diary=diary,
    workers=10,       # More workers for parallel processing
    qsize=1000,       # Larger queue for burst traffic
    retry_limit=5,    # More retries for reliability
    retry_delay=0.5   # Shorter delay between retries
)
```

### Batch Processing

Process multiple conversations efficiently:

```python
async def batch_process(writer, conversations):
    tasks = []
    for user_id, session_id, user_msg, bot_msg in conversations:
        task = writer.submit(user_id, session_id, user_msg, bot_msg)
        tasks.append(task)

    # Submit all at once
    await asyncio.gather(*tasks)
```

## Memory Limits and Cleanup

### Automatic Cleanup

The diary automatically enforces limits:

```python
diary = Diary(
    backend=backend,
    pref_table_cls=MyPrefTable,
    max_prefs_per_category=50,  # Keep only top 50 per category
    max_conversations=20        # Keep only last 20 conversations
)
```

### Automated Compaction Agent

Beyond hard limits, you can schedule clean-up sweeps that rewrite or delete stale
entries. `CompactionConfig` stores counters inside `_meta.compaction` so trigger state
survives restarts.

```python
from tomldiary.compaction import CompactionConfig

compaction = CompactionConfig(
    enabled=True,
    total_char_threshold=8000,      # run when the serialized store grows large
    segment_char_threshold=1000,    # or when an individual block is too long
    user_turn_interval=40,          # fallback cadence based on user turns
    cooldown_seconds=600,           # avoid back-to-back sweeps
    compact_preferences=True,
    compact_conversations=True,
)

diary = Diary(
    backend=backend,
    pref_table_cls=MyPrefTable,
    agent=extractor,
    compaction_config=compaction,
)
```

When a sweep runs, the compactor agent uses dedicated tools (`list_preference_blocks`,
`get_conversation_block`, `rewrite_*`, `delete_*`) and iterates until every block has been
reviewed. You can disable specific stores by toggling `compact_preferences` or
`compact_conversations`.

### Manual Cleanup

Implement custom cleanup logic:

```python
async def cleanup_old_memories(diary, user_id, days=30):
    # Load conversations
    convs_data = await diary._load_convs(user_id)

    # Filter old conversations
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    filtered = {}

    for session_id, conv in convs_data.items():
        if session_id == "_meta":
            filtered[session_id] = conv
            continue

        created = datetime.fromisoformat(conv.get("_created", ""))
        if created > cutoff:
            filtered[session_id] = conv

    # Save filtered data
    await diary._save_convs(user_id, filtered)
```

## Error Handling

### Custom Error Handlers

```python
class RobustMemoryWriter(MemoryWriter):
    async def _process_one(self, item):
        try:
            await super()._process_one(item)
        except Exception as e:
            # Log error
            print(f"Failed to process memory: {e}")

            # Send to dead letter queue
            await self.dead_letter_queue.put(item)

            # Alert monitoring
            await self.alert_monitor(item, e)
```

## Monitoring and Observability

### Add metrics collection:

```python
from prometheus_client import Counter, Histogram

memory_updates = Counter('memory_updates_total', 'Total memory updates')
update_duration = Histogram('memory_update_duration_seconds', 'Memory update duration')

class MetricsMemoryWriter(MemoryWriter):
    async def submit(self, user_id, session_id, user_msg, assistant_msg):
        memory_updates.inc()
        with update_duration.time():
            await super().submit(user_id, session_id, user_msg, assistant_msg)
```
