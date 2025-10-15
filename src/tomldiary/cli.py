"""Command-line interface for tomldiary.

Provides CLI commands for schema inspection and other utilities.
"""

from __future__ import annotations

import argparse
import importlib.util
import sys
from pathlib import Path

from .schema import show_conversations_schema, show_preferences_schema


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        prog="tomldiary",
        description="tomldiary - TOML-based memory system for AI agents",
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Schema command
    schema_parser = subparsers.add_parser("schema", help="Schema inspection utilities")
    schema_subparsers = schema_parser.add_subparsers(dest="schema_command", help="Schema commands")

    # Schema preferences command
    prefs_parser = schema_subparsers.add_parser("preferences", help="Show preference table schema")
    prefs_parser.add_argument(
        "class_path",
        help="Path to preference table class (format: path/to/file.py:ClassName)",
    )
    prefs_parser.add_argument(
        "-f",
        "--format",
        choices=["pretty", "json", "python"],
        default="pretty",
        help="Output format (default: pretty)",
    )

    # Schema conversations command
    convs_parser = schema_subparsers.add_parser("conversations", help="Show conversation schema")
    convs_parser.add_argument(
        "-f",
        "--format",
        choices=["pretty", "json", "python"],
        default="pretty",
        help="Output format (default: pretty)",
    )

    args = parser.parse_args()

    # Handle commands
    if args.command == "schema":
        if args.schema_command == "preferences":
            _handle_preferences_schema(args.class_path, args.format)
        elif args.schema_command == "conversations":
            _handle_conversations_schema(args.format)
        else:
            schema_parser.print_help()
            sys.exit(1)
    else:
        parser.print_help()
        sys.exit(1)


def _handle_preferences_schema(class_path: str, format: str):
    """Handle preferences schema command."""
    from typing import Literal, cast

    format_typed = cast(Literal["pretty", "json", "python"], format)
    try:
        # Parse class_path
        if ":" not in class_path:
            print(
                "Error: CLASS_PATH must be in format 'path/to/file.py:ClassName'",
                file=sys.stderr,
            )
            sys.exit(1)

        file_path_str, class_name = class_path.split(":", 1)
        file_path = Path(file_path_str)

        if not file_path.exists():
            print(f"Error: File not found: {file_path}", file=sys.stderr)
            sys.exit(1)

        # Import the module
        spec = importlib.util.spec_from_file_location("_tomldiary_temp_module", file_path)
        if spec is None or spec.loader is None:
            print(f"Error: Could not load module from {file_path}", file=sys.stderr)
            sys.exit(1)

        module = importlib.util.module_from_spec(spec)
        sys.modules["_tomldiary_temp_module"] = module
        spec.loader.exec_module(module)

        # Get the class
        if not hasattr(module, class_name):
            print(
                f"Error: Class '{class_name}' not found in {file_path}",
                file=sys.stderr,
            )
            sys.exit(1)

        pref_table_cls = getattr(module, class_name)

        # Show schema
        output = show_preferences_schema(pref_table_cls, format=format_typed)
        print(output)

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


def _handle_conversations_schema(format: str):
    """Handle conversations schema command."""
    from typing import Literal, cast

    format_typed = cast(Literal["pretty", "json", "python"], format)
    try:
        output = show_conversations_schema(format=format_typed)
        print(output)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


def cli():
    """CLI entry point for backwards compatibility."""
    main()


if __name__ == "__main__":
    main()
