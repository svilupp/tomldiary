"""Schema inspection utilities for tomldiary.

This module provides tools to inspect and display schemas for preference tables
and conversation items. Useful for API design, documentation, and type validation.
"""

from __future__ import annotations

import json
from typing import Literal

from pydantic import BaseModel

from .models import ConversationItem
from .utils import extract_categories_from_schema


def get_preferences_schema(pref_table_cls: type[BaseModel]) -> dict:
    """Get structured schema information for a preference table class.

    Args:
        pref_table_cls: A Pydantic model class representing the preference table

    Returns:
        Dictionary containing:
        - schema_name: Name of the preference table class
        - categories: List of category names (field names)
        - json_schema: Full Pydantic JSON schema
        - category_types: Mapping of category names to their type annotations
        - descriptions: Mapping of category names to their field descriptions

    Example:
        >>> from examples.culinary_prefs import CulinaryPrefTable
        >>> schema = get_preferences_schema(CulinaryPrefTable)
        >>> print(schema["schema_name"])
        'CulinaryPrefTable'
        >>> print(schema["categories"])
        ['favorite_foods', 'cooking_techniques', ...]
    """
    categories = extract_categories_from_schema(pref_table_cls)
    json_schema = pref_table_cls.model_json_schema()

    # Extract type annotations and descriptions
    category_types = {}
    descriptions = {}

    for category in categories:
        field_info = pref_table_cls.model_fields.get(category)
        if field_info:
            # Get type annotation as string
            annotation = field_info.annotation
            if annotation is None:
                type_str = "Any"
            else:
                type_str = (
                    annotation.__name__ if hasattr(annotation, "__name__") else str(annotation)
                )

            category_types[category] = type_str
            descriptions[category] = field_info.description or ""

    return {
        "schema_name": pref_table_cls.__name__,
        "categories": categories,
        "json_schema": json_schema,
        "category_types": category_types,
        "descriptions": descriptions,
    }


def get_conversations_schema() -> dict:
    """Get structured schema information for conversation items.

    Returns:
        Dictionary containing:
        - schema_name: "ConversationItem"
        - json_schema: Full Pydantic JSON schema
        - fields: List of field names in ConversationItem

    Example:
        >>> schema = get_conversations_schema()
        >>> print(schema["fields"])
        ['created', 'updated', 'turns', 'summary', 'keywords']
    """
    json_schema = ConversationItem.model_json_schema()
    fields = list(ConversationItem.model_fields.keys())

    return {
        "schema_name": "ConversationItem",
        "json_schema": json_schema,
        "fields": fields,
    }


def _format_schema_pretty(schema_info: dict, kind: Literal["preferences", "conversations"]) -> str:
    """Format schema as a pretty tree structure.

    Args:
        schema_info: Schema information from get_*_schema()
        kind: Type of schema ("preferences" or "conversations")

    Returns:
        Formatted tree string
    """
    lines = []
    lines.append(f"{schema_info['schema_name']}")
    lines.append("")

    if kind == "preferences":
        categories = schema_info["categories"]
        descriptions = schema_info["descriptions"]
        category_types = schema_info["category_types"]

        for i, category in enumerate(categories):
            is_last = i == len(categories) - 1
            prefix = "└──" if is_last else "├──"
            type_str = category_types.get(category, "dict[str, PreferenceItem]")

            lines.append(f"{prefix} {category}: {type_str}")

            # Add description if available
            desc = descriptions.get(category, "")
            if desc:
                # Truncate long descriptions
                desc_preview = desc.strip().split("\n")[0]
                if len(desc_preview) > 80:
                    desc_preview = desc_preview[:77] + "..."

                desc_prefix = "    " if is_last else "│   "
                lines.append(f"{desc_prefix}└─ {desc_preview}")

    else:  # conversations
        fields = schema_info["fields"]
        json_schema = schema_info["json_schema"]
        properties = json_schema.get("properties", {})

        # Map field names to their serialization names (handle aliases)
        from .models import ConversationItem

        field_aliases = {
            name: field.serialization_alias or name
            for name, field in ConversationItem.model_fields.items()
        }

        for i, field in enumerate(fields):
            is_last = i == len(fields) - 1
            prefix = "└──" if is_last else "├──"

            # Use the serialization alias to look up in properties
            serialized_name = field_aliases.get(field, field)
            field_schema = properties.get(serialized_name, {})
            field_type = field_schema.get("type", "unknown")
            field_desc = field_schema.get("description", "")

            lines.append(f"{prefix} {field}: {field_type}")

            if field_desc:
                desc_preview = field_desc.strip().split("\n")[0]
                if len(desc_preview) > 80:
                    desc_preview = desc_preview[:77] + "..."
                desc_prefix = "    " if is_last else "│   "
                lines.append(f"{desc_prefix}└─ {desc_preview}")

    return "\n".join(lines)


def _format_schema_json(schema_info: dict) -> str:
    """Format schema as JSON.

    Args:
        schema_info: Schema information from get_*_schema()

    Returns:
        JSON string of the full JSON schema
    """
    return json.dumps(schema_info["json_schema"], indent=2)


def _format_schema_python(schema_info: dict, kind: Literal["preferences", "conversations"]) -> str:
    """Format schema as Python type hints.

    Args:
        schema_info: Schema information from get_*_schema()
        kind: Type of schema ("preferences" or "conversations")

    Returns:
        Python class definition with type hints
    """
    lines = []
    lines.append("from pydantic import BaseModel, Field")
    lines.append("from tomldiary import PreferenceItem, ConversationItem")
    lines.append("")

    if kind == "preferences":
        lines.append(f"class {schema_info['schema_name']}(BaseModel):")
        categories = schema_info["categories"]
        descriptions = schema_info["descriptions"]

        if not categories:
            lines.append("    pass")
        else:
            for category in categories:
                # Default type for preference categories
                type_hint = "dict[str, PreferenceItem]"
                desc = descriptions.get(category, "")

                if desc:
                    # Add description as Field
                    desc_escaped = desc.replace('"', '\\"').replace("\n", "\\n")
                    # Truncate very long descriptions
                    if len(desc_escaped) > 200:
                        desc_escaped = desc_escaped[:197] + "..."
                    lines.append(f"    {category}: {type_hint} = Field(")
                    lines.append("        default_factory=dict,")
                    lines.append(f'        description="{desc_escaped}"')
                    lines.append("    )")
                else:
                    lines.append(f"    {category}: {type_hint} = {{}}")

    else:  # conversations
        lines.append(f"class {schema_info['schema_name']}(BaseModel):")
        fields = schema_info["fields"]
        json_schema = schema_info["json_schema"]
        properties = json_schema.get("properties", {})

        if not fields:
            lines.append("    pass")
        else:
            for field in fields:
                field_schema = properties.get(field, {})
                field_type = field_schema.get("type", "str")

                # Map JSON types to Python types
                type_map = {
                    "string": "str",
                    "integer": "int",
                    "array": "list[str]",  # Simplified
                    "boolean": "bool",
                }
                python_type = type_map.get(field_type, "str")

                field_desc = field_schema.get("description", "")
                if field_desc:
                    desc_escaped = field_desc.replace('"', '\\"').replace("\n", "\\n")
                    if len(desc_escaped) > 200:
                        desc_escaped = desc_escaped[:197] + "..."
                    lines.append(
                        f'    {field}: {python_type} = Field(description="{desc_escaped}")'
                    )
                else:
                    lines.append(f"    {field}: {python_type}")

    return "\n".join(lines)


def show_preferences_schema(
    pref_table_cls: type[BaseModel], format: Literal["pretty", "json", "python"] = "pretty"
) -> str:
    """Display the schema for a preference table class.

    Args:
        pref_table_cls: A Pydantic model class representing the preference table
        format: Output format - "pretty" (tree), "json" (JSON schema), or "python" (type hints)

    Returns:
        Formatted schema string

    Example:
        >>> from examples.culinary_prefs import CulinaryPrefTable
        >>> print(show_preferences_schema(CulinaryPrefTable))
        CulinaryPrefTable
        ├── favorite_foods: dict[str, PreferenceItem]
        │   └─ CAPTURE: Specific dishes, cuisines...
        ...

        >>> print(show_preferences_schema(CulinaryPrefTable, format="json"))
        {
          "$defs": {...},
          "properties": {...},
          ...
        }
    """
    schema_info = get_preferences_schema(pref_table_cls)

    if format == "json":
        return _format_schema_json(schema_info)
    elif format == "python":
        return _format_schema_python(schema_info, "preferences")
    else:  # pretty
        return _format_schema_pretty(schema_info, "preferences")


def show_conversations_schema(format: Literal["pretty", "json", "python"] = "pretty") -> str:
    """Display the schema for conversation items.

    Args:
        format: Output format - "pretty" (tree), "json" (JSON schema), or "python" (type hints)

    Returns:
        Formatted schema string

    Example:
        >>> print(show_conversations_schema())
        ConversationItem
        ├── created: string
        ├── updated: string
        ├── turns: integer
        ├── summary: string
        └── keywords: array

        >>> print(show_conversations_schema(format="json"))
        {
          "properties": {...},
          ...
        }
    """
    schema_info = get_conversations_schema()

    if format == "json":
        return _format_schema_json(schema_info)
    elif format == "python":
        return _format_schema_python(schema_info, "conversations")
    else:  # pretty
        return _format_schema_pretty(schema_info, "conversations")
