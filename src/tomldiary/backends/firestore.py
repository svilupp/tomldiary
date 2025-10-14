"""
Firestore Backend for TOMLDiary

A production-ready Firestore backend implementing TOMLDiary's backend interface.

Firestore Schema:
-----------------
{base_path}/                           # Configurable base path (e.g., app/memory)
  {user_id}/                           # User document
    preferences.toml                   # Document (TOML content)
    conversations.toml                 # Document (TOML content)

Example with base_path="app/memory":
app/                           # Collection
  memory/                             # Document
    {user_id}/                        # Collection
      preferences.toml                # Document
      conversations.toml              # Document

Document Structure:
-------------------
{
    "content": "...TOML string...",
    "updated_at": "2025-10-10T12:00:00Z",
    "version": "0.3"
}

Path Validation:
---------------
Firestore requires paths to follow collection/document alternating pattern.
The base_path must have an EVEN number of segments to ensure valid paths.
"""

import asyncio
from datetime import UTC, datetime

try:
    from google.api_core import exceptions as gcp_exceptions
    from google.cloud import firestore
    from loguru import logger
except ImportError as e:
    raise ImportError(
        "google-cloud-firestore is required for FirestoreBackend. "
        "Install with: uv add 'tomldiary[firestore]' or pip install 'tomldiary[firestore]'"
    ) from e


class FirestoreBackend:
    """
    Firestore backend for TOMLDiary memory storage.

    This backend stores TOML memory files in Google Cloud Firestore,
    following Firestore's collection/document hierarchy requirements.

    Args:
        project_id: Google Cloud project ID
        base_path: Base path for storing memory files (e.g., "experiments/memory")
                   Must have an EVEN number of segments for Firestore compatibility
        credentials_path: Optional path to service account JSON (if not using default credentials)
        database: Firestore database name (default: "(default)")

    Example:
        ```python
        from tomldiary.backends import FirestoreBackend

        backend = FirestoreBackend(
            project_id="my-project",
            base_path="experiments/memory"
        )
        await backend.save("user-123", "preferences", "toml content here")
        content = await backend.load("user-123", "preferences")
        ```
    """

    def __init__(
        self,
        project_id: str,
        base_path: str = "users",
        credentials_path: str | None = None,
        database: str = "(default)",
    ):
        """
        Initialize Firestore backend.

        Args:
            project_id: GCP project ID
            base_path: Base path for Firestore documents (e.g., "experiments/memory")
            credentials_path: Path to service account JSON file (optional)
            database: Firestore database name (default: "(default)")

        Raises:
            ValueError: If base_path has an odd number of segments (Firestore requirement)
        """
        self.project_id = project_id
        self.database = database
        self.base_path = base_path.strip("/")

        # Validate base_path has even number of segments
        path_segments = [s for s in self.base_path.split("/") if s]
        if len(path_segments) % 2 != 0:
            raise ValueError(
                f"Invalid base_path '{base_path}': Firestore requires an EVEN number of path segments.\n"
                f"Current path has {len(path_segments)} segments: {path_segments}\n"
                f"Firestore paths must alternate: collection/document/collection/document/...\n"
                f"Please add one more segment to your base_path to make it even.\n"
                f"Example: '{base_path}/memory' (if your current path is just one segment)"
            )

        # Initialize Firestore client
        if credentials_path:
            from google.oauth2 import service_account

            credentials = service_account.Credentials.from_service_account_file(credentials_path)
            self.db = firestore.Client(
                project=project_id, database=database, credentials=credentials
            )
        else:
            # Use default credentials (works with emulator or ADC)
            self.db = firestore.Client(project=project_id, database=database)

        logger.info(
            f"FirestoreBackend initialized: project={project_id}, database={database}, "
            f"base_path={self.base_path} ({len(path_segments)} segments)"
        )

    def _get_document_ref(self, user_id: str, kind: str):
        """
        Get Firestore document reference following the hierarchy:
        {base_path}/{user_id}/{kind}.toml

        Example with base_path="experiments/memory":
        experiments (collection) / memory (doc) / {user_id} (collection) / {kind}.toml (doc)

        Args:
            user_id: User identifier
            kind: File kind (e.g., "preferences", "conversations")

        Returns:
            Firestore document reference
        """
        # Navigate through base_path segments
        path_segments = [s for s in self.base_path.split("/") if s]

        # Start with the first collection
        ref = self.db.collection(path_segments[0])

        # Navigate through alternating document/collection pairs
        for i in range(1, len(path_segments)):
            # Odd index = document, even index = collection
            ref = ref.document(path_segments[i]) if i % 2 == 1 else ref.collection(path_segments[i])

        # Add user_id collection and kind.toml document
        file_name = f"{kind}.toml"
        return ref.collection(user_id).document(file_name)

    async def load(self, user_id: str, kind: str) -> str | None:
        """
        Load TOML content from Firestore.

        Args:
            user_id: User identifier
            kind: Either "preferences" or "conversations"

        Returns:
            TOML content as string, or None if not found

        Raises:
            Exception: If Firestore read fails
        """
        try:
            doc_ref = self._get_document_ref(user_id, kind)

            # Firestore operations are synchronous, run in executor
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
        """
        Save TOML content to Firestore.

        Args:
            user_id: User identifier
            kind: Either "preferences" or "conversations"
            content: TOML content as string

        Raises:
            Exception: If Firestore write fails
        """
        try:
            doc_ref = self._get_document_ref(user_id, kind)

            # Prepare document data
            data = {
                "content": content,
                "updated_at": datetime.now(UTC).isoformat(),
                "version": "0.3",
            }

            # Write to Firestore (atomic operation)
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, doc_ref.set, data)

            logger.debug(f"Wrote {kind} for user {user_id}: {len(content)} chars")

        except Exception as e:
            logger.error(f"Failed to write {kind} for {user_id}: {e}")
            raise

    # ─────── Optional utility methods (not required by TOMLDiary interface) ───────

    async def exists(self, user_id: str, kind: str) -> bool:
        """
        Check if document exists in Firestore.

        Args:
            user_id: User identifier
            kind: Either "preferences" or "conversations"

        Returns:
            True if document exists, False otherwise
        """
        try:
            doc_ref = self._get_document_ref(user_id, kind)

            loop = asyncio.get_event_loop()
            doc = await loop.run_in_executor(None, doc_ref.get)

            return doc.exists

        except Exception as e:
            logger.error(f"Failed to check existence for {user_id}/{kind}: {e}")
            return False

    async def list_users(self) -> list[str]:
        """
        List all user IDs in the database.

        Returns:
            List of user IDs

        Raises:
            Exception: If Firestore query fails
        """
        try:
            # Navigate to the document that contains user collections
            path_segments = [s for s in self.base_path.split("/") if s]

            # Navigate to the last document in base_path
            ref = self.db.collection(path_segments[0])
            for i in range(1, len(path_segments)):
                # Odd index = document, even index = collection
                ref = (
                    ref.document(path_segments[i])
                    if i % 2 == 1
                    else ref.collection(path_segments[i])
                )

            # List all collections (user_ids) under this document
            loop = asyncio.get_event_loop()
            collections = await loop.run_in_executor(None, ref.collections)

            user_ids = [col.id for col in collections]
            logger.debug(f"Listed {len(user_ids)} users")

            return user_ids

        except Exception as e:
            logger.error(f"Failed to list users: {e}")
            raise

    async def delete(self, user_id: str, kind: str) -> None:
        """
        Delete a document from Firestore.

        Args:
            user_id: User identifier
            kind: Either "preferences" or "conversations"

        Raises:
            Exception: If Firestore delete fails
        """
        try:
            doc_ref = self._get_document_ref(user_id, kind)

            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, doc_ref.delete)

            logger.debug(f"Deleted {kind} for user {user_id}")

        except Exception as e:
            logger.error(f"Failed to delete {kind} for {user_id}: {e}")
            raise

    async def delete_user(self, user_id: str) -> None:
        """
        Delete all data for a user (all documents in their collection).

        Args:
            user_id: User identifier

        Raises:
            Exception: If Firestore delete fails
        """
        try:
            # Navigate to the user's collection
            path_segments = [s for s in self.base_path.split("/") if s]
            ref = self.db.collection(path_segments[0])
            for i in range(1, len(path_segments)):
                # Odd index = document, even index = collection
                ref = (
                    ref.document(path_segments[i])
                    if i % 2 == 1
                    else ref.collection(path_segments[i])
                )

            # Get the user collection
            user_collection = ref.collection(user_id)

            # Delete all documents in the user's collection
            loop = asyncio.get_event_loop()
            docs = await loop.run_in_executor(None, user_collection.stream)

            for doc in docs:
                await loop.run_in_executor(None, doc.reference.delete)
                logger.debug(f"Deleted {user_id}/{doc.id}")

            logger.info(f"Deleted all data for user {user_id}")

        except Exception as e:
            logger.error(f"Failed to delete user {user_id}: {e}")
            raise
