"""
tomldiary - A TOML-based memory system for tracking user preferences and conversations.
"""

from .compaction import CompactionConfig, compactor_agent
from .diary import Diary, TOMLDiary
from .extractor_factory import build_extractor, extractor_agent, extractor_prompt_check
from .loaders import (
    ConversationLoader,
    PreferenceLoader,
    load_conversations,
    load_preferences,
)
from .models import ConversationItem, MemoryDeps, MetaInfo, PreferenceItem
from .pretty_print import (
    ConversationsPrinter,
    PreferencesPrinter,
    pretty_print_conversations,
    pretty_print_preferences,
)
from .schema import (
    get_conversations_schema,
    get_preferences_schema,
    show_conversations_schema,
    show_preferences_schema,
)
from .writer import MemoryWriter, shutdown_all_background_tasks

__all__ = [
    # Core
    "Diary",
    "TOMLDiary",
    "PreferenceItem",
    "ConversationItem",
    "MemoryDeps",
    "MetaInfo",
    # Compaction
    "CompactionConfig",
    "compactor_agent",
    # Extractors
    "build_extractor",
    "extractor_agent",
    "extractor_prompt_check",
    # Writer
    "MemoryWriter",
    "shutdown_all_background_tasks",
    # Pretty printing
    "PreferencesPrinter",
    "ConversationsPrinter",
    "pretty_print_preferences",
    "pretty_print_conversations",
    # Schema utilities
    "get_preferences_schema",
    "get_conversations_schema",
    "show_preferences_schema",
    "show_conversations_schema",
    # Loaders
    "PreferenceLoader",
    "ConversationLoader",
    "load_preferences",
    "load_conversations",
]
