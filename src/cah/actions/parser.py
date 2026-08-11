"""Parse LLM output into structured actions (the real-LLM tool protocol)."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass

from cah.models import Action

_JSON_START_RE = re.compile(r"\{")
_INVOKE_RE = re.compile(
    r"<[^>]*invoke\s+name=[\"']([^\"']+)[\"'][^>]*>(.*?)</[^>]*invoke>", re.S
)
_PARAM_RE = re.compile(
    r"<[^>]*parameter\s+name=[\"']([^\"']+)[\"'][^>]*>(.*?)</[^>]*parameter>", re.S
)


@dataclass
class ParseResult:
    action: Action | None = None
    done: bool = False
    answer: str | None = None
    error: str | None = None


def _extract_json(text: str) -> str | None:
    """Return the first balanced JSON object found in the text, if any."""
    match = _JSON_START_RE.search(text)
    if not match:
        return None
    start = match.start()
    depth = 0
    in_string = False
    escape = False
    for i in range(start, len(text)):
        ch = text[i]
        if in_string:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[start : i + 1]
    return None


def parse_action(text: str, available_tools: list[str]) -> ParseResult:
    """Interpret a model response.

    - A JSON object with ``{"action": {"type": ..., "params": ...}}`` (or a
      top-level ``type``) becomes an Action.
    - An explicit ``{"done": true, "answer": ...}`` or any plain text without
      a valid JSON action is treated as the final answer.
    - Malformed JSON or unknown tools produce an error for bounded retry.
    """

    raw = text.strip()
    if not raw:
        return ParseResult(done=True, answer="")

    obj_text = _extract_json(raw)
    if obj_text is None:
        if raw.startswith("{"):
            return ParseResult(error="FORMAT_ERROR: unbalanced JSON object")
        if "```" in raw:
            return ParseResult(
                error=(
                    "FORMAT_ERROR: code blocks in the reply are not allowed; "
                    "to write files you must emit a JSON action object like "
                    '{"action": {"type": "write_file", "params": {"path": "main.py", "content": "..."}}}'
                )
            )
        invoke_match = _INVOKE_RE.search(raw)
        if invoke_match:
            tool_type = invoke_match.group(1)
            body = invoke_match.group(2)
            if tool_type not in available_tools:
                return ParseResult(error=f"FORMAT_ERROR: unknown tool '{tool_type}'")
            params = {
                m.group(1): m.group(2).strip() for m in _PARAM_RE.finditer(body)
            }
            return ParseResult(
                action=Action(id="", type=tool_type, params=params, run_id="")
            )
        return ParseResult(done=True, answer=raw)

    try:
        payload = json.loads(obj_text)
    except json.JSONDecodeError as exc:
        return ParseResult(error=f"FORMAT_ERROR: invalid JSON action: {exc}")

    if not isinstance(payload, dict):
        return ParseResult(error="FORMAT_ERROR: action payload must be a JSON object")

    if payload.get("done") is True:
        return ParseResult(done=True, answer=str(payload.get("answer", raw)))

    action_obj = payload.get("action") if isinstance(payload.get("action"), dict) else payload
    tool_type = action_obj.get("type") if isinstance(action_obj, dict) else None
    if not isinstance(tool_type, str) or not tool_type:
        return ParseResult(error="FORMAT_ERROR: action object missing 'type'")
    if tool_type not in available_tools:
        return ParseResult(error=f"FORMAT_ERROR: unknown tool '{tool_type}'")
    params = action_obj.get("params", {})
    if not isinstance(params, dict):
        return ParseResult(error="FORMAT_ERROR: action 'params' must be an object")
    return ParseResult(action=Action(id="", type=tool_type, params=params, run_id=""))
