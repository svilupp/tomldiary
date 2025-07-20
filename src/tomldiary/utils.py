"""Utility functions for tomldiary."""


def extract_categories_from_schema(pref_table_cls) -> list[str]:
    """Extract allowed categories from a preference table class.

    Args:
        pref_table_cls: A Pydantic model class representing the preference table

    Returns:
        List of category names (field names from the model)
    """
    return list(pref_table_cls.model_fields.keys())
