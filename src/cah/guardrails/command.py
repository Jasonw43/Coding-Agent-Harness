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
        lowered = [t.lower() for t in tokens]

        for pattern in self.deny_patterns:
            if self._tokens_contain(lowered, pattern):
                return GuardrailDecision(
                    verdict="BLOCKED",
                    reason=f"Command matches deny pattern: {pattern!r}",
                    risk_level="high",
                    action_id=action.id,
                )

        for prefix in self.allow_prefixes:
            if self._tokens_start_with(lowered, prefix):
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

    @staticmethod
    def _tokenize(pattern: str) -> list[str]:
        try:
            return [t.lower() for t in shlex.split(pattern)]
        except ValueError:
            return [pattern.lower()]

    @classmethod
    def _tokens_contain(cls, tokens: list[str], pattern: str) -> bool:
        """Token-level deny matching (avoids substring false positives)."""
        pat = cls._tokenize(pattern)
        if not pat:
            return False
        if len(pat) == 1:
            return pat[0] in tokens
        # contiguous subsequence match for multi-word patterns like "rm -rf"
        return any(
            tokens[i : i + len(pat)] == pat for i in range(len(tokens) - len(pat) + 1)
        )

    @classmethod
    def _tokens_start_with(cls, tokens: list[str], prefix: str) -> bool:
        pat = cls._tokenize(prefix)
        if not pat:
            return True  # empty prefix allows everything (matches old startswith(""))
        return tokens[: len(pat)] == pat
