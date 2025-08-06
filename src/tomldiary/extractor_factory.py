# pragma: no cover
import inspect
import textwrap
import tomllib
from pathlib import Path

import tomli_w
from pydantic_ai import Agent, ModelRetry, RunContext, Tool
from textprompts import Prompt

from . import tools
from .models import MemoryDeps
from .utils import extract_categories_from_schema


def build_extractor(
    pref_table_cls,
    model_name="openai:gpt-4.1-mini",
    prompt_template_path=None,
):  # pragma: no cover - CLI helper
    """Build an extraction agent for the given preference table class."""

    # 1. derive docs & use utility to get categories
    cats = extract_categories_from_schema(pref_table_cls)
    docs = textwrap.dedent(inspect.getdoc(pref_table_cls) or "")

    # Use default prompt template path if not provided
    if prompt_template_path is None:
        prompt_template_path = Path(__file__).parent / "prompts" / "extractor_prompt.txt"

    prompt_template = Prompt.from_path(prompt_template_path, meta="allow").prompt
    system_prompt = prompt_template.format(
        categories_doc=docs,
    )

    # 2. assemble tools with updated names
    tool_list = [
        Tool(tools.list_categories, takes_ctx=True),
        Tool(tools.list_preferences, takes_ctx=True),
        Tool(tools.list_conversation_summary, takes_ctx=True),
        Tool(tools.upsert_preference, takes_ctx=True),
        Tool(tools.forget_preference, takes_ctx=True),
        Tool(tools.update_conversation_summary, takes_ctx=True),
    ]

    # 3. create agent
    agent = Agent(
        model_name,
        deps_type=MemoryDeps,
        tools=tool_list,
        system_prompt=system_prompt,
    )

    # 4. TOML round-trip validator
    @agent.output_validator
    async def toml_roundtrip(
        ctx: RunContext[MemoryDeps], output: str
    ) -> str:  # pragma: no cover - simple validator
        try:
            tomllib.loads(tomli_w.dumps(ctx.deps.prefs))
        except tomllib.TOMLDecodeError as e:
            raise ModelRetry(f"Preferences TOML invalid after edits: {e}") from e
        try:
            tomllib.loads(tomli_w.dumps(ctx.deps.convs))
        except tomllib.TOMLDecodeError as e:
            raise ModelRetry(f"Conversation Summaries TOML invalid after edits: {e}") from e
        return output

    return agent, cats
