import asyncio
import os
import weakref
from pathlib import Path


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
