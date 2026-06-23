import re
from datetime import UTC, datetime

import httpx
import pytest
from pydantic import BaseModel, ValidationError
from pydantic_ai import ModelHTTPError
from pydantic_ai.messages import ModelRequest, SystemPromptPart
from pydantic_ai.models.fallback import FallbackModel
from pydantic_ai.models.test import TestModel
from textprompts import Prompt

from tomldiary.extractor_factory import (
    _round_current_time,
    extractor_agent,
    extractor_prompt_check,
)
from tomldiary.models import MemoryDeps

from .test_user_pref_table import MyPrefTable


def _make_deps(context_now: datetime | None = None) -> MemoryDeps:
    """Build a minimal MemoryDeps for exercising the extractor agent."""
    prefs = {"_meta": {"version": "0.3", "schema_name": "MyPrefTable"}, "preferences": {}}
    convs = {"_meta": {"version": "0.3", "schema_name": "MyPrefTable"}, "conversations": {}}
    return MemoryDeps(
        prefs=prefs,
        convs=convs,
        allowed_cats=["like", "dislike", "allergy", "habit", "about"],
        schema_name="MyPrefTable",
        session_id="session1",
        context_now=context_now,
    )


def _captured_system_prompt(result) -> str:
    """Extract the system prompt content from a completed agent run."""
    for message in result.all_messages():
        if isinstance(message, ModelRequest):
            for part in message.parts:
                if isinstance(part, SystemPromptPart):
                    return part.content
    raise AssertionError("No system prompt found in run messages")


def test_fallback_model_creation(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test")
    agent = extractor_agent(
        MyPrefTable,
        model="openai:gpt-4o-mini",
        fallback_retries=2,
    )
    assert isinstance(agent.model, FallbackModel)
    assert len(agent.model.models) == 3
    assert agent.model._fallback_on(ModelHTTPError(500, "test"))

    class M(BaseModel):
        a: int

    try:
        M(a="x")
    except ValidationError as e:  # pragma: no cover - executed for side effect
        assert agent.model._fallback_on(e)

    assert agent.model._fallback_on(httpx.TimeoutException("boom"))


async def test_prompt_object_handled(tmp_path, capsys):
    prompt_path = tmp_path / "prompt.txt"
    prompt_path.write_text("Test {categories_doc} {current_time}")
    prompt_obj = Prompt.from_path(prompt_path, meta="allow")
    agent = extractor_agent(MyPrefTable, model=TestModel(), prompt_template=prompt_obj)
    # The system prompt is now dynamic: placeholders are resolved per run, not at build time.
    result = await agent.run("hi", deps=_make_deps())
    system_prompt = _captured_system_prompt(result)
    assert "{categories_doc}" not in system_prompt
    assert "{current_time}" not in system_prompt
    assert capsys.readouterr().out == ""


def test_missing_placeholder_warning(tmp_path, capsys):
    prompt_path = tmp_path / "prompt.txt"
    prompt_path.write_text("No placeholders here")
    extractor_agent(MyPrefTable, model=TestModel(), prompt_template=prompt_path)
    captured = capsys.readouterr()
    assert "Missing placeholder" in captured.out
    assert "categories_doc" in captured.out
    assert "current_time" in captured.out


def test_prompt_check_warns(tmp_path, capsys):
    prompt_path = tmp_path / "prompt.txt"
    prompt_path.write_text("No placeholders here")
    extractor_prompt_check(prompt_path)
    output = capsys.readouterr().out
    assert "Missing placeholder" in output
    assert "categories_doc" in output
    assert "current_time" in output


def test_prompt_check_no_warning_when_valid(tmp_path, capsys):
    prompt_path = tmp_path / "prompt.txt"
    prompt_path.write_text("Valid prompt with {categories_doc} and {current_time}")
    extractor_prompt_check(prompt_path)
    output = capsys.readouterr().out
    assert output == ""  # No warning should be printed


def test_env_model_default(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test")
    monkeypatch.setenv("EXTRACTOR_MODEL", "openai:gpt-4o-mini")
    agent = extractor_agent(MyPrefTable, fallback_retries=1)
    assert agent.model.models[0].model_name == "gpt-4o-mini"
    monkeypatch.delenv("EXTRACTOR_MODEL", raising=False)


@pytest.mark.parametrize(
    ("hour", "minute", "expected"),
    [
        (9, 7, "09:00"),
        (9, 0, "09:00"),
        (9, 14, "09:00"),
        (9, 15, "09:15"),
        (9, 29, "09:15"),
        (9, 30, "09:30"),
        (9, 52, "09:45"),
        (23, 59, "23:45"),
    ],
)
def test_round_current_time(hour, minute, expected):
    now = datetime(2030, 1, 2, hour, minute, 33, 123, tzinfo=UTC)
    rounded = _round_current_time(now)
    assert rounded == f"2030-01-02 {expected}"


async def test_current_time_in_prompt():
    agent = extractor_agent(MyPrefTable, model=TestModel())
    # The prompt is dynamic; resolve it by running the agent.
    result = await agent.run("hi", deps=_make_deps())
    system_prompt = _captured_system_prompt(result)
    # Check that current_time placeholder was replaced with a timestamp
    assert "{current_time}" not in system_prompt
    # Check that a date-time pattern exists in the prompt
    match = re.search(r"\d{4}-\d{2}-\d{2} \d{2}:(\d{2})", system_prompt)
    assert match is not None
    # Check that minutes are rounded to 15-minute intervals
    minutes = int(match.group(1))
    assert minutes in [0, 15, 30, 45]


async def test_context_now_override_in_prompt():
    """An injected context_now drives the timestamp fresh per request (rounded)."""
    agent = extractor_agent(MyPrefTable, model=TestModel())
    deps = _make_deps(context_now=datetime(2030, 1, 2, 9, 7, tzinfo=UTC))
    result = await agent.run("hi", deps=deps)
    system_prompt = _captured_system_prompt(result)
    assert "2030-01-02 09:00" in system_prompt


async def test_context_now_override_varies_per_request():
    """Two runs with different context_now values yield different prompt timestamps."""
    agent = extractor_agent(MyPrefTable, model=TestModel())

    result_a = await agent.run(
        "hi", deps=_make_deps(context_now=datetime(2030, 1, 2, 9, 7, tzinfo=UTC))
    )
    result_b = await agent.run(
        "hi", deps=_make_deps(context_now=datetime(2031, 6, 3, 14, 52, tzinfo=UTC))
    )

    prompt_a = _captured_system_prompt(result_a)
    prompt_b = _captured_system_prompt(result_b)

    assert "2030-01-02 09:00" in prompt_a
    assert "2031-06-03 14:45" in prompt_b
    assert prompt_a != prompt_b
