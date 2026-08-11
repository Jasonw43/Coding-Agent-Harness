"""Demo-mode approval console helpers used by the Gradio UI on HF Spaces.

Gradio-independent so the logic stays deterministically testable.
"""

from __future__ import annotations

import json
import tempfile
import threading
import time
from pathlib import Path
from uuid import uuid4

from cah.actions.registry import ToolRegistry
from cah.actions.sandbox import WorkspaceSandbox
from cah.guardrails.command import CommandGuardrail
from cah.guardrails.pipeline import GuardrailPipeline
from cah.hitl.state_machine import HITLStateMachine
from cah.llm.mock import MockLLM
from cah.loop.agent import AgentLoop

DEFAULT_STORE_DIR = Path(tempfile.gettempdir()) / "cah-hf"


class DemoConsole:
    """Holds one scripted demo run and exposes approve/reject for a UI."""

    def __init__(self, store_dir: str | Path = DEFAULT_STORE_DIR) -> None:
        self.store_dir = Path(store_dir)
        self.store_dir.mkdir(parents=True, exist_ok=True)
        self.runs: dict[str, list[dict]] = {}
        self.finished: set[str] = set()
        self.tokens: dict[str, dict] = {}

    def hitl(self) -> HITLStateMachine:
        return HITLStateMachine(self.store_dir / "approvals.json", timeout_s=120)

    def start_demo(self) -> str:
        run_id = uuid4().hex[:8]
        threading.Thread(target=self._run_demo, args=(run_id,), daemon=True).start()
        return run_id

    def _run_demo(self, run_id: str) -> None:
        events: list[dict] = []
        self.runs[run_id] = events
        ws = self.store_dir / "demo-ws"
        ws.mkdir(exist_ok=True)
        sandbox = WorkspaceSandbox(ws, read_only=True)
        tools = ToolRegistry(sandbox=sandbox)
        pipeline = GuardrailPipeline([CommandGuardrail([], [])])
        sm = self.hitl()

        script = self.store_dir / "demo-script.jsonl"
        script.write_text(
            "\n".join(
                json.dumps(s)
                for s in [
                    {
                        "text": "I will deploy to production now",
                        "action": {
                            "type": "shell",
                            "params": {"command": "deploy --prod"},
                        },
                        "done": False,
                    },
                    {"text": "done", "action": None, "done": True},
                ]
            )
            + "\n",
            encoding="utf-8",
        )
        llm = MockLLM(script)

        def resolver(action_id: str, token: str) -> str:
            self.tokens[action_id] = {"token": token, "run_id": run_id}
            deadline = time.time() + 120
            while time.time() < deadline:
                rec = self.hitl().get(action_id)  # re-read from disk
                if rec is None:
                    time.sleep(0.2)
                    continue
                if rec.state == "APPROVED":
                    return "approved"
                if rec.state in ("REJECTED", "EXPIRED", "CANCELED"):
                    return "rejected"
                time.sleep(0.2)
            return "rejected"

        loop = AgentLoop(
            llm=llm,
            tools=tools,
            pipeline=pipeline,
            hitl=sm,
            validator=None,
            memory=None,
            workspace=ws,
            max_steps=5,
            max_retries=0,
            approval_resolver=resolver,
            run_id=run_id,
        )
        result = loop.run("deploy the application safely")
        for event in result.actions_log:
            events.append(event)
        events.append({"event": "FINAL", "status": result.status})
        self.finished.add(run_id)

    def pending(self) -> list[dict]:
        out: list[dict] = []
        for rec in self.hitl().list_pending():
            info = self.tokens.get(rec.action_id, {})
            out.append(
                {
                    "action_id": rec.action_id,
                    "reason": rec.reason,
                    "token": info.get("token", ""),
                    "run_id": info.get("run_id", ""),
                }
            )
        return out

    def decide(self, action_id: str, token: str, kind: str) -> str:
        try:
            if kind == "approve":
                rec = self.hitl().approve(action_id, token, "web")
            else:
                rec = self.hitl().reject(action_id, token, "web")
        except (KeyError, PermissionError) as exc:
            return f"error: {exc}"
        return f"{action_id} -> {rec.state}"

    def events_text(self, run_id: str, limit: int = 30) -> str:
        evs = self.runs.get(run_id, [])
        return "\n".join(json.dumps(e, ensure_ascii=False) for e in evs[-limit:])

    def running_runs(self) -> list[str]:
        return [r for r in self.runs if r not in self.finished]
