#!/usr/bin/env python3
"""
🍳 Cooking Show Memory System with AI Chefs
Celebrity chefs discuss their culinary preferences with an AI host.
"""

import asyncio
from pathlib import Path
from pydantic_ai import Agent, RunContext
from tomldiary import TOMLDiary, MemoryWriter, shutdown_all_background_tasks
from tomldiary.backends.local import LocalBackend
from culinary_prefs import CulinaryPrefTable
import tomllib
from typing import Dict, Any


# Define the deps type for our cooking show context
class CookingShowContext:
    def __init__(self, chef_name: str, episode: str, diary: TOMLDiary, writer: MemoryWriter):
        self.chef_name = chef_name
        self.episode = episode
        self.diary = diary
        self.writer = writer
        self.prefs: Dict[str, Any] = {"preferences": {}}


# Create the cooking show host agent
host_agent = Agent(
    'openai:gpt-4o-mini',
    deps_type=CookingShowContext,
    system_prompt="""You are a friendly cooking show host interviewing celebrity chefs.
    Ask about their favorite dishes, cooking techniques, dietary restrictions, and culinary experiences.
    Keep responses conversational and enthusiastic. Extract preferences naturally through conversation."""
)


# Create the celebrity chef agent
chef_agent = Agent(
    'openai:gpt-4o-mini',
    deps_type=CookingShowContext,
    system_prompt="""You are a celebrity chef on a cooking show. You have strong opinions about food.
    Share your culinary preferences, favorite dishes, cooking habits, and any dietary restrictions.
    Be passionate and specific about your likes and dislikes. Each chef has a unique personality."""
)


@host_agent.tool
async def save_memory(ctx: RunContext[CookingShowContext], user_msg: str, assistant_msg: str) -> str:
    """Save the conversation to memory"""
    await ctx.deps.writer.submit(
        ctx.deps.chef_name,
        ctx.deps.episode,
        user_msg,
        assistant_msg
    )
    return "Memory saved"


@chef_agent.tool  
async def record_preference(ctx: RunContext[CookingShowContext], category: str, item: str, text: str, contexts: list[str]) -> str:
    """Record a preference in the chef's profile"""
    prefs = ctx.deps.prefs.setdefault("preferences", {})
    cat_prefs = prefs.setdefault(category, {})
    
    cat_prefs[item] = {
        "text": text,
        "contexts": contexts,
        "_count": cat_prefs.get(item, {}).get("_count", 0) + 1,
        "_created": "2024-01-01T00:00:00Z",
        "_updated": "2024-01-01T00:00:00Z"
    }
    
    return f"Recorded {category}: {item}"


async def chef_interview(chef_name: str, chef_personality: str, episodes: list[tuple[str, str]], diary: TOMLDiary, writer: MemoryWriter):
    """Conduct an interview with a celebrity chef"""
    
    for episode, topic in episodes:
        print(f"\n📺 {chef_name} - Episode: {episode}")
        print("-" * 40)
        
        context = CookingShowContext(chef_name, episode, diary, writer)
        
        # Customize chef's personality
        chef_with_personality = chef_agent.override(
            system_prompt=chef_agent._system_prompt + f"\n\nYour personality: {chef_personality}"
        )
        
        # Host introduces the topic
        host_intro = await host_agent.run(
            f"Welcome chef! Today let's talk about {topic}. What are your thoughts?",
            deps=context
        )
        print(f"🎤 Host: {host_intro.data}")
        
        # Chef responds
        chef_response = await chef_with_personality.run(
            host_intro.data,
            deps=context
        )
        print(f"👨‍🍳 {chef_name}: {chef_response.data}")
        
        # Save the initial exchange
        await context.writer.submit(chef_name, episode, host_intro.data, chef_response.data)
        
        # Continue conversation with follow-up
        host_followup = await host_agent.run(
            f"That's fascinating! Can you tell me more about your preferences regarding {topic}?",
            deps=context,
            message_history=host_intro.new_messages()
        )
        print(f"🎤 Host: {host_followup.data}")
        
        chef_detail = await chef_with_personality.run(
            host_followup.data,
            deps=context,
            message_history=chef_response.new_messages()
        )
        print(f"👨‍🍳 {chef_name}: {chef_detail.data}")
        
        # Save the follow-up
        await context.writer.submit(chef_name, episode, host_followup.data, chef_detail.data)


async def cooking_show_demo():
    """Run the AI-powered cooking show memory demo."""
    print("🍳 Welcome to the AI Cooking Show Memory System!")
    print("=" * 50)
    
    # Setup
    backend = LocalBackend(Path("memory_cooking_show"))
    
    # Create diary with the original CulinaryAgent for memory extraction
    from tomldiary import TOMLDiary
    
    class CulinaryAgent:
        """Agent that extracts cooking preferences from conversations."""
        
        async def run(self, message: str, deps=None):
            if not deps:
                return
            
            msg_lower = message.lower()
            prefs = deps.prefs.setdefault("preferences", {})
            
            # Extract favorite foods
            if any(word in msg_lower for word in ["love", "favorite", "enjoy", "best", "prefer", "fantastic", "amazing"]):
                favorite_foods = prefs.setdefault("favorite_foods", {})
                
                if "pasta" in msg_lower:
                    favorite_foods["pasta"] = {
                        "text": "enjoys pasta dishes",
                        "contexts": ["italian", "comfort-food"],
                        "_count": favorite_foods.get("pasta", {}).get("_count", 0) + 1,
                        "_created": "2024-01-01T00:00:00Z",
                        "_updated": "2024-01-01T00:00:00Z"
                    }
                
                if "sushi" in msg_lower:
                    favorite_foods["sushi"] = {
                        "text": "loves sushi",
                        "contexts": ["japanese", "seafood"],
                        "_count": favorite_foods.get("sushi", {}).get("_count", 0) + 1,
                        "_created": "2024-01-01T00:00:00Z",
                        "_updated": "2024-01-01T00:00:00Z"
                    }
                
                if "chocolate" in msg_lower:
                    favorite_foods["chocolate"] = {
                        "text": "chocolate lover",
                        "contexts": ["dessert", "sweet"],
                        "_count": favorite_foods.get("chocolate", {}).get("_count", 0) + 1,
                        "_created": "2024-01-01T00:00:00Z",
                        "_updated": "2024-01-01T00:00:00Z"
                    }
            
            # Extract cooking techniques
            if any(word in msg_lower for word in ["technique", "method", "style", "way"]):
                techniques = prefs.setdefault("cooking_techniques", {})
                
                if "grill" in msg_lower or "bbq" in msg_lower:
                    techniques["grilling"] = {
                        "text": "specializes in grilling and BBQ",
                        "contexts": ["technique", "outdoor"],
                        "_count": 1,
                        "_created": "2024-01-01T00:00:00Z",
                        "_updated": "2024-01-01T00:00:00Z"
                    }
                
                if "french" in msg_lower and ("technique" in msg_lower or "method" in msg_lower):
                    techniques["french_cooking"] = {
                        "text": "trained in French cooking techniques",
                        "contexts": ["technique", "classical"],
                        "_count": 1,
                        "_created": "2024-01-01T00:00:00Z",
                        "_updated": "2024-01-01T00:00:00Z"
                    }
            
            # Extract dislikes
            if any(word in msg_lower for word in ["hate", "dislike", "avoid", "never", "can't stand", "terrible"]):
                dislikes = prefs.setdefault("dislike", {})
                
                if "spicy" in msg_lower:
                    dislikes["spicy_food"] = {
                        "text": "avoids spicy food",
                        "contexts": ["preference"],
                        "_count": 1,
                        "_created": "2024-01-01T00:00:00Z",
                        "_updated": "2024-01-01T00:00:00Z"
                    }
                
                if "overcooked" in msg_lower or "overcook" in msg_lower:
                    dislikes["overcooked_food"] = {
                        "text": "hates overcooked food",
                        "contexts": ["technique", "quality"],
                        "_count": 1,
                        "_created": "2024-01-01T00:00:00Z",
                        "_updated": "2024-01-01T00:00:00Z"
                    }
            
            # Extract dietary restrictions
            if any(word in msg_lower for word in ["allergic", "allergy", "vegetarian", "vegan", "gluten", "lactose"]):
                restrictions = prefs.setdefault("dietary_restrictions", {})
                
                if "nuts" in msg_lower or "peanut" in msg_lower:
                    restrictions["nuts"] = {
                        "text": "nut allergy",
                        "contexts": ["health", "critical"],
                        "_count": 1,
                        "_created": "2024-01-01T00:00:00Z",
                        "_updated": "2024-01-01T00:00:00Z"
                    }
                
                if "shellfish" in msg_lower:
                    restrictions["shellfish"] = {
                        "text": "shellfish allergy",
                        "contexts": ["health", "seafood"],
                        "_count": 1,
                        "_created": "2024-01-01T00:00:00Z",
                        "_updated": "2024-01-01T00:00:00Z"
                    }
            
            # Extract cooking habits
            if any(word in msg_lower for word in ["always", "every", "daily", "regularly", "routine", "habit"]):
                habits = prefs.setdefault("cooking_habits", {})
                
                if "breakfast" in msg_lower:
                    habits["breakfast_cooking"] = {
                        "text": "cooks breakfast regularly",
                        "contexts": ["morning", "routine"],
                        "_count": 1,
                        "_created": "2024-01-01T00:00:00Z",
                        "_updated": "2024-01-01T00:00:00Z"
                    }
                
                if "taste" in msg_lower and "while" in msg_lower:
                    habits["taste_while_cooking"] = {
                        "text": "always tastes food while cooking",
                        "contexts": ["technique", "quality"],
                        "_count": 1,
                        "_created": "2024-01-01T00:00:00Z",
                        "_updated": "2024-01-01T00:00:00Z"
                    }
                
                if "fresh" in msg_lower and ("pasta" in msg_lower or "ingredient" in msg_lower):
                    habits["fresh_ingredients"] = {
                        "text": "uses fresh ingredients daily",
                        "contexts": ["quality", "sourcing"],
                        "_count": 1,
                        "_created": "2024-01-01T00:00:00Z",
                        "_updated": "2024-01-01T00:00:00Z"
                    }
    
    agent = CulinaryAgent()
    
    diary = TOMLDiary(
        backend=backend,
        pref_table_cls=CulinaryPrefTable,
        agent=(agent, ["favorite_foods", "cooking_techniques", "flavor_preferences", "dislikes", "dietary_restrictions", "cooking_habits", "ingredient_preferences"]),
        max_prefs_per_category=10,
        max_conversations=5
    )
    
    writer = MemoryWriter(diary, workers=4, qsize=20)
    
    # Chef personalities and interview topics
    chefs = [
        ("chef_gordon", "A passionate British chef known for high standards and fiery temperament. Loves perfection.", [
            ("basics_masterclass", "Italian cuisine and pasta"),
            ("dessert_special", "chocolate desserts and pastries")
        ]),
        ("chef_julia", "A warm French chef who believes in simple, quality ingredients. Very traditional.", [
            ("morning_show", "breakfast and morning routines"),
            ("technique_talk", "French cooking techniques")
        ]),
        ("chef_marco", "An innovative fusion chef who combines Asian and Italian cuisines. Very creative.", [
            ("fusion_episode", "combining different cuisines"),
            ("ingredient_focus", "working with fresh ingredients")
        ])
    ]
    
    # Conduct interviews
    print("\n🎬 Starting celebrity chef interviews...\n")
    
    for chef_name, personality, episodes in chefs:
        await chef_interview(chef_name, personality, episodes, diary, writer)
        await asyncio.sleep(0.5)  # Brief pause between chefs
    
    # Let processing complete
    await asyncio.sleep(1)
    
    # Display the memories
    print("\n\n📚 Chef Profiles & Memories:")
    print("=" * 50)
    
    for chef_name, _, _ in chefs:
        print(f"\n👨‍🍳 {chef_name.upper()}")
        print("-" * 30)
        
        # Show preferences
        prefs_toml = await diary.preferences(chef_name)
        if prefs_toml:
            prefs_data = tomllib.loads(prefs_toml)
            preferences = prefs_data.get("preferences", {})
            
            if "favorite_foods" in preferences:
                print("  🍽️  Favorite Foods:")
                for item, details in preferences["favorite_foods"].items():
                    print(f"    - {item}: {details['text']} (mentioned {details.get('_count', 1)}x)")
            
            if "cooking_techniques" in preferences:
                print("  👨‍🍳 Cooking Techniques:")
                for item, details in preferences["cooking_techniques"].items():
                    print(f"    - {item}: {details['text']}")
            
            if "dislikes" in preferences:
                print("  👎 Dislikes:")
                for item, details in preferences["dislikes"].items():
                    print(f"    - {item}: {details['text']}")
            
            if "dietary_restrictions" in preferences:
                print("  ⚠️  Dietary Restrictions:")
                for item, details in preferences["dietary_restrictions"].items():
                    print(f"    - {item}: {details['text']}")
            
            if "cooking_habits" in preferences:
                print("  🔄 Cooking Habits:")
                for item, details in preferences["cooking_habits"].items():
                    print(f"    - {item}: {details['text']}")
        
        # Show episodes
        conversations = await diary.last_conversations(chef_name, n=5)
        if conversations:
            print(f"  📺 Recent Episodes ({len(conversations)}):")
            for session_id, conv in conversations.items():
                print(f"    - {session_id}: {conv['_turns']} segments recorded")
    
    # Show sample TOML
    print("\n📄 Sample TOML file (chef_gordon preferences):")
    print("-" * 50)
    gordon_prefs = await diary.preferences("chef_gordon")
    if gordon_prefs:
        print(gordon_prefs[:500] + "..." if len(gordon_prefs) > 500 else gordon_prefs)
    
    # Cleanup
    await writer.close()
    await shutdown_all_background_tasks()
    
    print("\n✨ Cooking show memories saved successfully!")
    print(f"📁 Check the 'memory_cooking_show' directory for TOML files")


if __name__ == "__main__":
    # Note: Requires OPENAI_API_KEY environment variable
    import os
    if not os.getenv("OPENAI_API_KEY"):
        print("⚠️  Please set OPENAI_API_KEY environment variable")
        print("   Example: export OPENAI_API_KEY='your-key-here'")
    else:
        asyncio.run(cooking_show_demo())