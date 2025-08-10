import httpx
from pydantic import BaseModel, ValidationError
from pydantic_ai import ModelHTTPError
from pydantic_ai.models.fallback import FallbackModel
from textprompts import Prompt

from src.tomldiary.extractor_factory import (
    extractor_agent,
    extractor_prompt_check,
)
from tests.test_user_pref_table import MyPrefTable


def test_fallback_model_creation():
    agent = extractor_agent(MyPrefTable, model_name="test", fallback_retries=2)
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


def test_prompt_object_handled(tmp_path, capsys):
    prompt_path = tmp_path / "prompt.txt"
    prompt_path.write_text("Test {categories_doc} {current_time}")
    prompt_obj = Prompt.from_path(prompt_path, meta="allow")
    agent = extractor_agent(MyPrefTable, model_name="test", prompt_template=prompt_obj)
    assert "{categories_doc}" not in agent._system_prompts[0]
    assert "{current_time}" not in agent._system_prompts[0]
    assert capsys.readouterr().out == ""


def test_missing_placeholder_warning(tmp_path, capsys):
    prompt_path = tmp_path / "prompt.txt"
    prompt_path.write_text("No placeholders here")
    extractor_agent(MyPrefTable, model_name="test", prompt_template=prompt_path)
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


def test_env_model_default(monkeypatch):
    monkeypatch.setenv("EXTRACTOR_MODEL", "test")
    agent = extractor_agent(MyPrefTable, fallback_retries=1)
    assert agent.model.models[0].model_name == "test"
    monkeypatch.delenv("EXTRACTOR_MODEL", raising=False)


def test_current_time_in_prompt():
    agent = extractor_agent(MyPrefTable, model_name="test")
    system_prompt = agent._system_prompts[0]
    # Check that current_time placeholder was replaced with a timestamp
    assert "{current_time}" not in system_prompt
    # Check that a date-time pattern exists in the prompt
    import re
    match = re.search(r"\d{4}-\d{2}-\d{2} \d{2}:(\d{2})", system_prompt)
    assert match is not None
    # Check that minutes are rounded to 15-minute intervals
    minutes = int(match.group(1))
    assert minutes in [0, 15, 30, 45]
