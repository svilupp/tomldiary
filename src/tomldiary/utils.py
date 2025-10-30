"""Utility functions for tomldiary."""

from __future__ import annotations

from pydantic import BaseModel


def extract_categories_from_schema(pref_table_cls: type[BaseModel]) -> list[str]:
    """Extract allowed categories from a preference table class.

    Args:
        pref_table_cls: A Pydantic model class representing the preference table

    Returns:
        List of category names (field names from the model)
    """
    return list(pref_table_cls.model_fields.keys())
