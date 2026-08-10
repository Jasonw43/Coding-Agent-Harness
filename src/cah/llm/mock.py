"""Scripted, deterministic mock LLM for offline tests and demos."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from cah.models import Action, LLMResponse


class MockLLM:
    """Reads JSONL script steps and replays them one call at a time."""

    def __init__(self, script_path: str | Path, loop: bool = False) -> None:
        self.script_path = Path(script_path)
        self.loop = loop
        self._steps: list[dict[str, Any]] = []
        with self.script_path.open("r", encoding="utf-8") as f:
            for line_no, line in enumerate(f, start=1):
                line = line.strip()
                if not line:
                    continue
                try:
                    self._steps.append(json.loads(line))
                except json.JSONDecodeError as exc:
                    raise ValueError(
                        f"{self.script_path}:{line_no}: invalid JSON: {exc}"
                    ) from exc
        self._cursor = 0

    def complete(self, context: list[dict], available_actions: list[dict]) -> LLMResponse:
        if self._cursor >= len(self._steps):
            if self.loop:
                self._cursor = 0
            else:
                raise StopIteration("mock LLM script exhausted")
        step = self._steps[self._cursor]
        self._cursor += 1

        raw_action = step.get("action")
        if isinstance(raw_action, dict):
            action = Action(
                id=str(raw_action.get("id", "")),
                type=str(raw_action.get("type", "")),
                params=dict(raw_action.get("params", {})),
                run_id=str(raw_action.get("run_id", "")),
            )
        else:
            action = None
        return LLMResponse(text=str(step.get("text", "")), action=action, done=bool(step.get("done", False)))
