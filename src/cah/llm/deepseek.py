"""DeepSeek LLM client (OpenAI-compatible chat completions) via httpx."""

from __future__ import annotations

import httpx

from cah.models import LLMResponse


class LLMError(Exception):
    """Raised when the LLM provider cannot be reached."""


class DeepSeekLLM:
    """Minimal real-LLM client.

    Current limitation: returns the model's final text (done=true) without
    tool-use parsing; deterministic mock-driven behavior is the tested path.
    """

    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.deepseek.com",
        model: str = "deepseek-chat",
        timeout_s: int = 60,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.model = model
        self._client = httpx.Client(
            base_url=base_url,
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=timeout_s,
            transport=transport,
        )

    def complete(self, context: list[dict], available_actions: list[str]) -> LLMResponse:
        messages = [
            {"role": m.get("role", "user"), "content": str(m.get("content", ""))}
            for m in context
        ]
        payload = {"model": self.model, "messages": messages}
        try:
            resp = self._client.post("/chat/completions", json=payload)
            resp.raise_for_status()
            data = resp.json()
        except httpx.HTTPError as exc:
            raise LLMError(f"DeepSeek API error: {exc}") from exc
        text = data["choices"][0]["message"]["content"]
        return LLMResponse(text=text, action=None, done=True)
