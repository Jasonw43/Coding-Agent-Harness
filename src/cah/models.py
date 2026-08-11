"""Core data models for the Coding Agent Harness."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Action:
    """An executable action proposed by the LLM."""

    id: str
    type: str
    params: dict[str, Any]
    run_id: str


@dataclass
class ToolResult:
    """Outcome of executing a tool/action."""

    ok: bool
    output: str
    meta: dict[str, Any] = field(default_factory=dict)


@dataclass
class GuardrailDecision:
    """Verdict of a guardrail over a proposed action."""

    verdict: str
    reason: str = ""
    risk_level: str = "low"
    action_id: str = ""


@dataclass
class Feedback:
    """Feedback to feed back into the agent loop (e.g. test results)."""

    ok: bool
    failures: list[str]
    summary: str


@dataclass
class LLMResponse:
    """Structured response from an LLM client."""

    text: str
    action: Action | None
    done: bool
    actions: list[Action] | None = None


@dataclass
class RunResult:
    """Snapshot of an agent run."""

    run_id: str
    status: str
    steps: int
    actions_log: list[Action]
    final_output: str
