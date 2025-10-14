#!/usr/bin/env python3
"""
🍽️ Restaurant Booking Agent Demo
Simplified demo showing preference learning for restaurant bookings using tomldiary's built-in methods.
"""

import asyncio
import json
import os
from dataclasses import dataclass
from pathlib import Path

import logfire
from dotenv import load_dotenv
from pydantic import BaseModel, Field
from pydantic_ai import Agent, RunContext
from pydantic_ai.models.google import GoogleModel
from pydantic_ai.providers.google import GoogleProvider

from tomldiary import Diary, PreferenceItem
from tomldiary.backends import LocalBackend

load_dotenv()
logfire.configure(
    service_name="booking-agent",
    scrubbing=False,
    token=os.getenv("LOGFIRE_TOKEN"),
    environment="development",
    send_to_logfire="if-token-present",
)
logfire.instrument_pydantic_ai()


# Mock Restaurant Booking Data
MOCK_RESTAURANTS = [
    {
        "id": "rest_001",
        "name": "Bella Italia",
        "cuisine": "Italian",
        "description": "Authentic Italian restaurant with fresh pasta and wood-fired pizza",
        "price_range": "$$",
        "specialties": ["pasta", "pizza", "risotto"],
        "available_times": ["6:00 PM", "7:30 PM", "9:00 PM"],
        "table_types": ["2-person", "4-person", "6-person"],
        "features": ["romantic", "date-friendly", "wine selection"],
    },
    {
        "id": "rest_002",
        "name": "Tokyo Sushi Bar",
        "cuisine": "Japanese",
        "description": "Fresh sushi and sashimi with traditional Japanese atmosphere",
        "price_range": "$$$",
        "specialties": ["sushi", "sashimi", "ramen"],
        "available_times": ["5:30 PM", "7:00 PM", "8:30 PM"],
        "table_types": ["2-person", "4-person", "sushi bar"],
        "features": ["fresh fish", "authentic", "chef's choice"],
    },
    {
        "id": "rest_003",
        "name": "Green Garden Cafe",
        "cuisine": "Vegetarian",
        "description": "Plant-based cafe with organic, locally-sourced ingredients",
        "price_range": "$",
        "specialties": ["salads", "smoothie bowls", "vegan burgers"],
        "available_times": ["12:00 PM", "1:30 PM", "6:00 PM"],
        "table_types": ["2-person", "4-person"],
        "features": ["vegan", "organic", "healthy", "casual"],
    },
    {
        "id": "rest_004",
        "name": "Spice Route",
        "cuisine": "Indian",
        "description": "Aromatic Indian curries and tandoor specialties",
        "price_range": "$$",
        "specialties": ["curry", "tandoor", "naan"],
        "available_times": ["6:30 PM", "8:00 PM", "9:30 PM"],
        "table_types": ["2-person", "4-person", "6-person", "large groups"],
        "features": ["spicy", "family-friendly", "authentic"],
    },
    {
        "id": "rest_005",
        "name": "The Steakhouse",
        "cuisine": "American",
        "description": "Premium steaks and classic American dishes",
        "price_range": "$$$",
        "specialties": ["steaks", "burgers", "ribs"],
        "available_times": ["7:00 PM", "8:30 PM"],
        "table_types": ["2-person", "4-person", "private booth"],
        "features": ["upscale", "business dining", "wine cellar"],
    },
    {
        "id": "rest_006",
        "name": "Mediterranean Breeze",
        "cuisine": "Mediterranean",
        "description": "Fresh Mediterranean flavors with grilled seafood and mezze",
        "price_range": "$$",
        "specialties": ["grilled fish", "hummus", "falafel"],
        "available_times": ["6:00 PM", "7:30 PM", "9:00 PM"],
        "table_types": ["2-person", "4-person", "outdoor patio"],
        "features": ["healthy", "seafood", "outdoor dining"],
    },
]

# Mock booking storage
MOCK_BOOKINGS = []


def search_restaurants(ctx: RunContext, query: str = "", cuisine: str = "") -> str:  # noqa: ARG001
    """Search function that returns available restaurants for booking."""
    _ = (ctx, query, cuisine)
    return "Here are the available restaurants for booking: " + json.dumps(
        MOCK_RESTAURANTS, indent=2
    )


def book_restaurant(
    ctx: RunContext,
    restaurant_id: str,
    date: str,
    time: str,
    party_size: int,
    special_requests: str = "",
) -> str:  # noqa: ARG001
    """Book a table at a restaurant."""
    _ = ctx
    # Find the restaurant
    restaurant = None
    for rest in MOCK_RESTAURANTS:
        if rest["id"] == restaurant_id:
            restaurant = rest
            break

    if not restaurant:
        return f"❌ Restaurant with ID {restaurant_id} not found."

    # Check if time is available
    if time not in restaurant["available_times"]:
        return f"❌ {time} is not available at {restaurant['name']}. Available times: {', '.join(restaurant['available_times'])}"

    # Create booking
    booking_id = f"booking_{len(MOCK_BOOKINGS) + 1}"
    booking = {
        "booking_id": booking_id,
        "restaurant_name": restaurant["name"],
        "restaurant_id": restaurant_id,
        "date": date,
        "time": time,
        "party_size": party_size,
        "special_requests": special_requests,
        "status": "confirmed",
    }

    MOCK_BOOKINGS.append(booking)

    return f"✅ Booking confirmed! Reservation #{booking_id} at {restaurant['name']} for {party_size} people on {date} at {time}. {f'Special requests: {special_requests}' if special_requests else ''}"


def check_availability(ctx: RunContext, restaurant_id: str, date: str) -> str:  # noqa: ARG001
    """Check availability for a specific restaurant on a date."""
    _ = ctx
    restaurant = None
    for rest in MOCK_RESTAURANTS:
        if rest["id"] == restaurant_id:
            restaurant = rest
            break

    if not restaurant:
        return f"❌ Restaurant with ID {restaurant_id} not found."

    return f"📅 {restaurant['name']} availability for {date}:\n" + json.dumps(
        {
            "available_times": restaurant["available_times"],
            "table_types": restaurant["table_types"],
            "features": restaurant["features"],
        },
        indent=2,
    )


class UserDiningPreferences(BaseModel):
    """
    Dining and restaurant booking preferences table focused on learning user preferences
    valuable for restaurant recommendations and booking assistance.
    We capture dining preferences, restrictions, occasions, and booking patterns
    to enhance restaurant recommendations and booking experiences.

    Extract dining preferences from conversations:
    - likes: Cuisines, restaurants, dining styles, atmospheres, occasions
    - dislikes: Foods, restaurant types, atmospheres, service styles to avoid
    - dietary_restrictions: Allergies, dietary choices (vegan, keto, etc.), health needs
    - booking_patterns: Preferred times, party sizes, special occasions, seating preferences
    - about_the_user: Lifestyle factors relevant for dining and booking choices

    Be specific with context like preference: "Italian restaurants" context: "for romantic dates".
    Extract implicit preferences - business person = quiet restaurants, family = kid-friendly places.
    """

    likes: dict[str, PreferenceItem] = Field(
        default_factory=dict,
        description="Cuisines, restaurants, dining styles, and atmospheres the user enjoys. "
        "Context-specific preferences (date nights, business meals, family dining, celebrations). "
        "Examples: 'loves Italian restaurants for dates', 'enjoys sushi bars for lunch meetings', "
        "'prefers cozy cafes for casual dining', 'likes outdoor patios in summer'",
    )
    dislikes: dict[str, PreferenceItem] = Field(
        default_factory=dict,
        description="Foods, restaurant types, atmospheres, and service styles the user avoids. "
        "Context-specific dislikes and dining aversions. "
        "Examples: 'hates noisy restaurants', 'avoids chain restaurants', 'dislikes formal dining', "
        "'uncomfortable with sushi bars', 'never books weekend brunch'",
    )
    dietary_restrictions: dict[str, PreferenceItem] = Field(
        default_factory=dict,
        description="Allergies, dietary choices, and health-related food restrictions. "
        "Examples: 'allergic to shellfish', 'follows vegan diet', 'gluten intolerant', "
        "'keto lifestyle', 'lactose sensitive', 'avoiding alcohol'",
    )
    booking_patterns: dict[str, PreferenceItem] = Field(
        default_factory=dict,
        description="Preferred booking times, party sizes, occasions, and seating preferences. "
        "Examples: 'prefers 7:30 PM reservations', 'usually books for 2 people', "
        "'likes window seats', 'books private booths for business', 'prefers early dinner with kids'",
    )
    about_the_user: dict[str, PreferenceItem] = Field(
        default_factory=dict,
        description="Lifestyle factors and personal details relevant to dining choices. "
        "Examples: 'busy executive - needs quick service', 'celebrates anniversaries monthly', "
        "'has young children - needs kid-friendly places', 'entertaining clients often', "
        "'lives downtown - prefers walking distance', 'works late - needs late reservations'",
    )


@dataclass
class BookingContext:
    user_id: str
    session_id: str
    diary: Diary


# Create the booking agent
booking_agent = Agent(
    GoogleModel(
        "gemini-2.5-flash",
        provider=GoogleProvider(api_key=os.getenv("GEMINI_API_KEY")),
    ),
    deps_type=BookingContext,
    tools=[search_restaurants, book_restaurant, check_availability],
    system_prompt="""You are BookingBot, a restaurant reservation specialist and dining concierge.
    You help users find and book restaurants that perfectly match their preferences, occasions, and needs.

    ### Your Role
    - Restaurant Booking Expert: Handle reservations, check availability, and manage special requests
    - Dining Concierge: Provide personalized restaurant recommendations based on learned preferences
    - Communication Style: Professional yet friendly, like a knowledgeable concierge

    You focus on:
    - Understanding user's dining preferences, dietary restrictions, and occasion needs
    - Learning their booking patterns (preferred times, party sizes, seating preferences)
    - Discovering their favorite cuisines, restaurant types, and atmospheres
    - Understanding what restaurants/foods they dislike or need to avoid
    - Gathering context about special occasions, business needs, and lifestyle factors
    - Making actual restaurant bookings when requested

    Always ask for specific details needed for bookings: date, time, party size, and any special requests.
    Be enthusiastic about helping them find the perfect dining experience!""",
)


@booking_agent.system_prompt
async def add_booking_memory(ctx: RunContext[BookingContext]) -> str:
    """Add the user's existing dining and booking memory context to the system prompt."""
    memory_parts = []

    # Get formatted preferences using new pretty method
    formatted_prefs = await ctx.deps.diary.pretty_preferences(ctx.deps.user_id)
    if formatted_prefs != "No preferences found for user.":
        memory_parts.append("Your knowledge about this user's dining preferences:")
        memory_parts.append(formatted_prefs)

    # Get formatted conversations using new pretty method
    formatted_convs = await ctx.deps.diary.pretty_conversations(ctx.deps.user_id, limit=3)
    if formatted_convs != "No conversations found for user.":
        memory_parts.append("Recent conversation highlights:")
        memory_parts.append(formatted_convs)

    return "\n\n".join(memory_parts) if memory_parts else ""


async def booking_conversation(
    user_id: str, session_id: str, message: str, diary: Diary, history=None
):
    """Run a booking conversation with memory context."""
    print(f"\n🍽️ Booking Session: {session_id}")
    print("-" * 40)

    # Create context
    context = BookingContext(user_id=user_id, session_id=session_id, diary=diary)

    # Run the conversation with memory-aware system prompt
    result = await booking_agent.run(message, deps=context, message_history=history or [])

    print(f"👤 User: {message}")
    print(f"🤖 Booking AI: {result.output}")

    # Update memory after every conversation
    await diary.update_memory(
        user_id=user_id, session_id=session_id, user_msg=message, assistant_msg=result.output
    )

    return result


async def booking_demo():
    """Run the simplified restaurant booking memory demo."""
    print("🍽️ Restaurant Booking Agent Demo")
    print("=" * 50)

    # Setup
    backend = LocalBackend(Path("./memories"))
    diary = Diary(
        backend=backend,
        pref_table_cls=UserDiningPreferences,
        max_prefs_per_category=20,
        max_conversations=10,
    )

    user_id = "demo_user"

    # Booking conversations that reveal dining preferences and booking patterns
    conversations = [
        (
            "anniversary_dinner",
            [
                "Hi! I need to book a romantic dinner for my anniversary next Friday. We love Italian food and prefer cozy, intimate places. Can you help me find something special?",
                "Perfect! Can you book us a table for 2 at Bella Italia for Friday at 7:30 PM? We'd love a quiet table if possible.",
            ],
        ),
        (
            "business_lunch",
            [
                "I need to book lunch for a business meeting next Tuesday. Somewhere quiet where we can talk, good for 4 people. I'm vegetarian but my clients eat everything.",
                "Actually, let me check availability at a few places first. What are the options for Tuesday around 12:30 PM?",
            ],
        ),
        (
            "dietary_restrictions",
            [
                "I'm looking for dinner reservations but I'm vegan and my friend is gluten-free. We need somewhere that can accommodate both dietary restrictions.",
                "Green Garden Cafe sounds perfect! Can you book us a table for 2 this Saturday at 6:00 PM?",
            ],
        ),
        (
            "family_celebration",
            [
                "We're celebrating my mom's birthday with the whole family - about 8 people including 2 kids. We need somewhere family-friendly but still nice. She loves Mediterranean food.",
                "That sounds great! Can you book Mediterranean Breeze for Sunday at 6:00 PM for 8 people? Please mention it's for a birthday celebration.",
            ],
        ),
    ]

    print("\n📅 Starting booking conversations...\n")

    # Run conversations
    for session_id, messages in conversations:
        result = None
        for message in messages:
            result = await booking_conversation(
                user_id=user_id,
                session_id=session_id,
                message=message,
                diary=diary,
                history=result.all_messages() if result else None,
            )
        await asyncio.sleep(0.5)  # Brief pause between sessions

    print("\n📚 Dining Memory Profile:")
    print("=" * 50)

    # Show preferences using new pretty method
    formatted_prefs = await diary.pretty_preferences(user_id)
    if formatted_prefs != "No preferences found for user.":
        print("🍽️ Dining Preferences:")
        for line in formatted_prefs.split("\n"):
            if line.strip():
                print(f"  {line}")

    # Show conversation summaries using new pretty method
    formatted_convs = await diary.pretty_conversations(user_id, limit=5)
    if formatted_convs != "No conversations found for user.":
        print("\n💬 Recent Booking Sessions:")
        for line in formatted_convs.split("\n"):
            if line.strip():
                print(f"  {line}")

    # Show successful bookings
    if MOCK_BOOKINGS:
        print("\n📋 Confirmed Reservations:")
        for booking in MOCK_BOOKINGS:
            print(
                f"  ✅ {booking['restaurant_name']} - {booking['date']} at {booking['time']} for {booking['party_size']} people"
            )

    print("\n✨ Dining memories and bookings saved successfully!")
    print("📁 Check the './memories' directory for TOML files")


if __name__ == "__main__":
    # Note: Requires GEMINI_API_KEY environment variable
    if not os.getenv("GEMINI_API_KEY"):
        print("⚠️  Please set GEMINI_API_KEY environment variable")
        print("   Example: export GEMINI_API_KEY='your-key-here'")
    else:
        asyncio.run(booking_demo())
