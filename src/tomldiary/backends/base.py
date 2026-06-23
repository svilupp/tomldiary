"""Common backend typing contracts."""

from __future__ import annotations

from typing import Protocol

# Control characters (incl. NUL) plus path separators are never valid in an id.
_FORBIDDEN_CHARS = frozenset("/\\\x00") | frozenset(chr(c) for c in range(0x20)) | {"\x7f"}


def validate_identifier(value: str, name: str = "identifier") -> str:
    """Validate a ``user_id`` or ``kind`` used to build a storage path.

    Returns the value unchanged when valid so it can be used inline. Rejects
    values that could escape the storage root or break path invariants:
    non-strings, empty/whitespace-only, a leading dot, ``..`` anywhere, path
    separators (``/`` or ``\\``), NUL, and other control characters. Normal
    ids (alphanumerics, ``-``, ``_``, UUIDs, emails-as-ids) still pass.

    Raises:
        ValueError: If the value is not a valid identifier.
    """
    if not isinstance(value, str):
        raise ValueError(f"Invalid {name}: expected a string, got {type(value).__name__}")
    if not value.strip():
        raise ValueError(f"Invalid {name}: must not be empty or whitespace-only")
    if value.startswith("."):
        raise ValueError(f"Invalid {name} {value!r}: must not start with '.'")
    if ".." in value:
        raise ValueError(f"Invalid {name} {value!r}: must not contain '..'")
    bad = _FORBIDDEN_CHARS.intersection(value)
    if bad:
        raise ValueError(
            f"Invalid {name} {value!r}: must not contain path separators or control characters"
        )
    return value


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
