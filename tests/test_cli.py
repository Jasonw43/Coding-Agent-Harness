"""Deterministic tests for the CLI entrypoint."""

import threading
import time
import os
import subprocess
import sys
from pathlib import Path

from cah.cli import build_parser, main
from cah.cli import wait_for_decision
from cah.hitl.state_machine import HITLStateMachine


def test_parser_commands():
    p = build_parser()
    cases = {
        "run": ["run", "task"],
        "approve": ["approve", "a1", "--token", "t"],
        "reject": ["reject", "a1", "--token", "t"],
        "status": ["status"],
        "key": ["key", "status"],
        "config": ["config", "show"],
        "demo": ["demo"],
    }
    for cmd, argv in cases.items():
        args = p.parse_args(argv)
        assert args.command == cmd


def test_mock_run_smoke(tmp_path, capsys):
    code = main(["run", "--mock", "--workspace", str(tmp_path), "hello task"])
    out = capsys.readouterr().out
    assert code == 0 and "done" in out.lower()


def test_run_invalid_workspace_clean_error(tmp_path, capsys):
    blocker = tmp_path / "blocker"
    blocker.write_text("x", encoding="utf-8")
    ws = blocker / "ws"  # parent is a file -> mkdir fails on all platforms
    code = main(["run", "--mock", "--workspace", str(ws), "task"])
    err = capsys.readouterr().err
    assert code == 2 and "workspace" in err.lower()


def test_wait_for_decision_returns_approved_after_external_approval(tmp_path):
    store = tmp_path / "approvals.json"
    sm = HITLStateMachine(store, timeout_s=300)
    rec, token = sm.submit("a1", "danger")
    result: list[str] = []

    def waiter():
        result.append(wait_for_decision("a1", store, timeout_s=5))

    t = threading.Thread(target=waiter, daemon=True)
    t.start()
    time.sleep(0.3)
    sm.approve("a1", token, "cli-test")
    t.join(timeout=6)
    assert result == ["approved"]


def test_wait_for_decision_returns_rejected_on_timeout(tmp_path):
    store = tmp_path / "approvals.json"
    sm = HITLStateMachine(store, timeout_s=300)
    sm.submit("a2", "danger")
    result: list[str] = []

    def waiter():
        result.append(wait_for_decision("a2", store, timeout_s=1))

    t = threading.Thread(target=waiter, daemon=True)
    t.start()
    t.join(timeout=3)
    assert result == ["rejected"]


def test_python_m_cah_runs():
    env = {**os.environ, "PYTHONPATH": str(Path.cwd() / "src")}
    proc = subprocess.run(
        [sys.executable, "-m", "cah", "--help"],
        capture_output=True,
        text=True,
        env=env,
        timeout=30,
    )
    assert proc.returncode == 0
    assert "usage: cah" in proc.stdout
