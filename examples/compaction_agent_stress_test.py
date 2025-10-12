#!/usr/bin/env python3
"""
🧪 Compaction Agent Stress Test
Comprehensive test suite for the TomlDiary compaction service.

Tests various scenarios where memories need to be compressed:
- Redundant duplicates
- Contradictory evolution
- Noise/filler content
- Granular → consolidated
- Volume stress
- Mixed chaos
"""

import asyncio
from pathlib import Path
from datetime import datetime, UTC
from tomldiary import Diary
from tomldiary.backends.local import LocalBackend
from tomldiary.compaction import CompactionConfig
from culinary_prefs import CulinaryPrefTable

# Enable logfire for observability
import os
from dotenv import load_dotenv
load_dotenv()
import logfire
logfire.configure(scrubbing=False, service_name="compaction_stress_test", send_to_logfire='if-token-present')
logfire.instrument_pydantic_ai()


class CompactionTestRunner:
    """Helper class to run compaction test scenarios."""

    def __init__(self, storage_dir: Path):
        self.storage_dir = storage_dir
        self.backend = LocalBackend(storage_dir)

        # Aggressive compaction config to force immediate runs
        self.compaction_config = CompactionConfig(
            enabled=True,
            total_char_threshold=100,  # Very low threshold
            segment_char_threshold=50,  # Very low threshold
            user_turn_interval=1,  # Compact after every turn
            cooldown_seconds=0,  # No cooldown
            compact_preferences=True,
            compact_conversations=True,
        )

        # Let Diary create the compactor automatically
        self.diary = Diary(
            backend=self.backend,
            pref_table_cls=CulinaryPrefTable,
            max_prefs_per_category=50,
            max_conversations=50,
            compaction_config=self.compaction_config,
        )

    async def get_stats(self, user_id: str):
        """Get current memory statistics."""
        prefs = await self.diary._load_prefs(user_id)
        convs = await self.diary._load_convs(user_id)

        # Count preference blocks
        pref_count = 0
        pref_chars = 0
        pref_blocks = []
        for category, items in prefs.get("preferences", {}).items():
            for pref_id, data in items.items():
                pref_count += 1
                text = data.get("text", "")
                pref_chars += len(text)
                pref_blocks.append(f"{category}/{pref_id}: {text[:60]}...")

        # Count conversation blocks
        conv_count = len(convs.get("conversations", {}))
        conv_chars = 0
        conv_blocks = []
        for session_id, data in convs.get("conversations", {}).items():
            summary = data.get("summary", "")
            conv_chars += len(summary)
            conv_blocks.append(f"{session_id}: {summary[:60]}...")

        return {
            "pref_count": pref_count,
            "pref_chars": pref_chars,
            "pref_blocks": pref_blocks,
            "conv_count": conv_count,
            "conv_chars": conv_chars,
            "conv_blocks": conv_blocks,
            "total_chars": pref_chars + conv_chars,
        }

    def print_stats(self, label: str, stats: dict):
        """Print formatted statistics."""
        print(f"\n{label}")
        print(f"  • Preferences: {stats['pref_count']} blocks, {stats['pref_chars']} chars")
        print(f"  • Conversations: {stats['conv_count']} blocks, {stats['conv_chars']} chars")
        print(f"  • Total: {stats['total_chars']} chars")

    def print_comparison(self, before: dict, after: dict):
        """Print before/after comparison with metrics."""
        pref_reduction = ((before['pref_count'] - after['pref_count']) / before['pref_count'] * 100) if before['pref_count'] > 0 else 0
        char_reduction = ((before['total_chars'] - after['total_chars']) / before['total_chars'] * 100) if before['total_chars'] > 0 else 0

        print(f"\n📊 IMPACT:")
        print(f"  • Preferences: {before['pref_count']} → {after['pref_count']} ({pref_reduction:+.0f}%)")
        print(f"  • Total chars: {before['total_chars']} → {after['total_chars']} ({char_reduction:+.0f}%)")

        if char_reduction > 20:
            print(f"  ✅ Significant compression achieved")
        elif char_reduction > 0:
            print(f"  ⚠️  Modest compression")
        else:
            print(f"  ❌ No compression or growth")


async def scenario_1_redundant_duplicates():
    """Test compaction of highly redundant, duplicate preferences."""
    print("\n" + "="*70)
    print("🧪 SCENARIO 1: Redundant Duplicates")
    print("="*70)
    print("Testing: 12 preferences saying essentially the same thing")

    runner = CompactionTestRunner(Path("memory_stress_test_s1"))
    user_id = "chef_redundant"

    # Create 12 redundant preferences about Italian food
    redundant_phrases = [
        "I absolutely love Italian food",
        "Italian cuisine is my favorite",
        "I really enjoy Italian dishes",
        "Italian food is amazing",
        "Nothing beats Italian cooking",
        "Italian is the best cuisine",
        "I prefer Italian over everything",
        "Italian food is wonderful",
        "I'm passionate about Italian cuisine",
        "Italian dishes are my go-to",
        "I can't get enough of Italian food",
        "Italian cooking is the best",
    ]

    # Inject all redundant memories
    for i, phrase in enumerate(redundant_phrases):
        await runner.diary.update_memory(
            user_id=user_id,
            session_id=f"interview_{i}",
            user_msg=f"What's your favorite cuisine?",
            assistant_msg=phrase
        )

    before = await runner.get_stats(user_id)
    runner.print_stats("📊 BEFORE:", before)

    print("\n🤖 Compaction should consolidate these redundant preferences...")

    after = await runner.get_stats(user_id)
    runner.print_stats("📊 AFTER:", after)
    runner.print_comparison(before, after)

    # Show what's left
    print(f"\n📄 Remaining preferences:")
    for block in after['pref_blocks'][:5]:
        print(f"  {block}")

    return before, after


async def scenario_2_contradictory_evolution():
    """Test handling of preferences that evolved/contradicted over time."""
    print("\n" + "="*70)
    print("🧪 SCENARIO 2: Contradictory Evolution")
    print("="*70)
    print("Testing: Preferences that changed dramatically over time")

    runner = CompactionTestRunner(Path("memory_stress_test_s2"))
    user_id = "chef_evolving"

    # Create evolving contradictory preferences
    evolution = [
        ("early_episode", "I absolutely hate spicy food. Can't stand it at all."),
        ("middle_episode", "You know, spicy food isn't as bad as I thought. I can tolerate mild spice now."),
        ("recent_episode", "I've completely changed my mind - I love really spicy food now! The hotter the better!"),
    ]

    for session_id, msg in evolution:
        await runner.diary.update_memory(
            user_id=user_id,
            session_id=session_id,
            user_msg="How do you feel about spicy food?",
            assistant_msg=msg
        )

    before = await runner.get_stats(user_id)
    runner.print_stats("📊 BEFORE:", before)

    print("\n🤖 Compaction should resolve contradictions (keep latest or note evolution)...")

    after = await runner.get_stats(user_id)
    runner.print_stats("📊 AFTER:", after)
    runner.print_comparison(before, after)

    print(f"\n📄 Final preferences:")
    for block in after['pref_blocks']:
        print(f"  {block}")

    return before, after


async def scenario_3_noise_filler():
    """Test removal of conversational noise while keeping substance."""
    print("\n" + "="*70)
    print("🧪 SCENARIO 3: Noise/Filler Content")
    print("="*70)
    print("Testing: Conversations with lots of filler, minimal substance")

    runner = CompactionTestRunner(Path("memory_stress_test_s3"))
    user_id = "chef_chatty"

    # Mix filler with occasional substance
    conversations = [
        ("chat1", "Thanks so much for having me on the show!", "Thank you for being here!"),
        ("chat2", "That's really interesting, I appreciate that.", "Great to hear!"),
        ("chat3", "I prefer organic ingredients whenever possible.", "That's wonderful!"),
        ("chat4", "You know, I think that's a good point.", "Glad you think so!"),
        ("chat5", "Thanks again, this has been fun!", "Thank you!"),
        ("chat6", "I always use fresh herbs from my garden.", "Amazing!"),
        ("chat7", "That's so kind of you to say.", "My pleasure!"),
        ("chat8", "I appreciate the opportunity to share.", "Of course!"),
    ]

    for session_id, user_msg, assistant_msg in conversations:
        await runner.diary.update_memory(
            user_id=user_id,
            session_id=session_id,
            user_msg=user_msg,
            assistant_msg=assistant_msg
        )

    before = await runner.get_stats(user_id)
    runner.print_stats("📊 BEFORE:", before)

    print("\n🤖 Compaction should remove filler, keep substance...")

    after = await runner.get_stats(user_id)
    runner.print_stats("📊 AFTER:", after)
    runner.print_comparison(before, after)

    print(f"\n📄 Remaining content:")
    for block in after['pref_blocks']:
        print(f"  PREF: {block}")
    for block in after['conv_blocks'][:5]:
        print(f"  CONV: {block}")

    return before, after


async def scenario_4_granular_to_consolidated():
    """Test consolidation of many specific items into groups."""
    print("\n" + "="*70)
    print("🧪 SCENARIO 4: Granular → Consolidated")
    print("="*70)
    print("Testing: Many specific items that could be semantically grouped")

    runner = CompactionTestRunner(Path("memory_stress_test_s4"))
    user_id = "chef_detailed"

    # Create many granular herb preferences
    herbs = ["basil", "oregano", "thyme", "rosemary", "parsley", "cilantro", "sage", "mint", "dill", "tarragon"]

    for i, herb in enumerate(herbs):
        await runner.diary.update_memory(
            user_id=user_id,
            session_id=f"herb_talk_{i}",
            user_msg=f"Do you like {herb}?",
            assistant_msg=f"Oh yes, I absolutely love {herb}. I use it all the time."
        )

    before = await runner.get_stats(user_id)
    runner.print_stats("📊 BEFORE:", before)

    print("\n🤖 Compaction should group related items...")

    after = await runner.get_stats(user_id)
    runner.print_stats("📊 AFTER:", after)
    runner.print_comparison(before, after)

    print(f"\n📄 Result (should be grouped):")
    for block in after['pref_blocks']:
        print(f"  {block}")

    return before, after


async def scenario_5_volume_stress():
    """Test compaction under high volume with mixed quality."""
    print("\n" + "="*70)
    print("🧪 SCENARIO 5: Volume Stress Test")
    print("="*70)
    print("Testing: 50 memories with mixed redundancy, uniqueness, and noise")

    runner = CompactionTestRunner(Path("memory_stress_test_s5"))
    user_id = "chef_prolific"

    # Generate 50 memories with varying patterns
    messages = []

    # 15 redundant about pasta
    for i in range(15):
        messages.append((f"pasta_{i}", f"I love pasta", f"Pasta is wonderful"))

    # 10 unique valuable facts
    unique_facts = [
        "I trained at Le Cordon Bleu in Paris",
        "I'm allergic to shellfish",
        "I always cook with kosher salt",
        "I prefer cast iron pans",
        "I make my own pasta dough weekly",
        "I grow heirloom tomatoes",
        "I use a Japanese santoku knife",
        "I'm lactose intolerant",
        "I studied under Gordon Ramsay",
        "I only use grass-fed beef",
    ]
    for i, fact in enumerate(unique_facts):
        messages.append((f"unique_{i}", "Tell me about yourself", fact))

    # 15 filler conversations
    for i in range(15):
        messages.append((f"filler_{i}", "Thanks", "You're welcome"))

    # 10 more redundant about French cuisine
    for i in range(10):
        messages.append((f"french_{i}", "What cuisine do you like?", "French cuisine is my favorite"))

    for session_id, user_msg, assistant_msg in messages:
        await runner.diary.update_memory(
            user_id=user_id,
            session_id=session_id,
            user_msg=user_msg,
            assistant_msg=assistant_msg
        )

    before = await runner.get_stats(user_id)
    runner.print_stats("📊 BEFORE:", before)

    print("\n🤖 Compaction should significantly reduce volume while preserving unique facts...")

    after = await runner.get_stats(user_id)
    runner.print_stats("📊 AFTER:", after)
    runner.print_comparison(before, after)

    print(f"\n📄 Sample of what survived (first 10 prefs):")
    for block in after['pref_blocks'][:10]:
        print(f"  {block}")

    return before, after


async def scenario_6_mixed_chaos():
    """Test realistic messy data combining all patterns."""
    print("\n" + "="*70)
    print("🧪 SCENARIO 6: Mixed Signal Chaos")
    print("="*70)
    print("Testing: Realistic mess with duplicates + contradictions + noise + value")

    runner = CompactionTestRunner(Path("memory_stress_test_s6"))
    user_id = "chef_realistic"

    # A realistic mess combining all problems
    messages = [
        # Some redundant
        ("s1", "What do you like?", "I love Italian food"),
        ("s2", "Favorite cuisine?", "Italian is my favorite"),
        ("s3", "What cuisine?", "I prefer Italian"),

        # Some contradictory
        ("s4", "Spicy food?", "I hate spicy food"),
        ("s5", "Still don't like spice?", "I'm warming up to spicy food"),
        ("s6", "Any change?", "I love spicy food now!"),

        # Some noise
        ("s7", "Thanks!", "You're welcome!"),
        ("s8", "Great show!", "Thank you!"),
        ("s9", "Appreciate it", "My pleasure"),

        # Some valuable unique facts
        ("s10", "Training?", "I studied at Le Cordon Bleu"),
        ("s11", "Allergies?", "Severe nut allergy"),
        ("s12", "Equipment?", "I only use carbon steel knives"),

        # More redundant
        ("s13", "Pasta?", "Love pasta"),
        ("s14", "Pasta dishes?", "Pasta is amazing"),
        ("s15", "Italian food again?", "Yes, especially pasta"),

        # Mix of everything
        ("s16", "Your style?", "I'm a perfectionist in the kitchen"),
        ("s17", "Thanks for sharing", "Happy to help"),
        ("s18", "Organic?", "I only use organic vegetables"),
        ("s19", "More about Italian?", "Italian food is the best cuisine ever"),
        ("s20", "Philosophy?", "Simple ingredients, perfect execution"),
    ]

    for session_id, user_msg, assistant_msg in messages:
        await runner.diary.update_memory(
            user_id=user_id,
            session_id=session_id,
            user_msg=user_msg,
            assistant_msg=assistant_msg
        )

    before = await runner.get_stats(user_id)
    runner.print_stats("📊 BEFORE:", before)

    print("\n🤖 Compaction should clean up across all dimensions...")

    after = await runner.get_stats(user_id)
    runner.print_stats("📊 AFTER:", after)
    runner.print_comparison(before, after)

    print(f"\n📄 Final clean profile:")
    for block in after['pref_blocks']:
        print(f"  {block}")

    return before, after


async def run_all_scenarios():
    """Run all test scenarios and provide summary."""
    print("\n🧪 COMPACTION AGENT STRESS TEST SUITE")
    print("="*70)
    print("Testing the compaction service with artificial memories")
    print("="*70)

    results = {}

    try:
        results['s1'] = await scenario_1_redundant_duplicates()
    except Exception as e:
        print(f"❌ Scenario 1 failed: {e}")
        import traceback
        traceback.print_exc()

    try:
        results['s2'] = await scenario_2_contradictory_evolution()
    except Exception as e:
        print(f"❌ Scenario 2 failed: {e}")
        import traceback
        traceback.print_exc()

    try:
        results['s3'] = await scenario_3_noise_filler()
    except Exception as e:
        print(f"❌ Scenario 3 failed: {e}")
        import traceback
        traceback.print_exc()

    try:
        results['s4'] = await scenario_4_granular_to_consolidated()
    except Exception as e:
        print(f"❌ Scenario 4 failed: {e}")
        import traceback
        traceback.print_exc()

    try:
        results['s5'] = await scenario_5_volume_stress()
    except Exception as e:
        print(f"❌ Scenario 5 failed: {e}")
        import traceback
        traceback.print_exc()

    try:
        results['s6'] = await scenario_6_mixed_chaos()
    except Exception as e:
        print(f"❌ Scenario 6 failed: {e}")
        import traceback
        traceback.print_exc()

    # Summary
    print("\n" + "="*70)
    print("📊 OVERALL SUMMARY")
    print("="*70)

    for scenario, (before, after) in results.items():
        char_reduction = ((before['total_chars'] - after['total_chars']) / before['total_chars'] * 100) if before['total_chars'] > 0 else 0
        print(f"{scenario.upper()}: {before['total_chars']} → {after['total_chars']} chars ({char_reduction:+.0f}%)")

    print("\n✅ Test suite complete! Check the memory_stress_test_* directories for TOML files")


if __name__ == "__main__":
    if not os.getenv("OPENAI_API_KEY"):
        print("⚠️  Please set OPENAI_API_KEY environment variable")
        print("   Example: export OPENAI_API_KEY='your-key-here'")
    else:
        asyncio.run(run_all_scenarios())
