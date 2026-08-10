"""Guardrail pipeline: run checks in order, fail closed on errors."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from cah.models import Action, GuardrailDecision


class Guardrail(Protocol):
    def check(self, action: Action, workspace: Path | None) -> GuardrailDecision: ...


class GuardrailPipeline:
    """Run guardrails in order; the first non-SAFE verdict wins."""

    def __init__(self, guards: list[Guardrail]) -> None:
        self.guards = guards

    def check(self, action: Action, workspace: Path | None) -> GuardrailDecision:
        for guard in self.guards:
            try:
                decision = guard.check(action, workspace)
            except Exception as exc:  # fail-closed: guardrail bugs must not let actions through
                return GuardrailDecision(
                    verdict="BLOCKED",
                    reason=f"Guardrail error: {exc!r}",
                    risk_level="high",
                    action_id=action.id,
                )
            if decision.verdict != "SAFE":
                return decision
        return GuardrailDecision(verdict="SAFE", action_id=action.id)
