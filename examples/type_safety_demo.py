#!/usr/bin/env python3
"""
Type Safety & Schema Utilities Demo

This comprehensive example demonstrates tomldiary's type safety features:
1. Schema Inspection - View and understand your preference table structure
2. Safe Loading - Validate TOML data with runtime type checking
3. CLI Tools - Command-line utilities for schema inspection
4. Production Patterns - FastAPI integration and error handling

Perfect for understanding how to:
- Design type-safe APIs with tomldiary
- Validate data at runtime
- Generate API documentation
- Integrate with production systems

Run with:
    uv run examples/type_safety_demo.py
"""

import asyncio
from pathlib import Path

from dotenv import load_dotenv
from pydantic import ValidationError

from tomldiary import Diary
from tomldiary.backends import LocalBackend
from tomldiary.loaders import (
    PreferenceLoader,
    load_conversations,
    load_preferences,
)
from tomldiary.schema import (
    get_preferences_schema,
    show_preferences_schema,
)

load_dotenv()

# Import example preference tables
import sys

sys.path.insert(0, str(Path(__file__).parent))

from culinary_prefs import CulinaryPrefTable  # noqa: E402


def section(title: str, number: int = None):
    """Print a section header."""
    print("\n" + "=" * 80)
    if number:
        print(f"{number}. {title.upper()}")
    else:
        print(title.upper())
    print("=" * 80 + "\n")


# ============================================================================
# PART 1: SCHEMA INSPECTION
# ============================================================================


def demo_schema_formats():
    """Show different schema output formats."""
    section("Schema Inspection - Output Formats", 1)

    print("📋 Pretty Format (Human-Readable Tree):\n")
    print(show_preferences_schema(CulinaryPrefTable))

    print("\n" + "-" * 80)
    print("\n📋 JSON Format (first 30 lines - for API docs):\n")
    json_output = show_preferences_schema(CulinaryPrefTable, format="json")
    lines = json_output.split("\n")
    print("\n".join(lines[:30]))
    print(f"... ({len(lines) - 30} more lines)")

    print("\n" + "-" * 80)
    print("\n📋 Python Format (Type Hints - first 20 lines):\n")
    python_output = show_preferences_schema(CulinaryPrefTable, format="python")
    lines = python_output.split("\n")
    print("\n".join(lines[:20]))
    print("...")

    print("\n💡 Use Case: Choose format based on your needs")
    print("   - pretty: Quick inspection, documentation")
    print("   - json: API docs, OpenAPI specs, client SDKs")
    print("   - python: Code reference, type checking")


def demo_programmatic_schema():
    """Show programmatic schema access."""
    section("Programmatic Schema Access", 2)

    schema_info = get_preferences_schema(CulinaryPrefTable)

    print("📊 Structured Schema Information:\n")
    print(f"Schema Name: {schema_info['schema_name']}")
    print(f"Total Categories: {len(schema_info['categories'])}")
    print(f"\nCategories: {', '.join(schema_info['categories'][:5])}...")

    print("\n📊 Category Types (first 3):\n")
    for i, (cat, type_str) in enumerate(schema_info["category_types"].items()):
        if i >= 3:
            print("  ...")
            break
        print(f"  - {cat}: {type_str}")

    print("\n💡 Use Case: FastAPI Integration")
    print("""
    from fastapi import FastAPI
    from tomldiary.schema import get_preferences_schema

    app = FastAPI()

    @app.get("/api/schema/preferences")
    def schema_endpoint():
        return get_preferences_schema(CulinaryPrefTable)["json_schema"]
    """)


def demo_cli_tools():
    """Show CLI usage."""
    section("CLI Tools for Schema Inspection", 3)

    print("🖥️  Command-Line Interface:\n")
    print("# View schema (pretty format)")
    print("$ tomldiary schema preferences examples/culinary_prefs.py:CulinaryPrefTable\n")

    print("# Generate JSON schema for API docs")
    print(
        "$ tomldiary schema preferences examples/culinary_prefs.py:CulinaryPrefTable -f json > api_schema.json\n"
    )  # noqa: E501

    print("# View Python type hints")
    print("$ tomldiary schema preferences examples/culinary_prefs.py:CulinaryPrefTable -f python\n")

    print("# Conversation schema (standardized, no class needed)")
    print("$ tomldiary schema conversations")
    print("$ tomldiary schema conversations -f json\n")

    print("💡 Try it now:")
    print("   Run the commands above to see schema inspection in action!")


# ============================================================================
# PART 2: SAFE DATA LOADING
# ============================================================================


def demo_basic_loading():
    """Demonstrate basic preference loading with validation."""
    section("Safe Data Loading - Basic Validation", 4)

    toml_data = """
[preferences.favorite_foods.pizza]
text = "loves Neapolitan pizza with fresh mozzarella"
contexts = ["food", "italian"]
_count = 5
_created = "2024-01-01T12:00:00Z"
_updated = "2024-01-15T18:30:00Z"

[preferences.cooking_techniques.knife_skills]
text = "excellent knife work and precision cutting"
contexts = ["technique", "professional"]
_count = 2
_created = "2024-01-03T10:00:00Z"
_updated = "2024-01-03T10:00:00Z"
"""

    print("📄 Input TOML Data:\n")
    print(toml_data)

    print("🔒 Loading with type validation...\n")

    # Load and validate
    prefs = load_preferences(toml_data, CulinaryPrefTable)

    print("✅ Validation passed!")
    print(f"   Type: {type(prefs).__name__}")
    print("   Categories populated:")
    print(f"     - favorite_foods: {len(prefs.favorite_foods)} items")
    print(f"     - cooking_techniques: {len(prefs.cooking_techniques)} items")

    print("\n📊 Type-Safe Access:\n")
    for food_id, pref_item in prefs.favorite_foods.items():
        print(f"  {food_id}:")
        print(f"    text: {pref_item.text}")
        print(f"    count: {pref_item.count}")
        print(f"    Type: {type(pref_item).__name__}")  # PreferenceItem


def demo_validation_errors():
    """Show validation error handling."""
    section("Validation Error Handling", 5)

    # Invalid TOML - missing required field
    invalid_toml = """
[preferences.favorite_foods.pizza]
contexts = ["food"]
_count = 1
# Missing required 'text' field!
_created = "2024-01-01T00:00:00Z"
_updated = "2024-01-01T00:00:00Z"
"""

    print("📄 Invalid TOML (missing required 'text' field):\n")
    print(invalid_toml)

    print("🔒 Attempting to load...\n")

    try:
        load_preferences(invalid_toml, CulinaryPrefTable)
        print("❌ Should have raised ValidationError!")
    except ValidationError as e:
        print("✅ Validation error caught (as expected):\n")
        print(f"   Error count: {e.error_count()}")
        for error in e.errors():
            print(f"   - Field: {'.'.join(str(x) for x in error['loc'])}")
            print(f"     Type: {error['type']}")
            print(f"     Message: {error['msg']}")

    print("\n💡 Production Benefit:")
    print("   Clear error messages help debug data issues quickly")
    print("   Prevents corrupted data from entering your system")


def demo_api_validation():
    """Demonstrate validating API payloads."""
    section("API Payload Validation (Production Pattern)", 6)

    print("💡 Use Case: Validating incoming API requests\n")

    # Simulate API payload
    api_payload = {
        "pizza_margherita": {
            "text": "classic Margherita pizza",
            "contexts": ["food", "italian"],
            "_count": 1,
            "_created": "2024-01-01T00:00:00Z",
            "_updated": "2024-01-01T00:00:00Z",
        },
        "carbonara": {
            "text": "traditional Roman carbonara",
            "contexts": ["food", "pasta"],
            "_count": 1,
            "_created": "2024-01-01T00:00:00Z",
            "_updated": "2024-01-01T00:00:00Z",
        },
    }

    print("📥 Incoming API Payload:")
    print("   Category: favorite_foods")
    print(f"   Items: {len(api_payload)}\n")

    loader = PreferenceLoader(CulinaryPrefTable)

    try:
        validated = loader.validate_partial("favorite_foods", api_payload)
        print("✅ API payload validated successfully!")
        print("   Type: dict[str, PreferenceItem]")
        print(f"   Validated items: {len(validated)}")

        for item_id, pref in validated.items():
            print(f"   - {item_id}: {pref.text}")

    except ValidationError as e:
        print(f"❌ Validation failed: {e}")

    print("\n💡 FastAPI Integration Pattern:")
    print("""
    from fastapi import FastAPI, HTTPException
    from pydantic import ValidationError
    from tomldiary.loaders import PreferenceLoader

    loader = PreferenceLoader(CulinaryPrefTable)

    @app.post("/users/{user_id}/preferences/{category}")
    async def add_preferences(user_id: str, category: str, items: dict):
        try:
            validated = loader.validate_partial(category, items)
            # Safe to store - data is validated
            await store_preferences(user_id, category, validated)
            return {"success": True, "count": len(validated)}

        except ValueError as e:
            raise HTTPException(400, f"Invalid category: {category}")

        except ValidationError as e:
            raise HTTPException(422, {
                "error": "Invalid data",
                "details": e.errors()
            })
    """)


async def demo_diary_integration():
    """Show integration with Diary."""
    section("Diary Integration - Complete Workflow", 7)

    print("💡 Complete workflow: Store → Load → Validate → Use\n")

    # Setup
    backend = LocalBackend(Path("memory_type_safety_demo"))
    diary = Diary(
        backend=backend,
        pref_table_cls=CulinaryPrefTable,
        max_prefs_per_category=10,
    )

    user_id = "chef_alice"
    session_id = "session_001"

    # Create data
    await diary.ensure_session(user_id, session_id)
    print("📝 Step 1: Creating sample data in diary...\n")

    prefs = await diary._load_prefs(user_id)
    prefs["preferences"]["favorite_foods"] = {
        "ramen": {
            "text": "tonkotsu ramen with chashu pork",
            "contexts": ["food", "japanese"],
            "_count": 4,
            "_created": "2024-01-01T00:00:00Z",
            "_updated": "2024-01-10T00:00:00Z",
        }
    }
    await diary._save_prefs(user_id, prefs)

    # Load with validation
    print("🔒 Step 2: Loading diary data with validation...\n")

    toml_str = await diary.preferences(user_id)
    loader = PreferenceLoader(CulinaryPrefTable)

    validated_prefs = loader.load_from_toml_str(toml_str)

    print("✅ Step 3: Data validated successfully!")
    print(f"   Schema type: {type(validated_prefs).__name__}")
    print("   Safe to use in production")

    print("\n📊 Step 4: Type-safe data access:\n")
    for food_id, pref in validated_prefs.favorite_foods.items():
        print(f"   {food_id}: {pref.text}")
        print(f"     Count: {pref.count}, Contexts: {pref.contexts}")

    print("\n💡 Why This Matters:")
    print("   ✓ Runtime type safety prevents errors")
    print("   ✓ Schema validation catches data corruption")
    print("   ✓ IDE autocomplete & type checking")
    print("   ✓ Production-ready error handling")


def demo_conversation_loading():
    """Show conversation validation."""
    section("Conversation Loading & Validation", 8)

    conv_toml = """
[conversations.dinner_planning]
_created = "2024-01-01T18:00:00Z"
_updated = "2024-01-01T19:30:00Z"
_turns = 12
summary = "Discussed dinner party menu planning for Italian-themed event"
keywords = ["dinner party", "italian", "menu planning"]

[conversations.recipe_help]
_created = "2024-01-02T14:00:00Z"
_updated = "2024-01-02T14:45:00Z"
_turns = 7
summary = "Helped troubleshoot carbonara recipe"
keywords = ["carbonara", "recipe", "troubleshooting"]
"""

    print("📄 Conversation TOML:\n")
    print(conv_toml)

    print("\n🔒 Loading with validation...\n")

    convs = load_conversations(conv_toml)

    print("✅ Validated successfully!")
    print("   Type: dict[str, ConversationItem]")
    print(f"   Sessions: {len(convs)}\n")

    for session_id, conv in convs.items():
        print(f"  {session_id}:")
        print(f"    Turns: {conv.turns}")
        print(f"    Summary: {conv.summary[:50]}...")


# ============================================================================
# MAIN DEMO FLOW
# ============================================================================


def main():
    """Run the complete type safety demo."""
    print("\n")
    print("╔" + "=" * 78 + "╗")
    print("║" + " " * 20 + "TYPE SAFETY & SCHEMA UTILITIES" + " " * 28 + "║")
    print("╚" + "=" * 78 + "╝")

    # Part 1: Schema Inspection
    demo_schema_formats()
    demo_programmatic_schema()
    demo_cli_tools()

    # Part 2: Safe Loading
    demo_basic_loading()
    demo_validation_errors()
    demo_api_validation()
    asyncio.run(demo_diary_integration())
    demo_conversation_loading()

    print("=" * 80)
    print("✅ Type Safety Demo Complete!")
    print("=" * 80)
    print()


if __name__ == "__main__":
    main()
