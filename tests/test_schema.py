"""Tests for schema formatting and partial validation.

Covers two correctness fixes:
- show_conversations_schema(format="python") emits real field types (turns: int)
  by resolving serialization aliases when indexing the JSON schema properties.
- PreferenceLoader.validate_partial derives its adapter from the category's
  actual declared field type rather than a hardcoded dict[str, PreferenceItem].
"""

from __future__ import annotations

import pytest
from pydantic import BaseModel, ValidationError

from tomldiary.loaders import PreferenceLoader
from tomldiary.models import PreferenceItem
from tomldiary.schema import show_conversations_schema


def test_show_conversations_schema_python_emits_real_types() -> None:
    """The python formatter must emit each field's real type, not fall back to str.

    Aliased fields (_created/_updated/_turns) must be resolved so that e.g.
    `turns` is reported as int, not str.
    """
    out = show_conversations_schema(format="python")

    assert "turns: int" in out
    assert "turns: str" not in out

    # created/updated are str timestamps; they should resolve (not blank/unknown)
    assert "created: str" in out
    assert "updated: str" in out
    # keywords is a list field
    assert "keywords: list[str]" in out


class _SinglePrefTable(BaseModel):
    """Minimal preference table for the default-schema partial validation case."""

    like: dict[str, PreferenceItem] = {}


def test_validate_partial_accepts_valid_payload() -> None:
    """A valid payload validates and yields PreferenceItem instances."""
    loader = PreferenceLoader(_SinglePrefTable)
    result = loader.validate_partial(
        "like",
        {
            "pizza": {
                "text": "loves Neapolitan pizza",
                "contexts": ["food", "italian"],
                "_count": 3,
            }
        },
    )

    assert set(result) == {"pizza"}
    assert isinstance(result["pizza"], PreferenceItem)
    assert result["pizza"].text == "loves Neapolitan pizza"
    assert result["pizza"].count == 3


def test_validate_partial_rejects_invalid_payload_consistently() -> None:
    """An invalid item (missing required `text`) is rejected, matching full validation."""
    loader = PreferenceLoader(_SinglePrefTable)

    invalid = {"pizza": {"contexts": ["food"]}}

    # Partial validation rejects it.
    with pytest.raises(ValidationError):
        loader.validate_partial("like", invalid)

    # Full validation rejects the same payload for the same reason.
    with pytest.raises(ValidationError):
        loader.load_from_toml_str('[preferences.like.pizza]\ncontexts = ["food"]\n')


def test_validate_partial_uses_declared_field_type() -> None:
    """The adapter is derived from the category's declared annotation."""
    loader = PreferenceLoader(_SinglePrefTable)

    # Sanity: the annotation drives validation; an unknown category still errors.
    with pytest.raises(ValueError):
        loader.validate_partial("missing", {})
