# Type Schema Utilities - Implementation Plan (v0.3)

## Overview
Add comprehensive type schema utilities to help users:
1. **Generate/show Python type schemas** for their preference tables (for API design, documentation)
2. **Safely load TOML data** into correctly-typed Python objects using Pydantic TypeAdapter

This will make tomldiary more useful for real-world scenarios where users need to:
- Design APIs that accept/return preference data
- Validate incoming TOML payloads against expected schemas
- Integrate tomldiary data with type-safe applications
- Document the structure of their preference/conversation data

## Goals
- Provide utilities to extract and display Python type information from PrefTable classes
- Show both JSON Schema and Python type annotations for preference tables
- Provide safe loading utilities using Pydantic TypeAdapter for runtime validation
- Document these utilities comprehensively with examples
- Increase version to 0.3
- Add examples demonstrating the new functionality

## Architecture

### 1. Schema Utilities (in `src/tomldiary/schema.py` - NEW FILE)

**Design Principles:**
- Symmetric naming: preferences and conversations are equal
- Consistent parameters: all `show_*` functions use same `format` kwarg
- Clear purpose: `show_*` for display, `get_*` for programmatic access
- CLI-friendly: Easy to expose via command-line interface

#### a) `show_preferences_schema(pref_table_cls, format="pretty") -> str`
Display preference table schema in various formats:
- `format="pretty"` - Formatted tree view (human-readable)
- `format="json"` - JSON schema (for API docs/OpenAPI)
- `format="python"` - Python type hints (for code reference)

```python
# Pretty format example:
CulinaryPrefTable
├── favorite_foods: dict[str, PreferenceItem]
│   └── Description: CAPTURE: Specific dishes, cuisines...
├── cooking_techniques: dict[str, PreferenceItem]
│   └── Description: CAPTURE: Specific cooking methods...
...

# JSON format: Full JSON schema (pydantic.model_json_schema())
# Python format: Python type annotations
```

#### b) `show_conversations_schema(format="pretty") -> str`
Display conversation schema (standardized structure):
- Same format options as preferences
- No class parameter needed (ConversationItem is standardized)

#### c) `get_preferences_schema(pref_table_cls) -> dict`
Programmatic access to preference schema:
```python
{
    "schema_name": "CulinaryPrefTable",
    "categories": ["favorite_foods", "cooking_techniques", ...],
    "json_schema": {...},  # Full pydantic JSON schema
    "category_types": {
        "favorite_foods": "dict[str, PreferenceItem]",
        ...
    },
    "descriptions": {
        "favorite_foods": "CAPTURE: Specific dishes...",
        ...
    }
}
```

#### d) `get_conversations_schema() -> dict`
Programmatic access to conversation schema:
```python
{
    "schema_name": "ConversationItem",
    "json_schema": {...},
    "fields": ["created", "updated", "turns", "summary", "keywords"]
}
```

#### Internal helpers:
- `_format_schema_pretty(schema_info, kind)` - Tree formatting
- `_format_schema_json(schema_info)` - JSON formatting
- `_format_schema_python(schema_info, kind)` - Python type formatting

### 2. CLI Interface (in `src/tomldiary/cli.py` - NEW FILE)

Command-line interface for easy schema inspection:

```bash
# Show preference schema
tomldiary schema preferences examples/culinary_prefs.py:CulinaryPrefTable
tomldiary schema preferences examples/culinary_prefs.py:CulinaryPrefTable --format=json
tomldiary schema preferences examples/culinary_prefs.py:CulinaryPrefTable -f python

# Show conversation schema
tomldiary schema conversations
tomldiary schema conversations --format=json
tomldiary schema conversations -f python
```

Implementation using `click`:
```python
import click

@click.group()
def cli():
    """tomldiary command-line interface."""
    pass

@cli.group()
def schema():
    """Schema inspection utilities."""
    pass

@schema.command("preferences")
@click.argument("class_path")  # file.py:ClassName
@click.option("--format", "-f", type=click.Choice(["pretty", "json", "python"]), default="pretty")
def show_prefs_schema(class_path: str, format: str):
    """Show preference table schema."""
    ...

@schema.command("conversations")
@click.option("--format", "-f", type=click.Choice(["pretty", "json", "python"]), default="pretty")
def show_convs_schema(format: str):
    """Show conversation schema."""
    ...
```

Entry point in `pyproject.toml`:
```toml
[project.scripts]
tomldiary = "tomldiary.cli:cli"
```

### 3. Safe Loading Utilities (in `src/tomldiary/loaders.py` - NEW FILE)

#### a) `PreferenceLoader` class
```python
class PreferenceLoader:
    """Safe loader for preference TOML data using Pydantic TypeAdapter."""

    def __init__(self, pref_table_cls: type[BaseModel]):
        self.pref_table_cls = pref_table_cls
        self.adapter = TypeAdapter(pref_table_cls)

    def load_from_toml_str(self, toml_str: str) -> BaseModel:
        """Load and validate TOML string into preference table."""
        data = tomllib.loads(toml_str)
        # Extract preferences section
        prefs_data = data.get("preferences", {})
        return self.adapter.validate_python(prefs_data)

    def load_from_file(self, path: Path) -> BaseModel:
        """Load and validate TOML file into preference table."""
        ...

    def validate_partial(self, category: str, data: dict) -> dict[str, PreferenceItem]:
        """Validate a single category's data."""
        ...
```

#### b) `ConversationLoader` class
```python
class ConversationLoader:
    """Safe loader for conversation TOML data using Pydantic TypeAdapter."""

    def __init__(self):
        self.adapter = TypeAdapter(dict[str, ConversationItem])

    def load_from_toml_str(self, toml_str: str) -> dict[str, ConversationItem]:
        """Load and validate TOML string into conversation dict."""
        ...

    def load_from_file(self, path: Path) -> dict[str, ConversationItem]:
        """Load and validate TOML file into conversation dict."""
        ...
```

#### c) Helper functions
```python
def load_preferences(toml_str: str, pref_table_cls: type[BaseModel]) -> BaseModel:
    """Convenience function for quick loading."""
    loader = PreferenceLoader(pref_table_cls)
    return loader.load_from_toml_str(toml_str)

def load_conversations(toml_str: str) -> dict[str, ConversationItem]:
    """Convenience function for quick loading."""
    loader = ConversationLoader()
    return loader.load_from_toml_str(toml_str)
```

### 4. Documentation Updates

#### a) Update `README.md`
Add new sections:
1. **Type Schema Utilities** section
   - How to inspect schema of your preference tables
   - Example showing `print_schema()` output
   - Use cases: API design, documentation, validation

2. **Safe Data Loading** section
   - How to use `PreferenceLoader` and `ConversationLoader`
   - Example showing validation of TOML payloads
   - Use cases: API endpoints, data migration, validation

#### b) Create new doc: `docs/type-safety.md`
Comprehensive guide covering:
- Introduction to type schema utilities
- Inspecting preference table schemas
- Generating JSON schemas for API design
- Safe loading with Pydantic TypeAdapter
- Handling validation errors
- Integration with FastAPI/other frameworks
- Complete examples with CulinaryPrefTable

#### c) Update `docs/api-reference.md`
Document all new functions and classes:
- `get_schema_info()`
- `print_schema()`
- `get_conversation_schema()`
- `PreferenceLoader` class
- `ConversationLoader` class
- Helper functions

### 5. Example Implementations

#### a) Create `examples/schema_inspection_demo.py`
Demonstrates:
- Using `show_preferences_schema()` with CulinaryPrefTable
- Getting JSON schema for API documentation
- Showing different output formats (pretty/json/python)
- Practical use case: designing an API endpoint
- CLI usage examples

```python
from tomldiary.schema import show_preferences_schema, show_conversations_schema, get_preferences_schema
from examples.culinary_prefs import CulinaryPrefTable

# Show pretty format (human-readable)
print(show_preferences_schema(CulinaryPrefTable))

# JSON format for API docs
print(show_preferences_schema(CulinaryPrefTable, format="json"))

# Python format for code reference
print(show_preferences_schema(CulinaryPrefTable, format="python"))

# Conversations schema
print(show_conversations_schema())

# Get JSON schema programmatically for FastAPI
from fastapi import FastAPI
app = FastAPI()

@app.get("/schema/preferences")
def get_pref_schema():
    return get_preferences_schema(CulinaryPrefTable)
```

#### b) Create `examples/safe_loading_demo.py`
Demonstrates:
- Loading TOML data safely with PreferenceLoader
- Validating partial data (single category)
- Handling validation errors
- Loading conversations with ConversationLoader
- Integration with existing diary system

```python
from tomldiary.loaders import PreferenceLoader, ConversationLoader
from examples.culinary_prefs import CulinaryPrefTable

# Load preferences safely
loader = PreferenceLoader(CulinaryPrefTable)

# From diary
toml_data = await diary.preferences("user123")
prefs = loader.load_from_toml_str(toml_data)

# Now you have fully typed, validated data
print(type(prefs))  # CulinaryPrefTable
print(type(prefs.favorite_foods))  # dict[str, PreferenceItem]

# Validate API payload
try:
    incoming_data = request.json  # From API
    validated = loader.validate_partial("favorite_foods", incoming_data)
except ValidationError as e:
    return {"error": str(e)}
```

#### c) Update existing examples
Add type schema demonstrations to:
- `examples/simple_example.py` - Show basic schema inspection
- `examples/dietary_preferences.py` - Show safe loading in booking agent

### 6. Testing

#### a) Create `tests/test_schema.py`
Test coverage for:
- `get_preferences_schema()` with various preference tables
- `get_conversations_schema()`
- `show_preferences_schema()` all formats (pretty/json/python)
- `show_conversations_schema()` all formats
- Edge cases: empty tables, complex nested types
- Format validation and output structure

#### b) Create `tests/test_loaders.py`
Test coverage for:
- `PreferenceLoader.load_from_toml_str()` - valid data
- `PreferenceLoader.load_from_toml_str()` - invalid data (should raise ValidationError)
- `PreferenceLoader.validate_partial()` - category validation
- `ConversationLoader.load_from_toml_str()` - valid conversations
- `ConversationLoader.load_from_toml_str()` - invalid conversations
- Loading from actual diary output
- Roundtrip: save → load → validate

#### c) Update existing tests
- Ensure all tests still pass
- Add schema validation to integration tests

### 7. Version Update

Update version to 0.3:
- `pyproject.toml` - version = "0.3.0"
- `src/tomldiary/models.py` - `_MODEL_VERSION = "0.3"` (already done)
- `CHANGELOG.md` - Add v0.3.0 section with new features

## Implementation Order

1. **Phase 1: Schema Utilities** (Priority: HIGH)
   - [ ] Create `src/tomldiary/schema.py`
   - [ ] Implement `get_preferences_schema()` and `get_conversations_schema()`
   - [ ] Implement `show_preferences_schema()` and `show_conversations_schema()`
   - [ ] Implement formatting helpers (`_format_schema_*`)
   - [ ] Add unit tests in `tests/test_schema.py`

2. **Phase 2: CLI Interface** (Priority: HIGH)
   - [ ] Create `src/tomldiary/cli.py`
   - [ ] Implement `schema preferences` command
   - [ ] Implement `schema conversations` command
   - [ ] Add CLI entry point to `pyproject.toml`
   - [ ] Add `click` dependency to `pyproject.toml`
   - [ ] Test CLI commands manually

3. **Phase 3: Safe Loading** (Priority: HIGH)
   - [ ] Create `src/tomldiary/loaders.py`
   - [ ] Implement `PreferenceLoader` class
   - [ ] Implement `ConversationLoader` class
   - [ ] Implement helper functions
   - [ ] Add unit tests in `tests/test_loaders.py`

4. **Phase 4: Examples** (Priority: MEDIUM)
   - [ ] Create `examples/schema_inspection_demo.py`
   - [ ] Create `examples/safe_loading_demo.py`
   - [ ] Update `examples/simple_example.py` with schema demo
   - [ ] Update `examples/dietary_preferences.py` with loading demo

5. **Phase 5: Documentation** (Priority: MEDIUM)
   - [ ] Create `docs/type-safety.md`
   - [ ] Update `README.md` with Type Schema section
   - [ ] Update `README.md` with Safe Loading section
   - [ ] Update `README.md` with CLI section
   - [ ] Update `docs/api-reference.md` with new APIs
   - [ ] Update `docs/getting-started.md` with schema examples

6. **Phase 6: Version & Release** (Priority: MEDIUM)
   - [ ] Update `pyproject.toml` to version 0.3.0
   - [ ] Update `CHANGELOG.md` with v0.3.0 features
   - [ ] Run full test suite
   - [ ] Manual testing of all examples
   - [ ] Test CLI commands
   - [ ] Final review

## API Interface Summary

**New Interface** (clear & symmetric):
```
schema.py (NEW)
├── show_preferences_schema()    # User-facing, display (plural)
├── show_conversations_schema()  # User-facing, display (plural)
├── get_preferences_schema()     # Programmatic access (plural)
├── get_conversations_schema()   # Programmatic access (plural)
└── _format_* helpers            # Internal formatting

cli.py (NEW)
├── schema preferences <path:Class>  # CLI command
└── schema conversations             # CLI command

loaders.py (NEW)
├── PreferenceLoader                 # Safe TOML loading with validation
├── ConversationLoader               # Safe TOML loading with validation
└── Helper functions                 # Convenience wrappers
```

**Key improvements:**
✅ Symmetric naming (preferences ↔ conversations)
✅ Plural names match file names (preferences.toml, conversations.toml)
✅ Consistent `format` parameter across all show_* functions
✅ Clear separation: show_* for display, get_* for programmatic use
✅ CLI-friendly design for easy command-line access

## Key Design Decisions

### Why Pydantic TypeAdapter?
- **Type Safety**: Runtime validation ensures TOML data matches expected types
- **Error Handling**: Clear validation errors for malformed data
- **Ecosystem**: Works seamlessly with FastAPI, Pydantic models
- **Performance**: Fast validation with minimal overhead

### Why Separate Loaders Module?
- **Separation of Concerns**: Core diary logic vs. data loading
- **Optional Usage**: Users can choose when they need validation
- **Clear API**: `PreferenceLoader` and `ConversationLoader` are self-documenting
- **Testability**: Easy to test in isolation

### Schema Formats
- **Pretty**: Human-readable, for CLI/documentation
- **JSON**: For API documentation (OpenAPI/Swagger)
- **Python**: For code generation/reference

## Success Criteria

1. **Functionality**
   - [ ] Users can inspect schema of any preference table
   - [ ] Users can generate JSON schema for API docs
   - [ ] Users can safely load/validate TOML data
   - [ ] All examples run without errors

2. **Documentation**
   - [ ] README clearly explains new utilities
   - [ ] Comprehensive guide in `docs/type-safety.md`
   - [ ] API reference updated
   - [ ] Examples demonstrate real-world use cases

3. **Testing**
   - [ ] >90% test coverage for new code
   - [ ] Integration tests with existing diary
   - [ ] All existing tests pass
   - [ ] Examples work as documentation

4. **Quality**
   - [ ] Code passes ruff linting
   - [ ] Type hints are complete
   - [ ] Docstrings follow project style
   - [ ] No breaking changes to existing API

## Migration Notes

This is a **non-breaking** addition:
- All existing code continues to work
- New utilities are opt-in
- No changes to core Diary API
- Version bump to 0.3 reflects new features, not breaking changes

## Future Enhancements (Out of Scope)

- CLI tool for schema inspection
- Automatic OpenAPI spec generation
- Schema migration utilities
- GraphQL schema generation
- TypeScript type generation

## Open Questions

1. **Should we add schema validation to Diary itself?**
   - Pro: Prevents invalid data from being stored
   - Con: Adds overhead, users may want flexibility
   - **Decision**: Keep optional, provide as utility

2. **Should we support schema evolution/migration?**
   - Pro: Helpful for production systems
   - Con: Complex, may be premature
   - **Decision**: Document manual migration, revisit in v0.4

3. **Should loaders handle _meta section?**
   - Pro: More complete data representation
   - Con: Users typically only care about preferences/conversations
   - **Decision**: Strip _meta by default, add `include_meta` flag

## Summary

This plan adds essential type safety and schema introspection to tomldiary while maintaining simplicity and backward compatibility. The new utilities address real-world needs:

1. **API Design**: Get JSON schemas for documentation
2. **Validation**: Safely load external TOML data
3. **Integration**: Type-safe integration with FastAPI/other frameworks
4. **Documentation**: Auto-generate API schemas from preference tables

The implementation is straightforward, well-tested, and fully documented with practical examples.
