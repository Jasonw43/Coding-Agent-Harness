"""LLM client abstraction."""

from __future__ import annotations

from typing import Protocol

from cah.models import LLMResponse


class LLMClient(Protocol):
    """Contract for any LLM backend used by the harness loop."""

    def complete(self, context: list[dict], available_actions: list[dict]) -> LLMResponse:
        """Return a structured response given conversation context."""
        ...
