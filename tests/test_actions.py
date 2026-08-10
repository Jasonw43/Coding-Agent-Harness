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
