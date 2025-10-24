#!/usr/bin/env python3
# /// script
# requires-python = ">=3.13"
# dependencies = [
#     "python-dotenv",
#     "tomldiary[firestore]",
# ]
# ///
"""
Test script for Firestore backend

Tests CRUD operations with live Firestore to validate the connection and backend functionality.

Usage:
    uv run scripts/firestore_test_connection.py

Required Environment Variables:
    FIREBASE_ADMIN_PROJECT_ID: Google Cloud project ID
    FIREBASE_ADMIN_CREDS: JSON string with Firebase service account credentials

Optional Environment Variables:
    FIREBASE_WINDOW_SHOP_DB_NAME: Firestore database name (defaults to "(default)")
    FIRESTORE_BASE_PATH: Base path for Firestore documents (defaults to "experiments/memory")
"""

import asyncio
import json
import os
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Load environment variables
from dotenv import load_dotenv

load_dotenv()

# Import Firestore backend implementation directly
from google.api_core import exceptions as gcp_exceptions
from google.cloud import firestore
from google.oauth2 import service_account

# Import tomldiary components
from pydantic import BaseModel

from tomldiary.loaders import ConversationLoader, PreferenceLoader
from tomldiary.logging import get_logger
from tomldiary.models import PreferenceItem

logger = get_logger(__name__)


# Define test preference table
class TestPrefTable(BaseModel):
    """Test preference table for cooking preferences.

    favorite_foods : Dishes and ingredients the user enjoys
    dietary_restrictions : Foods the user avoids or cannot eat
    """

    favorite_foods: dict[str, PreferenceItem] = {}
    dietary_restrictions: dict[str, PreferenceItem] = {}


# Track latencies
latencies = {
    "write": [],
    "read": [],
    "exists": [],
    "delete": [],
    "list_users": [],
}


class FirestoreBackend:
    """Firestore backend for testing - copied from tomldiary.backends.firestore"""

    def __init__(
        self,
        project_id: str,
        base_path: str = "users",
        credentials_path: str | None = None,
        credentials_dict: dict | None = None,
        database: str = "(default)",
    ):
        self.project_id = project_id
        self.database = database
        self.base_path = base_path.strip("/")

        # Validate base_path has even number of segments
        path_segments = [s for s in self.base_path.split("/") if s]
        if len(path_segments) % 2 != 0:
            raise ValueError(
                f"Invalid base_path '{base_path}': must have EVEN number of segments.\n"
                f"Current: {len(path_segments)} segments: {path_segments}\n"
                f"Firestore paths alternate: collection/document/collection/document/..."
            )

        # Initialize Firestore client
        if credentials_dict:
            credentials = service_account.Credentials.from_service_account_info(credentials_dict)
            self.db = firestore.Client(
                project=project_id, database=database, credentials=credentials
            )
        elif credentials_path:
            credentials = service_account.Credentials.from_service_account_file(credentials_path)
            self.db = firestore.Client(
                project=project_id, database=database, credentials=credentials
            )
        else:
            self.db = firestore.Client(project=project_id, database=database)

        logger.info(
            f"FirestoreBackend initialized: project={project_id}, database={database}, "
            f"base_path={self.base_path} ({len(path_segments)} segments)"
        )

    def _get_document_ref(self, user_id: str, kind: str):
        """Get Firestore document reference"""
        path_segments = [s for s in self.base_path.split("/") if s]
        ref = self.db.collection(path_segments[0])

        for i in range(1, len(path_segments)):
            ref = ref.document(path_segments[i]) if i % 2 == 1 else ref.collection(path_segments[i])

        file_name = f"{kind}.toml"
        return ref.collection(user_id).document(file_name)

    async def load(self, user_id: str, kind: str) -> str | None:
        """Load TOML content from Firestore"""
        try:
            doc_ref = self._get_document_ref(user_id, kind)
            loop = asyncio.get_event_loop()
            doc = await loop.run_in_executor(None, doc_ref.get)

            if doc.exists:
                data = doc.to_dict()
                content = data.get("content")
                if content:
                    logger.debug(f"Read {kind} for user {user_id}: {len(content)} chars")
                    return content
                else:
                    logger.warning(f"Document exists but has no content: {user_id}/{kind}")
                    return None
            else:
                logger.debug(f"No {kind} found for user {user_id}")
                return None

        except gcp_exceptions.NotFound:
            logger.debug(f"Document not found: {user_id}/{kind}")
            return None
        except Exception as e:
            logger.error(f"Failed to read {kind} for {user_id}: {e}")
            raise

    async def save(self, user_id: str, kind: str, content: str) -> None:
        """Save TOML content to Firestore"""
        try:
            doc_ref = self._get_document_ref(user_id, kind)
            data = {
                "content": content,
                "updated_at": datetime.now(UTC).isoformat(),
                "version": "0.3",
            }

            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, doc_ref.set, data)
            logger.debug(f"Wrote {kind} for user {user_id}: {len(content)} chars")

        except Exception as e:
            logger.error(f"Failed to write {kind} for {user_id}: {e}")
            raise

    async def exists(self, user_id: str, kind: str) -> bool:
        """Check if document exists"""
        try:
            doc_ref = self._get_document_ref(user_id, kind)
            loop = asyncio.get_event_loop()
            doc = await loop.run_in_executor(None, doc_ref.get)
            return doc.exists
        except Exception as e:
            logger.error(f"Failed to check existence for {user_id}/{kind}: {e}")
            return False

    async def list_users(self) -> list[str]:
        """List all user IDs"""
        try:
            path_segments = [s for s in self.base_path.split("/") if s]
            ref = self.db.collection(path_segments[0])
            for i in range(1, len(path_segments)):
                ref = (
                    ref.document(path_segments[i])
                    if i % 2 == 1
                    else ref.collection(path_segments[i])
                )

            loop = asyncio.get_event_loop()
            collections = await loop.run_in_executor(None, ref.collections)
            user_ids = [col.id for col in collections]
            logger.debug(f"Listed {len(user_ids)} users")
            return user_ids

        except Exception as e:
            logger.error(f"Failed to list users: {e}")
            raise

    async def delete(self, user_id: str, kind: str) -> None:
        """Delete a document"""
        try:
            doc_ref = self._get_document_ref(user_id, kind)
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, doc_ref.delete)
            logger.debug(f"Deleted {kind} for user {user_id}")
        except Exception as e:
            logger.error(f"Failed to delete {kind} for {user_id}: {e}")
            raise

    async def delete_user(self, user_id: str) -> None:
        """Delete all data for a user"""
        try:
            path_segments = [s for s in self.base_path.split("/") if s]
            ref = self.db.collection(path_segments[0])
            for i in range(1, len(path_segments)):
                ref = (
                    ref.document(path_segments[i])
                    if i % 2 == 1
                    else ref.collection(path_segments[i])
                )

            user_collection = ref.collection(user_id)
            loop = asyncio.get_event_loop()
            docs = await loop.run_in_executor(None, user_collection.stream)

            for doc in docs:
                await loop.run_in_executor(None, doc.reference.delete)
                logger.debug(f"Deleted {user_id}/{doc.id}")

            logger.info(f"Deleted all data for user {user_id}")

        except Exception as e:
            logger.error(f"Failed to delete user {user_id}: {e}")
            raise


def setup_firebase_credentials():
    """Setup Firebase credentials from environment variables and return as dict"""
    creds_json = os.getenv("FIREBASE_ADMIN_CREDS")
    if not creds_json:
        raise ValueError(
            "FIREBASE_ADMIN_CREDS not found in environment.\n"
            "Please set it to your Firebase service account JSON string."
        )

    # Parse credentials JSON
    try:
        creds_dict = json.loads(creds_json)
        print(f"  ✓ Parsed credentials for project: {creds_dict.get('project_id', 'unknown')}")
        print(f"  ✓ Service account: {creds_dict.get('client_email', 'unknown')}")
        return creds_dict
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid FIREBASE_ADMIN_CREDS JSON: {e}") from e


async def test_write_and_read(backend):
    """Test writing and reading TOML content"""
    print("Test 1: Write and Read")

    test_content = """[_meta]
version = "0.3"

[preferences.favorite_foods.pasta_carbonara]
text = "creamy pasta carbonara with crispy bacon"
contexts = ["italian", "pasta", "comfort food"]
_count = 3
"""

    start = time.perf_counter()
    await backend.save("test-user-1", "preferences", test_content)
    write_latency = (time.perf_counter() - start) * 1000
    latencies["write"].append(write_latency)
    print(f"  ✓ Wrote preferences ({write_latency:.2f}ms)")

    start = time.perf_counter()
    content = await backend.load("test-user-1", "preferences")
    read_latency = (time.perf_counter() - start) * 1000
    latencies["read"].append(read_latency)
    assert content == test_content, "Content mismatch!"
    print(f"  ✓ Read preferences matches ({read_latency:.2f}ms)")

    print("✅ Write and Read test passed\n")


async def test_nonexistent_user(backend):
    """Test reading from non-existent user"""
    print("Test 2: Non-existent User")

    start = time.perf_counter()
    content = await backend.load("nonexistent-user-xyz", "preferences")
    read_latency = (time.perf_counter() - start) * 1000
    latencies["read"].append(read_latency)
    assert content is None, "Should return None for non-existent user"
    print(f"  ✓ Returns None for non-existent user ({read_latency:.2f}ms)")

    print("✅ Non-existent user test passed\n")


async def test_exists(backend):
    """Test exists() method"""
    print("Test 3: Exists Check")

    start = time.perf_counter()
    await backend.save("test-user-2", "preferences", "test=data")
    write_latency = (time.perf_counter() - start) * 1000
    latencies["write"].append(write_latency)

    start = time.perf_counter()
    exists = await backend.exists("test-user-2", "preferences")
    exists_latency = (time.perf_counter() - start) * 1000
    latencies["exists"].append(exists_latency)
    assert exists is True, "Should exist after write"
    print(f"  ✓ Exists returns True after write ({exists_latency:.2f}ms)")

    start = time.perf_counter()
    exists = await backend.exists("nonexistent-user-xyz", "preferences")
    exists_latency = (time.perf_counter() - start) * 1000
    latencies["exists"].append(exists_latency)
    assert exists is False, "Should not exist"
    print(f"  ✓ Exists returns False for non-existent ({exists_latency:.2f}ms)")

    print("✅ Exists test passed\n")


async def test_list_users(backend):
    """Test list_users() method"""
    print("Test 4: List Users")

    start = time.perf_counter()
    await backend.save("test-user-3", "preferences", "user3=data")
    write_latency = (time.perf_counter() - start) * 1000
    latencies["write"].append(write_latency)

    start = time.perf_counter()
    await backend.save("test-user-4", "preferences", "user4=data")
    write_latency = (time.perf_counter() - start) * 1000
    latencies["write"].append(write_latency)

    start = time.perf_counter()
    users = await backend.list_users()
    list_latency = (time.perf_counter() - start) * 1000
    latencies["list_users"].append(list_latency)
    print(f"  Found {len(users)} users ({list_latency:.2f}ms)")

    assert "test-user-3" in users, "test-user-3 not found"
    assert "test-user-4" in users, "test-user-4 not found"
    print("  ✓ Test users found in list")

    print("✅ List users test passed\n")


async def test_delete(backend):
    """Test delete() method"""
    print("Test 5: Delete")

    start = time.perf_counter()
    await backend.save("test-user-5", "preferences", "test=data")
    write_latency = (time.perf_counter() - start) * 1000
    latencies["write"].append(write_latency)

    start = time.perf_counter()
    exists = await backend.exists("test-user-5", "preferences")
    exists_latency = (time.perf_counter() - start) * 1000
    latencies["exists"].append(exists_latency)
    assert exists is True
    print(f"  ✓ Data exists before delete ({exists_latency:.2f}ms)")

    start = time.perf_counter()
    await backend.delete("test-user-5", "preferences")
    delete_latency = (time.perf_counter() - start) * 1000
    latencies["delete"].append(delete_latency)

    start = time.perf_counter()
    exists = await backend.exists("test-user-5", "preferences")
    exists_latency = (time.perf_counter() - start) * 1000
    latencies["exists"].append(exists_latency)
    assert exists is False, "Should not exist after delete"
    print(f"  ✓ Data deleted successfully ({delete_latency:.2f}ms)")

    print("✅ Delete test passed\n")


async def test_multiple_file_types(backend):
    """Test storing both preferences and conversations"""
    print("Test 6: Multiple File Types")

    prefs_content = "[preferences]\ntest = 'prefs'"
    start = time.perf_counter()
    await backend.save("test-user-6", "preferences", prefs_content)
    write_latency = (time.perf_counter() - start) * 1000
    latencies["write"].append(write_latency)
    print(f"  ✓ Wrote preferences.toml ({write_latency:.2f}ms)")

    convs_content = "[conversations]\ntest = 'convs'"
    start = time.perf_counter()
    await backend.save("test-user-6", "conversations", convs_content)
    write_latency = (time.perf_counter() - start) * 1000
    latencies["write"].append(write_latency)
    print(f"  ✓ Wrote conversations.toml ({write_latency:.2f}ms)")

    start = time.perf_counter()
    prefs = await backend.load("test-user-6", "preferences")
    read_latency = (time.perf_counter() - start) * 1000
    latencies["read"].append(read_latency)

    start = time.perf_counter()
    convs = await backend.load("test-user-6", "conversations")
    read_latency2 = (time.perf_counter() - start) * 1000
    latencies["read"].append(read_latency2)

    assert prefs == prefs_content, "Preferences mismatch"
    assert convs == convs_content, "Conversations mismatch"

    print(
        f"  ✓ Both file types stored and read independently ({read_latency:.2f}ms, {read_latency2:.2f}ms)"
    )
    print("✅ Multiple file types test passed\n")


async def test_update_existing(backend):
    """Test updating existing content"""
    print("Test 7: Update Existing")

    initial = "version = 1"
    start = time.perf_counter()
    await backend.save("test-user-7", "preferences", initial)
    write_latency = (time.perf_counter() - start) * 1000
    latencies["write"].append(write_latency)
    print(f"  ✓ Initial write ({write_latency:.2f}ms)")

    updated = "version = 2"
    start = time.perf_counter()
    await backend.save("test-user-7", "preferences", updated)
    update_latency = (time.perf_counter() - start) * 1000
    latencies["write"].append(update_latency)
    print(f"  ✓ Update write ({update_latency:.2f}ms)")

    start = time.perf_counter()
    content = await backend.load("test-user-7", "preferences")
    read_latency = (time.perf_counter() - start) * 1000
    latencies["read"].append(read_latency)
    assert content == updated, "Should have updated content"
    print(f"  ✓ Content updated successfully ({read_latency:.2f}ms)")

    print("✅ Update test passed\n")


async def create_persistent_test_user(backend):
    """Create a persistent test user that won't be cleaned up"""
    print("Test 8: Creating Persistent Test User (with validation)")

    user_id = "firebase-test-user-123456"

    # Correct TOML structure: [preferences.{category}.{id}]
    preferences_content = """[_meta]
version = "0.3"

[preferences.favorite_foods.pref001]
text = "homemade pasta with fresh tomato sauce"
contexts = ["italian", "comfort food", "dinner"]
_count = 5
_created = "2025-10-13T17:00:00Z"
_updated = "2025-10-13T18:00:00Z"
_created_by = "test-session-001"
_updated_by = "test-session-003"

[preferences.favorite_foods.pref002]
text = "grilled salmon with lemon and herbs"
contexts = ["seafood", "healthy", "protein"]
_count = 3
_created = "2025-10-13T17:15:00Z"
_updated = "2025-10-13T17:45:00Z"
_created_by = "test-session-002"
_updated_by = "test-session-002"

[preferences.dietary_restrictions.pref001]
text = "no dairy products - lactose intolerant"
contexts = ["dairy", "allergy", "health"]
_count = 2
_created = "2025-10-13T17:30:00Z"
_updated = "2025-10-13T17:30:00Z"
_created_by = "test-session-002"
_updated_by = "test-session-002"
"""

    # Correct TOML structure: [conversations.{session_id}] (not array of tables)
    conversations_content = """[_meta]
version = "0.3"

[conversations.session_001]
_created = "2025-10-13T17:45:00Z"
_updated = "2025-10-13T17:50:00Z"
_turns = 4
summary = "User discussed Italian cooking preferences, loves homemade pasta and fresh ingredients"
keywords = ["pasta", "italian", "tomato sauce", "cooking", "homemade", "fresh"]

[conversations.session_002]
_created = "2025-10-13T18:00:00Z"
_updated = "2025-10-13T18:05:00Z"
_turns = 3
summary = "User mentioned lactose intolerance and preference for grilled salmon dishes"
keywords = ["salmon", "grilled", "seafood", "lactose", "dairy-free", "healthy"]
"""

    # Write preferences
    start = time.perf_counter()
    await backend.save(user_id, "preferences", preferences_content)
    write_latency = (time.perf_counter() - start) * 1000
    latencies["write"].append(write_latency)
    print(f"  ✓ Wrote preferences.toml ({write_latency:.2f}ms)")

    # Write conversations
    start = time.perf_counter()
    await backend.save(user_id, "conversations", conversations_content)
    write_latency = (time.perf_counter() - start) * 1000
    latencies["write"].append(write_latency)
    print(f"  ✓ Wrote conversations.toml ({write_latency:.2f}ms)")

    # Read back and validate preferences
    start = time.perf_counter()
    prefs = await backend.load(user_id, "preferences")
    read_latency = (time.perf_counter() - start) * 1000
    latencies["read"].append(read_latency)
    assert prefs == preferences_content, "Preferences mismatch"

    # Validate preferences structure using loader
    try:
        pref_loader = PreferenceLoader(TestPrefTable)
        validated_prefs = pref_loader.load_from_toml_str(prefs)
        print(f"  ✓ Preferences validated successfully ({read_latency:.2f}ms)")
        print(f"    - {len(validated_prefs.favorite_foods)} items in 'favorite_foods' category")
        print(
            f"    - {len(validated_prefs.dietary_restrictions)} items in 'dietary_restrictions' category"
        )
    except Exception as e:
        print(f"  ❌ Preference validation failed: {e}")
        raise

    # Read back and validate conversations
    start = time.perf_counter()
    convs = await backend.load(user_id, "conversations")
    read_latency2 = (time.perf_counter() - start) * 1000
    latencies["read"].append(read_latency2)
    assert convs == conversations_content, "Conversations mismatch"

    # Validate conversations structure using loader
    try:
        conv_loader = ConversationLoader()
        validated_convs = conv_loader.load_from_toml_str(convs)
        print(f"  ✓ Conversations validated successfully ({read_latency2:.2f}ms)")
        print(f"    - {len(validated_convs)} conversation sessions")
        for session_id, conv in validated_convs.items():
            print(f"    - {session_id}: {conv.turns} turns, {len(conv.keywords)} keywords")
    except Exception as e:
        print(f"  ❌ Conversation validation failed: {e}")
        raise

    print(f"  ℹ️  User '{user_id}' will remain in Firestore")
    print("✅ Persistent test user created with validated data\n")


def print_latency_statistics():
    """Print latency statistics for all operations"""
    print("=" * 60)
    print("LATENCY STATISTICS")
    print("=" * 60)
    print()

    for operation, times in latencies.items():
        if not times:
            continue

        count = len(times)
        min_time = min(times)
        max_time = max(times)
        avg_time = sum(times) / count
        median_time = sorted(times)[count // 2]

        sorted_times = sorted(times)
        p95_idx = int(count * 0.95)
        p99_idx = int(count * 0.99)
        p95_time = sorted_times[p95_idx] if p95_idx < count else max_time
        p99_time = sorted_times[p99_idx] if p99_idx < count else max_time

        print(f"{operation.upper():12} (n={count:2})")
        print(f"  Min:    {min_time:7.2f}ms")
        print(f"  Max:    {max_time:7.2f}ms")
        print(f"  Avg:    {avg_time:7.2f}ms")
        print(f"  Median: {median_time:7.2f}ms")
        print(f"  P95:    {p95_time:7.2f}ms")
        print(f"  P99:    {p99_time:7.2f}ms")
        print()


async def cleanup_test_data(backend):
    """Clean up test data"""
    print("Cleanup: Removing test users")

    test_users = [f"test-user-{i}" for i in range(1, 8)]

    for user_id in test_users:
        try:
            await backend.delete_user(user_id)
            print(f"  ✓ Cleaned up {user_id}")
        except Exception as e:
            print(f"  ⚠️  Could not clean up {user_id}: {e}")

    print("✅ Cleanup complete\n")


async def main():
    """Run all tests"""
    print("=" * 60)
    print("FIRESTORE BACKEND TEST SUITE")
    print("=" * 60)
    print()

    # Setup credentials
    print("Setting up Firebase credentials...")
    try:
        creds_dict = setup_firebase_credentials()
    except Exception as e:
        print(f"❌ ERROR: Failed to setup credentials: {e}")
        sys.exit(1)

    # Get configuration from environment (use project_id from credentials)
    project_id = creds_dict.get("project_id")
    if not project_id:
        print("❌ ERROR: project_id not found in credentials")
        sys.exit(1)

    database_name = os.getenv("FIREBASE_WINDOW_SHOP_DB_NAME", "(default)")
    base_path = os.getenv("FIRESTORE_BASE_PATH", "experiments/memory")

    print(f"  Project: {project_id}")
    print(f"  Database: {database_name}")
    print(f"  Base path: {base_path}")
    print()

    print("⚠️  Using live Firestore!")
    print(f"   Database: {database_name}")
    print(f"   Path: {base_path}/test-user-*/...")
    print()

    try:
        # Initialize backend with credentials dict
        print("Initializing Firestore backend...")
        backend = FirestoreBackend(
            project_id=project_id,
            base_path=base_path,
            credentials_dict=creds_dict,
            database=database_name,
        )
        print("  ✓ Backend initialized\n")

        # Run tests
        await test_write_and_read(backend)
        await test_nonexistent_user(backend)
        await test_exists(backend)
        await test_list_users(backend)
        await test_delete(backend)
        await test_multiple_file_types(backend)
        await test_update_existing(backend)
        await create_persistent_test_user(backend)

        print("=" * 60)
        print("✅ ALL TESTS PASSED")
        print("=" * 60)
        print()

        # Print latency statistics
        print_latency_statistics()

        # Cleanup
        await cleanup_test_data(backend)

        print("Firestore backend is ready to use!")
        print(f"Data stored at: {base_path}/<user_id>/<filename>")
        print()
        print("📌 Persistent test data available:")
        print("   User ID: firebase-test-user-123456")
        print(f"   Location: {base_path}/firebase-test-user-123456/")
        print("   Files: preferences.toml, conversations.toml")
        print()
        print("You can view the data in Firebase Console:")
        print(
            f"https://console.firebase.google.com/project/{project_id}/firestore/databases/{database_name}/data"
        )

    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
