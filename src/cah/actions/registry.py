"""Tool registry: name -> callable, with uniform dispatch."""

from __future__ import annotations

from collections.abc import Callable

from cah.actions.sandbox import WorkspaceSandbox
from cah.models import ToolResult

ToolFn = Callable[[dict], ToolResult]


class ToolRegistry:
    """Dispatch actions to registered tool functions."""

    def __init__(self, sandbox: WorkspaceSandbox, memory=None) -> None:
        self.sandbox = sandbox
        self.memory = memory
        self._tools: dict[str, ToolFn] = {}

    def register(self, name: str, fn: ToolFn) -> None:
        self._tools[name] = fn

    def names(self) -> list[str]:
        return sorted(self._tools)

    def dispatch(self, tool_type: str, params: dict) -> ToolResult:
        fn = self._tools.get(tool_type)
        if fn is None:
            return ToolResult(ok=False, output=f"unknown tool: {tool_type}", meta={})
        try:
            return fn(params)
        except Exception as exc:  # tool errors become structured results
            return ToolResult(ok=False, output=f"tool error: {exc!r}", meta={})
