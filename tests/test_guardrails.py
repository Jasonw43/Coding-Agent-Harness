from pathlib import Path

from cah.guardrails.command import CommandGuardrail
from cah.guardrails.path import PathGuardrail
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


def test_path_inside_ok(tmp_path):
    ws = tmp_path / "ws"
    ws.mkdir()
    g = PathGuardrail()
    d = g.check(
        Action(id="a", type="write_file", params={"path": "ok.txt"}, run_id="r"),
        ws,
    )
    assert d.verdict == "SAFE"


def test_path_escape_blocked(tmp_path):
    ws = tmp_path / "ws"
    ws.mkdir()
    g = PathGuardrail()
    d = g.check(
        Action(id="a", type="write_file", params={"path": "../escape.txt"}, run_id="r"),
        ws,
    )
    assert d.verdict == "BLOCKED"


def test_tool_disabled_blocked():
    from cah.guardrails.tool import ToolGuardrail

    g = ToolGuardrail(tools_enabled=["read_file"], read_only=False)
    d = g.check(Action(id="a", type="shell", params={}, run_id="r"), None)
    assert d.verdict == "BLOCKED"


def test_tool_readonly_blocks_writes():
    from cah.guardrails.tool import ToolGuardrail

    g = ToolGuardrail(tools_enabled=["write_file"], read_only=True)
    d = g.check(Action(id="a", type="write_file", params={}, run_id="r"), None)
    assert d.verdict == "BLOCKED"


def test_pipeline_first_non_safe_wins():
    from pathlib import Path

    from cah.guardrails.command import CommandGuardrail
    from cah.guardrails.path import PathGuardrail
    from cah.guardrails.pipeline import GuardrailPipeline

    p = GuardrailPipeline(
        [
            PathGuardrail(),
            CommandGuardrail(deny_patterns=["rm -rf"], allow_prefixes=[]),
        ]
    )
    d = p.check(
        Action(id="a", type="shell", params={"command": "rm -rf x"}, run_id="r"),
        Path("."),
    )
    assert d.verdict == "BLOCKED"


def test_pipeline_all_safe_is_safe(tmp_path):
    from pathlib import Path

    from cah.guardrails.command import CommandGuardrail
    from cah.guardrails.pipeline import GuardrailPipeline

    p = GuardrailPipeline(
        [CommandGuardrail(deny_patterns=["rm -rf"], allow_prefixes=["python -m pytest"])]
    )
    d = p.check(
        Action(
            id="a",
            type="shell",
            params={"command": "python -m pytest tests"},
            run_id="r",
        ),
        tmp_path,
    )
    assert d.verdict == "SAFE"


def test_pipeline_fail_closed_on_exception():
    from cah.guardrails.pipeline import GuardrailPipeline

    class Boom:
        def check(self, action, workspace):
            raise RuntimeError("guardrail bug")

    p = GuardrailPipeline([Boom()])
    d = p.check(Action(id="a", type="read_file", params={}, run_id="r"), None)
    assert d.verdict == "BLOCKED"


def test_deny_token_does_not_false_positive_on_substring():
    g = CommandGuardrail(deny_patterns=["rm"], allow_prefixes=[])
    d = g.check(
        Action(id="a", type="shell", params={"command": "termtests --help"}, run_id="r"),
        Path("."),
    )
    assert d.verdict != "BLOCKED"


def test_deny_single_token_blocks_exact_token():
    g = CommandGuardrail(deny_patterns=["sudo"], allow_prefixes=[])
    d = g.check(
        Action(id="a", type="shell", params={"command": "sudo apt update"}, run_id="r"),
        Path("."),
    )
    assert d.verdict == "BLOCKED"
