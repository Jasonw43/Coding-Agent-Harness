"""Tool-level guardrail: which tools may run and whether writes are allowed."""

from __future__ import annotations

from pathlib import Path

from cah.models import Action, GuardrailDecision

WRITE_TOOL_TYPES = frozenset({"write_file", "shell"})


class ToolGuardrail:
    """Restrict available tools and enforce read-only mode."""

    def __init__(self, tools_enabled: list[str], read_only: bool = False) -> None:
        self.tools_enabled = set(tools_enabled)
        self.read_only = read_only

    def check(self, action: Action, workspace: Path | None) -> GuardrailDecision:
        if action.type not in self.tools_enabled:
            return GuardrailDecision(
                verdict="BLOCKED",
                reason=f"Tool '{action.type}' is not enabled",
                risk_level="medium",
                action_id=action.id,
            )
        if self.read_only and action.type in WRITE_TOOL_TYPES:
            return GuardrailDecision(
                verdict="BLOCKED",
                reason="Read-only mode forbids write actions",
                risk_level="high",
                action_id=action.id,
            )
        return GuardrailDecision(verdict="SAFE", action_id=action.id)
