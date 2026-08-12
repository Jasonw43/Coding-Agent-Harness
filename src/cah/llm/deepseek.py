"""DeepSeek LLM client (OpenAI-compatible chat completions) via httpx."""

from __future__ import annotations

import httpx
import json
import time

from cah.models import Action, LLMResponse


class LLMError(Exception):
    """Raised when the LLM provider cannot be reached."""


class DeepSeekLLM:
    """Minimal real-LLM client.

    Returns raw text with done=False; the harness loop parses the tool
    protocol (JSON actions) and decides when the task is complete.
    """

    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.deepseek.com",
        model: str = "deepseek-chat",
        timeout_s: int = 60,
        transport: httpx.BaseTransport | None = None,
        max_attempts: int = 3,
        retry_delay_s: float = 1.0,
        max_tokens: int = 8192,
    ) -> None:
        self.model = model
        self.max_attempts = max_attempts
        self.retry_delay_s = retry_delay_s
        self.max_tokens = max_tokens
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
        payload = {
            "model": self.model,
            "messages": messages,
            "max_tokens": self.max_tokens,
            "tools": [
                {
                    "type": "function",
                    "function": {
                        "name": name,
                        "description": f"{name} tool",
                        "parameters": {"type": "object", "properties": {}},
                    },
                }
                for name in available_actions
            ],
            "tool_choice": "auto",
        }
        last_error: Exception | None = None
        for attempt in range(1, self.max_attempts + 1):
            try:
                resp = self._client.post("/chat/completions", json=payload)
                resp.raise_for_status()
                data = resp.json()
                break
            except (httpx.HTTPError, ValueError) as exc:
                last_error = exc
                if attempt < self.max_attempts:
                    time.sleep(self.retry_delay_s)
        else:
            raise LLMError(f"DeepSeek API error after {self.max_attempts} attempts: {last_error}") from last_error
        message = data["choices"][0]["message"]
        text = message.get("content") or ""
        actions: list[Action] = []
        for call in message.get("tool_calls") or []:
            fn = call.get("function", {})
            name = fn.get("name", "")
            if name not in available_actions:
                continue
            try:
                args = json.loads(fn.get("arguments") or "{}")
            except json.JSONDecodeError:
                args = {}
            if not isinstance(args, dict):
                args = {}
            actions.append(Action(id="", type=name, params=args, run_id=""))
        return LLMResponse(
            text=text,
            action=actions[0] if actions else None,
            actions=actions or None,
            done=False,
        )
