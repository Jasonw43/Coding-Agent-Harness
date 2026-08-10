"""Mechanism demo: deterministically reproduce the three required behaviors.

Run: python demo/mechanism_demo.py  (exit code 0 = all behaviors verified)

1. The guardrail intercepts a dangerous action (BLOCKED, no LLM involved).
2. An injected failure is fed back into the loop, changing the next action,
   and the run converges to done.
3. The focus dimension (HITL approval state machine) transitions are
   exercised deterministically.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from cah.actions.registry import ToolRegistry
from cah.actions.sandbox import WorkspaceSandbox
from cah.guardrails.command import CommandGuardrail
from cah.guardrails.pipeline import GuardrailPipeline
from cah.hitl.state_machine import HITLStateMachine
from cah.llm.mock import MockLLM
from cah.loop.agent import AgentLoop
from cah.memory.store import MemoryStore
from cah.models import Action, Feedback


def demo_1_guardrail_blocks() -> None:
    g = CommandGuardrail(deny_patterns=["rm -rf"], allow_prefixes=[])
    d = g.check(
        Action(id="a1", type="shell", params={"command": "rm -rf /"}, run_id="r"),
        Path("."),
    )
    assert d.verdict == "BLOCKED", d
    print(f"1) guardrail blocked dangerous action: BLOCKED ({d.reason})")


def demo_2_feedback_changes_next_action() -> None:
    with tempfile.TemporaryDirectory() as td:
        p = Path(td)
        script = p / "script.jsonl"
        script.write_text(
            "\n".join(
                json.dumps(s)
                for s in [
                    {
                        "text": "write the file",
                        "action": {"type": "write_file", "params": {"path": "x.py", "content": "1"}},
                        "done": False,
                    },
                    {
                        "text": "write it again",
                        "action": {"type": "write_file", "params": {"path": "x.py", "content": "2"}},
                        "done": False,
                    },
                ]
            )
            + "\n",
            encoding="utf-8",
        )
        ws = p / "ws"
        ws.mkdir()
        loop = AgentLoop(
            llm=MockLLM(script),
            tools=ToolRegistry(sandbox=WorkspaceSandbox(ws, read_only=False)),
            pipeline=GuardrailPipeline([]),
            hitl=None,
            validator=None,
            memory=MemoryStore(p / "memory.json"),
            workspace=ws,
            max_steps=5,
            max_retries=1,
            approval_resolver=lambda i, t: "approve",
        )

        class Flaky:
            def __init__(self) -> None:
                self.n = 0

            def validate(self, workspace) -> Feedback:
                self.n += 1
                return Feedback(
                    ok=self.n > 1,
                    failures=[] if self.n > 1 else ["FAILED test_x"],
                    summary="flaky validator",
                )

        loop.validator = Flaky()
        result = loop.run("task")
        assert result.status == "done", result
        assert (ws / "x.py").read_text(encoding="utf-8") == "2"
        print(
            "2) feedback loop: first validation failed -> feedback fed back -> "
            "next action changed and run converged to done"
        )


def demo_3_hitl_transitions() -> None:
    with tempfile.TemporaryDirectory() as td:
        sm = HITLStateMachine(Path(td) / "approvals.json", timeout_s=300)
        rec, token = sm.submit("danger-1", "deploy to production")
        assert rec.state == "PENDING"
        assert sm.reject("danger-1", token, "demo-user").state == "REJECTED"
        rec2, token2 = sm.submit("danger-2", "drop the table")
        assert sm.approve("danger-2", token2, "demo-user").state == "APPROVED"
        # wrong token must be rejected
        try:
            sm.approve("danger-2", "wrong-token", "demo-user")
            raise AssertionError("wrong token should be rejected")
        except PermissionError:
            pass
        print("3) HITL state machine: PENDING -> APPROVED/REJECTED + wrong-token guard")


def main() -> int:
    demo_1_guardrail_blocks()
    demo_2_feedback_changes_next_action()
    demo_3_hitl_transitions()
    print("mechanism demo: all three behaviors verified")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
