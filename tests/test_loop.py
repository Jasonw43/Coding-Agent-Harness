"""Deterministic tests for the agent main loop (mock LLM driven)."""

import json

from cah.actions.registry import ToolRegistry
from cah.actions.sandbox import WorkspaceSandbox
from cah.feedback.validators import TestRunnerValidator
from cah.guardrails.command import CommandGuardrail
from cah.guardrails.pipeline import GuardrailPipeline
from cah.hitl.state_machine import HITLStateMachine
from cah.llm.mock import MockLLM
from cah.loop.agent import AgentLoop
from cah.memory.store import MemoryStore
from cah.models import Feedback


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
