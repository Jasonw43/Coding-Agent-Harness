import shlex
from pathlib import Path

from cah.models import Action, GuardrailDecision


class CommandGuardrail:
    """Check shell commands against deny patterns and allow prefixes."""

    def __init__(self, deny_patterns: list[str], allow_prefixes: list[str]) -> None:
        self.deny_patterns = deny_patterns
        self.allow_prefixes = allow_prefixes

    def check(self, action: Action, workspace: Path) -> GuardrailDecision:
        if action.type != "shell":
            return GuardrailDecision(verdict="SAFE")

        raw_command = action.params.get("command", "")
        # Tokenize and rejoin for normalised matching
        try:
            tokens = shlex.split(raw_command)
        except ValueError:
            return GuardrailDecision(
                verdict="REQUIRE_APPROVAL",
                reason="Unparseable command (ambiguous syntax)",
                risk_level="medium",
                action_id=action.id,
            )
        normalised = " ".join(tokens)

        for pattern in self.deny_patterns:
            if pattern in normalised:
                return GuardrailDecision(
                    verdict="BLOCKED",
                    reason=f"Command matches deny pattern: {pattern!r}",
                    risk_level="high",
                    action_id=action.id,
                )

        for prefix in self.allow_prefixes:
            if normalised.startswith(prefix):
                return GuardrailDecision(
                    verdict="SAFE",
                    reason="Command matches allow prefix",
                    action_id=action.id,
                )

        # Default: conservative — require human approval
        return GuardrailDecision(
            verdict="REQUIRE_APPROVAL",
            reason="Command not explicitly allowed or denied",
            risk_level="medium",
            action_id=action.id,
        )
