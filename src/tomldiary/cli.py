"""Command-line interface for tomldiary.

Provides CLI commands for schema inspection and other utilities.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import click

from .schema import show_conversations_schema, show_preferences_schema


@click.group()
def cli():
    """tomldiary - TOML-based memory system for AI agents.

    Use 'tomldiary COMMAND --help' for more information on a specific command.
    """
    pass


@cli.group()
def schema():
    """Schema inspection utilities.

    View type schemas for preference tables and conversations to help with
    API design, documentation, and type-safe data handling.
    """
    pass


@schema.command("preferences")
@click.argument("class_path")
@click.option(
    "--format",
    "-f",
    type=click.Choice(["pretty", "json", "python"]),
    default="pretty",
    help="Output format (default: pretty)",
)
def show_prefs_schema(class_path: str, format: str):
    """Show preference table schema.

    CLASS_PATH format: path/to/file.py:ClassName

    Examples:

        \b
        # Pretty tree format (human-readable)
        tomldiary schema preferences examples/culinary_prefs.py:CulinaryPrefTable

        \b
        # JSON schema (for API documentation)
        tomldiary schema preferences examples/culinary_prefs.py:CulinaryPrefTable -f json

        \b
        # Python type hints (for code reference)
        tomldiary schema preferences examples/culinary_prefs.py:CulinaryPrefTable -f python
    """
    try:
        # Parse class_path
        if ":" not in class_path:
            click.echo("Error: CLASS_PATH must be in format 'path/to/file.py:ClassName'", err=True)
            sys.exit(1)

        file_path_str, class_name = class_path.split(":", 1)
        file_path = Path(file_path_str)

        if not file_path.exists():
            click.echo(f"Error: File not found: {file_path}", err=True)
            sys.exit(1)

        # Import the module
        spec = importlib.util.spec_from_file_location("_tomldiary_temp_module", file_path)
        if spec is None or spec.loader is None:
            click.echo(f"Error: Could not load module from {file_path}", err=True)
            sys.exit(1)

        module = importlib.util.module_from_spec(spec)
        sys.modules["_tomldiary_temp_module"] = module
        spec.loader.exec_module(module)

        # Get the class
        if not hasattr(module, class_name):
            click.echo(
                f"Error: Class '{class_name}' not found in {file_path}",
                err=True,
            )
            sys.exit(1)

        pref_table_cls = getattr(module, class_name)

        # Show schema
        output = show_preferences_schema(pref_table_cls, format=format)
        click.echo(output)

    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@schema.command("conversations")
@click.option(
    "--format",
    "-f",
    type=click.Choice(["pretty", "json", "python"]),
    default="pretty",
    help="Output format (default: pretty)",
)
def show_convs_schema(format: str):
    """Show conversation schema.

    The conversation schema is standardized across all tomldiary instances.

    Examples:

        \b
        # Pretty tree format (human-readable)
        tomldiary schema conversations

        \b
        # JSON schema (for API documentation)
        tomldiary schema conversations -f json

        \b
        # Python type hints (for code reference)
        tomldiary schema conversations -f python
    """
    try:
        output = show_conversations_schema(format=format)
        click.echo(output)
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


if __name__ == "__main__":
    cli()
