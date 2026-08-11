"""Deterministic tests for the workspace sandbox and tool registry."""

from cah.actions.registry import ToolRegistry
from cah.actions.sandbox import WorkspaceSandbox


def test_write_read_file(tmp_path):
    sb = WorkspaceSandbox(root=tmp_path, read_only=False)
    r = sb.write_file("hello.txt", "hi")
    assert r.ok
    assert sb.read_file("hello.txt").output == "hi"


def test_write_escape_blocked(tmp_path):
    sb = WorkspaceSandbox(root=tmp_path, read_only=False)
    r = sb.write_file("../evil.txt", "x")
    assert not r.ok


def test_read_escape_blocked(tmp_path):
    sb = WorkspaceSandbox(root=tmp_path, read_only=False)
    r = sb.read_file("../../etc/passwd")
    assert not r.ok


def test_read_only_blocks_writes(tmp_path):
    sb = WorkspaceSandbox(root=tmp_path, read_only=True)
    assert not sb.write_file("a.txt", "x").ok
    assert not sb.run_shell("echo hi", timeout_s=10).ok


def test_shell_runs_in_workspace(tmp_path):
    sb = WorkspaceSandbox(root=tmp_path, read_only=False)
    r = sb.run_shell('python -c "import os;print(os.getcwd())"', timeout_s=30)
    assert r.ok and str(tmp_path.resolve()) in r.output


def test_registry_dispatch(tmp_path):
    sb = WorkspaceSandbox(root=tmp_path, read_only=False)
    reg = ToolRegistry(sandbox=sb)
    r = reg.dispatch("write_file", {"path": "a.txt", "content": "x"})
    assert r.ok
    r2 = reg.dispatch("no_such_tool", {})
    assert not r2.ok


def test_search_does_not_follow_symlink_outside_workspace(tmp_path):
    import os

    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "secret.txt").write_text("TOPSECRET", encoding="utf-8")
    ws = tmp_path / "ws"
    ws.mkdir()
    link = ws / "leak"
    try:
        os.symlink(outside, link, target_is_directory=True)
    except (OSError, NotImplementedError):
        import pytest

        pytest.skip("symlinks not permitted on this platform")
    sb = WorkspaceSandbox(root=ws, read_only=False)
    reg = ToolRegistry(sandbox=sb)
    r = reg.dispatch("search", {"pattern": "TOPSECRET", "path": "."})
    assert r.ok
    assert "secret.txt" not in r.output


def test_output_limit_truncates_large_reads(tmp_path):
    from cah.actions.sandbox import OUTPUT_LIMIT

    sb = WorkspaceSandbox(root=tmp_path, read_only=False)
    sb.write_file("big.txt", "x" * (OUTPUT_LIMIT * 2))
    r = sb.read_file("big.txt")
    assert r.ok and len(r.output) <= OUTPUT_LIMIT


def test_shell_env_sanitizes_secrets(tmp_path, monkeypatch):
    monkeypatch.setenv("CAH_TEST_SECRET", "hunter2")
    sb = WorkspaceSandbox(root=tmp_path, read_only=False)
    r = sb.run_shell(
        "python -c \"import os;print(os.environ.get('CAH_TEST_SECRET','MISSING'))\"",
        timeout_s=30,
    )
    assert r.ok and "MISSING" in r.output
