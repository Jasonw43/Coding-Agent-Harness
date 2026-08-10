"""Deterministic validators that turn test output into structured feedback."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Protocol

from cah.models import Feedback


class Validator(Protocol):
    def validate(self, workspace: Path) -> Feedback: ...


class TestRunnerValidator:
    """Run a test command and parse its output into objective feedback."""

    def __init__(self, command: list[str], timeout_s: int = 120) -> None:
        self.command = command
        self.timeout_s = timeout_s

    def validate(self, workspace: Path) -> Feedback:
        try:
            proc = subprocess.run(
                self.command,
                cwd=workspace,
                capture_output=True,
                text=True,
                timeout=self.timeout_s,
            )
        except subprocess.TimeoutExpired:
            return Feedback(
                ok=False,
                failures=["test run timed out"],
                summary=f"test run timed out after {self.timeout_s}s",
            )
        except OSError as exc:
            return Feedback(ok=False, failures=[str(exc)], summary="failed to start tests")

        output = f"{proc.stdout}\n{proc.stderr}"
        if proc.returncode == 0:
            return Feedback(ok=True, failures=[], summary="tests passed")

        failures = [
            line.strip()
            for line in output.splitlines()
            if "FAILED" in line or "Error" in line or "error" in line
        ][:20]
        return Feedback(
            ok=False,
            failures=failures,
            summary=f"tests failed with exit code {proc.returncode} ({len(failures)} failure lines)",
        )
