"""
Firestore Connection Configuration

Centralized configuration for Firestore backend examples and tests.
Loads configuration from environment variables with validation.

Required Environment Variables:
    FIREBASE_ADMIN_PROJECT_ID: Google Cloud project ID
    FIREBASE_ADMIN_CREDS: JSON string with Firebase service account credentials

Optional Environment Variables:
    FIREBASE_WINDOW_SHOP_DB_NAME: Firestore database name (defaults to "(default)")
    FIRESTORE_BASE_PATH: Base path for Firestore documents (defaults to "tomldiary/demo")

Usage:
    from scripts.firestore_connection import get_firestore_config, setup_credentials

    config = get_firestore_config()
    creds_path = setup_credentials(config.credentials_json)

    backend = FirestoreBackend(
        project_id=config.project_id,
        base_path=config.base_path,
        credentials_path=creds_path,
        database=config.database
    )
"""

import json
import os
from dataclasses import dataclass
from pathlib import Path


@dataclass
class FirestoreConfig:
    """Firestore connection configuration."""

    project_id: str
    database: str
    base_path: str
    credentials_json: str


def get_firestore_config() -> FirestoreConfig:
    """
    Load Firestore configuration from environment variables.

    Returns:
        FirestoreConfig with validated settings

    Raises:
        ValueError: If required environment variables are missing
    """
    # Required variables
    project_id = os.getenv("FIREBASE_ADMIN_PROJECT_ID")
    if not project_id:
        raise ValueError(
            "FIREBASE_ADMIN_PROJECT_ID environment variable is required.\n"
            "Please set it to your Google Cloud project ID."
        )

    credentials_json = os.getenv("FIREBASE_ADMIN_CREDS")
    if not credentials_json:
        raise ValueError(
            "FIREBASE_ADMIN_CREDS environment variable is required.\n"
            "Please set it to your Firebase service account JSON string."
        )

    # Optional variables with defaults
    database = os.getenv("FIREBASE_WINDOW_SHOP_DB_NAME", "(default)")
    base_path = os.getenv("FIRESTORE_BASE_PATH", "tomldiary/demo")

    # Validate base_path has even number of segments
    path_segments = [s for s in base_path.strip("/").split("/") if s]
    if len(path_segments) % 2 != 0:
        raise ValueError(
            f"Invalid FIRESTORE_BASE_PATH '{base_path}': must have an EVEN number of segments.\n"
            f"Current path has {len(path_segments)} segments: {path_segments}\n"
            f"Examples of valid paths: 'app/memory', 'prod/users', 'v1/app/data/memory'"
        )

    return FirestoreConfig(
        project_id=project_id,
        database=database,
        base_path=base_path,
        credentials_json=credentials_json,
    )


def setup_credentials(credentials_json: str, temp_dir: Path | None = None) -> str:
    """
    Create temporary credentials file from JSON string.

    Args:
        credentials_json: Service account JSON as string
        temp_dir: Directory for temp file (defaults to current directory)

    Returns:
        Path to temporary credentials file

    Raises:
        ValueError: If credentials JSON is invalid
    """
    try:
        creds = json.loads(credentials_json)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid FIREBASE_ADMIN_CREDS JSON: {e}") from e

    if temp_dir is None:
        temp_dir = Path.cwd()

    creds_path = temp_dir / "temp_firebase_creds.json"

    with open(creds_path, "w") as f:
        json.dump(creds, f)

    return str(creds_path)


def cleanup_credentials(creds_path: str) -> None:
    """
    Remove temporary credentials file.

    Args:
        creds_path: Path to credentials file to remove
    """
    try:
        creds_file = Path(creds_path)
        if creds_file.exists():
            creds_file.unlink()
    except Exception:
        pass  # Best effort cleanup
