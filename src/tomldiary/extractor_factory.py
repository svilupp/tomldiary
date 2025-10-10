# pragma: no cover
import inspect
import os
import re
import textwrap
import tomllib
import warnings
from collections.abc import Callable, Sequence
from copy import deepcopy
from datetime import datetime
from pathlib import Path

import httpx
import tomli_w
from pydantic import ValidationError
from pydantic_ai import Agent, ModelHTTPError, ModelRetry, RunContext, Tool
from pydantic_ai.models import KnownModelName, Model
from pydantic_ai.models.fallback import FallbackModel
from textprompts import Prompt

from . import tools
from .models import MemoryDeps

REQUIRED_PLACEHOLDERS = {"categories_doc", "current_time"}


def _warn_missing_placeholders(prompt_text: str, required: Sequence[str]) -> None:
    """Check placeholders in the prompt and warn if required ones are missing."""

    found = set(re.findall(r"{(.*?)}", prompt_text))
    missing = set(required) - found
    if missing:  # pragma: no cover - trivial warning
        print(
            "⚠️  Missing placeholder(s) in prompt: "
            + ", ".join(sorted(missing))
            + ". This may hurt extraction results."
        )


def extractor_prompt_check(prompt: str | Path | Prompt) -> None:
    """Public helper to validate custom prompt placeholders."""

    if isinstance(prompt, Prompt):
        text = prompt.prompt
    else:
        text = Prompt.from_path(Path(prompt), meta="allow").prompt
    _warn_missing_placeholders(text, list(REQUIRED_PLACEHOLDERS))


ModelInput = Model | KnownModelName | str


def _clone_model(model: ModelInput) -> ModelInput:
    """Create a clone of a model instance when possible."""

    if isinstance(model, Model):
        try:
            return deepcopy(model)
        except TypeError:  # pragma: no cover - defensive copy fallback
            return model
    return model


def extractor_agent(
    pref_table_cls,
    model: ModelInput | None = None,
    prompt_template: str | Path | Prompt | None = None,
    fallback_retries: int = 3,
    fallback_on: Callable[[Exception], bool] | Sequence[type[Exception]] | None = None,
    *,
    model_name: ModelInput | None = None,
):  # pragma: no cover - CLI helper
    """Build an extraction agent for the given preference table class."""

    if model_name is not None:
        if model is not None:  # pragma: no cover - defensive
            msg = "Provide either 'model' or 'model_name', not both."
            raise ValueError(msg)
        warnings.warn(
            "The 'model_name' parameter is deprecated, use 'model' instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        model = model_name

    # 1. derive docs from preference table class docstring
    docs = textwrap.dedent(inspect.getdoc(pref_table_cls) or "")

    # Use default prompt template if not provided
    if prompt_template is None:
        prompt_template = Path(__file__).parent / "prompts" / "extractor_prompt.txt"

    if isinstance(prompt_template, Prompt):
        prompt_obj = prompt_template
    else:
        prompt_obj = Prompt.from_path(Path(prompt_template), meta="allow")

    extractor_prompt_check(prompt_obj)

    # Get current time rounded to nearest 15 minutes (to not break prompt caching)
    now = datetime.now()
    minutes = (now.minute // 15) * 15
    rounded_time = now.replace(minute=minutes, second=0, microsecond=0)
    current_time = rounded_time.strftime("%Y-%m-%d %H:%M")

    system_prompt = prompt_obj.prompt.format(categories_doc=docs, current_time=current_time)

    # 2. assemble tools with updated names
    tool_list: list[Tool[MemoryDeps]] = [
        Tool(tools.list_categories, takes_ctx=True),
        Tool(tools.list_preferences, takes_ctx=True),
        Tool(tools.list_conversation_summary, takes_ctx=True),
        Tool(tools.upsert_preference, takes_ctx=True),
        Tool(tools.forget_preference, takes_ctx=True),
        Tool(tools.update_conversation_summary, takes_ctx=True),
    ]

    # 3. build model with fallback retries
    if fallback_on is None:
        fallback_on = (ModelHTTPError, ValidationError, httpx.TimeoutException)

    if (
        isinstance(fallback_on, Sequence)
        and not isinstance(fallback_on, str)
        and not callable(fallback_on)
    ):
        fallback_on_param: Callable[[Exception], bool] | tuple[type[Exception], ...] = tuple(
            fallback_on
        )
    else:
        fallback_on_param = fallback_on

    model_input: ModelInput = model or os.getenv("EXTRACTOR_MODEL", "openai:gpt-5-mini")  # type: ignore[assignment]

    fallback_model: ModelInput | FallbackModel
    if fallback_retries > 0:
        fallback_model = FallbackModel(
            model_input,
            *(_clone_model(model_input) for _ in range(fallback_retries)),
            fallback_on=fallback_on_param,
        )
    else:
        fallback_model = model_input

    agent = Agent(
        fallback_model,
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

    return agent


def build_extractor(
    pref_table_cls,
    model_name: str | None = None,
    prompt_template_path: str | Path | Prompt | None = None,
):  # pragma: no cover - legacy alias
    """Backward compatible alias for :func:`extractor_agent`."""

    return extractor_agent(
        pref_table_cls,
        model=model_name,
        prompt_template=prompt_template_path,
    )
