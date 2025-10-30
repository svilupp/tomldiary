"""Common backend typing contracts."""

from __future__ import annotations

from typing import Protocol


class BackendProtocol(Protocol):
    """Protocol describing the required backend interface for ``Diary``."""

    async def load(self, user_id: str, kind: str) -> str | None:
        """Load TOML content for a given user and document kind."""

    async def save(self, user_id: str, kind: str, content: str) -> None:
        """Persist TOML content for a given user and document kind."""

    async def exists(self, user_id: str, kind: str) -> bool:
        """Return ``True`` when the document exists for the user."""

    async def delete(self, user_id: str, kind: str) -> None:
        """Remove the specific document for the user, if present."""

    async def delete_user(self, user_id: str) -> None:
        """Remove all stored data for the user."""

    async def list_users(self) -> list[str]:
        """Return all user identifiers that currently have stored data."""
