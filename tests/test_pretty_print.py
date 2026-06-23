"""Tests for tomldiary pretty printing utilities."""

from datetime import UTC, datetime

from tomldiary.pretty_print import ConversationsPrinter


def test_format_datetime_bare_datetime_does_not_raise():
    """Bare TOML datetimes parse into datetime objects, not strings."""
    printer = ConversationsPrinter()
    dt = datetime(2024, 1, 15, 14, 30, tzinfo=UTC)

    result = printer._format_datetime(dt)

    assert isinstance(result, str)
    assert result == "Jan 15, 2024 02:30 PM"


def test_format_datetime_iso_string_unchanged():
    """The normal ISO-string path keeps its existing output format."""
    printer = ConversationsPrinter()

    result = printer._format_datetime("2024-01-15T14:30:00+00:00")

    assert result == "Jan 15, 2024 02:30 PM"


def test_format_datetime_bare_matches_iso_string():
    """A bare datetime formats identically to the equivalent ISO string."""
    printer = ConversationsPrinter()
    dt = datetime(2024, 1, 15, 14, 30, tzinfo=UTC)

    assert printer._format_datetime(dt) == printer._format_datetime(dt.isoformat())


def test_format_conversations_with_bare_datetime_does_not_raise():
    """format_conversations on a dict with a datetime _updated must not crash."""
    printer = ConversationsPrinter()
    convs = {
        "session-1": {
            "summary": "A chat",
            "_updated": datetime(2024, 1, 15, 14, 30, tzinfo=UTC),
        }
    }

    output = printer.format_conversations(convs)

    assert isinstance(output, str)
    assert "session-1" in output
    assert "Jan 15, 2024 02:30 PM" in output
