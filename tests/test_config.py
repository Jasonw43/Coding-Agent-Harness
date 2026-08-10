import tomllib
from pathlib import Path

import pytest

from cah.config import HarnessConfig, load_config


def test_load_valid_toml(tmp_path):
    p = tmp_path / "harness.toml"
    p.write_text('model = "mock"\nmax_steps = 5\n', encoding="utf-8")
    cfg = load_config(p)
    assert cfg.model == "mock" and cfg.max_steps == 5


def test_invalid_config_fails_fast(tmp_path):
    p = tmp_path / "bad.toml"
    p.write_text('model = "mock"\nmax_steps = "not-int"\n', encoding="utf-8")
    with pytest.raises(ValueError):
        load_config(p)


def test_missing_fields_use_defaults(tmp_path):
    p = tmp_path / "minimal.toml"
    p.write_text("", encoding="utf-8")
    cfg = load_config(p)
    assert cfg.max_steps == 10
    assert cfg.approval_timeout_s == 300
    assert cfg.workspace == "."
    assert cfg.read_only is False
    assert cfg.memory_enabled is True


def test_load_returns_harness_config(tmp_path):
    p = tmp_path / "harness.toml"
    p.write_text("", encoding="utf-8")
    assert isinstance(load_config(p), HarnessConfig)
