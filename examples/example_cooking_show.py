#!/usr/bin/env python3
"""
🍳 Cooking Show Memory System with AI Chefs
Celebrity chefs discuss their culinary preferences with an AI host.
Uses direct diary.update_memory() calls for simple, reliable memory updates.
"""

import asyncio
from pathlib import Path
from pydantic_ai import Agent, RunContext
from tomldiary import Diary
from tomldiary.backends.local import LocalBackend
from culinary_prefs import CulinaryPrefTable

## Enable logfire for better observability
import os
from dotenv import load_dotenv
load_dotenv()
import logfire
logfire.configure(scrubbing=False, service_name="cooking_show", send_to_logfire='if-token-present')
logfire.instrument_pydantic_ai()


# Define the deps type for our cooking show context
class CookingShowContext:
    def __init__(self, chef_name: str, episode: str, diary: Diary, personality: str = ""):
        self.chef_name = chef_name
        self.episode = episode
        self.diary = diary
        self.personality = personality


# Create the cooking show host agent
host_agent = Agent(
    'openai:gpt-4.1-mini',
    deps_type=CookingShowContext,
    system_prompt="""You are a friendly cooking show host interviewing celebrity chefs.
    Ask about their favorite dishes, cooking techniques, dietary restrictions, and culinary experiences.
    Keep responses conversational and enthusiastic. Extract preferences naturally through conversation."""
)


# Create the celebrity chef agent with dynamic memory awareness
chef_agent = Agent(
    'openai:gpt-4.1-mini',
    deps_type=CookingShowContext,
    system_prompt="""You are a celebrity chef on a cooking show. You have strong opinions about food.
    Share your culinary preferences, favorite dishes, cooking habits, and any dietary restrictions.
    Be passionate and specific about your likes and dislikes. Stay consistent with any preferences you've previously mentioned."""
)


@chef_agent.system_prompt
async def add_chef_memory(ctx: RunContext[CookingShowContext]) -> str:
    """Add the chef's existing memory context to the system prompt."""
    # Use diary's built-in pretty printing methods
    memory_parts = []
    
    # Get formatted preferences
    formatted_prefs = await ctx.deps.diary.pretty_preferences(ctx.deps.chef_name)
    if formatted_prefs != "No preferences found for user.":
        memory_parts.append("Your existing preferences:")
        memory_parts.append(formatted_prefs)
    
    # Get formatted conversations
    formatted_convs = await ctx.deps.diary.pretty_conversations(ctx.deps.chef_name, limit=3)
    if formatted_convs != "No conversations found for user.":
        memory_parts.append("Recent conversation highlights:")
        memory_parts.append(formatted_convs)
    
    return "\n\n".join(memory_parts) if memory_parts else ""


@chef_agent.system_prompt
def add_chef_personality(ctx: RunContext[CookingShowContext]) -> str:
    """Add the chef's personality to the system prompt."""
    if ctx.deps.personality:
        return f"Your personality: {ctx.deps.personality}"
    return ""


async def chef_interview(chef_name: str, chef_personality: str, episodes: list[tuple[str, str]], diary: Diary):
    """Conduct an interview with a celebrity chef using AI agents"""
    
    for episode, topic in episodes:
        print(f"\n📺 {chef_name} - Episode: {episode}")
        print("-" * 40)
        
        # Create context with personality included
        context = CookingShowContext(chef_name, episode, diary, chef_personality)
        
        # Host introduces the topic
        host_intro = await host_agent.run(
            f"Welcome chef! Today let's talk about {topic}. What are your thoughts?",
            deps=context
        )
        print(f"🎤 Host: {host_intro.output}")
        
        # Chef responds (system prompt will dynamically include memory and personality)
        chef_response = await chef_agent.run(
            host_intro.output,
            deps=context
        )
        print(f"👨‍🍳 {chef_name}: {chef_response.output}")
        
        # Update memory using direct diary.update_memory() call
        await diary.update_memory(
            user_id=chef_name,
            session_id=episode,
            user_msg=host_intro.output,
            assistant_msg=chef_response.output
        )
        
        # Continue conversation with follow-up
        host_followup = await host_agent.run(
            f"That's fascinating! Can you tell me more about your preferences regarding {topic}?",
            deps=context,
            message_history=host_intro.new_messages()
        )
        print(f"🎤 Host: {host_followup.output}")
        
        chef_detail = await chef_agent.run(
            host_followup.output,
            deps=context,
            message_history=chef_response.new_messages()
        )
        print(f"👨‍🍳 {chef_name}: {chef_detail.output}")
        
        # Update memory for the follow-up exchange
        await diary.update_memory(
            user_id=chef_name,
            session_id=episode,
            user_msg=host_followup.output,
            assistant_msg=chef_detail.output
        )


async def cooking_show_demo():
    """Run the AI-powered cooking show memory demo."""
    print("🍳 Welcome to the AI Cooking Show Memory System!")
    print("=" * 50)
    
    # Setup
    backend = LocalBackend(Path("memory_cooking_show"))
    
    # Create diary with build_extractor (proper approach)
    diary = Diary(
        backend=backend,
        pref_table_cls=CulinaryPrefTable,
        max_prefs_per_category=10,
        max_conversations=5
    )
    
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
        await chef_interview(chef_name, personality, episodes, diary)
        await asyncio.sleep(0.5)  # Brief pause between chefs
    
    print("\n📚 Chef Memory Profiles:")
    print("=" * 50)
    
    # Display the memories for each chef
    chefs = ["chef_gordon", "chef_julia", "chef_marco"]
    
    for chef_name in chefs:
        print(f"\n👨‍🍳 {chef_name.upper().replace('_', ' ')}")
        print("-" * 30)
        
        # Show preferences
        formatted_prefs = await diary.pretty_preferences(chef_name)
        if formatted_prefs != "No preferences found for user.":
            print("🍽️  Culinary Preferences:")
            for line in formatted_prefs.split('\n'):
                if line.strip():
                    print(f"  {line}")
        
        # Show conversation summaries
        formatted_convs = await diary.pretty_conversations(chef_name, limit=3)
        if formatted_convs != "No conversations found for user.":
            print(f"\n📺 Recent Sessions:")
            for line in formatted_convs.split('\n'):
                if line.strip():
                    print(f"  {line}")
    
    # Show raw TOML for one chef
    print(f"\n📄 Sample TOML (chef_gordon preferences):")
    print("-" * 50)
    gordon_prefs = await diary.preferences("chef_gordon")
    if gordon_prefs:
        # Show first 800 characters
        preview = gordon_prefs[:800] + "..." if len(gordon_prefs) > 800 else gordon_prefs
        print(preview)
    
    # Show conversation TOML
    print(f"\n📄 Sample TOML (chef_gordon conversations):")
    print("-" * 50)
    gordon_convs = await diary.last_conversations("chef_gordon", limit=2)
    if gordon_convs:
        import tomli_w
        convs_preview = tomli_w.dumps(gordon_convs)[:600] + "..." if len(tomli_w.dumps(gordon_convs)) > 600 else tomli_w.dumps(gordon_convs)
        print(convs_preview)
    
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