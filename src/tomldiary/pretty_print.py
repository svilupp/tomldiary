"""Pretty printing utilities for TOMLDiary data."""

import tomllib
from datetime import datetime
from typing import Any


class BasePrettyPrinter:
    """Base class for pretty printing utilities."""

    def __init__(self, indent_size: int = 2, max_width: int = 80):
        self.indent_size = indent_size
        self.max_width = max_width
        self._indent_char = " "

    def _indent(self, level: int) -> str:
        """Generate indentation string."""
        return self._indent_char * (self.indent_size * level)

    def _format_datetime(self, iso_string: str) -> str:
        """Format ISO datetime string to human-friendly format."""
        try:
            dt = datetime.fromisoformat(iso_string.replace("Z", "+00:00"))
            return dt.strftime("%b %d, %Y %I:%M %p")
        except (ValueError, AttributeError):
            return iso_string


class PreferencesPrinter(BasePrettyPrinter):
    """Pretty printer for preferences data."""

    def __init__(
        self,
        indent_size: int = 2,
        max_width: int = 80,
        fields: set[str] | None = None,
        show_count: bool = True,
        show_timestamps: bool = True,
    ):
        super().__init__(indent_size, max_width)
        self.fields = fields or {"text", "contexts"}
        self.show_count = show_count
        self.show_timestamps = show_timestamps

    def format_preferences(self, prefs_toml: str, skip_metadata: bool = True) -> str:
        """Format preferences TOML string into pretty output."""
        if not prefs_toml:
            return "No preferences found."

        prefs_data = tomllib.loads(prefs_toml)
        preferences = prefs_data.get("preferences", {})

        if not preferences:
            return "No preferences found."

        output = []

        if not skip_metadata and "_meta" in prefs_data:
            meta = prefs_data["_meta"]
            output.append("Metadata:")
            output.append(f"{self._indent(1)}Version: {meta.get('version', 'unknown')}")
            output.append(f"{self._indent(1)}Schema: {meta.get('schema_name', 'unknown')}")
            output.append("")

        output.append("preferences:")

        for category, items in preferences.items():
            if not items:
                continue

            output.append(f"{self._indent(1)}{category}:")

            # Sort items by updated timestamp (newest first)
            sorted_items = sorted(
                items.items(), key=lambda x: x[1].get("_updated", ""), reverse=True
            )

            for item_id, details in sorted_items:
                # Header with ID and timestamp
                header_parts = [item_id]
                if self.show_timestamps and "_updated" in details:
                    header_parts.append(f"(Updated: {self._format_datetime(details['_updated'])})")

                output.append(f"{self._indent(2)}{' '.join(header_parts)}")

                # Text content
                if "text" in self.fields and "text" in details:
                    text = details["text"]
                    if self.show_count and "_count" in details and details["_count"] > 1:
                        text += f" ({details['_count']}x)"
                    output.append(f"{self._indent(3)}{text}")

                # Contexts
                if "contexts" in self.fields and details.get("contexts"):
                    contexts_str = ", ".join(details["contexts"])
                    output.append(f"{self._indent(3)}contexts: {contexts_str}")

                output.append("")  # Empty line between items

        return "\n".join(output).rstrip()


class ConversationsPrinter(BasePrettyPrinter):
    """Pretty printer for conversations data."""

    def __init__(
        self,
        indent_size: int = 2,
        max_width: int = 80,
        fields: set[str] | None = None,
        show_turns: bool = True,
    ):
        super().__init__(indent_size, max_width)
        self.fields = fields or {"summary", "keywords"}
        self.show_turns = show_turns

    def format_conversations(self, convs_dict: dict[str, Any], skip_metadata: bool = True) -> str:
        """Format conversations dictionary into pretty output."""
        if not convs_dict:
            return "No conversations found."

        # Filter out metadata if requested
        conv_entries = {
            k: v
            for k, v in convs_dict.items()
            if skip_metadata and k != "_meta" or not skip_metadata
        }

        if not conv_entries or (len(conv_entries) == 1 and "_meta" in conv_entries):
            return "No conversations found."

        output = []

        if not skip_metadata and "_meta" in convs_dict:
            meta = convs_dict["_meta"]
            output.append("Metadata:")
            output.append(f"{self._indent(1)}Version: {meta.get('version', 'unknown')}")
            output.append(f"{self._indent(1)}Schema: {meta.get('schema_name', 'unknown')}")
            output.append("")

        # Sort by updated timestamp (newest first)
        sorted_convs = sorted(
            [(k, v) for k, v in conv_entries.items() if k != "_meta"],
            key=lambda x: x[1].get("_updated", x[1].get("_created", "")),
            reverse=True,
        )

        for session_id, conv in sorted_convs:
            # Header with session ID and timestamp
            timestamp = conv.get("_updated", conv.get("_created", ""))
            header = f"{session_id}"
            if timestamp:
                header += f" (Updated: {self._format_datetime(timestamp)})"

            output.append(header)

            # Summary
            if "summary" in self.fields and conv.get("summary"):
                summary = conv["summary"]
                # Wrap long summaries
                if len(summary) > self.max_width - self.indent_size:
                    summary = summary[: self.max_width - self.indent_size - 3] + "..."
                output.append(f"{self._indent(1)}{summary}")

            # Keywords
            if "keywords" in self.fields and conv.get("keywords"):
                keywords_str = ", ".join(conv["keywords"])
                output.append(f"{self._indent(1)}keywords: {keywords_str}")

            # Turn count
            if self.show_turns and "_turns" in conv:
                output.append(f"{self._indent(1)}turns: {conv['_turns']}")

            output.append("")  # Empty line between conversations

        return "\n".join(output).rstrip()


def pretty_print_preferences(prefs_toml: str, skip_metadata: bool = True, **kwargs) -> str:
    """Convenience function to pretty print preferences."""
    printer = PreferencesPrinter(**kwargs)
    return printer.format_preferences(prefs_toml, skip_metadata=skip_metadata)


def pretty_print_conversations(
    convs_dict: dict[str, Any], skip_metadata: bool = True, **kwargs
) -> str:
    """Convenience function to pretty print conversations."""
    printer = ConversationsPrinter(**kwargs)
    return printer.format_conversations(convs_dict, skip_metadata=skip_metadata)
