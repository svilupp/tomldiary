import asyncio
import os
import weakref
from pathlib import Path

from ..logging import get_logger

logger = get_logger(__name__)


class LocalBackend:
    """File-based backend with path-level locking for concurrent access."""

    def __init__(self, base_path: Path):
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)
        self._locks: weakref.WeakValueDictionary[Path, asyncio.Lock] = weakref.WeakValueDictionary()

    def _get_file_path(self, user_id: str, kind: str) -> Path:
        """Get the file path for a user's data kind."""
        user_dir = self.base_path / user_id
        user_dir.mkdir(exist_ok=True)
        return user_dir / f"{kind}.toml"

    async def _get_lock(self, path: Path) -> asyncio.Lock:
        """Get or create a lock for a specific file path."""
        lock = self._locks.get(path)
        if lock is None:
            lock = asyncio.Lock()
            self._locks[path] = lock
        return lock

    async def load(self, user_id: str, kind: str) -> str | None:
        """Load TOML content for a user and kind."""
        file_path = self._get_file_path(user_id, kind)
        if not file_path.exists():
            return None

        try:
            # Use asyncio.to_thread for file I/O to avoid blocking
            return await asyncio.to_thread(file_path.read_text)
        except Exception:
            return None

    async def save(self, user_id: str, kind: str, content: str) -> None:
        """Save TOML content for a user and kind with atomic write and path-level locking."""
        file_path = self._get_file_path(user_id, kind)
        temp_path = file_path.with_suffix(".tmp")

        # Get lock for this specific path to prevent concurrent writes
        async with await self._get_lock(file_path):
            try:
                # Write to temporary file
                await asyncio.to_thread(temp_path.write_text, content)

                # Atomic rename
                await asyncio.to_thread(os.replace, str(temp_path), str(file_path))
            except Exception:
                # Clean up temp file if something went wrong
                if temp_path.exists():
                    await asyncio.to_thread(temp_path.unlink)
                raise

    async def exists(self, user_id: str, kind: str) -> bool:
        """Check if a document exists for a user."""
        # Don't use _get_file_path as it creates directories
        file_path = self.base_path / user_id / f"{kind}.toml"
        return await asyncio.to_thread(file_path.exists)

    async def delete(self, user_id: str, kind: str) -> None:
        """Delete a specific document for a user."""
        # Don't use _get_file_path as it creates directories
        file_path = self.base_path / user_id / f"{kind}.toml"

        # Get lock for this path to prevent concurrent access
        async with await self._get_lock(file_path):
            if await asyncio.to_thread(file_path.exists):
                await asyncio.to_thread(file_path.unlink)
                logger.debug(f"Deleted {kind} for user {user_id}")
            else:
                logger.debug(f"Delete called but {kind} doesn't exist for user {user_id}")

    async def delete_user(self, user_id: str) -> None:
        """Delete all data for a user."""
        user_dir = self.base_path / user_id

        if await asyncio.to_thread(user_dir.exists):
            import shutil

            await asyncio.to_thread(shutil.rmtree, user_dir)
            logger.info(f"Deleted all data for user {user_id}")
        else:
            logger.debug(f"Delete user called but user {user_id} doesn't exist")

    async def list_users(self) -> list[str]:
        """List all user IDs with stored data."""

        def _list_user_dirs():
            """Synchronous helper to list user directories."""
            if not self.base_path.exists():
                return []

            return [d.name for d in self.base_path.iterdir() if d.is_dir()]

        return await asyncio.to_thread(_list_user_dirs)
