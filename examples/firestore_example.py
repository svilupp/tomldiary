"""
Example: Using TOMLDiary with Firestore Backend

This example demonstrates how to use TOMLDiary with Google Cloud Firestore
for cloud-based storage of user preferences and conversations.

Prerequisites:
    1. Install Firestore dependencies:
       uv add 'tomldiary[firestore]'

    2. Set up environment variables (required):
       export FIREBASE_ADMIN_PROJECT_ID="your-gcp-project-id"
       export FIREBASE_ADMIN_CREDS='{"type":"service_account",...}'

    3. Optional environment variables:
       export FIREBASE_WINDOW_SHOP_DB_NAME="your-database"  # defaults to "(default)"
       export FIRESTORE_BASE_PATH="app/memory"  # defaults to "tomldiary/demo"

Usage:
    uv run --extra firestore examples/firestore_example.py
"""

import asyncio
import os
import sys

from pydantic import BaseModel

try:
    from tomldiary import Diary, PreferenceItem
    from tomldiary.backends import FirestoreBackend
except ImportError as e:
    print("ERROR: Failed to import required dependencies")
    print(f"  {e}")
    print("\nPlease install with:")
    print("  uv add 'tomldiary[firestore]'")
    sys.exit(1)

# ============================================================================
# CONFIGURATION - Load from environment variables
# ============================================================================

# Required environment variables
FIREBASE_PROJECT_ID = os.getenv("FIREBASE_ADMIN_PROJECT_ID")
if not FIREBASE_PROJECT_ID:
    print("ERROR: FIREBASE_ADMIN_PROJECT_ID environment variable is required")
    print("Set it to your Google Cloud project ID")
    sys.exit(1)

# Optional environment variables with defaults
FIREBASE_DATABASE = os.getenv("FIREBASE_WINDOW_SHOP_DB_NAME", "(default)")
FIRESTORE_BASE_PATH = os.getenv("FIRESTORE_BASE_PATH", "tomldiary/demo")

# Validate base_path has even number of segments (Firestore requirement)
path_segments = [s for s in FIRESTORE_BASE_PATH.strip("/").split("/") if s]
if len(path_segments) % 2 != 0:
    print("ERROR: FIRESTORE_BASE_PATH must have EVEN number of segments")
    print(f"Current: '{FIRESTORE_BASE_PATH}' has {len(path_segments)} segments")
    print("Examples: 'app/memory', 'prod/users', 'v1/app/data/memory'")
    sys.exit(1)

# ============================================================================


# Define your preference schema
class UserPreferences(BaseModel):
    """
    likes       : Things the user enjoys
    dislikes    : Things the user avoids
    interests   : Topics of interest
    goals       : Personal objectives
    """

    likes: dict[str, PreferenceItem] = {}
    dislikes: dict[str, PreferenceItem] = {}
    interests: dict[str, PreferenceItem] = {}
    goals: dict[str, PreferenceItem] = {}


async def main():
    """Demonstrate Firestore backend usage."""

    # Initialize Firestore backend with configuration from environment
    backend = FirestoreBackend(
        project_id=FIREBASE_PROJECT_ID,
        base_path=FIRESTORE_BASE_PATH,
        database=FIREBASE_DATABASE,
    )

    # Create diary instance
    diary = Diary(
        backend=backend,
        pref_table_cls=UserPreferences,
        max_prefs_per_category=50,
        max_conversations=20,
    )

    # Example user and session IDs
    user_id = "demo-user-123"
    session_id = "session-2025-10-14"

    print("=" * 60)
    print("TOMLDiary with Firestore Backend - Demo")
    print("=" * 60)
    print()

    # Ensure session exists
    is_new = await diary.ensure_session(user_id, session_id)
    print(f"Session status: {'New session created' if is_new else 'Existing session'}")
    print()

    # Simulate a conversation
    print("Simulating conversation...")
    user_msg = "I really enjoy hiking in the mountains on weekends."
    assistant_msg = "That's wonderful! I'll remember that you enjoy hiking in the mountains."

    await diary.update_memory(user_id, session_id, user_msg, assistant_msg)
    print(f"  User: {user_msg}")
    print(f"  Assistant: {assistant_msg}")
    print()

    # Add another preference
    user_msg2 = "I'm learning Python programming and want to build AI applications."
    assistant_msg2 = "Great goal! I'll remember your interest in Python and AI development."

    await diary.update_memory(user_id, session_id, user_msg2, assistant_msg2)
    print(f"  User: {user_msg2}")
    print(f"  Assistant: {assistant_msg2}")
    print()

    # Retrieve and display preferences
    print("=" * 60)
    print("Stored Preferences:")
    print("=" * 60)
    prefs = await diary.pretty_preferences(user_id)
    print(prefs)
    print()

    # Retrieve and display conversations
    print("=" * 60)
    print("Conversation Summary:")
    print("=" * 60)
    convs = await diary.pretty_conversations(user_id, limit=5)
    print(convs)
    print()

    print("=" * 60)
    print("✓ Demo completed successfully!")
    print()
    print("Your data is now stored in Firestore at:")
    print(f"  {backend.base_path}/{user_id}/preferences.toml")
    print(f"  {backend.base_path}/{user_id}/conversations.toml")
    print()
    print("View it in Firebase Console:")
    print(
        f"  https://console.firebase.google.com/project/{backend.project_id}/firestore/databases/{backend.database}/data"
    )


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        print(f"\nError: {e}")
        print("\nMake sure you have:")
        print("  1. Installed Firestore dependencies: uv add 'tomldiary[firestore]'")
        print("  2. Set environment variables:")
        print("     export FIREBASE_ADMIN_PROJECT_ID='your-project-id'")
        print("     export FIREBASE_ADMIN_CREDS='{...service account json...}'")
        print("  3. (Optional) Set FIRESTORE_BASE_PATH and FIREBASE_WINDOW_SHOP_DB_NAME")
        sys.exit(1)
