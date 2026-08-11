"""Declarative TOML configuration for the harness."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class HarnessConfig:
    """Runtime configuration loaded from a TOML file."""

    model: str = "mock"
    max_steps: int = 10
    approval_timeout_s: int = 300
    max_retries: int = 3
    deny_patterns: list[str] = field(
        default_factory=lambda: [
            "rm -rf",
            "DROP DATABASE",
            "git push",
            "curl | sh",
            "sudo",
            "chmod 777",
            "format ",
            "del /f /s /q",
        ]
    )
    allow_prefixes: list[str] = field(default_factory=list)
    tools_enabled: list[str] = field(default_factory=list)
    validators: list[str] = field(default_factory=list)
    workspace: str = "."
    read_only: bool = False
    memory_enabled: bool = True


# Field name -> (expected type, human-readable label)
_FIELD_TYPES: dict[str, type] = {
    "model": str,
    "max_steps": int,
    "approval_timeout_s": int,
    "max_retries": int,
    "deny_patterns": list,
    "allow_prefixes": list,
    "tools_enabled": list,
    "validators": list,
    "workspace": str,
    "read_only": bool,
    "memory_enabled": bool,
}


def load_config(path: str | Path) -> HarnessConfig:
    """Load a TOML config, validating each known field's type.

    Raises ValueError with location info on malformed TOML or invalid types.
    """
    p = Path(path)
    try:
        with p.open("rb") as f:
            raw: dict[str, Any] = tomllib.load(f)
    except tomllib.TOMLDecodeError as exc:
        raise ValueError(f"{p}: invalid TOML: {exc}") from exc

    unknown = set(raw) - set(_FIELD_TYPES)
    if unknown:
        raise ValueError(f"{p}: unknown field(s): {sorted(unknown)}")

    for key, expected in _FIELD_TYPES.items():
        if key not in raw:
            continue
        value = raw[key]
        if not isinstance(value, expected):
            raise ValueError(
                f"{p}: field '{key}' must be {expected.__name__}, got {type(value).__name__}"
            )

    return HarnessConfig(**raw)
