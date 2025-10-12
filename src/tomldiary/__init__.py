"""
tomldiary - A TOML-based memory system for tracking user preferences and conversations.
"""

from .compaction import CompactionConfig, compactor_agent
from .diary import Diary, TOMLDiary
from .extractor_factory import build_extractor, extractor_agent, extractor_prompt_check
from .models import ConversationItem, MemoryDeps, MetaInfo, PreferenceItem
from .pretty_print import (
    ConversationsPrinter,
    PreferencesPrinter,
    pretty_print_conversations,
    pretty_print_preferences,
)
from .writer import MemoryWriter, shutdown_all_background_tasks

__all__ = [
    "Diary",
    "TOMLDiary",
    "PreferenceItem",
    "ConversationItem",
    "MemoryDeps",
    "MetaInfo",
    "CompactionConfig",
    "compactor_agent",
    "build_extractor",
    "extractor_agent",
    "extractor_prompt_check",
    "MemoryWriter",
    "shutdown_all_background_tasks",
    "PreferencesPrinter",
    "ConversationsPrinter",
    "pretty_print_preferences",
    "pretty_print_conversations",
]
