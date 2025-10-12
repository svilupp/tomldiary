#!/usr/bin/env python3
"""
Minimal Memory System Example

This demonstrates the simplest possible use of Diary for educational purposes.
No external dependencies, no complex AI - just the core memory functionality.
"""

import asyncio
from pathlib import Path

from pydantic import BaseModel, Field

from tomldiary import Diary, MemoryWriter, shutdown_all_background_tasks
from tomldiary.backends.local import LocalBackend
from tomldiary.models import PreferenceItem
from tomldiary.compaction import CompactionConfig


# Define a simple preference schema
class SimplePrefTable(BaseModel):
    """Very simple preference table for educational purposes."""

    like: dict[str, PreferenceItem] = Field(default_factory=dict)
    dislike: dict[str, PreferenceItem] = Field(default_factory=dict)
    about: dict[str, PreferenceItem] = Field(default_factory=dict)


class SimpleAgent:
    """Educational agent that extracts basic preferences from text."""

    async def run(self, message: str, deps=None):
        """Extract preferences from a message - educational implementation."""
        if not deps:
            return

        msg_lower = message.lower()
        prefs = deps.prefs.setdefault("preferences", {})

        # Extract likes
        if any(word in msg_lower for word in ["love", "like", "enjoy", "favorite"]):
            likes = prefs.setdefault("like", {})

            if "pizza" in msg_lower:
                likes["pizza"] = {
                    "text": "enjoys pizza",
                    "contexts": ["food"],
                    "_count": likes.get("pizza", {}).get("_count", 0) + 1,
                    "_created": "2024-01-01T00:00:00Z",
                    "_updated": "2024-01-01T00:00:00Z",
                }

            if "coffee" in msg_lower:
                likes["coffee"] = {
                    "text": "coffee lover",
                    "contexts": ["beverage"],
                    "_count": likes.get("coffee", {}).get("_count", 0) + 1,
                    "_created": "2024-01-01T00:00:00Z",
                    "_updated": "2024-01-01T00:00:00Z",
                }

        # Extract dislikes
        if any(word in msg_lower for word in ["hate", "dislike", "avoid"]):
            dislikes = prefs.setdefault("dislike", {})

            if "spicy" in msg_lower:
                dislikes["spicy_food"] = {
                    "text": "dislikes spicy food",
                    "contexts": ["food"],
                    "_count": 1,
                    "_created": "2024-01-01T00:00:00Z",
                    "_updated": "2024-01-01T00:00:00Z",
                }

        # Extract facts about the person
        if any(word in msg_lower for word in ["i am", "i'm", "work as", "live in"]):
            about = prefs.setdefault("about", {})

            if "chef" in msg_lower:
                about["profession"] = {
                    "text": "works as a chef",
                    "contexts": ["career"],
                    "_count": 1,
                    "_created": "2024-01-01T00:00:00Z",
                    "_updated": "2024-01-01T00:00:00Z",
                }

            if "italy" in msg_lower:
                about["location"] = {
                    "text": "from Italy",
                    "contexts": ["geography"],
                    "_count": 1,
                    "_created": "2024-01-01T00:00:00Z",
                    "_updated": "2024-01-01T00:00:00Z",
                }


async def simple_demo():
    """Educational demo showing the core memory system functionality."""
    print("📚 Diary Educational Example")
    print("=" * 40)
    print("This shows the simplest possible memory system usage.\n")

    # 1. Setup storage and agent
    print("1️⃣ Setting up memory storage...")
    backend = LocalBackend(Path("memory_simple"))
    agent = SimpleAgent()

    # 2. Create diary with simple schema
    print("2️⃣ Creating memory diary...")
    compaction = CompactionConfig(
        enabled=False,  # flip to True to enable background compaction sweeps
        compact_preferences=True,
        compact_conversations=False,
    )
    diary = Diary(
        backend=backend,
        pref_table_cls=SimplePrefTable,
        agent=(agent, ["like", "dislike", "about"]),
        max_prefs_per_category=5,
        max_conversations=3,
        compaction_config=compaction,
    )

    # 3. Create writer for async operations
    print("3️⃣ Starting memory writer...")
    writer = MemoryWriter(diary, workers=1, qsize=5)

    # 4. Simple conversations (what a user might say)
    print("\n4️⃣ Processing conversations...")
    conversations = [
        ("alice", "chat_1", "I love pizza and coffee!", "Great choices!"),
        ("alice", "chat_1", "I hate spicy food though", "Good to know!"),
        ("bob", "chat_1", "I'm a chef from Italy", "How interesting!"),
        ("bob", "chat_1", "I enjoy coffee every morning", "A good habit!"),
    ]

    # 5. Submit conversations for processing
    tasks = []
    for user, session, user_msg, response in conversations:
        print(f"   💬 {user}: '{user_msg}'")
        task = writer.submit(user, session, user_msg, response)
        tasks.append(task)

    await asyncio.gather(*tasks)
    await asyncio.sleep(0.2)  # Let processing finish

    # 6. Show what was learned
    print("\n5️⃣ Extracted memories:")
    for user in ["alice", "bob"]:
        print(f"\n👤 {user.upper()}:")

        # Get preferences
        prefs_toml = await diary.preferences(user)
        if prefs_toml:
            import tomllib

            prefs_data = tomllib.loads(prefs_toml)
            preferences = prefs_data.get("preferences", {})

            for category, items in preferences.items():
                if items:
                    print(f"  {category}:")
                    for _item, details in items.items():
                        count = details.get("_count", 1)
                        count_text = f" ({count}x)" if count > 1 else ""
                        print(f"    • {details['text']}{count_text}")

        # Show conversations
        conversations_data = await diary.last_conversations(user, limit=5)
        if conversations_data:
            print(f"  conversations: {len(conversations_data)} sessions")

    # 7. Show raw TOML file contents
    print("\n6️⃣ Sample TOML file (alice):")
    alice_prefs = await diary.preferences("alice")
    if alice_prefs:
        print(alice_prefs)

    # 8. Cleanup
    await writer.close()
    await shutdown_all_background_tasks()

    print("\n✅ Educational demo complete!")
    print("📁 Files saved in 'memory_simple' directory")
    print("\n🎯 Key concepts demonstrated:")
    print("   • TOML-based preference storage")
    print("   • Simple text-based extraction")
    print("   • Multi-user memory isolation")
    print("   • Conversation logging with turn counts")


if __name__ == "__main__":
    asyncio.run(simple_demo())
