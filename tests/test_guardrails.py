from pathlib import Path

from cah.guardrails.command import CommandGuardrail
from cah.models import Action


def test_blocks_rm_rf():
    g = CommandGuardrail(deny_patterns=["rm -rf"], allow_prefixes=["python -m pytest"])
    d = g.check(Action(id="a", type="shell", params={"command": "rm -rf /"}, run_id="r"), Path("."))
    assert d.verdict == "BLOCKED"


def test_allows_test_command():
    g = CommandGuardrail(deny_patterns=["rm -rf"], allow_prefixes=["python -m pytest"])
    d = g.check(Action(id="a", type="shell", params={"command": "python -m pytest tests"}, run_id="r"), Path("."))
    assert d.verdict == "SAFE"


def test_non_shell_action_safe():
    g = CommandGuardrail(deny_patterns=[], allow_prefixes=[])
    d = g.check(Action(id="a", type="read_file", params={"path": "x"}, run_id="r"), Path("."))
    assert d.verdict == "SAFE"
