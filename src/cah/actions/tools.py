"""Built-in tools mounted into the ToolRegistry."""

from __future__ import annotations

import re
from pathlib import Path

from cah.actions.registry import ToolRegistry
from cah.models import ToolResult


def install_tools(registry: ToolRegistry) -> None:
    sb = registry.sandbox

    def read_file(params: dict) -> ToolResult:
        return sb.read_file(str(params.get("path", "")))

    def write_file(params: dict) -> ToolResult:
        return sb.write_file(str(params.get("path", "")), str(params.get("content", "")))

    def list_dir(params: dict) -> ToolResult:
        return sb.list_dir(str(params.get("path", ".")))

    def shell(params: dict) -> ToolResult:
        return sb.run_shell(
            str(params.get("command", "")), timeout_s=int(params.get("timeout_s", 120))
        )

    def run_tests(params: dict) -> ToolResult:
        command = str(params.get("command", "python -m pytest -q"))
        return sb.run_shell(command, timeout_s=int(params.get("timeout_s", 300)))

    def search(params: dict) -> ToolResult:
        pattern = str(params.get("pattern", ""))
        base = sb.resolve(str(params.get("path", ".")))
        try:
            rx = re.compile(pattern)
        except re.error as exc:
            return ToolResult(ok=False, output=f"invalid pattern: {exc}", meta={})
        matches: list[str] = []
        for p in base.rglob("*"):
            try:
                resolved = p.resolve()
            except OSError:
                continue
            # never read through symlinks pointing outside the workspace
            if resolved != sb.root and sb.root not in resolved.parents:
                continue
            if resolved.is_file():
                try:
                    if rx.search(resolved.read_text(encoding="utf-8", errors="ignore")):
                        matches.append(str(resolved.relative_to(sb.root)))
                except OSError:
                    continue
        return ToolResult(ok=True, output="\n".join(matches[:200]), meta={"count": len(matches)})

    def memory_store(params: dict) -> ToolResult:
        if registry.memory is None:
            return ToolResult(ok=False, output="memory not configured", meta={})
        entry = registry.memory.store(
            str(params.get("key", "")), str(params.get("content", "")), params.get("tags", [])
        )
        return ToolResult(ok=True, output=f"stored {entry.key}", meta={})

    def memory_recall(params: dict) -> ToolResult:
        if registry.memory is None:
            return ToolResult(ok=False, output="memory not configured", meta={})
        hits = registry.memory.recall(str(params.get("query", "")))
        lines = [f"[{e.key}] {e.content}" for e in hits]
        return ToolResult(ok=True, output="\n".join(lines), meta={"count": len(hits)})

    registry.register("read_file", read_file)
    registry.register("write_file", write_file)
    registry.register("list_dir", list_dir)
    registry.register("shell", shell)
    registry.register("run_tests", run_tests)
    registry.register("search", search)
    registry.register("memory_store", memory_store)
    registry.register("memory_recall", memory_recall)
