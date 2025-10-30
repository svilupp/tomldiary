"""Backend implementations and typing contracts for diary storage."""

from .base import BackendProtocol
from .local import LocalBackend

__all__ = ["BackendProtocol", "LocalBackend"]

# Optional Firestore backend - requires 'tomldiary[firestore]' installation
try:
    from .firestore import FirestoreBackend  # noqa: F401

    __all__.append("FirestoreBackend")
except ImportError:
    # Firestore dependencies not installed
    # Users can install with: uv add 'tomldiary[firestore]'
    pass
