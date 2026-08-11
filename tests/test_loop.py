"""Deterministic tests for the agent main loop (mock LLM driven)."""

import json

from cah.actions.registry import ToolRegistry
from cah.actions.sandbox import WorkspaceSandbox
from cah.feedback.validators import TestRunnerValidator
from cah.guardrails.command import CommandGuardrail
from cah.guardrails.pipeline import GuardrailPipeline
from cah.hitl.state_machine import HITLStateMachine
from cah.llm.mock import MockLLM
from cah.loop.agent import AgentLoop, HarnessContext
from cah.memory.store import MemoryStore
from cah.models import Feedback
from cah.models import Action, LLMResponse


def _make_loop(tmp_path, script, approval="approve"):
    sp = tmp_path / "script.jsonl"
    sp.write_text("\n".join(json.dumps(s) for s in script), encoding="utf-8")
    ws = tmp_path / "ws"
    ws.mkdir()
    return AgentLoop(
        llm=MockLLM(sp),
        tools=ToolRegistry(sandbox=WorkspaceSandbox(ws, read_only=False)),
        pipeline=GuardrailPipeline(
            [CommandGuardrail(deny_patterns=["rm -rf"], allow_prefixes=[])]
        ),
        hitl=HITLStateMachine(tmp_path / "approvals.json", timeout_s=300),
        validator=TestRunnerValidator(["python", "-c", "pass"]),
        memory=MemoryStore(tmp_path / "memory.json"),
        workspace=ws,
        max_steps=5,
        max_retries=1,
        approval_resolver=lambda i, t: approval,
    )


def test_loop_runs_to_done(tmp_path):
    loop = _make_loop(
        tmp_path,
        [
            {"text": "done", "action": None, "done": True},
        ],
    )
    r = loop.run("task")
    assert r.status == "done" and r.final_output == "done"


def test_loop_blocks_dangerous_action(tmp_path):
    loop = _make_loop(
        tmp_path,
        [
            {"text": "rm", "action": {"type": "shell", "params": {"command": "rm -rf /"}}, "done": False},
            {"text": "done", "action": None, "done": True},
        ],
    )
    r = loop.run("task")
    assert any("BLOCKED" in str(e) or "blocked" in str(e) for e in r.actions_log)


def test_loop_hits_max_steps(tmp_path):
    loop = _make_loop(
        tmp_path,
        [
            {"text": "again", "action": {"type": "read_file", "params": {"path": "a.txt"}}, "done": False},
            {"text": "again", "action": {"type": "read_file", "params": {"path": "a.txt"}}, "done": False},
        ],
    )
    r = loop.run("task")
    assert r.status == "failed" and r.steps >= 2


def test_feedback_changes_next_action(tmp_path):
    calls = {"n": 0}

    class Flaky:
        def validate(self, ws):
            calls["n"] += 1
            return Feedback(ok=calls["n"] > 1, failures=[], summary="flaky")

    loop = _make_loop(
        tmp_path,
        [
            {"text": "write", "action": {"type": "write_file", "params": {"path": "x.py", "content": "1"}}, "done": False},
            {"text": "write again", "action": {"type": "write_file", "params": {"path": "x.py", "content": "2"}}, "done": False},
        ],
    )
    loop.validator = Flaky()
    r = loop.run("task")
    assert r.status == "done" and calls["n"] == 2


def test_loop_parses_real_style_json_actions(tmp_path):
    """Real-LLM mode: plain text containing a JSON action is parsed and executed."""
    loop = _make_loop(
        tmp_path,
        [
            {
                "text": '{"action": {"type": "write_file", "params": {"path": "x.py", "content": "print(1)"}}}',
                "action": None,
                "done": False,
            },
            {"text": "wrote the file and finished", "action": None, "done": False},
        ],
    )
    r = loop.run("task")
    assert r.status == "done"
    assert (tmp_path / "ws" / "x.py").read_text(encoding="utf-8") == "print(1)"
    assert r.final_output == "wrote the file and finished"


def test_loop_code_block_without_action_triggers_feedback(tmp_path):
    """A code-block answer without an action must be fed back as a format error."""
    loop = _make_loop(
        tmp_path,
        [
            {
                "text": '```python\ndef add_big(a, b):\n    return a + b\n```',
                "action": None,
                "done": False,
            },
            {
                "text": '{"action": {"type": "write_file", "params": {"path": "main.py", "content": "def add_big(a, b): return a+b"}}}',
                "action": None,
                "done": False,
            },
            {"text": "created main.py", "action": None, "done": False},
        ],
    )
    r = loop.run("task")
    assert r.status == "done"
    assert (tmp_path / "ws" / "main.py").exists()
    assert any(e.get("event") == "FEEDBACK" for e in r.actions_log)


def test_loop_parses_invoke_style_tool_call(tmp_path):
    """Claude-style tool invocation tags are parsed and executed."""
    loop = _make_loop(
        tmp_path,
        [
            {
                "text": (
                    "Let me create the file.\n"
                    '<dsml:invoke name="write_file">\n'
                    '<dsml:parameter name="path">invoke.txt</dsml:parameter>\n'
                    '<dsml:parameter name="content">ok</dsml:parameter>\n'
                    "</dsml:invoke>"
                ),
                "action": None,
                "done": False,
            },
            {"text": "done", "action": None, "done": False},
        ],
    )
    r = loop.run("task")
    assert r.status == "done"
    assert (tmp_path / "ws" / "invoke.txt").read_text(encoding="utf-8") == "ok"


def test_loop_executes_multiple_actions_in_one_reply(tmp_path):
    loop = _make_loop(
        tmp_path,
        [
            {
                "text": (
                    '{"action": {"type": "write_file", "params": {"path": "a.txt", "content": "1"}}}\n'
                    '{"action": {"type": "write_file", "params": {"path": "b.txt", "content": "2"}}}'
                ),
                "action": None,
                "done": False,
            },
            {"text": "done", "action": None, "done": False},
        ],
    )
    r = loop.run("task")
    assert r.status == "done"
    assert (tmp_path / "ws" / "a.txt").read_text(encoding="utf-8") == "1"
    assert (tmp_path / "ws" / "b.txt").read_text(encoding="utf-8") == "2"


def test_loop_uses_native_tool_calls(tmp_path):
    """Structured tool_calls from the LLM client are executed directly."""
    ws = tmp_path / "ws"
    ws.mkdir()

    class NativeLLM:
        def __init__(self):
            self.calls = 0

        def complete(self, context, available_actions):
            self.calls += 1
            if self.calls == 1:
                return LLMResponse(
                    text="",
                    action=None,
                    done=False,
                    actions=[
                        Action(
                            id="",
                            type="write_file",
                            params={"path": "native.txt", "content": "ok"},
                            run_id="",
                        )
                    ],
                )
            return LLMResponse(text="finished", action=None, done=True)

    loop = AgentLoop(
        llm=NativeLLM(),
        tools=ToolRegistry(sandbox=WorkspaceSandbox(ws, read_only=False)),
        pipeline=GuardrailPipeline([]),
        hitl=None,
        validator=None,
        memory=None,
        workspace=ws,
        max_steps=5,
        max_retries=1,
        approval_resolver=lambda i, t: "approve",
    )
    r = loop.run("task")
    assert r.status == "done"
    assert (ws / "native.txt").read_text(encoding="utf-8") == "ok"


def test_context_budget_truncates_old_events(tmp_path):
    loop = _make_loop(tmp_path, [])
    loop.context_budget_tokens = 40
    events = [f"event-{i} " * 20 for i in range(10)]  # each ~180 chars
    ctx = loop._build_context("task", events)
    contents = " ".join(str(m.get("content", "")) for m in ctx)
    assert "(earlier events truncated" in contents
    kept_events = [m for m in ctx if str(m.get("content", "")).startswith("event-")]
    assert len(kept_events) < 10


def test_from_context_builds_equivalent_loop(tmp_path):
    ws = tmp_path / "ws"
    ws.mkdir()
    script = tmp_path / "script.jsonl"
    script.write_text('{"text":"done","action":null,"done":true}\n', encoding="utf-8")
    ctx = HarnessContext(
        llm=MockLLM(script),
        tools=ToolRegistry(sandbox=WorkspaceSandbox(ws, read_only=False)),
        pipeline=GuardrailPipeline([]),
        workspace=ws,
        max_steps=3,
        max_retries=0,
    )
    loop = AgentLoop.from_context(ctx)
    assert loop.max_steps == 3 and loop.max_retries == 0
    assert loop.tools is ctx.tools and loop.workspace == ws


def test_full_pipeline_integration(workspace, registry, tmp_path):
    """parser -> guardrails -> tools -> feedback -> retry -> converged done."""
    script = tmp_path / "integration.jsonl"
    script.write_text(
        "\n".join(
            json.dumps(s)
            for s in [
                {
                    "text": '{"action": {"type": "write_file", "params": {"path": "x.py", "content": "print(1)"}}}',
                    "action": None,
                    "done": False,
                },
                {
                    "text": '{"action": {"type": "shell", "params": {"command": "rm -rf /"}}}',
                    "action": None,
                    "done": False,
                },
                {
                    "text": '{"action": {"type": "write_file", "params": {"path": "x.py", "content": "print(2)"}}}',
                    "action": None,
                    "done": False,
                },
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    calls = {"n": 0}

    class Converge:
        def validate(self, ws):
            calls["n"] += 1
            ok = (ws / "x.py").read_text(encoding="utf-8") == "print(2)"
            return Feedback(ok=ok, failures=[] if ok else ["wrong content"], summary="check x.py")

    loop = AgentLoop(
        llm=MockLLM(script),
        tools=registry,
        pipeline=GuardrailPipeline(
            [CommandGuardrail(deny_patterns=["rm -rf"], allow_prefixes=[])]
        ),
        hitl=None,
        validator=Converge(),
        memory=None,
        workspace=workspace,
        max_steps=8,
        max_retries=2,
        approval_resolver=lambda i, t: "approve",
    )
    r = loop.run("task")
    assert r.status == "done"
    assert (workspace / "x.py").read_text(encoding="utf-8") == "print(2)"
    events = [e.get("event") for e in r.actions_log]
    assert "BLOCKED" in events
    assert "FEEDBACK" in events
    assert calls["n"] == 2
