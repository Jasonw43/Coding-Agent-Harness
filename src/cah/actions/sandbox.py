"""Workspace-confined file and shell operations for the harness."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from cah.models import ToolResult

SENSITIVE_ENV_MARKERS = ("KEY", "TOKEN", "SECRET", "PASSWORD", "CREDENTIAL", "AUTH")
OUTPUT_LIMIT = 64 * 1024


class PathEscapeError(Exception):
    """Raised when a path resolves outside the workspace root."""


class WorkspaceSandbox:
    """Read/write/list/run commands confined to a workspace root."""

    def __init__(self, root: Path, read_only: bool = False) -> None:
        self.root = Path(root).resolve()
        self.read_only = read_only
        self.root.mkdir(parents=True, exist_ok=True)

    def resolve(self, rel_path: str) -> Path:
        """Resolve a relative path and enforce the workspace boundary."""
        target = (self.root / rel_path).resolve()
        if target != self.root and self.root not in target.parents:
            raise PathEscapeError(f"path escapes workspace: {rel_path!r}")
        return target

    def _ok(self, output: str, meta: dict | None = None) -> ToolResult:
        return ToolResult(ok=True, output=output, meta=meta or {})

    def _err(self, output: str) -> ToolResult:
        return ToolResult(ok=False, output=output, meta={})

    # ---- file tools ----

    def read_file(self, rel_path: str) -> ToolResult:
        try:
            target = self.resolve(rel_path)
        except PathEscapeError as exc:
            return self._err(str(exc))
        try:
            content = target.read_text(encoding="utf-8", errors="replace")
        except FileNotFoundError:
            return self._err(f"file not found: {rel_path}")
        except IsADirectoryError:
            return self._err(f"is a directory: {rel_path}")
        except OSError as exc:
            return self._err(f"read failed: {exc}")
        return self._ok(content[:OUTPUT_LIMIT], {"path": str(target)})

    def write_file(self, rel_path: str, content: str) -> ToolResult:
        if self.read_only:
            return self._err("read-only mode forbids writes")
        try:
            target = self.resolve(rel_path)
        except PathEscapeError as exc:
            return self._err(str(exc))
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
        except OSError as exc:
            return self._err(f"write failed: {exc}")
        return self._ok("", {"path": str(target), "bytes": len(content.encode("utf-8"))})

    def list_dir(self, rel_path: str = ".") -> ToolResult:
        try:
            target = self.resolve(rel_path)
        except PathEscapeError as exc:
            return self._err(str(exc))
        try:
            names = sorted(p.name for p in target.iterdir())
        except FileNotFoundError:
            return self._err(f"directory not found: {rel_path}")
        except OSError as exc:
            return self._err(f"list failed: {exc}")
        return self._ok("\n".join(names), {"count": len(names)})

    # ---- shell ----

    def run_shell(self, command: str, timeout_s: int = 120) -> ToolResult:
        if self.read_only:
            return self._err("read-only mode forbids shell execution")
        env = {
            k: v
            for k, v in os.environ.items()
            if not any(marker in k.upper() for marker in SENSITIVE_ENV_MARKERS)
        }
        try:
            proc = subprocess.run(
                command,
                shell=True,
                cwd=self.root,
                env=env,
                capture_output=True,
                text=True,
                timeout=timeout_s,
            )
        except subprocess.TimeoutExpired:
            return self._err(f"command timed out after {timeout_s}s")
        except OSError as exc:
            return self._err(f"failed to run command: {exc}")
        output = (proc.stdout or "")[:OUTPUT_LIMIT]
        if proc.returncode != 0:
            detail = (proc.stderr or "")[:OUTPUT_LIMIT]
            return ToolResult(
                ok=False,
                output=output,
                meta={"returncode": proc.returncode, "stderr": detail},
            )
        return ToolResult(
            ok=True, output=output, meta={"returncode": 0, "cwd": str(self.root)}
        )
