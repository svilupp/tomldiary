# Getting Started with tomldiary

This guide will help you get up and running with tomldiary in minutes.

## Installation

Install tomldiary using `uv`:

```bash
uv sync
```

## Basic Concepts

tomldiary provides three main components:

1. **Diary**: The core class that manages memory storage and retrieval, it can have many "backends" to preserve the information
2. **MemoryWriter**: A background queue system for non-blocking memory updates
3. **Preference Tables**: Pydantic models that define memory categories (eg, "about", "likes", "dislike")

## Your First Memory System

Here's a complete example to get you started:

```python
import asyncio
from pathlib import Path
from pydantic import BaseModel
from typing import Dict
from tomldiary import (
    Diary,
    MemoryWriter, 
    PreferenceItem,
    shutdown_all_background_tasks
)
from tomldiary.backends import LocalBackend

# Step 1: Define your preference categories, be as specific as possible
class SimplePrefTable(BaseModel):
    """
    like    : Things the user enjoys
    dislike : Things the user avoids
    """
    like: Dict[str, PreferenceItem] = {}
    dislike: Dict[str, PreferenceItem] = {}

async def main():
    # Step 2: Create the diary
    diary = Diary(
        backend=LocalBackend(Path("./my_memories")),
        pref_table_cls=SimplePrefTable
    )
    
    # Step 3: Create the writer
    writer = MemoryWriter(diary)
    
    # Step 4: Process some conversations, requires LLM call
    await writer.submit(
        user_id="user123",
        session_id="session1",
        user_message="I love chocolate ice cream!",
        assistant_response="I'll remember you love chocolate ice cream."
    )
    
    # Wait a bit for processing
    await asyncio.sleep(1)
    
    # Step 5: Read the memories
    prefs = await diary.preferences("user123")
    print("User preferences:")
    print(prefs)
    
    # Step 6: Clean up
    await writer.close()
    await shutdown_all_background_tasks()

# Run the example
asyncio.run(main())
```

## Understanding the Output

After running the example, you'll find TOML files in `./my_memories/`:

- `user123_preferences.toml`: Contains categorized preferences
- `user123_conversations.toml`: Contains conversation summaries

The preferences file might look like:

```toml
[_meta]
version = "0.2"
schema_name = "SimplePrefTable"

[preferences.like.chocolate_ice_cream]
text = "loves chocolate ice cream"
contexts = ["food", "dessert"]
_count = 1
_created = "2024-01-01T12:00:00Z"
_updated = "2024-01-01T12:00:00Z"
```

## Next Steps

- [API Reference](api-reference.md) - Detailed API documentation
- [Advanced Usage](advanced-usage.md) - Custom backends and configurations
- [Examples](../examples/) - More example implementations