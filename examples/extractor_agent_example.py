#!/usr/bin/env python3
"""Demonstrate using extractor_agent and manual agent setup."""

from pathlib import Path

from pydantic_ai import Agent
from textprompts import Prompt
from tomldiary import Diary, extractor_agent, extractor_prompt_check
from tomldiary.backends import LocalBackend

from culinary_prefs import CulinaryPrefTable

import dotenv
dotenv.load_dotenv()


def main() -> None:
    prompt_path = Path(__file__).parent.parent / "src/tomldiary/prompts/extractor_prompt.txt"

    # Check the prompt for required placeholders
    extractor_prompt_check(prompt_path)

    # Automatically build agent with fallback support, we load the prompt via textprompts package
    agent = extractor_agent(CulinaryPrefTable, prompt_template=prompt_path)
    diary = Diary(LocalBackend(Path("memory_extractor")), CulinaryPrefTable, agent=agent)

    # Manual pydantic-ai Agent using textprompts directly
    prompt_obj = Prompt.from_path(prompt_path, meta="allow")
    manual = Agent("openai:gpt-5-mini", system_prompt=prompt_obj.prompt)
    manual_diary = Diary(
        LocalBackend(Path("memory_manual")),
        CulinaryPrefTable,
        agent=manual,
    )

    # Use diaries as needed... (omitted for brevity)
    print("Extractor agent ready:", bool(diary))
    print("Manual agent ready:", bool(manual_diary))


if __name__ == "__main__":
    main()
