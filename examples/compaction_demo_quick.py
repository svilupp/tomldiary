#!/usr/bin/env python3
"""
🧪 Quick Compaction Demo
A fast demonstration of the compaction service with one targeted scenario.
"""

import asyncio
import os
from pathlib import Path

from culinary_prefs import CulinaryPrefTable
from dotenv import load_dotenv

from tomldiary import Diary
from tomldiary.backends.local import LocalBackend
from tomldiary.compaction import CompactionConfig

load_dotenv()


async def main():
    print("\n🧪 QUICK COMPACTION DEMO")
    print("=" * 70)
    print("Demonstrating memory compression with redundant Italian food preferences\n")

    # Setup with aggressive compaction
    backend = LocalBackend(Path("memory_demo_quick"))
    compaction_config = CompactionConfig(
        enabled=True,
        total_char_threshold=500,  # Run when total exceeds 500 chars
        user_turn_interval=5,  # Or after 5 turns
        cooldown_seconds=0,
        compact_preferences=True,
        compact_conversations=True,
    )

    diary = Diary(
        backend=backend,
        pref_table_cls=CulinaryPrefTable,
        max_prefs_per_category=50,
        max_conversations=50,
        compaction_config=compaction_config,
    )

    user_id = "chef_demo"

    # Create 8 redundant preferences about Italian food
    print("📝 Creating 8 redundant memories about loving Italian food...")
    redundant_phrases = [
        "I absolutely love Italian food",
        "Italian cuisine is my favorite",
        "I really enjoy Italian dishes",
        "Italian food is amazing",
        "Nothing beats Italian cooking",
        "I prefer Italian over everything",
        "Italian food is wonderful",
        "I'm passionate about Italian cuisine",
    ]

    for i, phrase in enumerate(redundant_phrases):
        print(f'   {i + 1}. Adding: "{phrase}"')
        await diary.update_memory(
            user_id=user_id,
            session_id=f"interview_{i}",
            user_msg="What's your favorite cuisine?",
            assistant_msg=phrase,
        )

    # Get stats BEFORE showing to user
    prefs_before = await diary._load_prefs(user_id)
    convs_before = await diary._load_convs(user_id)

    pref_count_before = sum(len(items) for items in prefs_before.get("preferences", {}).values())
    pref_chars_before = sum(
        len(data.get("text", ""))
        for cat in prefs_before.get("preferences", {}).values()
        for data in cat.values()
    )

    conv_count_before = len(convs_before.get("conversations", {}))
    conv_chars_before = sum(
        len(data.get("summary", "")) for data in convs_before.get("conversations", {}).values()
    )

    print("\n📊 BEFORE COMPACTION:")
    print(f"   • Preferences: {pref_count_before} blocks, {pref_chars_before} chars")
    print(f"   • Conversations: {conv_count_before} blocks, {conv_chars_before} chars")
    print(f"   • Total: {pref_chars_before + conv_chars_before} chars")

    # Force one more update to trigger compaction
    print("\n⚙️  Triggering compaction...")
    await diary.update_memory(
        user_id=user_id,
        session_id="final",
        user_msg="Any other thoughts?",
        assistant_msg="I just love Italian food so much!",
    )

    # Get stats AFTER
    prefs_after = await diary._load_prefs(user_id)
    convs_after = await diary._load_convs(user_id)

    pref_count_after = sum(len(items) for items in prefs_after.get("preferences", {}).values())
    pref_chars_after = sum(
        len(data.get("text", ""))
        for cat in prefs_after.get("preferences", {}).values()
        for data in cat.values()
    )

    conv_count_after = len(convs_after.get("conversations", {}))
    conv_chars_after = sum(
        len(data.get("summary", "")) for data in convs_after.get("conversations", {}).values()
    )

    print("\n📊 AFTER COMPACTION:")
    print(f"   • Preferences: {pref_count_after} blocks, {pref_chars_after} chars")
    print(f"   • Conversations: {conv_count_after} blocks, {conv_chars_after} chars")
    print(f"   • Total: {pref_chars_after + conv_chars_after} chars")

    # Calculate reductions
    if pref_chars_before > 0:
        pref_reduction = (pref_chars_before - pref_chars_after) / pref_chars_before * 100
        print("\n✨ COMPRESSION:")
        print(
            f"   • Preference chars: {pref_chars_before} → {pref_chars_after} ({pref_reduction:.1f}% reduction)"
        )

    if pref_count_before != pref_count_after:
        print(f"   • Preference blocks: {pref_count_before} → {pref_count_after}")

    # Show what survived
    print("\n📄 RESULTING PREFERENCES:")
    for category, items in prefs_after.get("preferences", {}).items():
        for pref_id, data in items.items():
            text = data.get("text", "")
            print(f"   • [{category}/{pref_id}]: {text}")

    if not prefs_after.get("preferences"):
        print("   (All preferences were compacted/consolidated)")

    print("\n📄 SAMPLE CONVERSATIONS (first 3):")
    for _i, (session_id, data) in enumerate(list(convs_after.get("conversations", {}).items())[:3]):
        summary = data.get("summary", "")
        keywords = data.get("keywords", [])
        print(f"   • {session_id}:")
        print(f"     Summary: {summary}")
        print(f"     Keywords: {', '.join(keywords)}")

    print(f"\n✅ Demo complete! Check 'memory_demo_quick/{user_id}/' for TOML files")


if __name__ == "__main__":
    if not os.getenv("OPENAI_API_KEY"):
        print("⚠️  Please set OPENAI_API_KEY environment variable")
    else:
        asyncio.run(main())
