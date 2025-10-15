"""Safe loading utilities for TOML data with Pydantic validation.

This module provides utilities to safely load and validate TOML data from tomldiary
into properly typed Python objects using Pydantic's TypeAdapter for runtime validation.
"""

from __future__ import annotations

import tomllib
from pathlib import Path

from pydantic import BaseModel, TypeAdapter

from .models import ConversationItem, PreferenceItem


class PreferenceLoader:
    """Safe loader for preference TOML data using Pydantic TypeAdapter.

    This class provides methods to load and validate TOML preference data into
    properly typed Pydantic models, ensuring data integrity and type safety.

    Example:
        >>> from tomldiary.loaders import PreferenceLoader
        >>> from examples.culinary_prefs import CulinaryPrefTable
        >>>
        >>> loader = PreferenceLoader(CulinaryPrefTable)
        >>> prefs = loader.load_from_toml_str(toml_data)
        >>> print(type(prefs))  # CulinaryPrefTable
        >>> print(type(prefs.favorite_foods))  # dict[str, PreferenceItem]
    """

    def __init__(self, pref_table_cls: type[BaseModel]):
        """Initialize the loader with a preference table class.

        Args:
            pref_table_cls: A Pydantic model class representing the preference table
        """
        self.pref_table_cls = pref_table_cls
        self.adapter = TypeAdapter(pref_table_cls)

    def load_from_toml_str(self, toml_str: str) -> BaseModel:
        """Load and validate TOML string into preference table.

        Args:
            toml_str: TOML string containing preference data

        Returns:
            Validated preference table instance

        Raises:
            ValidationError: If the data doesn't match the expected schema
            tomllib.TOMLDecodeError: If the TOML is malformed

        Example:
            >>> toml_data = '''
            ... [preferences.favorite_foods.pizza]
            ... text = "loves Neapolitan pizza"
            ... contexts = ["food", "italian"]
            ... _count = 3
            ... _created = "2024-01-01T00:00:00Z"
            ... _updated = "2024-01-01T00:00:00Z"
            ... '''
            >>> prefs = loader.load_from_toml_str(toml_data)
        """
        data = tomllib.loads(toml_str)

        # Extract the preferences section
        prefs_data = data.get("preferences", {})

        # Validate and construct the preference table
        return self.adapter.validate_python(prefs_data)

    def load_from_file(self, path: Path | str) -> BaseModel:
        """Load and validate TOML file into preference table.

        Args:
            path: Path to TOML file

        Returns:
            Validated preference table instance

        Raises:
            ValidationError: If the data doesn't match the expected schema
            FileNotFoundError: If the file doesn't exist
            tomllib.TOMLDecodeError: If the TOML is malformed

        Example:
            >>> prefs = loader.load_from_file("memories/user123_preferences.toml")
        """
        path = Path(path)
        with open(path, "rb") as f:
            data = tomllib.load(f)

        prefs_data = data.get("preferences", {})
        return self.adapter.validate_python(prefs_data)

    def validate_partial(self, category: str, data: dict[str, dict]) -> dict[str, PreferenceItem]:
        """Validate a single category's data.

        Args:
            category: Category name (e.g., "favorite_foods")
            data: Dictionary mapping preference IDs to preference data

        Returns:
            Validated dictionary of PreferenceItems

        Raises:
            ValidationError: If any preference item is invalid
            ValueError: If category doesn't exist in schema

        Example:
            >>> category_data = {
            ...     "pizza": {
            ...         "text": "loves pizza",
            ...         "contexts": ["food"],
            ...         "_count": 1,
            ...         "_created": "2024-01-01T00:00:00Z",
            ...         "_updated": "2024-01-01T00:00:00Z"
            ...     }
            ... }
            >>> validated = loader.validate_partial("favorite_foods", category_data)
        """
        # Check if category exists in schema
        if category not in self.pref_table_cls.model_fields:
            valid_categories = list(self.pref_table_cls.model_fields.keys())
            raise ValueError(
                f"Category '{category}' not found in {self.pref_table_cls.__name__}. "
                f"Valid categories: {valid_categories}"
            )

        # Validate each item as PreferenceItem
        adapter = TypeAdapter(dict[str, PreferenceItem])
        return adapter.validate_python(data)


class ConversationLoader:
    """Safe loader for conversation TOML data using Pydantic TypeAdapter.

    This class provides methods to load and validate TOML conversation data into
    properly typed Pydantic models.

    Example:
        >>> from tomldiary.loaders import ConversationLoader
        >>>
        >>> loader = ConversationLoader()
        >>> convs = loader.load_from_toml_str(toml_data)
        >>> print(type(convs))  # dict[str, ConversationItem]
    """

    def __init__(self):
        """Initialize the conversation loader."""
        self.adapter = TypeAdapter(dict[str, ConversationItem])

    def load_from_toml_str(self, toml_str: str) -> dict[str, ConversationItem]:
        """Load and validate TOML string into conversation dictionary.

        Args:
            toml_str: TOML string containing conversation data

        Returns:
            Validated dictionary mapping session IDs to ConversationItems

        Raises:
            ValidationError: If the data doesn't match the expected schema
            tomllib.TOMLDecodeError: If the TOML is malformed

        Example:
            >>> toml_data = '''
            ... [conversations.session_123]
            ... _created = "2024-01-01T00:00:00Z"
            ... _updated = "2024-01-01T00:00:00Z"
            ... _turns = 5
            ... summary = "Discussed Italian food preferences"
            ... keywords = ["pizza", "pasta", "italian"]
            ... '''
            >>> convs = loader.load_from_toml_str(toml_data)
        """
        data = tomllib.loads(toml_str)

        # Extract the conversations section
        convs_data = data.get("conversations", {})

        # Validate and return
        return self.adapter.validate_python(convs_data)

    def load_from_file(self, path: Path | str) -> dict[str, ConversationItem]:
        """Load and validate TOML file into conversation dictionary.

        Args:
            path: Path to TOML file

        Returns:
            Validated dictionary mapping session IDs to ConversationItems

        Raises:
            ValidationError: If the data doesn't match the expected schema
            FileNotFoundError: If the file doesn't exist
            tomllib.TOMLDecodeError: If the TOML is malformed

        Example:
            >>> convs = loader.load_from_file("memories/user123_conversations.toml")
        """
        path = Path(path)
        with open(path, "rb") as f:
            data = tomllib.load(f)

        convs_data = data.get("conversations", {})
        return self.adapter.validate_python(convs_data)


# Convenience functions for quick loading


def load_preferences(toml_str: str, pref_table_cls: type[BaseModel]) -> BaseModel:
    """Convenience function to quickly load and validate preference TOML.

    Args:
        toml_str: TOML string containing preference data
        pref_table_cls: Pydantic model class for the preference table

    Returns:
        Validated preference table instance

    Example:
        >>> from tomldiary.loaders import load_preferences
        >>> from examples.culinary_prefs import CulinaryPrefTable
        >>>
        >>> prefs = load_preferences(toml_data, CulinaryPrefTable)
    """
    loader = PreferenceLoader(pref_table_cls)
    return loader.load_from_toml_str(toml_str)


def load_conversations(toml_str: str) -> dict[str, ConversationItem]:
    """Convenience function to quickly load and validate conversation TOML.

    Args:
        toml_str: TOML string containing conversation data

    Returns:
        Validated dictionary mapping session IDs to ConversationItems

    Example:
        >>> from tomldiary.loaders import load_conversations
        >>>
        >>> convs = load_conversations(toml_data)
    """
    loader = ConversationLoader()
    return loader.load_from_toml_str(toml_str)
